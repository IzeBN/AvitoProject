# Avito SaaS CRM Platform - Implementation Plan

---

## 1. ANALYSIS SUMMARY

### What we are building
Multi-tenant SaaS CRM platform for HR agencies working with Avito. The system consolidates functionality from two existing projects:
- **AvitoCRM** (React frontend): Candidates management, messenger, analytics, mailings
- **VectorBot** (FastAPI + aiogram): Avito API integration, webhooks, broadcasting, vacancy management, auto-responses, self-employed checks

### Key architectural shifts from existing codebase
1. **Single-tenant -> Multi-tenant** with org_id isolation on every table
2. **Telegram bot auth** -> **Email/password JWT auth** with RBAC
3. **In-memory caching** (Python dicts for tokens, mailing state) -> **Redis**
4. **Raw asyncpg** -> **SQLAlchemy async** with Alembic migrations
5. **Hardcoded rights string** -> **Configurable permissions in DB**
6. **BackgroundTasks for mailings** -> **Redis-backed task queue (arq)**
7. **Plain text secrets** -> **AES-256 encrypted sensitive fields**
8. **Desktop delivery via Tauri** instead of Telegram WebApp

---

## 2. DATABASE SCHEMA

### 2.1. Naming conventions
- All tables: `snake_case`, plural
- All columns: `snake_case`
- All PKs: `id UUID DEFAULT gen_random_uuid()`
- All FKs: `{entity}_id`
- All timestamps: `TIMESTAMPTZ`, auto-set `created_at`/`updated_at`
- Soft delete: `deleted_at TIMESTAMPTZ NULL`
- Multi-tenancy: `org_id UUID NOT NULL` on every business table (NOT on `organizations` itself)

### 2.2. Tables

#### Auth & Tenancy

```sql
-- Organizations (tenants)
CREATE TABLE organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) NOT NULL UNIQUE,

    -- Статус доступа
    -- 'active'    → работает нормально
    -- 'suspended' → заморожена вручную SuperAdmin (сотрудники видят экран блокировки)
    -- 'expired'   → subscription_until истёк (автоматически через scheduler)
    -- 'inactive'  → создана, но ещё не активирована
    access_status VARCHAR(20) NOT NULL DEFAULT 'active',
    suspended_at TIMESTAMPTZ,           -- когда была заморожена вручную
    suspended_by UUID REFERENCES users(id),  -- кто заморозил
    suspend_reason TEXT,                -- причина (показывается на экране блокировки)

    -- Лицензия
    subscription_until TIMESTAMPTZ,     -- NULL = бессрочно; указана = до этой даты
    -- За 7 дней до истечения → уведомление Owner в приложении
    -- После истечения → scheduler переводит в 'expired', доступ блокируется

    settings JSONB NOT NULL DEFAULT '{}',
    max_users INT NOT NULL DEFAULT 50,
    max_avito_accounts INT NOT NULL DEFAULT 5,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- IDX: (access_status) WHERE access_status != 'inactive'
-- IDX: (subscription_until) WHERE subscription_until IS NOT NULL  ← scheduler проверяет

-- Users
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id),
    email VARCHAR(255) NOT NULL,
    username VARCHAR(100) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'manager',  -- superadmin, owner, admin, manager
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    last_login_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(email),
    UNIQUE(username)
);
-- IDX: (org_id), (email), (username), (org_id, role)

-- OAuth providers (ready for future OAuth without schema changes)
CREATE TABLE auth_providers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    provider VARCHAR(50) NOT NULL,  -- 'google', 'yandex', etc.
    provider_user_id VARCHAR(255) NOT NULL,
    access_token_enc TEXT,  -- [ENCRYPTED]
    refresh_token_enc TEXT, -- [ENCRYPTED]
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(provider, provider_user_id)
);
-- IDX: (user_id), (provider, provider_user_id)

-- Refresh tokens
CREATE TABLE refresh_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash VARCHAR(255) NOT NULL UNIQUE,
    device_info VARCHAR(500),
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- IDX: (user_id), (token_hash), (expires_at)

-- Departments
CREATE TABLE departments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id),
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(org_id, name)
);
-- IDX: (org_id)

-- User-Department access (many-to-many, NULL = all departments)
CREATE TABLE user_departments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    department_id UUID NOT NULL REFERENCES departments(id) ON DELETE CASCADE,
    org_id UUID NOT NULL REFERENCES organizations(id),
    UNIQUE(user_id, department_id)
);
-- IDX: (user_id), (department_id), (org_id)

-- Permissions (configurable, not hardcoded)
CREATE TABLE permissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(100) NOT NULL UNIQUE,  -- 'crm.candidates.view', 'crm.chat.send', etc.
    name VARCHAR(255) NOT NULL,
    module VARCHAR(50) NOT NULL,  -- 'crm', 'mailing', 'vacancies', 'admin', etc.
    description TEXT
);

-- Role-Permission mapping
CREATE TABLE role_permissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id),
    role VARCHAR(20) NOT NULL,  -- 'owner', 'admin', 'manager'
    permission_id UUID NOT NULL REFERENCES permissions(id),
    UNIQUE(org_id, role, permission_id)
);
-- IDX: (org_id, role)

-- User-level permission overrides (grant/deny per user)
CREATE TABLE user_permissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    permission_id UUID NOT NULL REFERENCES permissions(id),
    org_id UUID NOT NULL REFERENCES organizations(id),
    granted BOOLEAN NOT NULL DEFAULT TRUE,  -- TRUE = grant, FALSE = explicit deny
    UNIQUE(user_id, permission_id)
);
-- IDX: (user_id)
```

#### Avito Integration

```sql
-- Avito accounts (one org can have many)
CREATE TABLE avito_accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id),
    app_id BIGINT NOT NULL,  -- avito internal app number
    client_id_enc TEXT NOT NULL,       -- [ENCRYPTED] AES-256
    client_secret_enc TEXT NOT NULL,   -- [ENCRYPTED] AES-256
    user_id BIGINT NOT NULL,           -- avito user_id
    account_name VARCHAR(255),
    webhook_secret VARCHAR(255),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(org_id, user_id)
);
-- IDX: (org_id), (user_id), (org_id, is_active)

-- Webhook endpoint registry: one row per account per event type
-- URL pattern: /webhooks/avito/{account_token}/{event_type}
-- account_token is a random secret slug generated on account creation,
-- so the URL itself authenticates + routes the request — no lookup needed.
CREATE TABLE avito_webhook_endpoints (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    avito_account_id UUID NOT NULL REFERENCES avito_accounts(id) ON DELETE CASCADE,
    event_type VARCHAR(50) NOT NULL,    -- 'new_response' | 'new_message' | 'message_read' | 'chat_blocked'
    account_token VARCHAR(64) NOT NULL UNIQUE,  -- random slug, part of URL, acts as secret
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    last_received_at TIMESTAMPTZ,       -- last time Avito hit this endpoint
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- IDX: (account_token) UNIQUE — primary lookup on every incoming webhook
-- IDX: (avito_account_id, event_type) UNIQUE — one endpoint per account per event
```

#### CRM Core

```sql
-- Pipeline stages (configurable per org)
CREATE TABLE pipeline_stages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id),
    name VARCHAR(255) NOT NULL,
    sort_order INT NOT NULL DEFAULT 0,
    color VARCHAR(7),  -- hex color
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(org_id, name)
);
-- IDX: (org_id, sort_order)

-- Tags (configurable per org)
CREATE TABLE tags (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id),
    name VARCHAR(100) NOT NULL,
    color VARCHAR(7),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(org_id, name)
);
-- IDX: (org_id)

-- Candidates (responses/applicants) - core entity
CREATE TABLE candidates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id),
    avito_account_id UUID REFERENCES avito_accounts(id),
    chat_id VARCHAR(255),           -- avito chat_id
    avito_user_id BIGINT,           -- avito user numeric id
    avito_item_id BIGINT,           -- avito vacancy item_id
    name VARCHAR(255),
    phone_enc TEXT,                  -- [ENCRYPTED] AES-256-GCM
    phone_search_hash VARCHAR(64),   -- HMAC-SHA256(phone, SEARCH_HASH_KEY) для точного поиска без расшифровки
    stage_id UUID REFERENCES pipeline_stages(id),
    department_id UUID REFERENCES departments(id),
    responsible_id UUID REFERENCES users(id),
    source VARCHAR(255),            -- account_name at time of creation
    location VARCHAR(255),
    vacancy VARCHAR(500),
    comment TEXT,
    due_date DATE,
    has_new_message BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ
);
-- IDX: (org_id, deleted_at), (org_id, chat_id), (org_id, stage_id),
--      (org_id, responsible_id), (org_id, department_id),
--      (org_id, has_new_message), (org_id, created_at DESC),
--      (org_id, avito_account_id), (avito_user_id)
-- Composite: (org_id, stage_id, has_new_message)

-- Candidate tags (many-to-many)
CREATE TABLE candidate_tags (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    candidate_id UUID NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
    tag_id UUID NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    org_id UUID NOT NULL REFERENCES organizations(id),
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(candidate_id, tag_id)
);
-- IDX: (candidate_id), (tag_id), (org_id)

-- =====================================================================
-- INDEXES STRATEGY FOR candidates (high-frequency list queries)
-- =====================================================================
-- Query: list candidates с фильтрами — выполняется на каждый запрос страницы
-- Все индексы партиальные (WHERE deleted_at IS NULL) — исключают удалённые строки

-- Базовый: постраничный список без фильтров
CREATE INDEX idx_candidates_org_created ON candidates (org_id, created_at DESC) WHERE deleted_at IS NULL;

-- Фильтр по этапу (самый частый фильтр)
CREATE INDEX idx_candidates_org_stage ON candidates (org_id, stage_id, created_at DESC) WHERE deleted_at IS NULL;

-- Фильтр по ответственному
CREATE INDEX idx_candidates_org_responsible ON candidates (org_id, responsible_id, created_at DESC) WHERE deleted_at IS NULL;

-- Фильтр по отделу
CREATE INDEX idx_candidates_org_department ON candidates (org_id, department_id, created_at DESC) WHERE deleted_at IS NULL;

-- Фильтр "только непрочитанные"
CREATE INDEX idx_candidates_org_new_msg ON candidates (org_id, has_new_message, created_at DESC) WHERE deleted_at IS NULL AND has_new_message = TRUE;

-- Фильтр по аккаунту Avito
CREATE INDEX idx_candidates_org_account ON candidates (org_id, avito_account_id, created_at DESC) WHERE deleted_at IS NULL;

-- Фильтр по due_date (просроченные задачи / дедлайны)
CREATE INDEX idx_candidates_org_duedate ON candidates (org_id, due_date) WHERE deleted_at IS NULL AND due_date IS NOT NULL;

-- Поиск по имени/телефону (ILIKE prefix поиск)
CREATE INDEX idx_candidates_name_trgm ON candidates USING gin (name gin_trgm_ops) WHERE deleted_at IS NULL;
-- Телефон ищем по расшифрованному значению — хранить phone_search_hash (HMAC) для точного поиска:
-- phone_search_hash = HMAC(phone, SEARCH_HASH_KEY) → детерминированный, неугадываемый
CREATE INDEX idx_candidates_phone_hash ON candidates (org_id, phone_search_hash) WHERE deleted_at IS NULL;

-- Webhook lookup: найти кандидата по chat_id при входящем сообщении (очень частый)
CREATE UNIQUE INDEX idx_candidates_chatid ON candidates (org_id, chat_id) WHERE deleted_at IS NULL;

-- Составной: фильтр этап + ответственный (частая комбинация в CRM)
CREATE INDEX idx_candidates_stage_responsible ON candidates (org_id, stage_id, responsible_id, created_at DESC) WHERE deleted_at IS NULL;

-- Chat messages cache (local copy)
-- PARTITIONED by month: огромные объёмы сообщений, старые читаются редко
CREATE TABLE chat_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id),
    candidate_id UUID NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
    chat_id VARCHAR(255) NOT NULL,
    author_type VARCHAR(20) NOT NULL,  -- 'account', 'candidate', 'system'
    message_type VARCHAR(20) NOT NULL DEFAULT 'text',  -- 'text', 'image', 'voice', 'file', 'system'
    content TEXT,
    avito_message_id VARCHAR(255),
    is_read BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
) PARTITION BY RANGE (created_at);

-- Партиции создаются автоматически воркером каждый месяц:
-- chat_messages_2025_01, chat_messages_2025_02, ...

-- =====================================================================
-- INDEXES для chat_messages (история чата — частый запрос)
-- =====================================================================

-- Основной: загрузка истории чата (пагинация по cursor)
CREATE INDEX idx_chat_messages_chat_created ON chat_messages (chat_id, created_at DESC);

-- Поиск сообщений кандидата (candidate_id → все чаты)
CREATE INDEX idx_chat_messages_candidate ON chat_messages (candidate_id, created_at DESC);

-- Дедупликация входящих от Avito
CREATE UNIQUE INDEX idx_chat_messages_avito_id ON chat_messages (avito_message_id) WHERE avito_message_id IS NOT NULL;

-- Chat metadata (last message, unread count)
-- 1 строка на чат, обновляется при каждом сообщении — горячая таблица
CREATE TABLE chat_metadata (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id),
    candidate_id UUID NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
    chat_id VARCHAR(255) NOT NULL,
    unread_count INT NOT NULL DEFAULT 0,
    is_blocked BOOLEAN NOT NULL DEFAULT FALSE,
    last_message TEXT,
    last_message_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(chat_id)
);

-- Список чатов (MessengerPage) — сортировка по последнему сообщению
CREATE INDEX idx_chat_meta_org_last ON chat_metadata (org_id, last_message_at DESC);
-- Фильтр "только непрочитанные чаты"
CREATE INDEX idx_chat_meta_unread ON chat_metadata (org_id, unread_count) WHERE unread_count > 0;
-- Webhook lookup по chat_id
CREATE INDEX idx_chat_meta_chatid ON chat_metadata (chat_id);
```

