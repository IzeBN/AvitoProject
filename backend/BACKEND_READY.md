# AvitoСRM Backend — Ready Checklist

## Быстрый старт

```bash
# 1. Скопировать конфигурацию
cp .env.example .env
# Заполнить .env реальными значениями

# 2. Запустить зависимости (PostgreSQL + Redis)
docker run -d --name pg -e POSTGRES_DB=avitocrm -e POSTGRES_USER=avitocrm -e POSTGRES_PASSWORD=secret -p 5432:5432 postgres:16
docker run -d --name redis -p 6379:6379 redis:7 redis-server --requirepass secret

# 3. Установить зависимости
pip install -r requirements.txt

# 4. Применить миграции
alembic upgrade head

# 5. Запустить API сервер
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 6. Запустить ARQ воркер (отдельный процесс)
arq app.workers.settings.WorkerSettings

# 7. Проверить импорты
python scripts/check_imports.py
```

---

## Структура проекта

```
backend/
├── app/
│   ├── main.py                    # FastAPI фабрика, lifespan, middleware
│   ├── config.py                  # Pydantic Settings v2
│   ├── database.py                # SQLAlchemy async engine + session factory
│   ├── redis.py                   # Redis пулы (app + ARQ)
│   ├── dependencies.py            # Depends: get_current_user, require_permission
│   ├── models/                    # SQLAlchemy ORM модели
│   │   ├── __init__.py            # Импортирует все модели для Alembic autogenerate
│   │   ├── auth.py                # Organization, User, UserCredentials, RefreshToken, ...
│   │   ├── crm.py                 # Candidate, CandidateTag, PipelineStage, Tag
│   │   ├── chat.py                # ChatMessage, ChatMetadata
│   │   ├── mailing.py             # MailingJob, MailingRecipient
│   │   ├── task.py                # Task
│   │   ├── vacancy.py             # Vacancy
│   │   ├── messaging.py           # DefaultMessage, ItemMessage, AutoResponseRule, FastAnswer
│   │   ├── self_employed.py       # SelfEmployedCheck
│   │   ├── audit.py               # AuditLog
│   │   └── error_log.py           # ErrorLog
│   ├── schemas/                   # Pydantic v2 схемы запросов/ответов
│   ├── repositories/              # Слой доступа к данным
│   ├── services/                  # Бизнес-логика
│   ├── routers/                   # FastAPI роутеры
│   ├── middleware/                # Tenant, OrgAccess, RequestID
│   ├── security/                  # JWT, пароли, AES-256 шифрование
│   └── workers/                   # ARQ фоновые задачи
│       ├── settings.py            # WorkerSettings (arq entry point)
│       ├── write_behind.py        # flush_write_behind_task
│       ├── webhook_worker.py      # handle_new_response/message/read/blocked
│       ├── mailing_worker.py      # run_mailing, check_scheduled_mailings
│       ├── scheduler.py           # check_subscription_expiry, create_monthly_partitions, flush_webhook_last_received
│       └── tasks.py               # check_self_employed_inn
├── alembic/
│   ├── env.py
│   └── versions/
│       └── 0001_initial_schema.py # Все таблицы, индексы, RLS политики
├── scripts/
│   └── check_imports.py           # Проверка всех импортов
├── requirements.txt
├── .env.example
└── alembic.ini
```

---

## Переменные окружения

| Переменная | Обязательна | По умолчанию | Описание |
|---|---|---|---|
| `DATABASE_URL` | Да | — | `postgresql+asyncpg://user:pass@host:5432/db` |
| `DATABASE_POOL_SIZE` | Нет | 20 | Размер основного пула соединений |
| `DATABASE_MAX_OVERFLOW` | Нет | 80 | Максимальное переполнение пула |
| `REDIS_URL` | Да | — | `redis://:pass@host:6379/0` |
| `REDIS_POOL_SIZE` | Нет | 20 | Размер Redis пула |
| `SECRET_KEY` | Да | — | Случайная строка 32+ символа (JWT подпись) |
| `ENCRYPTION_KEY` | Да | — | 64 hex-символа (AES-256-GCM ключ) |
| `SEARCH_HASH_KEY` | Да | — | Ключ HMAC-SHA256 для поиска телефона |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Нет | 15 | TTL access токена |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Нет | 30 | TTL refresh токена |
| `SUPERADMIN_EMAIL` | Да | — | Email суперадмина |
| `SUPERADMIN_PASSWORD` | Да | — | Пароль суперадмина |
| `APP_NAME` | Нет | AvitoСRM | Имя приложения |
| `ENVIRONMENT` | Нет | development | `development` / `production` |
| `DEBUG` | Нет | false | Debug режим |
| `LOG_LEVEL` | Нет | info | Уровень логирования |
| `SMTP_HOST` | Нет | — | SMTP хост (email отключён если не задан) |
| `SMTP_PORT` | Нет | 587 | SMTP порт |
| `SMTP_USER` | Нет | — | SMTP логин |
| `SMTP_PASSWORD` | Нет | — | SMTP пароль |
| `SMTP_FROM_NAME` | Нет | AvitoСRM | Имя отправителя |
| `SMTP_TLS` | Нет | true | Использовать STARTTLS |
| `SMTP_SSL` | Нет | false | Использовать SSL |
| `ARQ_REDIS_URL` | Нет | REDIS_URL | Отдельный Redis для ARQ очереди |

