"""
Конфигурация приложения через Pydantic Settings v2.
Все значения читаются из переменных окружения или .env файла.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ------------------------------------------------------------------
    # Приложение
    # ------------------------------------------------------------------
    APP_NAME: str = "AvitoСRM"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    LOG_LEVEL: str = "info"

    # ------------------------------------------------------------------
    # База данных
    # ------------------------------------------------------------------
    DATABASE_URL: str  # postgresql+asyncpg://user:password@host:port/db
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 80  # итого 100 соединений

    # ------------------------------------------------------------------
    # Redis
    # ------------------------------------------------------------------
    REDIS_URL: str  # redis://:password@host:6379/0
    REDIS_POOL_SIZE: int = 20

    # ------------------------------------------------------------------
    # Безопасность
    # ------------------------------------------------------------------
    SECRET_KEY: str          # для подписи JWT
    ENCRYPTION_KEY: str      # 64 hex-символа → 32 байта для AES-256-GCM
    SEARCH_HASH_KEY: str     # для HMAC-SHA256 хеша телефона при поиске

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # ------------------------------------------------------------------
    # SMTP
    # ------------------------------------------------------------------
    SMTP_HOST: str | None = None
    SMTP_PORT: int = 587
    SMTP_USER: str | None = None
    SMTP_PASSWORD: str | None = None
    SMTP_FROM_NAME: str = "AvitoСRM"
    SMTP_TLS: bool = True
    SMTP_SSL: bool = False

    # ------------------------------------------------------------------
    # SuperAdmin — создаётся при первом запуске
    # ------------------------------------------------------------------
    SUPERADMIN_EMAIL: str
    SUPERADMIN_PASSWORD: str

    # ------------------------------------------------------------------
    # ARQ — очередь фоновых задач
    # ------------------------------------------------------------------
    ARQ_REDIS_URL: str | None = None  # если None — используется REDIS_URL

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def encryption_key_bytes(self) -> bytes:
        """Возвращает ключ шифрования как 32 байта."""
        return bytes.fromhex(self.ENCRYPTION_KEY)

    @property
    def search_hash_key_bytes(self) -> bytes:
        """Возвращает ключ поиска как байты."""
        return self.SEARCH_HASH_KEY.encode()

    @property
    def arq_redis_url(self) -> str:
        """URL Redis для ARQ (fallback на основной REDIS_URL)."""
        return self.ARQ_REDIS_URL or self.REDIS_URL

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT == "development"


from functools import lru_cache


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Фабрика настроек — используется в Depends.
    Результат кешируется: Settings создаётся один раз за время жизни процесса.
    """
    return Settings()  # type: ignore[call-arg]