#### Mailings

```sql
-- Mailing jobs — полное управление жизненным циклом
CREATE TABLE mailing_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id),
    created_by UUID NOT NULL REFERENCES users(id),

    -- Состояние
    -- pending    → запланирована, ещё не запущена
    -- running    → активно отправляется
    -- paused     → на паузе (воркер остановлен, можно возобновить)
    -- resuming   → команда resume получена, воркер перезапускается
    -- stopping   → команда stop получена, воркер завершает текущую и останавливается
    -- done       → завершена полностью
    -- failed     → завершена с критической ошибкой
    -- cancelled  → отменена пользователем
    status VARCHAR(20) NOT NULL DEFAULT 'pending',

    message TEXT NOT NULL,
    file_url TEXT,                   -- прикреплённый файл (если есть)
    criteria JSONB NOT NULL,         -- { type: 'ids'|'filters', ids?: [], filters?: {} }

    -- Планирование
    scheduled_at TIMESTAMPTZ,        -- NULL = запустить сразу; указан = запустить в это время
    rate_limit_ms INT NOT NULL DEFAULT 1000,  -- задержка между сообщениями (мс)

    -- Прогресс (атомарно обновляется воркером)
    total INT NOT NULL DEFAULT 0,
    sent INT NOT NULL DEFAULT 0,
    failed INT NOT NULL DEFAULT 0,
    skipped INT NOT NULL DEFAULT 0,  -- заблокированные / не найденные

    -- Временные метки жизненного цикла
    started_at TIMESTAMPTZ,          -- фактический старт отправки
    paused_at TIMESTAMPTZ,
    resumed_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- Служебное
    arq_job_id VARCHAR(255),         -- ID задачи в arq для управления воркером
    last_error TEXT                  -- последняя ошибка воркера
);
CREATE INDEX idx_mailing_jobs_org_status ON mailing_jobs (org_id, status);
CREATE INDEX idx_mailing_jobs_org_created ON mailing_jobs (org_id, created_at DESC);
CREATE INDEX idx_mailing_jobs_scheduled ON mailing_jobs (scheduled_at) WHERE status = 'pending' AND scheduled_at IS NOT NULL;
-- SuperAdmin: все рассылки платформы
CREATE INDEX idx_mailing_jobs_status_global ON mailing_jobs (status, created_at DESC);

-- Mailing recipients — детальный трекинг каждого получателя
CREATE TABLE mailing_recipients (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    mailing_job_id UUID NOT NULL REFERENCES mailing_jobs(id) ON DELETE CASCADE,
    candidate_id UUID NOT NULL REFERENCES candidates(id),
    org_id UUID NOT NULL REFERENCES organizations(id),

    -- pending → in_progress → sent | failed | skipped
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    attempt_count INT NOT NULL DEFAULT 0,         -- кол-во попыток
    last_attempt_at TIMESTAMPTZ,
    sent_at TIMESTAMPTZ,
    error_code VARCHAR(50),                        -- 'rate_limited', 'blocked', 'not_found', 'api_error'
    error_message TEXT,

    UNIQUE(mailing_job_id, candidate_id)
);
CREATE INDEX idx_mailing_recip_job_status ON mailing_recipients (mailing_job_id, status);
CREATE INDEX idx_mailing_recip_job_pending ON mailing_recipients (mailing_job_id) WHERE status = 'pending';
-- Продолжение после паузы: воркер читает WHERE status = 'pending' ORDER BY id
-- уже отправленные пропускаются автоматически
```

**Lifecycle transitions:**
```
pending ──(start/scheduled_at наступил)──► running
running ──(pause команда)────────────────► paused
paused  ──(resume команда)───────────────► resuming ──► running
running ──(stop команда)─────────────────► stopping ──► cancelled
running ──(все отправлены)───────────────► done
running ──(критическая ошибка)───────────► failed
```

**Продолжение после паузы:** воркер при resume читает `mailing_recipients WHERE mailing_job_id = ? AND status = 'pending'` — уже отправленные (status='sent') автоматически пропускаются, прогресс сохраняется.

**Планировщик:** отдельный arq periodic task каждые 30 сек проверяет `mailing_jobs WHERE status='pending' AND scheduled_at <= now()` и запускает воркер.

#### Tasks

```sql
CREATE TABLE tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id),
    responsible_id UUID NOT NULL REFERENCES users(id),
    created_by UUID NOT NULL REFERENCES users(id),
    candidate_id UUID REFERENCES candidates(id),  -- optional link to candidate
    title VARCHAR(500) NOT NULL,
    description TEXT,
    deadline TIMESTAMPTZ,
    is_completed BOOLEAN NOT NULL DEFAULT FALSE,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- IDX: (org_id, responsible_id, is_completed), (org_id, deadline), (candidate_id)
```

#### Vacancy Management

```sql
CREATE TABLE vacancies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id),
    avito_account_id UUID NOT NULL REFERENCES avito_accounts(id),
    avito_item_id BIGINT NOT NULL,
    title VARCHAR(500),
    location VARCHAR(255),
    status VARCHAR(20) NOT NULL DEFAULT 'active',  -- active, archived, unknown
    raw_data JSONB,  -- full vacancy data from Avito API
    synced_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- IDX: (org_id, avito_account_id), (avito_item_id), (org_id, status)
```

#### Auto-response & Messages

```sql
-- Default message per avito account
CREATE TABLE default_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id),
    avito_account_id UUID NOT NULL REFERENCES avito_accounts(id),
    message TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(avito_account_id)
);

-- Per-item messages
CREATE TABLE item_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id),
    avito_item_id BIGINT NOT NULL,
    avito_account_id UUID NOT NULL REFERENCES avito_accounts(id),
    message TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(avito_item_id, avito_account_id)
);
-- IDX: (org_id), (avito_item_id, avito_account_id, is_active)

-- Auto-response rules
CREATE TABLE auto_response_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id),
    avito_item_id BIGINT,  -- NULL = all items for account
    avito_account_id UUID NOT NULL REFERENCES avito_accounts(id),
    auto_type VARCHAR(50) NOT NULL DEFAULT 'on_response',  -- on_response, on_message
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- IDX: (org_id, avito_account_id, is_active)

-- Fast/quick answers per user
CREATE TABLE fast_answers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id),
    user_id UUID NOT NULL REFERENCES users(id),
    message TEXT NOT NULL,
    sort_order INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- IDX: (org_id, user_id)
```

#### Self-employed Checks

```sql
CREATE TABLE self_employed_checks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id),
    inn VARCHAR(12) NOT NULL,
    status VARCHAR(20),  -- 'active', 'inactive', 'not_found', 'error'
    checked_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    raw_response JSONB
);
-- IDX: (org_id, inn)
```

#### Error Log (видно в SuperAdmin панели)

```sql
-- Все ошибки системы — webhook обработка, API запросы, воркеры
CREATE TABLE error_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID REFERENCES organizations(id),    -- NULL если ошибка на уровне платформы
    user_id UUID REFERENCES users(id),           -- NULL если ошибка в фоновом воркере

    -- Источник ошибки — где искать в коде
    source VARCHAR(50) NOT NULL,    -- 'webhook' | 'api' | 'worker' | 'scheduler' | 'avito_client'
    layer VARCHAR(100) NOT NULL,    -- 'router.candidates' | 'worker.mailing' | 'webhook.new_message' и т.д.
    handler VARCHAR(255) NOT NULL,  -- конкретный метод: 'CandidateService.get_list' | 'MailingWorker.send'

    -- Контекст запроса
    request_method VARCHAR(10),     -- GET / POST / etc.
    request_path VARCHAR(500),      -- /api/v1/candidates
    request_id VARCHAR(64),         -- UUID запроса (X-Request-ID header)

    -- Ошибка
    error_type VARCHAR(100) NOT NULL,   -- тип исключения: 'ValidationError', 'AvitoAPIError', etc.
    error_message TEXT NOT NULL,
    stack_trace TEXT,                   -- полный traceback

    -- Контекст задачи (для воркеров)
    job_type VARCHAR(50),           -- 'mailing' | 'webhook' | 'auto_response'
    job_id UUID,                    -- mailing_jobs.id или webhook event id

    -- HTTP статус (если это был API запрос)
    status_code INT,

    -- Мета
    resolved BOOLEAN NOT NULL DEFAULT FALSE,   -- SuperAdmin отметил как решённую
    resolved_by UUID REFERENCES users(id),
    resolved_at TIMESTAMPTZ,
    note TEXT,                                 -- комментарий SuperAdmin

    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
) PARTITION BY RANGE (created_at);
-- Партиции по месяцам

CREATE INDEX idx_error_log_org_created ON error_log (org_id, created_at DESC);
CREATE INDEX idx_error_log_global_created ON error_log (created_at DESC);         -- SuperAdmin: все ошибки
CREATE INDEX idx_error_log_source ON error_log (source, created_at DESC);
CREATE INDEX idx_error_log_unresolved ON error_log (resolved, created_at DESC) WHERE resolved = FALSE;
CREATE INDEX idx_error_log_org_unresolved ON error_log (org_id, resolved) WHERE resolved = FALSE;
```

#### Audit Log

```sql
CREATE TABLE audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id),

    -- Кто совершил действие
    user_id UUID REFERENCES users(id),      -- NULL только для системных действий (воркер, scheduler)
    user_full_name VARCHAR(255),            -- денормализовано: снимок имени на момент действия
    user_role VARCHAR(20),                  -- снимок роли на момент действия

    -- Что произошло
    -- Формат: {entity}.{verb}
    -- Примеры: candidate.stage_changed, candidate.responsible_assigned,
    --          chat.message_sent, chat.message_sent_file, chat.user_blocked,
    --          mailing.started, mailing.paused, mailing.resumed, mailing.cancelled,
    --          task.created, task.completed, task.deleted,
    --          vacancy.activated, vacancy.deactivated,
    --          candidate.tag_added, candidate.tag_removed,
    --          candidate.comment_updated, candidate.due_date_set,
    --          avito_account.added, avito_account.removed,
    --          auto_response.enabled, auto_response.disabled,
    --          user.invited, user.role_changed, user.deactivated,
    --          org.settings_changed, org.stage_created, org.department_created
    action VARCHAR(100) NOT NULL,

    -- К чему привязано действие (основной объект)
    entity_type VARCHAR(50) NOT NULL,  -- 'candidate' | 'mailing_job' | 'task' | 'chat' | 'vacancy' | 'user' | 'org_settings' | ...
    entity_id UUID,                    -- id объекта (NULL для действий без конкретного объекта)
    entity_display VARCHAR(500),       -- читаемое имя объекта на момент действия:
                                       -- для candidate: "Иван Петров (вакансия: Водитель)"
                                       -- для mailing:   "Рассылка от 12.03.2025 (150 получателей)"
                                       -- для task:      "Позвонить кандидату до 15:00"

    -- Связанные объекты (опционально, для контекста)
    -- Например, при отправке сообщения: candidate — основной, avito_account — связанный
    related_entity_type VARCHAR(50),
    related_entity_id UUID,
    related_entity_display VARCHAR(500),

    -- Детали изменения
    -- Для update: { "before": { "stage": "Новый" }, "after": { "stage": "Собеседование" } }
    -- Для create: { "data": { ... } }
    -- Для delete: { "snapshot": { ... } }
    -- Для send:   { "message_preview": "Здравствуйте, ..." (первые 100 символов) }
    -- Для mailing:{ "total": 150, "filter_summary": "Этап: Новый, Отдел: Москва" }
    details JSONB NOT NULL DEFAULT '{}',

    -- Человекочитаемая строка (генерируется на бэкенде, хранится для быстрого отображения)
    -- "Сменил этап с «Новый» на «Собеседование» у кандидата Иван Петров"
    -- "Отправил сообщение кандидату Иван Петров: «Здравствуйте, мы рассмотрели...»"
    -- "Запустил рассылку на 150 кандидатов (фильтр: этап Новый)"
    -- "Назначил ответственным Мария Сидорова на кандидата Иван Петров"
    -- "Заблокировал пользователя в чате с Иван Петров"
    human_readable TEXT NOT NULL,

    ip_address INET,
    user_agent VARCHAR(500),   -- браузер / версия десктоп приложения
    request_id VARCHAR(64),    -- X-Request-ID для связки с error_log

    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
) PARTITION BY RANGE (created_at);
-- Партиции по месяцам: audit_log_2025_01, audit_log_2025_02, ...

-- Лента активности сотрудника (самый частый запрос: "что делал Иван сегодня?")
CREATE INDEX idx_audit_user_created ON audit_log (org_id, user_id, created_at DESC);

-- История конкретного объекта ("все действия с кандидатом X")
CREATE INDEX idx_audit_entity ON audit_log (org_id, entity_type, entity_id, created_at DESC);

-- Общая лента организации
CREATE INDEX idx_audit_org_created ON audit_log (org_id, created_at DESC);

-- Фильтр по типу действия
CREATE INDEX idx_audit_action ON audit_log (org_id, action, created_at DESC);

-- SuperAdmin: платформенный аудит
CREATE INDEX idx_audit_global ON audit_log (created_at DESC);
```