---

## API Endpoints

### Аутентификация — `/api/v1/auth`
| Метод | Путь | Описание |
|---|---|---|
| POST | `/register` | Регистрация организации и первого пользователя |
| POST | `/login` | Вход, возвращает access + refresh токены |
| POST | `/refresh` | Обновить access токен по refresh токену |
| POST | `/logout` | Инвалидировать refresh токен |
| GET | `/me` | Текущий пользователь |

### Кандидаты — `/api/v1/candidates`
| Метод | Путь | Описание |
|---|---|---|
| GET | `` | Список кандидатов с фильтрами и пагинацией |
| POST | `` | Создать кандидата |
| GET | `/{id}` | Получить кандидата |
| PATCH | `/{id}` | Обновить кандидата |
| DELETE | `/{id}` | Удалить кандидата (soft delete) |
| GET | `/{id}/history` | История изменений кандидата |

### Чаты — `/api/v1/chat`
| Метод | Путь | Описание |
|---|---|---|
| GET | `/{candidate_id}/messages` | История сообщений |
| POST | `/{candidate_id}/messages` | Отправить сообщение |
| POST | `/{candidate_id}/read` | Отметить чат как прочитанный |

### Задачи — `/api/v1/tasks`
| Метод | Путь | Описание |
|---|---|---|
| GET | `` | Список задач |
| POST | `` | Создать задачу |
| PATCH | `/{id}` | Обновить задачу |
| DELETE | `/{id}` | Удалить задачу |

### Настройки — `/api/v1/settings`
| Метод | Путь | Описание |
|---|---|---|
| GET | `/pipeline` | Этапы воронки |
| POST | `/pipeline` | Создать этап |
| PUT | `/pipeline/{id}` | Обновить этап |
| DELETE | `/pipeline/{id}` | Удалить этап |
| GET | `/tags` | Теги |
| POST | `/tags` | Создать тег |

### Avito аккаунты — `/api/v1/avito-accounts`
| Метод | Путь | Описание |
|---|---|---|
| GET | `` | Список аккаунтов |
| POST | `` | Подключить аккаунт |
| DELETE | `/{id}` | Отключить аккаунт |
| POST | `/{id}/refresh-token` | Обновить токен аккаунта |

### Рассылки — `/api/v1/mailings`
| Метод | Путь | Описание |
|---|---|---|
| GET | `` | Список рассылок |
| POST | `/by-ids` | Создать рассылку по ID кандидатов |
| POST | `/by-filters` | Создать рассылку по фильтрам |
| GET | `/{id}` | Статус рассылки |
| GET | `/{id}/recipients` | Список получателей |
| POST | `/{id}/pause` | Приостановить рассылку |
| POST | `/{id}/resume` | Возобновить рассылку |
| POST | `/{id}/cancel` | Отменить рассылку |

### Вебхуки — `/api/v1/webhooks`
| Метод | Путь | Описание |
|---|---|---|
| POST | `/avito/{token}` | Входящий вебхук от Avito |
| GET | `` | Список webhook endpoints |

### Сообщения — `/api/v1/messaging`
| Метод | Путь | Описание |
|---|---|---|
| GET | `/fast-answers` | Быстрые ответы |
| POST | `/fast-answers` | Создать быстрый ответ |
| GET | `/default-messages` | Шаблоны сообщений |
| POST | `/auto-response-rules` | Создать правило автоответа |

