"""
Скрипт проверки импортов всех модулей проекта.
Запуск: python scripts/check_imports.py
Выходной код: 0 — всё ОК, 1 — есть ошибки.
"""

import importlib
import sys
import os
import traceback

# Добавить корень проекта в sys.path
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Устанавливаем минимальные env-переменные, чтобы Settings не упал
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("SECRET_KEY", "test_secret_key_at_least_32_chars_long_x")
os.environ.setdefault("ENCRYPTION_KEY", "0" * 64)
os.environ.setdefault("SEARCH_HASH_KEY", "test_search_hash_key")
os.environ.setdefault("SUPERADMIN_EMAIL", "admin@test.local")
os.environ.setdefault("SUPERADMIN_PASSWORD", "testpassword")

MODULES = [
    # Core
    "app.config",
    "app.database",
    "app.redis",
    "app.dependencies",
    # Security
    "app.security.passwords",
    "app.security.tokens",
    "app.security.encryption",
    # Models
    "app.models",
    "app.models.auth",
    "app.models.crm",
    "app.models.chat",
    "app.models.mailing",
    "app.models.task",
    "app.models.vacancy",
    "app.models.messaging",
    "app.models.self_employed",
    "app.models.audit",
    "app.models.error_log",
    # Schemas
    "app.schemas.auth",
    "app.schemas.candidate",
    "app.schemas.chat",
    "app.schemas.mailing",
    "app.schemas.task",
    "app.schemas.vacancy",
    "app.schemas.self_employed",
    "app.schemas.analytics",
    "app.schemas.messaging",
    # Repositories
    "app.repositories.candidate",
    "app.repositories.mailing",
    "app.repositories.self_employed",
    "app.repositories.avito_account",
    # Services
    "app.services.audit",
    "app.services.cache",
    "app.services.avito_client",
    "app.services.mailing",
    "app.services.self_employed",
    "app.services.email.smtp",
    # Middleware
    "app.middleware.tenant",
    "app.middleware.org_access",
    "app.middleware.request_id",
    # Routers
    "app.routers.auth",
    "app.routers.candidates",
    "app.routers.chat",
    "app.routers.tasks",
    "app.routers.settings",
    "app.routers.avito_accounts",
    "app.routers.mailings",
    "app.routers.webhooks",
    "app.routers.messaging",
    "app.routers.ws",
    "app.routers.analytics",
    "app.routers.vacancies",
    "app.routers.self_employed",
    "app.routers.users",
    "app.routers.superadmin",
    # Workers
    "app.workers.write_behind",
    "app.workers.scheduler",
    "app.workers.mailing_worker",
    "app.workers.webhook_worker",
    "app.workers.tasks",
    "app.workers.settings",
    # Main app
    "app.main",
]


def check_imports() -> int:
    ok = 0
    failed = 0
    errors: list[tuple[str, str]] = []

    print(f"Checking {len(MODULES)} modules...\n")

    for module_name in MODULES:
        try:
            importlib.import_module(module_name)
            print(f"  OK  {module_name}")
            ok += 1
        except Exception as exc:
            tb = traceback.format_exc()
            print(f"  FAIL  {module_name}")
            print(f"        {type(exc).__name__}: {exc}")
            errors.append((module_name, tb))
            failed += 1

    print(f"\n{'='*60}")
    print(f"Results: {ok} OK, {failed} FAILED")

    if errors:
        print(f"\nFailed modules:")
        for module_name, tb in errors:
            print(f"\n--- {module_name} ---")
            print(tb)
        return 1

    print("\nAll imports successful.")
    return 0


if __name__ == "__main__":
    sys.exit(check_imports())
