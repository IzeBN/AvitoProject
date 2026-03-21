"""
ARQ WorkerSettings — конфигурация фоновых задач.
ARQ использует Redis для очереди задач.
"""

import urllib.parse

from arq import cron
from arq.connections import RedisSettings

from app.config import get_settings


def get_redis_settings() -> RedisSettings:
    """Получить Redis настройки для ARQ из конфигурации приложения."""
    settings = get_settings()
    arq_url = settings.arq_redis_url

    # Парсим URL вида redis://:password@host:port/db
    parsed = urllib.parse.urlparse(arq_url)
    return RedisSettings(
        host=parsed.hostname or "localhost",
        port=parsed.port or 6379,
        password=parsed.password or None,
        database=int(parsed.path.lstrip("/") or "0"),
    )


# Импортируем lifecycle hooks и задачи
from app.workers.write_behind import (  # noqa: E402
    flush_write_behind_task,
    shutdown,
    startup,
)
# Phase 4: проверка самозанятых
from app.workers.tasks import check_self_employed_inn  # noqa: E402

# Phase 3: mailing, webhook, scheduler
from app.workers.mailing_worker import (  # noqa: E402
    check_scheduled_mailings,
    run_mailing,
)
from app.workers.webhook_worker import (  # noqa: E402
    handle_chat_blocked,
    handle_message_read,
    handle_new_message,
    handle_new_response,
)
from app.workers.scheduler import (  # noqa: E402
    check_subscription_expiry,
    create_monthly_partitions,
    flush_webhook_last_received,
)


class WorkerSettings:
    """
    Настройки ARQ воркера.
    """

    redis_settings = get_redis_settings()

    # Lifecycle hooks
    on_startup = startup
    on_shutdown = shutdown

    # Список обычных задач (запускаются по имени через arq.enqueue)
    functions = [
        flush_write_behind_task,
        # Phase 4: самозанятые
        check_self_employed_inn,
        # Рассылки
        run_mailing,
        # Вебхуки
        handle_new_response,
        handle_new_message,
        handle_message_read,
        handle_chat_blocked,
        # Планировщик
        flush_webhook_last_received,
    ]

    # Количество параллельных задач
    max_jobs = 10

    # Таймаут задачи по умолчанию — 30 минут (рассылки могут быть длительными)
    job_timeout = 1800

    # Keepalive для Redis соединения
    keep_result = 3600

    cron_jobs = [
        # Write-behind flush каждые 5 секунд
        cron(
            flush_write_behind_task,
            second={0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55},
            timeout=10,
        ),
        # Запланированные рассылки — каждые 30 секунд
        cron(
            check_scheduled_mailings,
            second={0, 30},
            timeout=30,
        ),
        # Проверка подписок — каждые 10 минут
        cron(
            check_subscription_expiry,
            minute={0, 10, 20, 30, 40, 50},
            timeout=60,
        ),
        # Создание партиций — ежедневно в 01:00
        cron(
            create_monthly_partitions,
            hour={1},
            minute={0},
            second={0},
            timeout=120,
        ),
        # flush webhook last_received_at — каждые 60 секунд
        cron(
            flush_webhook_last_received,
            second={0},
            timeout=30,
        ),
    ]