### WebSocket — `/api/v1/ws`
| Метод | Путь | Описание |
|---|---|---|
| WS | `/ws` | Real-time уведомления организации |

### Аналитика — `/api/v1/analytics`
| Метод | Путь | Описание |
|---|---|---|
| GET | `/funnel` | Воронка по этапам |
| GET | `/candidates-by-period` | Динамика кандидатов |
| GET | `/messages-by-period` | Динамика сообщений |

### Вакансии — `/api/v1/vacancies`
| Метод | Путь | Описание |
|---|---|---|
| GET | `` | Список вакансий |
| POST | `` | Синхронизировать вакансии из Avito |
| GET | `/{id}` | Вакансия |

### Самозанятые — `/api/v1/self-employed`
| Метод | Путь | Описание |
|---|---|---|
| POST | `/check` | Проверить ИНН |
| POST | `/check-bulk` | Массовая проверка ИНН (асинхронно через ARQ) |
| GET | `/history` | История проверок |

### Пользователи — `/api/v1/users`
| Метод | Путь | Описание |
|---|---|---|
| GET | `` | Список пользователей организации |
| POST | `` | Создать пользователя |
| PATCH | `/{id}` | Обновить пользователя |
| DELETE | `/{id}` | Деактивировать пользователя |
| GET | `/{id}/permissions` | Права пользователя |
| PUT | `/{id}/permissions` | Обновить права |

### Суперадмин — `/api/v1/superadmin`
| Метод | Путь | Описание |
|---|---|---|
| GET | `/organizations` | Список всех организаций |
| POST | `/organizations/{id}/suspend` | Заблокировать организацию |
| POST | `/organizations/{id}/activate` | Активировать организацию |
| PUT | `/organizations/{id}/subscription` | Установить срок подписки |

### Система
| Метод | Путь | Описание |
|---|---|---|
| GET | `/health` | Healthcheck |
| GET | `/api/docs` | Swagger UI |
| GET | `/api/redoc` | ReDoc |
| GET | `/api/openapi.json` | OpenAPI schema |

---

## ARQ Workers

### Функции (запускаются через enqueue_job)
| Функция | Модуль | Описание |
|---|---|---|
| `flush_write_behind_task` | write_behind | Сбросить write-behind кеш в БД |
| `check_self_employed_inn` | tasks | Проверить один ИНН через API налоговой |
| `run_mailing` | mailing_worker | Выполнить рассылку |
| `handle_new_response` | webhook_worker | Обработать новый отклик с Avito |
| `handle_new_message` | webhook_worker | Обработать новое сообщение |
| `handle_message_read` | webhook_worker | Обработать прочтение сообщения |
| `handle_chat_blocked` | webhook_worker | Обработать блокировку чата |
| `flush_webhook_last_received` | scheduler | Batch UPDATE last_received_at |

### Cron задачи
| Задача | Расписание | Описание |
|---|---|---|
| `flush_write_behind_task` | каждые 5 сек | Сброс write-behind кеша |
| `check_scheduled_mailings` | каждые 30 сек | Запуск запланированных рассылок |
| `check_subscription_expiry` | каждые 10 мин | Пометить истёкшие подписки |
| `create_monthly_partitions` | ежедневно 01:00 | Создать партиции таблиц |
| `flush_webhook_last_received` | каждые 60 сек | Обновить last_received_at webhook |

---

## База данных

### Партиционированные таблицы
- `chat_messages` — по `created_at` (RANGE, по месяцам)
- `audit_log` — по `created_at` (RANGE, по месяцам)
- `error_log` — по `created_at` (RANGE, по месяцам)

Партиции создаются: при старте приложения (`lifespan`) и ежедневно (`create_monthly_partitions`).

### RLS (Row Level Security)
Все таблицы защищены политиками RLS. Фильтрация по `org_id`.
Обход через `SET LOCAL app.is_superadmin = 'true'` в workers и служебных операциях.

### Миграции
```bash
alembic upgrade head        # Применить все миграции
alembic downgrade -1        # Откатить последнюю
alembic revision --autogenerate -m "описание"  # Создать новую
```

---

## Исправленные баги

1. **`app/workers/scheduler.py`** — неверное имя колонки в raw SQL:
   `subscription_expires_at` исправлено на `subscription_until` (соответствует модели Organization).

2. **`app/services/self_employed.py`** — неверный импорт ARQ:
   `from arq import ArqRedis` исправлено на `from arq.connections import ArqRedis`.