**Каталог всех действий по сущностям:**

```
candidate.*
  candidate.created              — кандидат попал в систему (через вебхук или вручную)
  candidate.stage_changed        — смена этапа воронки
  candidate.responsible_assigned — назначен ответственный
  candidate.department_changed   — смена отдела
  candidate.tag_added            — добавлен тег
  candidate.tag_removed          — удалён тег
  candidate.comment_updated      — изменён комментарий
  candidate.due_date_set         — установлена дата напоминания
  candidate.due_date_cleared     — дата напоминания снята
  candidate.bulk_stage_changed   — массовая смена этапа (details: кол-во кандидатов)
  candidate.bulk_responsible     — массовое переназначение

chat.*
  chat.message_sent              — отправлено текстовое сообщение
  chat.message_sent_file         — отправлен файл/изображение
  chat.user_blocked              — пользователь заблокирован
  chat.chat_read                 — чат отмечен прочитанным

mailing.*
  mailing.created                — рассылка создана / запланирована
  mailing.started                — рассылка запущена
  mailing.paused                 — поставлена на паузу
  mailing.resumed                — возобновлена
  mailing.cancelled              — отменена
  mailing.completed              — завершена (системное)

task.*
  task.created                   — задача создана
  task.completed                 — отмечена выполненной
  task.deadline_changed          — изменён дедлайн
  task.deleted                   — задача удалена

vacancy.*
  vacancy.synced                 — синхронизированы вакансии с Avito
  vacancy.activated              — вакансия опубликована
  vacancy.deactivated            — вакансия снята
  vacancy.edited                 — вакансия отредактирована

avito_account.*
  avito_account.added            — добавлен аккаунт Avito
  avito_account.removed          — аккаунт удалён
  avito_account.webhooks_setup   — вебхуки зарегистрированы

auto_response.*
  auto_response.rule_created     — создано правило автоответа
  auto_response.rule_toggled     — включено/выключено
  auto_response.default_msg_set  — изменено сообщение по умолчанию
  auto_response.item_msg_set     — установлено сообщение для объявления

user.*  (admin действия)
  user.invited                   — сотрудник добавлен
  user.role_changed              — изменена роль
  user.department_assigned       — назначен на отдел
  user.deactivated               — деактивирован
  user.reactivated               — восстановлен

org_settings.*  (admin действия)
  org_settings.stage_created     — создан этап воронки
  org_settings.stage_renamed     — переименован этап
  org_settings.stage_reordered   — изменён порядок этапов
  org_settings.stage_deleted     — удалён этап
  org_settings.department_created
  org_settings.department_deleted
  org_settings.tag_created
  org_settings.tag_deleted
  org_settings.permissions_changed — изменены права роли

self_employed.*
  self_employed.checked          — проверен ИНН (details: { inn, status })
```

**Сервис записи (единственная точка входа):**

```python
# app/services/audit.py
class AuditService:
    async def log(
        self,
        *,
        request: Request,           # для ip_address, user_agent, request_id
        action: str,                # 'candidate.stage_changed'
        entity_type: str,           # 'candidate'
        entity_id: UUID | None,
        entity_display: str,        # "Иван Петров (Водитель)"
        details: dict,              # { before: {}, after: {} }
        human_readable: str,        # "Сменил этап с «Новый» на «Собеседование»"
        related_entity_type: str | None = None,
        related_entity_id: UUID | None = None,
        related_entity_display: str | None = None,
    ) -> None:
        # Fire-and-forget: не ждём записи, не блокируем ответ
        # Пишет напрямую в DB (не write-behind — аудит должен быть немедленным)
        asyncio.create_task(self._write(...))
```

Вызывается из сервисного слоя после успешной операции:
```python
# В CandidateService.change_stage():
await self.audit.log(
    request=request,
    action="candidate.stage_changed",
    entity_type="candidate",
    entity_id=candidate.id,
    entity_display=f"{candidate.name} ({candidate.vacancy})",
    details={"before": {"stage": old_stage.name}, "after": {"stage": new_stage.name}},
    human_readable=f"Сменил этап с «{old_stage.name}» на «{new_stage.name}» "
                   f"у кандидата {candidate.name}",
)
```

**API для просмотра (в плане эндпоинтов):**
```
GET /audit                          — лента всей организации (admin+)
GET /audit?user_id={id}             — действия конкретного сотрудника
GET /audit?entity_type=candidate&entity_id={id}  — история объекта
GET /audit?action=mailing.*         — все действия с рассылками
GET /candidates/{id}/history        — история кандидата (удобный alias)
GET /users/{id}/activity            — активность сотрудника (удобный alias)
```

### 2.3. Row Level Security (RLS)

```sql
-- Enable RLS on all business tables
ALTER TABLE candidates ENABLE ROW LEVEL SECURITY;
-- (repeat for all business tables)

-- Policy: users see only their org's data
-- Applied via SET LOCAL app.current_org_id at connection level
CREATE POLICY org_isolation ON candidates
    USING (org_id = current_setting('app.current_org_id')::UUID);

-- Implementation: each request sets org_id on the DB session:
-- SET LOCAL app.current_org_id = '<org_uuid>';
-- This ensures data isolation even if application-level bugs miss org_id filtering.

-- SuperAdmin bypass (for platform admin operations):
CREATE POLICY superadmin_bypass ON candidates
    USING (current_setting('app.is_superadmin', true)::BOOLEAN = TRUE);
```

Tables with RLS policies:
- `users`, `departments`, `user_departments`, `user_permissions`, `role_permissions`
- `avito_accounts`, `avito_webhooks`
- `pipeline_stages`, `tags`, `candidates`, `candidate_tags`
- `chat_messages`, `chat_metadata`
- `mailing_jobs`, `mailing_recipients`
- `tasks`, `vacancies`
- `default_messages`, `item_messages`, `auto_response_rules`, `fast_answers`
- `self_employed_checks`, `audit_log`

---

## 3. BACKEND (Agent 1) -- FastAPI

### 3.1. Project Structure

```
backend/
├── alembic/
│   ├── versions/
│   ├── env.py
│   └── alembic.ini
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI app factory
│   ├── config.py                  # Pydantic settings
│   ├── database.py                # async engine, session factory
│   ├── redis.py                   # Redis connection pool
│   ├── security/
│   │   ├── __init__.py
│   │   ├── encryption.py          # AES-256 encrypt/decrypt
│   │   ├── jwt.py                 # JWT create/verify
│   │   ├── password.py            # bcrypt hash/verify
│   │   └── permissions.py         # permission checker
│   ├── middleware/
│   │   ├── __init__.py
│   │   ├── tenant.py              # extract org_id, set RLS
│   │   ├── rate_limit.py          # Redis-based rate limiter
│   │   └── logging.py             # request logging
│   ├── models/                    # SQLAlchemy ORM models
│   │   ├── __init__.py
│   │   ├── base.py                # Base, mixins (OrgMixin, TimestampMixin)
│   │   ├── auth.py                # Organization, User, AuthProvider, RefreshToken
│   │   ├── rbac.py                # Permission, RolePermission, UserPermission, Department, UserDepartment
│   │   ├── avito.py               # AvitoAccount, AvitoWebhook
│   │   ├── crm.py                 # Candidate, CandidateTag, Tag, PipelineStage
│   │   ├── chat.py                # ChatMessage, ChatMetadata
│   │   ├── mailing.py             # MailingJob, MailingRecipient
│   │   ├── task.py                # Task
│   │   ├── vacancy.py             # Vacancy
│   │   ├── messaging.py           # DefaultMessage, ItemMessage, AutoResponseRule, FastAnswer
│   │   └── audit.py               # AuditLog
│   ├── schemas/                   # Pydantic request/response DTOs
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── user.py
│   │   ├── organization.py
│   │   ├── candidate.py
│   │   ├── chat.py
│   │   ├── mailing.py
│   │   ├── task.py
│   │   ├── vacancy.py
│   │   ├── avito_account.py
│   │   ├── analytics.py
│   │   ├── auto_response.py
│   │   └── common.py              # Pagination, filters, errors
│   ├── repositories/              # DB query layer
│   │   ├── __init__.py
│   │   ├── base.py                # BaseRepository with CRUD
│   │   ├── user.py
│   │   ├── candidate.py
│   │   ├── chat.py
│   │   ├── mailing.py
│   │   ├── task.py
│   │   ├── vacancy.py
│   │   ├── avito_account.py
│   │   ├── analytics.py
│   │   └── audit.py
│   ├── services/                  # Business logic
│   │   ├── __init__.py
│   │   ├── auth.py                # login, register, refresh, logout
│   │   ├── user.py
│   │   ├── organization.py
│   │   ├── candidate.py
│   │   ├── chat.py
│   │   ├── mailing.py
│   │   ├── task.py
│   │   ├── vacancy.py
│   │   ├── avito_api.py           # Avito REST API client (aiohttp)
│   │   ├── avito_token.py         # Token management with Redis cache
│   │   ├── webhook_processor.py   # Webhook event processing
│   │   ├── auto_response.py
│   │   ├── self_employed.py       # INN check service
│   │   ├── analytics.py
│   │   └── encryption.py          # High-level encrypt/decrypt for fields
│   ├── routers/                   # API endpoints
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── users.py
│   │   ├── organizations.py
│   │   ├── candidates.py
│   │   ├── chats.py
│   │   ├── mailings.py
│   │   ├── tasks.py
│   │   ├── vacancies.py
│   │   ├── avito_accounts.py
│   │   ├── webhooks.py            # Avito webhook receivers
│   │   ├── analytics.py
│   │   ├── auto_response.py
│   │   ├── self_employed.py
│   │   ├── fast_answers.py
│   │   ├── settings.py            # Org settings, stages, tags, departments
│   │   └── websocket.py           # WS for real-time updates
│   ├── workers/                   # Background task workers (arq)
│   │   ├── __init__.py
│   │   ├── mailing_worker.py
│   │   ├── webhook_worker.py
│   │   └── sync_worker.py         # Periodic vacancy/account sync
│   ├── deps.py                    # FastAPI dependencies
│   └── exceptions.py              # Custom exceptions
├── tests/
│   ├── conftest.py
│   ├── test_auth.py
│   ├── test_candidates.py
│   └── ...
├── requirements.txt
├── Dockerfile
└── docker-compose.yml
```

### 3.2. Key Dependencies

```
fastapi==0.115.*
uvicorn[standard]
sqlalchemy[asyncio]==2.0.*
asyncpg
alembic
pydantic==2.*
pydantic-settings
python-jose[cryptography]    # JWT
passlib[bcrypt]              # passwords
cryptography                 # AES-256
redis[hiredis]               # Redis client
arq                          # Redis-based task queue
aiohttp                      # Avito API calls
python-multipart             # file uploads
```

### 3.3. API Endpoints

All endpoints prefixed with `/api/v1`. Auth: Bearer JWT token in `Authorization` header.

#### Auth Module

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| POST | `/auth/register` | Register new org + owner | No |
| POST | `/auth/login` | Login, returns access+refresh tokens | No |
| POST | `/auth/refresh` | Refresh access token | Refresh token |
| POST | `/auth/logout` | Revoke refresh token | Yes |
| GET | `/auth/me` | Current user profile | Yes |

**POST /auth/login**
```json
// Request
{ "email": "string", "password": "string" }
// Response 200
{
  "access_token": "string",
  "refresh_token": "string",
  "token_type": "bearer",
  "expires_in": 900,
  "user": { "id": "uuid", "email": "...", "role": "...", "org_id": "uuid", "full_name": "..." }
}
// Response 401
{ "detail": "Invalid credentials" }
```

