"""
Модуль настроек приложения Астро-Таро Бот.

Этот модуль отвечает за:
- Загрузку и валидацию переменных окружения
- Централизованное хранение всех настроек приложения
- Type-safe конфигурацию через Pydantic
- Автоматическую проверку обязательных параметров при старте
"""

import logging
import os
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

    # Делаем token опциональным с fallback на BOT_TOKEN
    token: SecretStr = Field(
        default_factory=lambda: SecretStr(os.getenv("TELEGRAM_BOT_TOKEN", os.getenv("BOT_TOKEN", ""))),
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

    # ДОБАВЛЕНО: ID администраторов бота
    admin_ids: list[int] = Field(
        default_factory=lambda: [
            int(x.strip())
            for x in os.getenv("BOT_ADMIN_IDS", "").split(",")
            if x.strip() and x.strip().isdigit()
        ],
        description="ID администраторов бота"
    )

    # ДОБАВЛЕНО: Версия бота
    version: str = Field(
        default="1.0.0",
        description="Версия бота"
    )

    # ДОБАВЛЕНО: Токен провайдера платежей для Telegram Payments
    provider_token: Optional[SecretStr] = Field(
        default_factory=lambda: SecretStr(os.getenv("TELEGRAM_PAYMENT_TOKEN", "")),
        description="Токен платежного провайдера Telegram"
    )

    model_config = SettingsConfigDict(
        env_prefix="TELEGRAM_BOT_",
        protected_namespaces=('settings_',),  # Исправляем warning с model_
        extra="ignore"  # Игнорируем лишние поля
    )

    @field_validator('token')
    @classmethod
    def validate_token(cls, v: SecretStr) -> SecretStr:
        """Проверяем, что токен не пустой."""
        if not v or not v.get_secret_value():
            # Пробуем альтернативные имена переменных
            alt_token = os.getenv("BOT_TOKEN") or os.getenv("TG_BOT_TOKEN") or ""
            if alt_token:
                return SecretStr(alt_token)
            raise ValueError('Токен бота не найден в переменных окружения')
        return v


class DatabaseSettings(BaseSettings):
    """Настройки базы данных PostgreSQL."""

    url: str = Field(
        default_factory=lambda: os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/astrotarot_db"),
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
        if not v:
            return "postgresql://postgres:postgres@localhost:5432/astrotarot_db"
        # Поддерживаем оба варианта - синхронный и асинхронный драйвер
        if not v.startswith(('postgresql://', 'postgresql+asyncpg://', 'postgres://')):
            raise ValueError('База данных должна быть PostgreSQL')
        # Заменяем postgres:// на postgresql:// для совместимости
        if v.startswith('postgres://'):
            v = v.replace('postgres://', 'postgresql://', 1)
        return v

    model_config = SettingsConfigDict(
        env_prefix="DATABASE_",
        extra="ignore"  # Игнорируем лишние поля
    )


class RedisSettings(BaseSettings):
    """Настройки Redis для кэширования и FSM."""

    url: str = Field(
        default_factory=lambda: os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        description="URL подключения к Redis"
    )
    decode_responses: bool = Field(
        default=True,
        description="Декодировать ответы в строки"
    )

    # ДОБАВЛЕНО: TTL для FSM состояний
    fsm_ttl: int = Field(
        default=86400,  # 24 часа
        description="Время жизни FSM состояний в секундах"
    )

    # ДОБАВЛЕНО: TTL для кэша
    cache_ttl: int = Field(
        default=3600,  # 1 час
        description="Время жизни кэша в секундах"
    )

    model_config = SettingsConfigDict(
        env_prefix="REDIS_",
        extra="ignore"  # Игнорируем лишние поля
    )


class LLMSettings(BaseSettings):
    """Настройки для языковых моделей."""

    # OpenAI
    openai_api_key: Optional[SecretStr] = Field(
        default=None,
        description="API ключ OpenAI"
    )
    openai_model: str = Field(
        default="gpt-4-turbo-preview",
        description="Модель OpenAI для использования"
    )

    # Anthropic
    anthropic_api_key: Optional[SecretStr] = Field(
        default=None,
        description="API ключ Anthropic"
    )
    anthropic_model: str = Field(
        default="claude-3-opus-20240229",
        description="Модель Anthropic для использования"
    )

    # Общие настройки
    temperature: float = Field(
        default=0.7,
        description="Температура генерации"
    )
    max_tokens: int = Field(
        default=2000,
        description="Максимальное количество токенов"
    )

    # ДОБАВЛЕНО: Таймаут для запросов
    request_timeout: int = Field(
        default=30,
        description="Таймаут запросов к LLM в секундах"
    )

    model_config = SettingsConfigDict(
        env_prefix="LLM_",
        protected_namespaces=('settings_',),
        extra="ignore"  # Игнорируем лишние поля
    )


class PaymentSettings(BaseSettings):
    """Настройки платежных систем."""

    # YooKassa
    yookassa_shop_id: Optional[str] = Field(
        default=None,
        description="ID магазина в ЮKassa"
    )
    yookassa_secret_key: Optional[SecretStr] = Field(
        default=None,
        description="Секретный ключ ЮKassa"
    )

    # Telegram Payments - УДАЛЕНО (перенесено в BotSettings)

    # CryptoBot
    cryptobot_token: Optional[SecretStr] = Field(
        default=None,
        description="Токен CryptoBot"
    )

    # Общие настройки
    test_mode: bool = Field(
        default=True,
        description="Тестовый режим платежей"
    )

    # ДОБАВЛЕНО: URL для webhook платежей
    webhook_url: Optional[str] = Field(
        default=None,
        description="URL для webhook уведомлений о платежах"
    )

    model_config = SettingsConfigDict(
        env_prefix="PAYMENT_",
        extra="ignore"  # Игнорируем лишние поля
    )

    @property
    def provider_token(self) -> Optional[SecretStr]:
        """Обратная совместимость для provider_token."""
        # Возвращаем токен из BotSettings для обратной совместимости
        from config import settings
        return settings.bot.provider_token


class SecuritySettings(BaseSettings):
    """Настройки безопасности."""

    secret_key: SecretStr = Field(
        default_factory=lambda: SecretStr(os.getenv("SECRET_KEY", os.urandom(32).hex())),
        description="Секретный ключ приложения"
    )

    encryption_key: SecretStr = Field(
        default_factory=lambda: SecretStr(os.getenv("ENCRYPTION_KEY", os.urandom(32).hex())),
        description="Ключ шифрования данных"
    )

    allowed_hosts: list[str] = Field(
        default=["*"],
        description="Разрешенные хосты"
    )

    model_config = SettingsConfigDict(
        env_prefix="SECURITY_",
        extra="ignore"  # Игнорируем лишние поля
    )


class CelerySettings(BaseSettings):
    """Настройки Celery для фоновых задач."""

    broker_url: str = Field(
        default_factory=lambda: os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/1"),
        description="URL брокера сообщений"
    )

    result_backend: str = Field(
        default_factory=lambda: os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/2"),
        description="URL для хранения результатов"
    )

    task_serializer: str = Field(
        default="json",
        description="Сериализатор задач"
    )

    result_serializer: str = Field(
        default="json",
        description="Сериализатор результатов"
    )

    model_config = SettingsConfigDict(
        env_prefix="CELERY_",
        extra="ignore"  # Игнорируем лишние поля
    )


class APISettings(BaseSettings):
    """Настройки API сервера."""

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
        env_prefix="API_",
        extra="ignore"  # Игнорируем лишние поля
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
        env_nested_delimiter="__",
        extra="ignore"  # ВАЖНО: Игнорируем все лишние поля из .env
    )

    def __init__(self, **kwargs):
        """Инициализация настроек с логированием."""
        super().__init__(**kwargs)
        logger.info(f"Настройки загружены для окружения: {self.environment}")

        # ДОБАВЛЕНО: Логируем количество админов
        if self.bot.admin_ids:
            logger.info(f"Загружено {len(self.bot.admin_ids)} администраторов")

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

        # ДОБАВЛЕНО: Проверка админов
        if not self.bot.admin_ids:
            logger.warning("Не указаны администраторы бота!")


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