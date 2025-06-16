"""
Модуль настроек приложения Астро-Таро Бот.

Этот модуль отвечает за:
- Загрузку и валидацию переменных окружения
- Централизованное хранение всех настроек приложения
- Type-safe конфигурацию через Pydantic
- Автоматическую проверку обязательных параметров при старте

Использование:
    from config.settings import settings

    bot_token = settings.bot.token
    db_url = settings.database.url
"""

import logging
from pathlib import Path
from typing import Literal, Optional
from functools import lru_cache

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Определяем базовые пути проекта
BASE_DIR = Path(__file__).resolve().parent.parent
LOGS_DIR = BASE_DIR / "logs"
STATIC_DIR = BASE_DIR / "static"

# Создаем директории, если их нет
LOGS_DIR.mkdir(exist_ok=True)
STATIC_DIR.mkdir(exist_ok=True)

logger = logging.getLogger(__name__)


class BotSettings(BaseSettings):
    """Настройки Telegram бота."""

    token: SecretStr = Field(
        ...,
        description="Токен Telegram бота от @BotFather"
    )
    name: str = Field(
        default="AstroTarotBot",
        description="Имя бота для логирования"
    )
    webhook_url: Optional[str] = Field(
        default=None,
        description="URL для вебхуков (если используется webhook режим)"
    )
    use_webhook: bool = Field(
        default=False,
        description="Использовать webhook вместо polling"
    )

    model_config = SettingsConfigDict(
        env_prefix="TELEGRAM_BOT_"
    )


class DatabaseSettings(BaseSettings):
    """Настройки базы данных PostgreSQL."""

    url: str = Field(
        ...,
        description="URL подключения к PostgreSQL"
    )
    echo: bool = Field(
        default=False,
        description="Логировать SQL запросы"
    )
    pool_size: int = Field(
        default=10,
        description="Размер пула соединений"
    )
    max_overflow: int = Field(
        default=20,
        description="Максимальное превышение пула"
    )

    @field_validator('url')
    @classmethod
    def validate_postgres_url(cls, v: str) -> str:
        """Проверяем, что URL для PostgreSQL."""
        if not v.startswith(('postgresql://', 'postgresql+asyncpg://')):
            raise ValueError('База данных должна быть PostgreSQL')
        return v

    model_config = SettingsConfigDict(
        env_prefix="DATABASE_"
    )


class RedisSettings(BaseSettings):
    """Настройки Redis для кэширования и FSM."""

    url: str = Field(
        default="redis://localhost:6379/0",
        description="URL подключения к Redis"
    )
    ttl: int = Field(
        default=3600,
        description="Время жизни кэша в секундах (по умолчанию 1 час)"
    )
    fsm_ttl: int = Field(
        default=86400,
        description="Время жизни состояний FSM (по умолчанию 24 часа)"
    )

    model_config = SettingsConfigDict(
        env_prefix="REDIS_"
    )


class LLMSettings(BaseSettings):
    """Настройки для работы с языковыми моделями."""

    openai_api_key: Optional[SecretStr] = Field(
        default=None,
        description="API ключ OpenAI"
    )
    anthropic_api_key: Optional[SecretStr] = Field(
        default=None,
        description="API ключ Anthropic Claude"
    )
    default_provider: Literal["openai", "anthropic"] = Field(
        default="openai",
        description="Провайдер по умолчанию"
    )
    model_name: str = Field(
        default="gpt-4o-mini",
        description="Модель по умолчанию"
    )
    max_tokens: int = Field(
        default=2000,
        description="Максимальное количество токенов в ответе"
    )
    temperature: float = Field(
        default=0.7,
        description="Температура генерации (0.0 - 1.0)"
    )
    cache_responses: bool = Field(
        default=True,
        description="Кэшировать ответы LLM"
    )

    @field_validator('temperature')
    @classmethod
    def validate_temperature(cls, v: float) -> float:
        """Проверяем диапазон температуры."""
        if not 0.0 <= v <= 1.0:
            raise ValueError('Температура должна быть от 0.0 до 1.0')
        return v

    model_config = SettingsConfigDict(
        env_prefix="LLM_"
    )