**POST /auth/register**
```json
// Request
{
  "org_name": "string",
  "email": "string",
  "username": "string",
  "password": "string",
  "full_name": "string"
}
// Response 201 - same as login response
```

#### Users Module

| Method | Path | Description | Auth/Role |
|--------|------|-------------|-----------|
| GET | `/users` | List users in org | admin+ |
| POST | `/users` | Create user (invite) | admin+ |
| GET | `/users/{id}` | Get user | admin+ |
| PATCH | `/users/{id}` | Update user | admin+ |
| DELETE | `/users/{id}` | Deactivate user | owner+ |
| PATCH | `/users/{id}/permissions` | Set user permission overrides | admin+ |
| GET | `/users/{id}/permissions` | Get effective permissions | admin+ |
| PUT | `/users/{id}/departments` | Set user departments | admin+ |

#### Candidates Module

| Method | Path | Description | Auth/Perm |
|--------|------|-------------|-----------|
| GET | `/candidates` | List with filters, pagination | crm.candidates.view |
| GET | `/candidates/{id}` | Get single candidate | crm.candidates.view |
| PATCH | `/candidates/{id}` | Update candidate (stage, responsible, comment, due_date, department) | crm.candidates.edit |
| PATCH | `/candidates/bulk` | Bulk update (stage, due_date) | crm.candidates.edit |
| POST | `/candidates/{id}/tags` | Add tag | crm.candidates.edit |
| DELETE | `/candidates/{id}/tags/{tag_id}` | Remove tag | crm.candidates.edit |
| PATCH | `/candidates/{id}/responsible` | Change responsible | crm.candidates.edit |
| POST | `/candidates/assign-by-filters` | Bulk assign by filters | crm.candidates.edit |

**GET /candidates** query params:
```
page: int = 1
per_page: int = 50 (max 100)
stage_id: UUID?
responsible_id: UUID?
department_id: UUID?
tag_id: UUID?
location: string?
vacancy: string?
source: string?
phone: string?
has_new_message: bool?
created_from: date?
created_to: date?
due_date_from: date?
due_date_to: date?
search: string?  (name/phone search)
sort_by: string = 'created_at'
sort_order: 'asc'|'desc' = 'desc'
```

Response:
```json
{
  "items": [
    {
      "id": "uuid",
      "name": "string",
      "phone": "string",  // decrypted on read
      "stage": { "id": "uuid", "name": "string", "color": "#hex" },
      "department": { "id": "uuid", "name": "string" },
      "responsible": { "id": "uuid", "full_name": "string" },
      "tags": [{ "id": "uuid", "name": "string", "color": "#hex" }],
      "location": "string",
      "vacancy": "string",
      "source": "string",
      "comment": "string",
      "due_date": "date",
      "has_new_message": true,
      "created_at": "datetime"
    }
  ],
  "total": 500,
  "page": 1,
  "per_page": 50,
  "pages": 10
}
```

#### Chats Module

| Method | Path | Description | Perm |
|--------|------|-------------|------|
| GET | `/chats` | List all chats with metadata | crm.chat.view |
| GET | `/chats/{candidate_id}/messages` | Get chat history | crm.chat.view |
| POST | `/chats/{candidate_id}/messages` | Send text message | crm.chat.send |
| POST | `/chats/{candidate_id}/messages/file` | Send file/image | crm.chat.send |
| POST | `/chats/{candidate_id}/read` | Mark as read | crm.chat.view |
| POST | `/chats/{candidate_id}/block` | Block user | crm.chat.block |
| GET | `/chats/{candidate_id}/voice/{voice_id}` | Get voice URL | crm.chat.view |

**GET /chats** query params:
```
page: int = 1
per_page: int = 50
only_unread: bool = false
stage_id: UUID?
responsible_id: UUID?
department_id: UUID?
search: string?
sort_by: 'last_message_at'|'unread_count' = 'last_message_at'
sort_order: 'asc'|'desc' = 'desc'
```

#### Mailings Module

| Method | Path | Description | Perm |
|--------|------|-------------|------|
| GET | `/mailings` | List all mailing jobs | mailing.view |
| POST | `/mailings/by-ids` | Start mailing by candidate IDs | mailing.send |
| POST | `/mailings/by-filters` | Start mailing by filters | mailing.send |
| GET | `/mailings/{id}` | Get mailing status | mailing.view |
| POST | `/mailings/{id}/pause` | Pause mailing | mailing.send |
| POST | `/mailings/{id}/resume` | Resume mailing | mailing.send |
| POST | `/mailings/{id}/cancel` | Cancel mailing | mailing.send |

#### Tasks Module

| Method | Path | Description | Perm |
|--------|------|-------------|------|
| GET | `/tasks` | List tasks (with filters) | crm.tasks.view |
| POST | `/tasks` | Create task | crm.tasks.create |
| PATCH | `/tasks/{id}` | Update task | crm.tasks.edit |
| DELETE | `/tasks/{id}` | Delete task | crm.tasks.delete |
| POST | `/tasks/{id}/complete` | Mark complete | crm.tasks.edit |

#### Avito Accounts Module

| Method | Path | Description | Perm |
|--------|------|-------------|------|
| GET | `/avito-accounts` | List accounts | avito.accounts.view |
| POST | `/avito-accounts` | Add account | avito.accounts.manage |
| DELETE | `/avito-accounts/{id}` | Remove account | avito.accounts.manage |
| GET | `/avito-accounts/{id}/balance` | Get balance | avito.accounts.view |
| POST | `/avito-accounts/{id}/webhooks/setup` | Setup webhooks | avito.accounts.manage |

#### Vacancies Module

| Method | Path | Description | Perm |
|--------|------|-------------|------|
| GET | `/vacancies` | List vacancies (synced) | vacancies.view |
| POST | `/vacancies/sync` | Sync from Avito | vacancies.manage |
| POST | `/vacancies/{id}/activate` | Prolongate/activate | vacancies.manage |
| POST | `/vacancies/{id}/deactivate` | Archive vacancy | vacancies.manage |
| PATCH | `/vacancies/{id}` | Edit vacancy on Avito | vacancies.edit |

#### Auto-response Module

| Method | Path | Description | Perm |
|--------|------|-------------|------|
| GET | `/auto-response/rules` | List rules | auto_response.view |
| POST | `/auto-response/rules` | Create rule | auto_response.manage |
| PATCH | `/auto-response/rules/{id}` | Update rule | auto_response.manage |
| DELETE | `/auto-response/rules/{id}` | Delete rule | auto_response.manage |
| GET | `/default-messages` | List default messages | auto_response.view |
| PUT | `/default-messages/{account_id}` | Set default message | auto_response.manage |
| GET | `/item-messages` | List item messages | auto_response.view |
| PUT | `/item-messages/{item_id}` | Set item message | auto_response.manage |

#### Fast Answers Module

| Method | Path | Description | Perm |
|--------|------|-------------|------|
| GET | `/fast-answers` | List user's fast answers | crm.chat.view |
| POST | `/fast-answers` | Create fast answer | crm.chat.send |
| PATCH | `/fast-answers/{id}` | Update | crm.chat.send |
| DELETE | `/fast-answers/{id}` | Delete | crm.chat.send |

#### Self-employed Module

| Method | Path | Description | Perm |
|--------|------|-------------|------|
| POST | `/self-employed/check` | Check INN | self_employed.check |
| GET | `/self-employed/history` | Check history | self_employed.check |

#### Analytics Module

| Method | Path | Description | Perm |
|--------|------|-------------|------|
| GET | `/analytics/overview` | Dashboard stats | analytics.view |
| GET | `/analytics/funnel` | Stage conversion funnel | analytics.view |
| GET | `/analytics/by-vacancy` | Stats per vacancy | analytics.view |
| GET | `/analytics/by-responsible` | Stats per responsible | analytics.view |
| GET | `/analytics/by-department` | Stats per department | analytics.view |

#### Settings Module (org config)

| Method | Path | Description | Perm |
|--------|------|-------------|------|
| GET | `/settings/stages` | List pipeline stages | admin |
| POST | `/settings/stages` | Create stage | admin |
| PATCH | `/settings/stages/{id}` | Update stage | admin |
| DELETE | `/settings/stages/{id}` | Delete stage | admin |
| PUT | `/settings/stages/reorder` | Reorder stages | admin |
| GET | `/settings/tags` | List tags | admin |
| POST | `/settings/tags` | Create tag | admin |
| PATCH | `/settings/tags/{id}` | Update tag | admin |
| DELETE | `/settings/tags/{id}` | Delete tag | admin |
| GET | `/settings/departments` | List departments | admin |
| POST | `/settings/departments` | Create department | admin |
| PATCH | `/settings/departments/{id}` | Update | admin |
| DELETE | `/settings/departments/{id}` | Delete | admin |
| GET | `/settings/permissions` | List all permissions | admin |
| GET | `/settings/role-permissions/{role}` | Get role permissions | admin |
| PUT | `/settings/role-permissions/{role}` | Set role permissions | owner |

#### SuperAdmin Module (prefix: /superadmin, role = superadmin only, без RLS — видит всё)

**Организации:**
| Method | Path | Description |
|--------|------|-------------|
| GET | `/superadmin/organizations` | Все организации (users count, mailings count, status) |
| POST | `/superadmin/organizations` | Создать организацию |
| GET | `/superadmin/organizations/{id}` | Детали организации |
| PATCH | `/superadmin/organizations/{id}` | Обновить лимиты / настройки |
| POST | `/superadmin/organizations/{id}/deactivate` | Заморозить (все юзеры теряют доступ) |
| POST | `/superadmin/organizations/{id}/activate` | Разморозить |
| POST | `/superadmin/organizations/{id}/impersonate` | Войти от имени Owner |
| PATCH | `/superadmin/organizations/{id}/subscription` | Установить/продлить subscription_until |

**Пользователи:**
| Method | Path | Description |
|--------|------|-------------|
| GET | `/superadmin/organizations/{id}/users` | Юзеры организации |
| POST | `/superadmin/organizations/{id}/users` | Добавить пользователя |
| PATCH | `/superadmin/organizations/{id}/users/{uid}` | Изменить роль |
| DELETE | `/superadmin/organizations/{id}/users/{uid}` | Удалить из организации |

**Рассылки (все организации):**
| Method | Path | Description |
|--------|------|-------------|
| GET | `/superadmin/mailings` | Все рассылки платформы (фильтр по org, status, date) |
| GET | `/superadmin/mailings/{id}` | Детальный прогресс с получателями |
| POST | `/superadmin/mailings/{id}/pause` | Принудительная пауза |
| POST | `/superadmin/mailings/{id}/cancel` | Принудительная остановка |
| GET | `/superadmin/mailings/{id}/recipients` | Список получателей постранично |

**Ошибки:**
| Method | Path | Description |
|--------|------|-------------|
| GET | `/superadmin/errors` | Все ошибки (фильтр: org, source, layer, resolved, date) |
| GET | `/superadmin/errors/{id}` | Детали: stack trace, request_id, org, handler |
| POST | `/superadmin/errors/{id}/resolve` | Отметить как решённую + note |
| POST | `/superadmin/errors/resolve-bulk` | Массово закрыть |

**Статистика:**
| Method | Path | Description |
|--------|------|-------------|
| GET | `/superadmin/stats` | Орг-й всего, активных, юзеров, webhook RPS, рассылок сегодня |

---

#### Mailing — управление состоянием (обновлённый набор эндпоинтов)

| Method | Path | Description | Perm |
|--------|------|-------------|------|
| GET | `/mailings` | Список с прогрессом (sent/total, status, eta) | mailing.view |
| POST | `/mailings/by-ids` | Запустить или запланировать по ID | mailing.send |
| POST | `/mailings/by-filters` | Запустить или запланировать по фильтрам | mailing.send |
| GET | `/mailings/{id}` | Детальный прогресс + breakdown по статусам | mailing.view |
| GET | `/mailings/{id}/recipients` | Постраничный список: кто получил, кто нет, ошибки | mailing.view |
| POST | `/mailings/{id}/pause` | Пауза — воркер дошлёт текущее, сохранит позицию | mailing.send |
| POST | `/mailings/{id}/resume` | Возобновить с места паузы | mailing.send |
| POST | `/mailings/{id}/cancel` | Отменить (pending получатели → cancelled) | mailing.send |

---

#### Webhooks (external — account_token в URL является авторизацией)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/webhooks/avito/{account_token}` | Все события от Avito — маршрутизация по event_type в теле |

-- account_token однозначно определяет: org_id + avito_account_id
-- event_type из тела → отдельный хендлер: new_response / new_message / message_read / chat_blocked
-- Регистрация токенов: POST /avito-accounts/{id}/webhooks/setup

#### WebSocket

| Path | Description |
|------|-------------|
| `/ws` | Real-time updates (new messages, webhook events, mailing progress) |

WebSocket message format:
```json
{
  "type": "new_message" | "candidate_update" | "mailing_progress" | "webhook_event",
  "payload": { ... }
}
```

### 3.4. Architecture Layers

```
Request → Middleware (rate limit, logging)
        → Router (validate request, extract params)
        → Dependency Injection (auth, DB session, permissions)
        → Service (business logic, orchestration)
        → Repository (DB queries via SQLAlchemy)
        → Database (PostgreSQL with RLS)

Background:
  arq Worker → Service → Repository → Database
  arq Worker → AvitoAPI Service → External API
```

### 3.5. Redis Caching Strategy

#### Read-through кеш (стандартный):
Читаем из Redis → если нет → читаем из DB → пишем в Redis → возвращаем.

| Key Pattern | Data | TTL | Invalidation trigger |
|-------------|------|-----|----------------------|
| `avito_token:{org_id}:{account_id}` | Avito access_token | 23h | On 401 from Avito |
| `org_status:{org_id}` | access_status + subscription_until | 60s | On org update (SuperAdmin) |
| `user:{user_id}:profile` | User + permissions + departments | 5 min | On user/perms update |
| `org:{org_id}:settings` | Stages, tags, departments, pipeline | 10 min | On settings change |
| `org:{org_id}:filters` | Доступные значения фильтров | 5 min | On candidate/stage/dept change |
| `candidates:{org_id}:{hash}` | Страница кандидатов (сериализованный JSON) | 30s | Write-invalidate при любом изменении |
| `candidate:{id}` | Одиночный кандидат | 2 min | On update |
| `chat_msgs:{chat_id}:{page}` | История сообщений (постранично) | 3 min | On new message в этом чате |
| `analytics:{org_id}:{type}:{date}` | Аналитика | 15 min | Cron rebuild |
| `mailing:{job_id}:progress` | Прогресс рассылки (sent/failed/total) | no TTL | DEL при завершении |
| `mailing:{job_id}:pause` | Флаг паузы | 1h | DEL при resume |
| `mailing:{job_id}:stop` | Флаг остановки | 5 min | Auto-expire |
| `webhook:dedup:{token}:{uid}` | Дедупликация вебхуков | 5 min | Auto-expire |
| `rate:{ip}:{route}` | Счётчик запросов | 1 min | Auto-expire |
| `ws:org:{org_id}:users` | Set активных user_id (WebSocket) | no TTL | On connect/disconnect |

#### Write-behind (отложенная запись в DB):
Данные, которые меняются очень часто — обновляются в Redis мгновенно,
в PostgreSQL — батчами раз в N секунд. RAM не раздувается т.к. одна запись
на сущность (не очередь событий).

```
Что пишем в write-behind:

1. chat_metadata (last_message, unread_count, last_message_at)
   → обновляется при КАЖДОМ входящем сообщении (высокая частота)
   → Redis Hash: "wb:chat_meta:{chat_id}" = { unread_count, last_message, last_message_at }
   → Flush в DB: каждые 5 сек (arq periodic) или при >= 50 накопленных изменений
   → Структура: Redis SET "wb:chat_meta:dirty" добавляет chat_id, flush читает всё и сбрасывает

2. candidates.has_new_message + candidates.updated_at
   → обновляется при каждом новом сообщении кандидата
   → Redis Hash: "wb:candidate_flags:{candidate_id}" = { has_new_message, updated_at }
   → Flush: каждые 5 сек вместе с chat_metadata

3. mailing_jobs (sent, failed счётчики)
   → воркер обновляет Redis атомарно через HINCRBY
   → Redis Hash: "wb:mailing_job:{job_id}" = { sent, failed }
   → Flush в DB: каждые 10 сек или при завершении

4. webhook_endpoints.last_received_at
   → пишется при каждом вебхуке
   → Redis String: "wb:webhook_last:{endpoint_id}" = timestamp
   → Flush: каждые 60 сек (некритично)
```

#### Flush-воркер (arq periodic):
```python
# Запускается каждые 5 секунд
async def flush_write_behind(ctx):
    # 1. chat_metadata
    dirty_chats = await redis.smembers("wb:chat_meta:dirty")
    if dirty_chats:
        updates = [await redis.hgetall(f"wb:chat_meta:{cid}") for cid in dirty_chats]
        await db.execute_many("""
            UPDATE chat_metadata SET
                last_message = $1, unread_count = $2, last_message_at = $3, updated_at = now()
            WHERE chat_id = $4
        """, updates)
        await redis.delete(*[f"wb:chat_meta:{cid}" for cid in dirty_chats])
        await redis.srem("wb:chat_meta:dirty", *dirty_chats)

    # 2. candidate flags — аналогично
    # 3. mailing counters — аналогично
```

#### RAM оценка (write-behind):
- 1 запись chat_metadata в Redis: ~200 bytes
- 10 000 активных чатов = 2 MB — незначительно
- Mailing job counter: ~100 bytes × 100 активных рассылок = 10 KB
- Итого write-behind overhead: < 50 MB при любой нагрузке

#### Что НЕ кешируем:
- `error_log` — пишется напрямую в DB (низкая частота, важна немедленная видимость)
- `audit_log` — пишется напрямую (критично для compliance)
- Данные аутентификации — только DB + refresh_token table
- Мутации (POST/PATCH/DELETE) — всегда через DB, кеш инвалидируется после

### 3.6. Encryption Service

```python
# AES-256-GCM encryption
# Key: 32-byte from env ENCRYPTION_KEY
# Each encrypted value stored as: base64(nonce + ciphertext + tag)

# Fields that are encrypted at rest:
# - avito_accounts.client_id_enc
# - avito_accounts.client_secret_enc
# - candidates.phone_enc
# - auth_providers.access_token_enc
# - auth_providers.refresh_token_enc
```

### 3.7. Webhook Processing Pipeline

**URL structure**: `/webhooks/avito/{account_token}`

`account_token` — уникальный случайный slug (64 символа), генерируется при добавлении
Avito-аккаунта. Один токен = один аккаунт = все типы событий через один URL
(Avito сам кладёт `type` в тело). Токен является одновременно секретом и роутером —
знание URL = авторизация, без дополнительных заголовков.

```
Avito POST → /webhooks/avito/{account_token}
  1. O(1) lookup: SELECT org_id, avito_account_id, event_type
                  FROM avito_webhook_endpoints
                  WHERE account_token = {token} AND is_active = TRUE
     → если не найден: 404, логируем (возможна атака / устаревший хук)
  2. Dedup: Redis SETNX "whook:{account_token}:{event_uid}" EX 300
     → если уже есть: 200 (idempotent, Avito повторяет при неответе)
  3. Немедленно UPDATE last_received_at (async, не блокирует)
  4. Enqueue to arq с полным контекстом:
     { org_id, avito_account_id, event_type, payload }
  5. Return 200 OK  ← всё выше занимает < 5ms

Worker (по event_type, строго раздельные хендлеры):
  ┌─ 'new_response' ──→ ResponseWebhookHandler
  │     • Upsert candidate в responses (by avito chat_id)
  │     • Привязать к вакансии по item_id
  │     • Если auto_response включён для этого item_id → enqueue send_message
  │     • Notify WebSocket org
  │     • Invalidate: candidates cache, filters cache
  │
  ├─ 'new_message' ───→ MessageWebhookHandler
  │     • Найти response по (avito_account_id, chat_id)
  │     • UPDATE avito_chats_data: last_message, unreaded_count++
  │     • Если направление IN и fast_answer настроен → enqueue auto_reply
  │     • Notify WebSocket: { type: 'new_message', candidate_id, chat_id }
  │     • Invalidate: chat messages cache, all_chats cache
  │
  ├─ 'message_read' ──→ ReadReceiptHandler
  │     • UPDATE avito_chats_data: unreaded_count = 0
  │     • Notify WebSocket: { type: 'chat_read', chat_id }
  │     • Invalidate: all_chats cache
  │
  └─ 'chat_blocked' ──→ BlockHandler
        • UPDATE avito_chats_data: is_block = true
        • Notify WebSocket
```

**Регистрация вебхука в Avito** (при добавлении аккаунта):
```
POST /avito-accounts/{id}/webhooks/setup
  → для каждого event_type:
      1. Генерация account_token (secrets.token_urlsafe(48))
      2. INSERT avito_webhook_endpoints
      3. Вызов Avito API: зарегистрировать URL {BASE_URL}/webhooks/avito/{token}
      4. Сохранить avito_webhook_id ответа в endpoint записи
```

### 3.8. Mailing Pipeline

```
POST /mailings/by-ids | /mailings/by-filters
  1. Validate request
  2. INSERT mailing_jobs (status='pending', scheduled_at если задано)
  3. Populate mailing_recipients: INSERT ... SELECT candidates WHERE criteria
     (все строки сразу, status='pending') — после этого total известен
  4. Если scheduled_at = NULL → enqueue arq job сразу
     Если scheduled_at задан → scheduler подхватит в нужное время
  5. Return { job_id, total } немедленно

Scheduler (arq periodic, каждые 30 сек):
  SELECT id FROM mailing_jobs
  WHERE status = 'pending' AND scheduled_at <= now()
  → для каждого: enqueue mailing_worker.run(job_id)

Worker run(job_id):
  1. UPDATE mailing_jobs SET status='running', started_at=now(), arq_job_id=current_job_id
  2. Читаем cursor-style: SELECT id, candidate_id FROM mailing_recipients
     WHERE mailing_job_id = ? AND status = 'pending' ORDER BY id
     (возобновление после паузы работает автоматически — уже sent пропускаются)
  3. Группируем батчи по avito_account_id (минимум переключений токена)
  4. Для каждого recipient:
     a. CHECK Redis pause flag: "mailing:{job_id}:pause"
        → если есть: UPDATE status='paused', выход из цикла
     b. CHECK Redis stop flag:  "mailing:{job_id}:stop"
        → если есть: UPDATE status='cancelled', выход
     c. Получить Avito token из Redis (кеш 23ч)
     d. Отправить сообщение через Avito API
     e. При успехе:
        UPDATE mailing_recipients SET status='sent', sent_at=now()
        UPDATE mailing_jobs SET sent = sent + 1  (атомарно через SQL)
     f. При ошибке:
        attempt_count++
        Если attempt_count < 3: добавить в retry queue (задержка 5/30/120 сек)
        Иначе: UPDATE status='failed', error_code, error_message
                UPDATE mailing_jobs SET failed = failed + 1
     g. 429 Too Many Requests: exponential backoff (5s, 15s, 60s)
     h. Каждые 10 отправок: SET Redis "mailing:{job_id}:progress" = {sent, failed, total}
        + WebSocket push: { type: 'mailing_progress', job_id, sent, failed, total, percent }
  5. Завершение:
     UPDATE mailing_jobs SET status='done', finished_at=now()
     DEL Redis прогресс ключи
     WebSocket push: { type: 'mailing_done', job_id }

Pause API (POST /mailings/{id}/pause):
  SET Redis "mailing:{job_id}:pause" EX 3600
  UPDATE mailing_jobs SET status='paused', paused_at=now()
  → воркер увидит флаг на следующей итерации и остановится

Resume API (POST /mailings/{id}/resume):
  DEL Redis "mailing:{job_id}:pause"
  UPDATE mailing_jobs SET status='resuming', resumed_at=now()
  enqueue arq: mailing_worker.run(job_id)
  → воркер продолжит с первого pending recipient

Cancel API (POST /mailings/{id}/cancel):
  SET Redis "mailing:{job_id}:stop"
  UPDATE mailing_recipients SET status='skipped' WHERE status='pending'
  UPDATE mailing_jobs SET status='cancelled', finished_at=now()
```

### 3.8a. Error Handling Strategy

**Все ошибки — в `error_log`, видны в SuperAdmin:**

```python
# Единый декоратор/middleware для API роутов
@capture_errors(source='api', layer='router.candidates')
async def get_candidates(request, ...):
    ...

# Единая обёртка для воркеров
@capture_errors(source='worker', layer='worker.mailing', job_type='mailing')
async def mailing_worker(ctx, job_id):
    ...

# Webhook обёртка
@capture_errors(source='webhook', layer='webhook.new_message')
async def process_new_message(payload):
    ...
```

При поимке исключения:
```python
await error_log_repo.create(
    org_id=org_id,           # всегда известен из контекста
    user_id=user_id,         # из JWT если есть
    source=source,           # 'api' | 'worker' | 'webhook'
    layer=layer,             # модуль
    handler=f"{cls}.{method}",  # точный метод
    request_path=request.url.path,
    request_id=request.headers.get('X-Request-ID'),
    error_type=type(exc).__name__,
    error_message=str(exc),
    stack_trace=traceback.format_exc(),
    job_type=job_type,
    job_id=job_id,
    status_code=status_code
)
```