class PaymentSettings(BaseSettings):
    """Настройки платежной системы YooKassa."""

    shop_id: Optional[str] = Field(
        default=None,
        description="ID магазина в YooKassa"
    )
    secret_key: Optional[SecretStr] = Field(
        default=None,
        description="Секретный ключ YooKassa"
    )
    return_url: Optional[str] = Field(
        default=None,
        description="URL для возврата после оплаты"
    )
    webhook_url: Optional[str] = Field(
        default=None,
        description="URL для вебхуков от YooKassa"
    )
    test_mode: bool = Field(
        default=True,
        description="Тестовый режим платежей"
    )

    model_config = SettingsConfigDict(
        env_prefix="YOOKASSA_"
    )


class SecuritySettings(BaseSettings):
    """Настройки безопасности."""

    secret_key: SecretStr = Field(
        ...,
        description="Секретный ключ для JWT и прочего"
    )
    encryption_key: SecretStr = Field(
        ...,
        description="Ключ для шифрования персональных данных"
    )
    jwt_algorithm: str = Field(
        default="HS256",
        description="Алгоритм JWT"
    )
    jwt_expire_minutes: int = Field(
        default=30,
        description="Время жизни JWT токена в минутах"
    )
    rate_limit_per_minute: int = Field(
        default=20,
        description="Лимит запросов на пользователя в минуту"
    )

    model_config = SettingsConfigDict(
        env_prefix="SECURITY_"
    )


class CelerySettings(BaseSettings):
    """Настройки Celery для фоновых задач."""

    broker_url: str = Field(
        default="redis://localhost:6379/0",
        description="URL брокера сообщений"
    )
    result_backend: str = Field(
        default="redis://localhost:6379/1",
        description="URL для хранения результатов"
    )
    task_serializer: str = Field(
        default="json",
        description="Формат сериализации задач"
    )
    result_serializer: str = Field(
        default="json",
        description="Формат сериализации результатов"
    )
    timezone: str = Field(
        default="UTC",
        description="Часовой пояс для планировщика"
    )

    model_config = SettingsConfigDict(
        env_prefix="CELERY_"
    )


class APISettings(BaseSettings):
    """Настройки REST API для админ-панели."""

    host: str = Field(
        default="0.0.0.0",
        description="Хост для API сервера"
    )
    port: int = Field(
        default=8000,
        description="Порт для API сервера"
    )
    cors_origins: list[str] = Field(
        default=["http://localhost:3000"],
        description="Разрешенные CORS origins"
    )
    docs_enabled: bool = Field(
        default=True,
        description="Включить Swagger документацию"
    )

    model_config = SettingsConfigDict(
        env_prefix="API_"
    )


class Settings(BaseSettings):
    """Главный класс настроек приложения."""

    # Окружение
    environment: Literal["development", "production", "testing"] = Field(
        default="development",
        description="Окружение запуска"
    )
    debug: bool = Field(
        default=True,
        description="Режим отладки"
    )

    # Логирование
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="Уровень логирования"
    )
    log_file: Path = Field(
        default=LOGS_DIR / "bot.log",
        description="Путь к файлу логов"
    )

    # Вложенные настройки
    bot: BotSettings = Field(default_factory=BotSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    payment: PaymentSettings = Field(default_factory=PaymentSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    celery: CelerySettings = Field(default_factory=CelerySettings)
    api: APISettings = Field(default_factory=APISettings)

    # Пути проекта
    base_dir: Path = Field(default=BASE_DIR)
    logs_dir: Path = Field(default=LOGS_DIR)
    static_dir: Path = Field(default=STATIC_DIR)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        # Позволяет использовать как префиксы, так и без них
        env_nested_delimiter="__"
    )

    def __init__(self, **kwargs):
        """Инициализация настроек с логированием."""
        super().__init__(**kwargs)
        logger.info(f"Настройки загружены для окружения: {self.environment}")

        # Проверяем критичные настройки для production
        if self.environment == "production":
            self._validate_production_settings()

    def _validate_production_settings(self) -> None:
        """Дополнительная валидация для production окружения."""
        if self.debug:
            raise ValueError("Debug режим должен быть выключен в production")

        if self.payment.test_mode:
            logger.warning("Платежи работают в тестовом режиме!")

        if not self.bot.webhook_url and self.bot.use_webhook:
            raise ValueError("Webhook URL обязателен при use_webhook=True")

        if self.database.echo:
            logger.warning("SQL логирование включено в production!")


@lru_cache()
def get_settings() -> Settings:
    """
    Получить экземпляр настроек (Singleton pattern).

    Returns:
        Settings: Объект с настройками приложения
    """
    return Settings()


# Создаем глобальный экземпляр настроек
settings = get_settings()

# Экспортируем для удобства
__all__ = ["settings", "get_settings", "Settings"]