**Ответ клиенту при ошибке API:**
```json
{
  "error": "internal_error",
  "message": "Something went wrong",
  "request_id": "uuid",   // по нему SuperAdmin найдёт в error_log
  "code": "CANDIDATE_NOT_FOUND"  // машиночитаемый код для фронтенда
}
```
Никогда не возвращать stack trace клиенту. request_id позволяет пользователю
сообщить об ошибке, а SuperAdmin найти её за O(1) по индексу.

### 3.9. JWT Token Strategy

- **Access token**: 15 min TTL, contains `{ user_id, org_id, role }`
- **Refresh token**: 30 days TTL, stored hashed in `refresh_tokens` table
- On each request: middleware decodes JWT, sets `app.current_org_id` on DB session for RLS

### 3.9a. Org Access Middleware

На каждый API запрос (кроме /auth/* и /webhooks/*) middleware проверяет статус организации:

```python
async def org_access_middleware(request, call_next):
    org_id = request.state.org_id  # из JWT

    # Читаем из Redis (TTL 60s) — не дёргаем DB на каждый запрос
    status = await redis.get(f"org_status:{org_id}")
    if not status:
        org = await db.fetchrow("SELECT access_status, subscription_until FROM organizations WHERE id = $1", org_id)
        status = org['access_status']
        await redis.setex(f"org_status:{org_id}", 60, status)

    if status == 'suspended':
        return JSONResponse(status_code=403, content={
            "error": "org_suspended",
            "message": "Доступ приостановлен администратором",
            "reason": org.get('suspend_reason')
        })
    if status == 'expired':
        return JSONResponse(status_code=403, content={
            "error": "org_expired",
            "message": "Срок действия подписки истёк"
        })
    if status not in ('active',):
        return JSONResponse(status_code=403, content={"error": "org_inactive"})

    return await call_next(request)
```

**SuperAdmin** пропускает этот middleware полностью (`role == 'superadmin'`).

**При suspend/unsuspend/expiry SuperAdmin-ом:**
→ `DEL org_status:{org_id}` (инвалидация кеша) — изменение вступает в силу максимум через 60 сек.
→ Всем активным WebSocket соединениям орга: push `{ type: 'org_access_changed', status }` — клиент немедленно показывает экран блокировки без ожидания следующего запроса.

### 3.9b. Subscription Scheduler

```python
# arq periodic task, каждые 10 минут
async def check_subscription_expiry(ctx):
    # Найти организации у которых подписка истекла, но статус ещё 'active'
    expired = await db.fetch("""
        SELECT id FROM organizations
        WHERE access_status = 'active'
          AND subscription_until IS NOT NULL
          AND subscription_until < now()
    """)
    for org in expired:
        await db.execute("""
            UPDATE organizations SET access_status = 'expired', updated_at = now()
            WHERE id = $1
        """, org['id'])
        await redis.delete(f"org_status:{org['id']}")
        # WebSocket уведомление всем юзерам орга
        await ws_manager.broadcast_org(org['id'], { "type": "org_access_changed", "status": "expired" })

    # Найти организации у которых истечение через 7, 3, 1 день — уведомить Owner
    warning_thresholds = [7, 3, 1]  # дней
    for days in warning_thresholds:
        expiring = await db.fetch("""
            SELECT id FROM organizations
            WHERE access_status = 'active'
              AND subscription_until BETWEEN now() + interval '{d} days' - interval '10 minutes'
                                        AND now() + interval '{d} days'
        """.format(d=days))
        for org in expiring:
            await notify_owner(org['id'], f"Подписка истекает через {days} дн.")
```

### 3.9c. SMTP Email Service

**Библиотека**: `fastapi-mail` (обёртка над `aiosmtplib`) — полностью async, не блокирует event loop.

**Конфиг (env variables):**
```
SMTP_HOST=smtp.gmail.com        # или mail.yourdomain.ru
SMTP_PORT=587                   # 587 (STARTTLS) или 465 (SSL)
SMTP_USER=noreply@yourdomain.ru
SMTP_PASSWORD=<app-password>
SMTP_FROM_NAME=AvitoСRM
SMTP_TLS=true
SMTP_SSL=false
```

**Структура:**
```
app/services/email/
├── __init__.py
├── smtp.py              # SMTPService: низкоуровневая отправка
├── notifications.py     # EmailNotificationService: бизнес-логика
└── templates/
    ├── base.html        # ЕДИНСТВЕННЫЙ шаблон — все письма через него
    └── styles.css       # инлайн-стили (встраиваются в base.html при сборке)
```

**Один шаблон для всех писем.**
Никаких отдельных файлов на каждый тип — только `base.html` + контекст из Python.

#### Архитектура шаблона `base.html`

Письмо состоит из фиксированных блоков, каждый из которых опционален:

```
┌─────────────────────────────────────┐
│  HEADER                             │
│  Логотип + название продукта        │
│  Цветная полоса (цвет = тип письма) │
├─────────────────────────────────────┤
│  BADGE (опционально)                │
│  Иконка + метка типа уведомления    │
│  "Предупреждение" / "Важно" / "Инфо"│
├─────────────────────────────────────┤
│  TITLE                              │
│  Крупный заголовок письма           │
├─────────────────────────────────────┤
│  BODY                               │
│  Основной текст (HTML через |safe)  │
├─────────────────────────────────────┤
│  DETAILS BLOCK (опционально)        │
│  Таблица деталей — ключ: значение   │
│  "Организация: ООО Вектор"          │
│  "Дата истечения: 25 апреля 2025"   │
├─────────────────────────────────────┤
│  HIGHLIGHT BOX (опционально)        │
│  Выделенный блок — пароль, код,     │
│  важное значение                    │
├─────────────────────────────────────┤
│  CTA BUTTON (опционально)           │
│  Кнопка действия                    │
├─────────────────────────────────────┤
│  SECONDARY TEXT (опционально)       │
│  Мелкий текст под кнопкой           │
├─────────────────────────────────────┤
│  FOOTER                             │
│  © AvitoСRM · Это автоматическое   │
│  уведомление                        │
└─────────────────────────────────────┘
```

#### Дизайн-система письма

```
Типографика:
  Font: Inter, -apple-system, sans-serif (системные шрифты — гарантированная поддержка)
  Title: 26px, weight 700, color #0f172a
  Body:  16px, weight 400, color #334155, line-height 1.6
  Meta:  13px, color #94a3b8

Цветовая схема по типу письма (accent_color в контексте):
  'info'     → #3b82f6  (синий)  — информационные
  'warning'  → #f59e0b  (жёлтый) — предупреждения
  'danger'   → #ef4444  (красный) — критичные (заморозка, истечение)
  'success'  → #22c55e  (зелёный) — позитивные (welcome, восстановление)

Layout:
  Внешний фон:  #f1f5f9
  Карточка:     #ffffff, border-radius 16px, box-shadow мягкий
  Макс. ширина: 600px, центрирован
  Padding карточки: 40px 48px

Header:
  Цветная полоса 4px сверху (цвет = accent_color)
  Логотип + "AvitoСRM" слева

Details block:
  Фон #f8fafc, border-radius 10px, border-left 3px solid accent_color
  Строки: padding 10px 0, border-bottom 1px solid #e2e8f0

Highlight box:
  Фон #f0f9ff, border 1px solid #bae6fd, border-radius 10px
  Моноширинный шрифт, font-size 22px, letter-spacing 2px

CTA Button:
  Фон = accent_color, color #fff
  border-radius 10px, padding 14px 32px
  font-weight 600, font-size 15px
  Центрирован, display inline-block

Все стили inline — максимальная совместимость с почтовыми клиентами
(Gmail, Outlook, Apple Mail, Яндекс.Почта)
```

#### Контекст из Python → шаблон

```python
# Единая структура контекста для всех писем:
EmailContext = {
    # Обязательные
    "accent_color": "#f59e0b",         # цвет темы
    "badge_label": "Предупреждение",   # None → блок не рендерится
    "badge_icon": "⚠️",               # эмодзи или None
    "title": "Подписка истекает через 3 дня",
    "body": "Доступ к <b>AvitoСRM</b> для вашей организации...",  # поддерживает HTML

    # Опциональные блоки
    "details": [                        # None → блок не рендерится
        {"label": "Организация",  "value": "ООО Вектор"},
        {"label": "Дата истечения", "value": "25 апреля 2025"},
        {"label": "Тариф",        "value": "Стандарт"},
    ],
    "highlight": None,                  # None → блок не рендерится
    # или: { "label": "Временный пароль", "value": "Xk9#mP2q" }

    "cta_text": "Продлить подписку",    # None → кнопки нет
    "cta_url":  "https://...",

    "secondary_text": "Если у вас есть вопросы, свяжитесь с поддержкой.",

    # Footer
    "footer_text": "© 2025 AvitoСRM · Это автоматическое уведомление, не отвечайте на него.",
    "product_name": "AvitoСRM",
}
```

#### Примеры сборки контекста из `EmailNotificationService`

```python
# Предупреждение об истечении подписки:
context = {
    "accent_color": "#f59e0b",
    "badge_label": "Предупреждение", "badge_icon": "⚠️",
    "title": f"Подписка истекает через {days_left} дн.",
    "body": f"Доступ вашей организации <b>{org.name}</b> к AvitoСRM будет приостановлен.",
    "details": [
        {"label": "Организация",    "value": org.name},
        {"label": "Истекает",       "value": format_date(org.subscription_until)},
    ],
    "cta_text": "Продлить подписку", "cta_url": settings.BILLING_URL,
    "secondary_text": "Обратитесь к администратору платформы для продления.",
}

# Организация заморожена:
context = {
    "accent_color": "#ef4444",
    "badge_label": "Важно", "badge_icon": "🔒",
    "title": "Доступ к организации приостановлен",
    "body": "Администратор платформы приостановил доступ вашей организации.",
    "details": [
        {"label": "Организация", "value": org.name},
        {"label": "Причина",     "value": reason or "Не указана"},
        {"label": "Дата",        "value": format_datetime(now())},
    ],
    "cta_text": None, "secondary_text": "Для восстановления свяжитесь с поддержкой.",
}

# Приглашение сотрудника:
context = {
    "accent_color": "#22c55e",
    "badge_label": "Добро пожаловать", "badge_icon": "👋",
    "title": f"Вас пригласили в {org.name}",
    "body": f"<b>{invited_by}</b> добавил вас в AvitoСRM.",
    "details": [
        {"label": "Организация", "value": org.name},
        {"label": "Ваша роль",   "value": role_display},
        {"label": "Логин",       "value": user.email},
    ],
    "highlight": {"label": "Временный пароль", "value": temp_password},
    "cta_text": "Войти в систему", "cta_url": settings.APP_URL,
    "secondary_text": "Смените пароль после первого входа.",
}
```

Любое новое уведомление = заполнить контекст + один вызов `smtp_service.send()`. Новый HTML-файл не нужен никогда.

**SMTPService:**
```python
class SMTPService:
    async def send(
        self,
        to: list[str],
        subject: str,
        template: str,       # имя шаблона без расширения
        context: dict,       # переменные для Jinja2
    ) -> None:
        # Рендерит шаблон, отправляет через aiosmtplib
        # При ошибке: пишет в error_log (source='smtp'), не бросает исключение вверх
        # Retry: 3 попытки с backoff 5s/30s — через arq job, не блокируя вызывающий код
```

**EmailNotificationService** — единственный класс с бизнес-логикой уведомлений:
```python
class EmailNotificationService:
    async def notify_subscription_warning(self, org_id, days_left: int): ...
    async def notify_subscription_expired(self, org_id): ...
    async def notify_org_suspended(self, org_id, reason: str): ...
    async def notify_welcome(self, user_email, org_name, temp_password): ...
    # Дальнейшее расширение: просто добавить метод + шаблон
```

**Получатели уведомлений:**
- Предупреждение об истечении → Owner организации (`role = 'owner'`)
- Организация заморожена → Owner + все Admin
- Все адреса берутся из DB по `org_id` + `role` — всегда актуальны

**Отправка через arq** (не блокирует HTTP запрос):
```python
# В subscription scheduler:
await arq_pool.enqueue_job('send_email', to=[owner_email], template='subscription_expiry_warning', context={...})

# arq worker:
async def send_email(ctx, to, template, context):
    await smtp_service.send(to=to, subject=..., template=template, context=context)
```

**Если SMTP не настроен** (переменные не заданы): SMTPService логирует предупреждение при старте,
все методы EmailNotificationService становятся no-op — приложение работает без email без ошибок.

### 3.10. Implementation Sequence

```
Phase 1 - Foundation (week 1-2):
  1. Project scaffolding, config, database.py, redis.py
  2. SQLAlchemy models (all tables)
  3. Alembic initial migration
  4. Encryption service
  5. Auth: register, login, refresh, JWT, password hashing
  6. Middleware: tenant isolation, RLS setup
  7. Base repository with CRUD

Phase 2 - Core CRM (week 3-4):
  8. Candidates CRUD + filters + pagination
  9. Chat service (messages via Avito API)
  10. Tags, stages, departments CRUD
  11. Responsible assignment
  12. Tasks CRUD
  13. Redis caching integration

Phase 3 - Avito Integration (week 5-6):
  14. Avito API client service (token management, all API methods)
  15. Avito accounts management
  16. Webhook receivers + arq workers
  17. Auto-response engine
  18. Default/item messages

Phase 4 - Advanced Features (week 7-8):
  19. Mailing system with arq workers
  20. Vacancy management (sync, activate, deactivate, edit)
  21. Self-employed INN check
  22. Analytics service
  23. WebSocket real-time updates
  24. Fast answers

Phase 5 - Polish (week 9):
  25. Rate limiting
  26. Audit logging
  27. Performance testing, index tuning
  28. API documentation cleanup
```

---

## 4. DESKTOP FRONTEND (Agent 2) -- Tauri + React/TypeScript

### 4.1. Project Structure

```
desktop/
├── src-tauri/
│   ├── src/
│   │   ├── main.rs               # Tauri entry point
│   │   ├── lib.rs                 # Plugin registration
│   │   ├── commands/
│   │   │   ├── mod.rs
│   │   │   ├── auth.rs            # Secure token storage in OS keychain
│   │   │   ├── notifications.rs   # Native notifications
│   │   │   └── files.rs           # File system access for exports
│   │   └── tray.rs                # System tray icon
│   ├── Cargo.toml
│   ├── tauri.conf.json
│   └── icons/
├── src/
│   ├── main.tsx                   # Entry point
│   ├── App.tsx                    # Root component + router
│   ├── services/
│   │   └── native/
│   │       ├── index.ts           # Exports correct impl based on VITE_PLATFORM
│   │       ├── tauri.ts           # Tauri (desktop): keychain, native dialogs, tray
│   │       └── web.ts             # Browser fallback: localStorage, Web APIs
│   ├── api/
│   │   ├── client.ts              # Axios instance, interceptors, token refresh
│   │   ├── auth.ts                # Auth API calls
│   │   ├── candidates.ts
│   │   ├── chats.ts
│   │   ├── mailings.ts
│   │   ├── tasks.ts
│   │   ├── vacancies.ts
│   │   ├── avito-accounts.ts
│   │   ├── analytics.ts
│   │   ├── auto-response.ts
│   │   ├── self-employed.ts
│   │   ├── fast-answers.ts
│   │   ├── settings.ts
│   │   ├── users.ts
│   │   └── websocket.ts           # WS connection manager
│   ├── stores/                    # Zustand stores
│   │   ├── auth.store.ts          # User, tokens, permissions
│   │   ├── candidates.store.ts
│   │   ├── chat.store.ts
│   │   ├── mailing.store.ts
│   │   ├── ui.store.ts            # Sidebar, modals, notifications
│   │   └── settings.store.ts      # Cached org settings (stages, tags)
│   ├── hooks/
│   │   ├── useAuth.ts
│   │   ├── useCandidates.ts       # React Query hooks
│   │   ├── useChats.ts
│   │   ├── useMailings.ts
│   │   ├── useTasks.ts
│   │   ├── useVacancies.ts
│   │   ├── useAnalytics.ts
│   │   ├── usePermission.ts       # Check current user permissions
│   │   ├── useWebSocket.ts
│   │   ├── useDebounce.ts
│   │   └── usePagination.ts
│   ├── pages/
│   │   ├── LoginPage/
│   │   │   └── LoginPage.tsx
│   │   ├── RegisterPage/
│   │   │   └── RegisterPage.tsx
│   │   ├── CandidatesPage/
│   │   │   └── CandidatesPage.tsx
│   │   ├── MessengerPage/
│   │   │   └── MessengerPage.tsx
│   │   ├── MailingsPage/
│   │   │   └── MailingsPage.tsx
│   │   ├── TasksPage/
│   │   │   └── TasksPage.tsx
│   │   ├── AnalyticsPage/
│   │   │   └── AnalyticsPage.tsx
│   │   ├── VacanciesPage/
│   │   │   └── VacanciesPage.tsx
│   │   ├── AvitoAccountsPage/
│   │   │   └── AvitoAccountsPage.tsx
│   │   ├── AutoResponsePage/
│   │   │   └── AutoResponsePage.tsx
│   │   ├── SelfEmployedPage/
│   │   │   └── SelfEmployedPage.tsx
│   │   ├── UsersPage/
│   │   │   └── UsersPage.tsx
│   │   ├── SettingsPage/
│   │   │   ├── StagesSettings.tsx
│   │   │   ├── TagsSettings.tsx
│   │   │   ├── DepartmentsSettings.tsx
│   │   │   └── PermissionsSettings.tsx
│   │   └── NotFoundPage/
│   │       └── NotFoundPage.tsx
│   ├── components/
│   │   ├── layout/
│   │   │   ├── AppLayout.tsx       # Main layout with sidebar
│   │   │   ├── Sidebar.tsx
│   │   │   ├── Header.tsx
│   │   │   └── AuthLayout.tsx      # Login/register layout
│   │   ├── candidates/
│   │   │   ├── CandidateTable.tsx
│   │   │   ├── CandidateCard.tsx
│   │   │   ├── CandidateModal.tsx
│   │   │   ├── CandidateFilters.tsx
│   │   │   ├── BulkActionsBar.tsx
│   │   │   └── StageSelect.tsx
│   │   ├── chat/
│   │   │   ├── ChatList.tsx
│   │   │   ├── ChatListItem.tsx
│   │   │   ├── ChatFilters.tsx
│   │   │   ├── MessagesList.tsx
│   │   │   ├── MessageItem.tsx
│   │   │   ├── MessageInput.tsx
│   │   │   ├── FilePreview.tsx
│   │   │   ├── VoicePlayer.tsx
│   │   │   ├── DateDivider.tsx
│   │   │   └── FastAnswersPopover.tsx
│   │   ├── mailings/
│   │   │   ├── MailingsList.tsx
│   │   │   ├── MailingCard.tsx
│   │   │   ├── StartMailingModal.tsx
│   │   │   └── MailingProgress.tsx
│   │   ├── tasks/
│   │   │   ├── TaskList.tsx
│   │   │   ├── TaskCard.tsx
│   │   │   ├── CreateTaskModal.tsx
│   │   │   └── TaskCalendar.tsx
│   │   ├── vacancies/
│   │   │   ├── VacancyList.tsx
│   │   │   ├── VacancyCard.tsx
│   │   │   └── EditVacancyModal.tsx
│   │   ├── analytics/
│   │   │   ├── StageConversionChart.tsx
│   │   │   ├── VacancyStats.tsx
│   │   │   ├── ResponsibleStats.tsx
│   │   │   └── OverviewCards.tsx
│   │   ├── avito-accounts/
│   │   │   ├── AccountList.tsx
│   │   │   ├── AccountCard.tsx
│   │   │   └── AddAccountModal.tsx
│   │   ├── auto-response/
│   │   │   ├── RulesList.tsx
│   │   │   ├── RuleEditor.tsx
│   │   │   ├── DefaultMessageEditor.tsx
│   │   │   └── ItemMessageEditor.tsx
│   │   ├── users/
│   │   │   ├── UsersList.tsx
│   │   │   ├── InviteUserModal.tsx
│   │   │   └── UserPermissionsModal.tsx
│   │   ├── settings/
│   │   │   ├── StageManager.tsx    # Drag-and-drop reorder
│   │   │   ├── TagManager.tsx
│   │   │   └── DepartmentManager.tsx
│   │   └── common/
│   │       ├── Pagination.tsx
│   │       ├── ConfirmDialog.tsx
│   │       ├── LoadingSpinner.tsx
│   │       ├── EmptyState.tsx
│   │       ├── ErrorBoundary.tsx
│   │       ├── Toast.tsx
│   │       ├── SearchInput.tsx
│   │       ├── DateRangePicker.tsx
│   │       ├── Badge.tsx
│   │       ├── Avatar.tsx
│   │       └── PermissionGate.tsx  # Renders children only if user has permission
│   ├── types/
│   │   ├── auth.ts
│   │   ├── candidate.ts
│   │   ├── chat.ts
│   │   ├── mailing.ts
│   │   ├── task.ts
│   │   ├── vacancy.ts
│   │   ├── settings.ts
│   │   └── common.ts
│   ├── utils/
│   │   ├── date.ts
│   │   ├── format.ts
│   │   ├── validation.ts
│   │   └── file.ts
│   ├── styles/
│   │   ├── globals.css
│   │   └── variables.css
│   └── providers/
│       ├── QueryProvider.tsx       # React Query
│       ├── WebSocketProvider.tsx
│       └── ThemeProvider.tsx
├── index.html
├── package.json
├── tsconfig.json
├── vite.config.ts
└── tailwind.config.ts
```

### 4.2. Technology Stack

- **UI Framework**: React 19 + TypeScript
- **Build**: Vite
- **State Management**: Zustand (global state) + React Query (server state)
- **Styling**: Tailwind CSS + shadcn/ui components
- **Routing**: React Router v7
- **HTTP Client**: Axios (with interceptor for token refresh)
- **Real-time**: native WebSocket via hook
- **Charts**: recharts
- **Tables**: TanStack Table
- **Desktop**: Tauri v2

### 4.3. Platform Abstraction Layer

**Critical rule**: React components NEVER import `@tauri-apps/*` directly.
All native calls go through `src/services/native/` which has two implementations:

```
src/services/native/
├── index.ts            # re-exports based on VITE_PLATFORM env var
├── tauri.ts            # Tauri implementation (desktop build)
└── web.ts              # Browser fallback (future web version)
```

Interface:
```typescript
interface NativeService {
  getToken(): Promise<string | null>         // keychain vs localStorage
  setToken(token: string): Promise<void>
  clearToken(): Promise<void>
  notify(title: string, body: string): Promise<void>   // native vs Web Notifications API
  pickFile(accept: string[]): Promise<File | null>     // native dialog vs <input type=file>
  saveFile(data: Blob, filename: string): Promise<void>
  getWindowState(): Promise<WindowState>
  setWindowState(state: WindowState): Promise<void>
}
```

This way the entire React app works in a browser unchanged — just swap `VITE_PLATFORM=web`.

### 4.3a. Tauri-specific Features (desktop only, via NativeService)

1. **Secure token storage**: `tauri-plugin-store` + OS keychain (Windows Credential Manager / macOS Keychain / Linux Secret Service)
2. **Auto-updater**: `tauri-plugin-updater` for silent background updates — Windows, macOS, Linux
3. **System tray**: Unread message/response count badge, quick actions menu
4. **Native notifications**: New message / new response alerts via `tauri-plugin-notification`
5. **File dialogs**: Native file picker for CSV uploads, file exports (`tauri-plugin-dialog`)
6. **Window management**: Remember size/position on close, restore on open
7. **Target OS**: Windows 10+, macOS 12+, Ubuntu 20.04+ (Tauri v2 targets)

### 4.4. Routing

```
/login                         -> LoginPage
/register                      -> RegisterPage
/candidates                    -> CandidatesPage
/messenger                     -> MessengerPage
/messenger/:candidateId        -> MessengerPage (chat open)
/mailings                      -> MailingsPage
/tasks                         -> TasksPage
/analytics                     -> AnalyticsPage
/vacancies                     -> VacanciesPage
/avito-accounts                -> AvitoAccountsPage
/auto-response                 -> AutoResponsePage
/self-employed                 -> SelfEmployedPage
/users                         -> UsersPage (admin+)
/settings                      -> SettingsPage (admin+)
/settings/stages               -> StagesSettings
/settings/tags                 -> TagsSettings
/settings/departments          -> DepartmentsSettings
/settings/permissions          -> PermissionsSettings
```

### 4.5. State Management

**Zustand stores** (client state):
- `authStore`: `{ user, tokens, isAuthenticated, login(), logout(), refreshToken() }`
- `uiStore`: `{ sidebarOpen, activeModals[], notifications[], theme }`

**React Query** (server state):
- All API data fetched/cached via `useQuery`/`useMutation`
- Query keys: `['candidates', filters]`, `['chats', filters]`, `['mailing', jobId]`, etc.
- Stale time: 30s for lists, 2min for details
- WebSocket events trigger `queryClient.invalidateQueries()`

### 4.6. WebSocket Integration

```typescript
// Connect on auth, reconnect with exponential backoff
// Messages:
// - 'new_message' -> invalidate chats, show notification
// - 'candidate_update' -> invalidate candidates list
// - 'mailing_progress' -> update mailing status in real-time
// - 'webhook_event' -> notification toast
```

### 4.7. Page Descriptions

| Page | Source in existing code | New functionality |
|------|----------------------|-------------------|
| Candidates | CandidatesPage.tsx | + department filter, configurable stages/tags |
| Messenger | MessengerPage.tsx | + fast answers, + file preview improvements |
| Mailings | MailingsPage.tsx | + pause/resume/cancel, + detailed recipient tracking |
| Tasks | Existed in API only | Full calendar view with task management |
| Analytics | AnalyticsPage.tsx | + by-department, + by-responsible charts |
| Vacancies | Bot only (callback handlers) | Full web UI: list, activate, deactivate, edit |
| Avito Accounts | Bot only | Web UI: add/remove accounts, view balances |
| Auto-response | Bot only (data.json) | Web UI: rules management, default/item messages |
| Self-employed | Bot only | Web UI: INN check with history |
| Users | New | User management, permissions |
| Settings | New | Stages, tags, departments, permissions config |

### 4.8. Implementation Sequence

```
Phase 1 (week 2-3, parallel with backend Phase 1-2):
  1. Project scaffolding: Tauri + Vite + React + Tailwind + shadcn/ui
  2. API client with interceptors (mock server initially)
  3. Auth pages (login, register)
  4. AppLayout + Sidebar + routing
  5. Auth store + protected routes

Phase 2 (week 4-5):
  6. CandidatesPage with table, filters, pagination
  7. CandidateModal (edit, tags, responsible)
  8. MessengerPage (chat list + message area)
  9. MessageInput with file upload

Phase 3 (week 6-7):
  10. MailingsPage + StartMailingModal + real-time progress
  11. TasksPage + calendar
  12. AnalyticsPage + charts
  13. WebSocket integration

Phase 4 (week 8-9):
  14. VacanciesPage
  15. AvitoAccountsPage
  16. AutoResponsePage
  17. SelfEmployedPage
  18. UsersPage + SettingsPage
  19. Tauri features (notifications, tray, auto-update)
```

---

## 5. INFRASTRUCTURE (Agent 3)

### 5.1. Docker Compose

```yaml
# docker-compose.yml
version: '3.9'

services:
  api:
    build:
      context: ./backend
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql+asyncpg://crm:${DB_PASSWORD}@postgres:5432/avito_crm
      - REDIS_URL=redis://redis:6379/0
      - ENCRYPTION_KEY=${ENCRYPTION_KEY}
      - JWT_SECRET=${JWT_SECRET}
      - JWT_ALGORITHM=HS256
      - ACCESS_TOKEN_EXPIRE_MINUTES=15
      - REFRESH_TOKEN_EXPIRE_DAYS=30
      - CORS_ORIGINS=tauri://localhost,https://tauri.localhost
      - WEBHOOK_BASE_URL=${WEBHOOK_BASE_URL}
      - LOG_LEVEL=info
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    restart: unless-stopped
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 2G
    networks:
      - app-network

  worker:
    build:
      context: ./backend
      dockerfile: Dockerfile
    command: arq app.workers.WorkerSettings
    environment:
      - DATABASE_URL=postgresql+asyncpg://crm:${DB_PASSWORD}@postgres:5432/avito_crm
      - REDIS_URL=redis://redis:6379/0
      - ENCRYPTION_KEY=${ENCRYPTION_KEY}
    depends_on:
      - postgres
      - redis
    restart: unless-stopped
    deploy:
      replicas: 2
      resources:
        limits:
          cpus: '1.0'
          memory: 1G
    networks:
      - app-network

  postgres:
    image: postgres:16-alpine
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./infra/postgres/init.sql:/docker-entrypoint-initdb.d/01-init.sql
      - ./infra/postgres/postgresql.conf:/etc/postgresql/postgresql.conf
    environment:
      - POSTGRES_DB=avito_crm
      - POSTGRES_USER=crm
      - POSTGRES_PASSWORD=${DB_PASSWORD}
    command: postgres -c config_file=/etc/postgresql/postgresql.conf
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U crm -d avito_crm"]
      interval: 5s
      timeout: 5s
      retries: 5
    restart: unless-stopped
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 4G
    networks:
      - app-network

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
      - ./infra/redis/redis.conf:/usr/local/etc/redis/redis.conf
    command: redis-server /usr/local/etc/redis/redis.conf
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5
    restart: unless-stopped
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 512M
    networks:
      - app-network

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./infra/nginx/nginx.conf:/etc/nginx/nginx.conf
      - ./infra/nginx/conf.d:/etc/nginx/conf.d
      - ./infra/certbot/conf:/etc/letsencrypt
      - ./infra/certbot/www:/var/www/certbot
    depends_on:
      - api
    restart: unless-stopped
    networks:
      - app-network

volumes:
  postgres_data:
  redis_data:

networks:
  app-network:
    driver: bridge
```

### 5.2. Nginx Config

```nginx
# infra/nginx/conf.d/api.conf
upstream api_backend {
    least_conn;
    server api:8000;
}

server {
    listen 80;
    server_name api.yourdomain.ru;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name api.yourdomain.ru;

    ssl_certificate /etc/letsencrypt/live/api.yourdomain.ru/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.yourdomain.ru/privkey.pem;

    # Security headers
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api_limit:10m rate=100r/s;
    limit_req_zone $binary_remote_addr zone=webhook_limit:10m rate=500r/s;

    # API
    location /api/ {
        limit_req zone=api_limit burst=50 nodelay;
        proxy_pass http://api_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Timeouts
        proxy_connect_timeout 10s;
        proxy_send_timeout 30s;
        proxy_read_timeout 30s;

        # File upload limit
        client_max_body_size 20M;
    }

    # Webhooks (higher rate limit)
    location /api/v1/webhooks/ {
        limit_req zone=webhook_limit burst=200 nodelay;
        proxy_pass http://api_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;

        proxy_connect_timeout 5s;
        proxy_send_timeout 10s;
        proxy_read_timeout 10s;
    }

    # WebSocket
    location /api/v1/ws {
        proxy_pass http://api_backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 86400s;
        proxy_send_timeout 86400s;
    }
}
```

### 5.3. PostgreSQL Config

```conf
# infra/postgres/postgresql.conf
# Optimized for 500+ RPS, 4GB RAM allocation

# Connections
max_connections = 300
superuser_reserved_connections = 3

# Memory
shared_buffers = 1GB
effective_cache_size = 3GB
work_mem = 8MB
maintenance_work_mem = 256MB
wal_buffers = 16MB

# Write-Ahead Log
wal_level = replica
max_wal_size = 2GB
min_wal_size = 512MB
checkpoint_completion_target = 0.9
checkpoint_timeout = 10min

# Query Planner
random_page_cost = 1.1
effective_io_concurrency = 200
default_statistics_target = 100

# Parallel Queries
max_worker_processes = 4
max_parallel_workers_per_gather = 2
max_parallel_workers = 4
max_parallel_maintenance_workers = 2

# Logging
log_min_duration_statement = 500
log_checkpoints = on
log_connections = on
log_disconnections = on
log_lock_waits = on
log_statement = 'ddl'

# Autovacuum
autovacuum_max_workers = 3
autovacuum_naptime = 30s
autovacuum_vacuum_threshold = 50
autovacuum_analyze_threshold = 50
autovacuum_vacuum_scale_factor = 0.05
autovacuum_analyze_scale_factor = 0.025

# Row Level Security
row_security = on
```

### 5.4. Redis Config

```conf
# infra/redis/redis.conf
bind 0.0.0.0
port 6379
protected-mode yes
requirepass ${REDIS_PASSWORD}

# Memory
maxmemory 256mb
maxmemory-policy allkeys-lru

# Persistence (AOF for arq task queue durability)
appendonly yes
appendfsync everysec
auto-aof-rewrite-percentage 100
auto-aof-rewrite-min-size 64mb

# RDB snapshots (backup)
save 900 1
save 300 10
save 60 10000

# Performance
tcp-keepalive 60
timeout 300
hz 10
```

### 5.5. Backend Dockerfile

```dockerfile
# backend/Dockerfile
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4", "--loop", "uvloop", "--http", "httptools"]
```

### 5.6. Environment Variables

```env
# .env (template)

# Database
DB_PASSWORD=<strong-password>
DATABASE_URL=postgresql+asyncpg://crm:${DB_PASSWORD}@postgres:5432/avito_crm

# Redis
REDIS_PASSWORD=<strong-password>
REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379/0

# Security
JWT_SECRET=<random-64-char-string>
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=30
ENCRYPTION_KEY=<32-bytes-base64-encoded>

# Avito Webhooks
WEBHOOK_BASE_URL=https://api.yourdomain.ru/api/v1/webhooks/avito

# CORS
CORS_ORIGINS=tauri://localhost,https://tauri.localhost

# App
LOG_LEVEL=info
ENVIRONMENT=production
SUPERADMIN_EMAIL=admin@yourdomain.ru

# SMTP (опционально — если не задано, email уведомления отключены автоматически)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=noreply@yourdomain.ru
SMTP_PASSWORD=<app-password>
SMTP_FROM_NAME=AvitoСRM
SMTP_TLS=true
SMTP_SSL=false
```

### 5.7. Infrastructure File Structure

```
infra/
├── nginx/
│   ├── nginx.conf
│   └── conf.d/
│       └── api.conf
├── postgres/
│   ├── postgresql.conf
│   └── init.sql              # CREATE EXTENSION, initial roles
├── redis/
│   └── redis.conf
├── certbot/
│   ├── conf/
│   └── www/
├── scripts/
│   ├── backup.sh             # pg_dump + redis BGSAVE
│   ├── restore.sh
│   └── deploy.sh             # docker compose pull && up -d
└── monitoring/
    └── docker-compose.monitoring.yml  # Prometheus + Grafana (optional)
```

---

## 6. IMPLEMENTATION ORDER (Cross-Agent Dependencies)

```
Week 1-2: [Backend Phase 1] Foundation
  - Backend: DB schema, models, migrations, auth, encryption
  - Desktop: Project scaffolding, Tauri setup, mock API client
  - Infra: Docker compose, PostgreSQL, Redis, Nginx

Week 3-4: [Backend Phase 2 + Desktop Phase 2]
  - Backend: Candidates, Chats, Tags, Stages APIs
  - Desktop: Auth pages, layout, CandidatesPage, MessengerPage
  (Backend delivers API -> Desktop integrates)

Week 5-6: [Backend Phase 3 + Desktop Phase 3]
  - Backend: Avito integration, webhooks, auto-response
  - Desktop: Mailings, Tasks, Analytics, WebSocket

Week 7-8: [Backend Phase 4 + Desktop Phase 4]
  - Backend: Mailings, Vacancies, Self-employed, Analytics
  - Desktop: Vacancies, Accounts, Auto-response, Settings

Week 9: [Polish]
  - Integration testing
  - Performance tuning
  - Tauri builds (Windows/Mac/Linux)
  - Documentation
```

**Blockers:**
- Desktop cannot integrate real API until Backend Phase 2 delivers endpoints
- Webhooks require Infra to expose public URL (WEBHOOK_BASE_URL)
- Mailing progress requires WebSocket which depends on Backend Phase 4

**Can be parallelized:**
- Infra is fully independent from Phase 1
- Desktop UI scaffolding and mock integration runs parallel to Backend
- Backend workers (arq) can be developed independently after Phase 2

---

## 7. RISKS AND EDGE CASES

### Performance
- **Risk**: Complex candidate list query with 6+ JOINs under 500 RPS
- **Mitigation**: Redis cache (30s TTL) for list responses; materialized columns for frequently filtered data; database connection pool size tuned (min=20, max=100)

- **Risk**: Avito API rate limits (undocumented)
- **Mitigation**: Per-account rate limiter in Redis; exponential backoff; queue-based sending

### Security
- **Risk**: Tenant data leakage if RLS misconfigured
- **Mitigation**: RLS + application-level org_id filtering (defense in depth); integration tests that verify cross-tenant isolation

- **Risk**: Encryption key rotation
- **Mitigation**: Store key version with encrypted data; support decrypting with old key + re-encrypting with new

### Reliability
- **Risk**: Webhook deduplication misses (race condition)
- **Mitigation**: Redis SETNX with TTL for dedup; database UNIQUE constraints as fallback

- **Risk**: Mailing interrupted mid-way (worker crash)
- **Mitigation**: Per-recipient status in DB; on restart, resume from last pending recipient

### Edge Cases
- Candidate without chat_id (response webhook before message webhook)
- Multiple Avito accounts with same user_id in different orgs (isolated by org_id)
- Avito token expires mid-mailing (refresh and retry)
- File upload to Avito fails (return error, do not mark as sent)
- WebSocket disconnect during mailing (client reconnects, fetches current status)
- User deleted while they are responsible for candidates (soft delete, re-assign)
- Organization reaches max_users limit (check on invite)
- Concurrent edits to same candidate (last-write-wins with updated_at optimistic check)
