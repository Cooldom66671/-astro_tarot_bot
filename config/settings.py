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
from typing import Literal, Optional, Union
from functools import lru_cache

from pydantic import Field, SecretStr, field_validator, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Определяем базовые пути проекта
BASE_DIR = Path(__file__).resolve().parent.parent
LOGS_DIR = BASE_DIR / "logs"
STATIC_DIR = BASE_DIR / "static"
UPLOADS_DIR = BASE_DIR / "uploads"
BACKUPS_DIR = BASE_DIR / "backups"

# Создаем директории, если их нет
for directory in [LOGS_DIR, STATIC_DIR, UPLOADS_DIR, BACKUPS_DIR]:
    directory.mkdir(exist_ok=True)

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
    username: str = Field(
        default_factory=lambda: os.getenv("BOT_USERNAME", "AstroTarotBot"),
        description="Username бота без @"
    )
    webhook_url: Optional[str] = Field(
        default=None,
        description="URL для вебхуков (если используется webhook режим)"
    )
    webhook_path: str = Field(
        default="/webhook",
        description="Путь для webhook эндпоинта"
    )
    webhook_secret: Optional[SecretStr] = Field(
        default=None,
        description="Секрет для проверки webhook запросов"
    )
    use_webhook: bool = Field(
        default=False,
        description="Использовать webhook вместо polling"
    )

    # ID администраторов бота
    admin_ids: list[int] = Field(
        default_factory=lambda: [
            int(x.strip())
            for x in os.getenv("ADMIN_IDS", os.getenv("BOT_ADMIN_IDS", "")).split(",")
            if x.strip() and x.strip().isdigit()
        ],
        description="ID администраторов бота"
    )

    # ID главного разработчика
    developer_id: Optional[int] = Field(
        default_factory=lambda: int(os.getenv("DEVELOPER_ID", "0")) if os.getenv("DEVELOPER_ID", "").isdigit() else None,
        description="ID главного разработчика"
    )

    # Версия бота
    version: str = Field(
        default="1.0.0",
        description="Версия бота"
    )

    # Токен провайдера платежей для Telegram Payments
    provider_token: Optional[SecretStr] = Field(
        default_factory=lambda: SecretStr(os.getenv("TELEGRAM_PAYMENT_TOKEN", os.getenv("TELEGRAM_PAYMENTS_TOKEN", ""))),
        description="Токен платежного провайдера Telegram"
    )

    model_config = SettingsConfigDict(
        env_prefix="TELEGRAM_BOT_",
        # Исправлено: правильное название параметра
        protected_namespaces=('model_',),
        extra="ignore"
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
            # В development можем работать без токена для тестов
            if os.getenv("ENVIRONMENT", "development") == "development":
                logger.warning("Токен бота не установлен - работаем в режиме разработки")
                return SecretStr("dummy:token")
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
    pool_timeout: int = Field(
        default=30,
        description="Таймаут получения соединения из пула"
    )
    pool_recycle: int = Field(
        default=3600,
        description="Время жизни соединения в секундах"
    )

    @field_validator('url')
    @classmethod
    def validate_postgres_url(cls, v: str) -> str:
        """Проверяем и корректируем URL для PostgreSQL."""
        if not v:
            return "postgresql://postgres:postgres@localhost:5432/astrotarot_db"

        # Заменяем postgres:// на postgresql:// для совместимости
        if v.startswith('postgres://'):
            v = v.replace('postgres://', 'postgresql://', 1)

        # Поддерживаем оба варианта - синхронный и асинхронный драйвер
        if not v.startswith(('postgresql://', 'postgresql+asyncpg://')):
            raise ValueError('База данных должна быть PostgreSQL')

        return v

    @computed_field
    @property
    def async_url(self) -> str:
        """Возвращает URL для асинхронного драйвера."""
        url = self.url
        if url.startswith('postgresql://'):
            return url.replace('postgresql://', 'postgresql+asyncpg://', 1)
        return url

    model_config = SettingsConfigDict(
        env_prefix="DATABASE_",
        extra="ignore"
    )


class RedisSettings(BaseSettings):
    """Настройки Redis для кэширования и FSM."""

    url: str = Field(
        default_factory=lambda: os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        description="URL подключения к Redis"
    )
    host: str = Field(
        default="localhost",
        description="Хост Redis"
    )
    port: int = Field(
        default=6379,
        description="Порт Redis"
    )
    db: int = Field(
        default=0,
        description="Номер базы данных Redis"
    )
    password: Optional[SecretStr] = Field(
        default=None,
        description="Пароль Redis"
    )
    decode_responses: bool = Field(
        default=True,
        description="Декодировать ответы в строки"
    )

    # TTL настройки
    fsm_ttl: int = Field(
        default=86400,  # 24 часа
        description="Время жизни FSM состояний в секундах"
    )
    cache_ttl: int = Field(
        default=3600,  # 1 час
        description="Время жизни кэша в секундах"
    )
    cache_prefix: str = Field(
        default="astrotarot:",
        description="Префикс для ключей кэша"
    )

    @field_validator('url')
    @classmethod
    def validate_redis_url(cls, v: str) -> str:
        """Проверяем URL Redis."""
        if not v.startswith('redis://'):
            raise ValueError('URL должен начинаться с redis://')
        return v

    model_config = SettingsConfigDict(
        env_prefix="REDIS_",
        extra="ignore"
    )


class LLMSettings(BaseSettings):
    """Настройки для языковых моделей."""

    # OpenAI
    openai_api_key: Optional[SecretStr] = Field(
        default_factory=lambda: SecretStr(os.getenv("OPENAI_API_KEY", "")),
        description="API ключ OpenAI"
    )
    openai_model: str = Field(
        default="gpt-4-turbo-preview",
        description="Модель OpenAI для использования"
    )

    # Anthropic
    anthropic_api_key: Optional[SecretStr] = Field(
        default_factory=lambda: SecretStr(os.getenv("ANTHROPIC_API_KEY", "")),
        description="API ключ Anthropic"
    )
    anthropic_model: str = Field(
        default="claude-3-opus-20240229",
        description="Модель Anthropic для использования"
    )

    # Общие настройки
    temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="Температура генерации"
    )
    max_tokens: int = Field(
        default=2000,
        ge=1,
        le=8000,
        description="Максимальное количество токенов"
    )
    request_timeout: int = Field(
        default=30,
        description="Таймаут запросов к LLM в секундах"
    )

    # Выбор провайдера
    provider: Literal["openai", "anthropic", "both"] = Field(
        default="openai",
        description="Какой LLM провайдер использовать"
    )

    model_config = SettingsConfigDict(
        env_prefix="LLM_",
        protected_namespaces=('model_',),
        extra="ignore"
    )


class PaymentSettings(BaseSettings):
    """Настройки платежных систем."""

    # YooKassa
    yookassa_shop_id: Optional[str] = Field(
        default_factory=lambda: os.getenv("YOOKASSA_SHOP_ID"),
        description="ID магазина в ЮKassa"
    )
    yookassa_secret_key: Optional[SecretStr] = Field(
        default_factory=lambda: SecretStr(os.getenv("YOOKASSA_SECRET_KEY", "")),
        description="Секретный ключ ЮKassa"
    )

    # CryptoBot
    cryptobot_token: Optional[SecretStr] = Field(
        default_factory=lambda: SecretStr(os.getenv("CRYPTO_BOT_TOKEN", "")),
        description="Токен CryptoBot"
    )

    # Общие настройки
    test_mode: bool = Field(
        default=True,
        description="Тестовый режим платежей"
    )
    webhook_url: Optional[str] = Field(
        default=None,
        description="URL для webhook уведомлений о платежах"
    )
    currency: str = Field(
        default="RUB",
        description="Валюта по умолчанию"
    )

    model_config = SettingsConfigDict(
        env_prefix="PAYMENT_",
        extra="ignore"
    )

    @property
    def provider_token(self) -> Optional[SecretStr]:
        """Обратная совместимость для provider_token."""
        # Импортируем здесь чтобы избежать циклических импортов
        try:
            from config import settings
            return settings.bot.provider_token
        except ImportError:
            return None


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
    jwt_secret: SecretStr = Field(
        default_factory=lambda: SecretStr(os.getenv("JWT_SECRET", os.urandom(32).hex())),
        description="Секрет для JWT токенов"
    )
    allowed_hosts: list[str] = Field(
        default=["*"],
        description="Разрешенные хосты"
    )
    cors_origins: list[str] = Field(
        default=["http://localhost:3000"],
        description="Разрешенные CORS origins"
    )

    model_config = SettingsConfigDict(
        env_prefix="SECURITY_",
        extra="ignore"
    )


class FeaturesSettings(BaseSettings):
    """Настройки функциональности."""

    enable_analytics: bool = Field(
        default=True,
        description="Включить аналитику"
    )
    enable_backups: bool = Field(
        default=True,
        description="Включить автоматические бэкапы"
    )
    enable_notifications: bool = Field(
        default=True,
        description="Включить уведомления"
    )
    enable_premium_features: bool = Field(
        default=True,
        description="Включить премиум функции"
    )
    enable_debug_mode: bool = Field(
        default=False,
        description="Включить режим отладки"
    )

    # Feature flags
    ai_interpretations: bool = Field(
        default=True,
        description="AI интерпретации раскладов"
    )
    voice_messages: bool = Field(
        default=False,
        description="Поддержка голосовых сообщений"
    )
    group_readings: bool = Field(
        default=False,
        description="Групповые расклады"
    )
    premium_trials: bool = Field(
        default=True,
        description="Пробный период премиума"
    )

    model_config = SettingsConfigDict(
        env_prefix="FEATURE_",
        extra="ignore"
    )


class LimitsSettings(BaseSettings):
    """Настройки лимитов."""

    max_daily_tarot_free: int = Field(
        default=3,
        description="Максимум раскладов Таро в день (бесплатно)"
    )
    max_daily_horoscope_free: int = Field(
        default=1,
        description="Максимум гороскопов в день (бесплатно)"
    )
    session_timeout_minutes: int = Field(
        default=30,
        description="Таймаут сессии в минутах"
    )
    rate_limit_messages_per_minute: int = Field(
        default=20,
        description="Лимит сообщений в минуту"
    )
    max_file_size_mb: int = Field(
        default=10,
        description="Максимальный размер файла в МБ"
    )

    model_config = SettingsConfigDict(
        env_prefix="",
        extra="ignore"
    )


class Settings(BaseSettings):
    """Главный класс настроек приложения."""

    # Окружение
    environment: Literal["development", "staging", "production", "testing"] = Field(
        default_factory=lambda: os.getenv("ENVIRONMENT", "development"),
        description="Окружение запуска"
    )
    debug: bool = Field(
        default_factory=lambda: os.getenv("DEBUG", "true").lower() in ("true", "1", "yes"),
        description="Режим отладки"
    )

    # Логирование
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"),
        description="Уровень логирования"
    )
    log_file: Optional[Path] = Field(
        default_factory=lambda: Path(os.getenv("LOG_FILE_PATH", str(LOGS_DIR / "bot.log"))),
        description="Путь к файлу логов"
    )

    # Таймзона
    timezone: str = Field(
        default_factory=lambda: os.getenv("DEFAULT_TIMEZONE", "Europe/Moscow"),
        description="Часовой пояс по умолчанию"
    )

    # Вложенные настройки
    bot: BotSettings = Field(default_factory=BotSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    payment: PaymentSettings = Field(default_factory=PaymentSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    features: FeaturesSettings = Field(default_factory=FeaturesSettings)
    limits: LimitsSettings = Field(default_factory=LimitsSettings)

    # Пути проекта
    base_dir: Path = Field(default=BASE_DIR, frozen=True)
    logs_dir: Path = Field(default=LOGS_DIR, frozen=True)
    static_dir: Path = Field(default=STATIC_DIR, frozen=True)
    uploads_dir: Path = Field(default=UPLOADS_DIR, frozen=True)
    backups_dir: Path = Field(default=BACKUPS_DIR, frozen=True)

    # Sentry
    sentry_dsn: Optional[str] = Field(
        default_factory=lambda: os.getenv("SENTRY_DSN"),
        description="DSN для Sentry"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        env_nested_delimiter="__",
        extra="ignore"
    )

    def __init__(self, **kwargs):
        """Инициализация настроек с логированием."""
        super().__init__(**kwargs)

        # Логируем загруженные настройки
        logger.info(f"Настройки загружены для окружения: {self.environment}")
        logger.info(f"Debug режим: {self.debug}")
        logger.info(f"Уровень логирования: {self.log_level}")

        if self.bot.admin_ids:
            logger.info(f"Загружено {len(self.bot.admin_ids)} администраторов")

        if self.bot.developer_id:
            logger.info(f"ID разработчика: {self.bot.developer_id}")

        # Проверяем критичные настройки для production
        if self.environment == "production":
            self._validate_production_settings()

    def _validate_production_settings(self) -> None:
        """Дополнительная валидация для production окружения."""
        errors = []
        warnings = []

        # Проверяем debug режим
        if self.debug:
            errors.append("Debug режим должен быть выключен в production")

        # Проверяем платежи
        if self.payment.test_mode:
            warnings.append("Платежи работают в тестовом режиме!")

        # Проверяем webhook
        if self.bot.use_webhook and not self.bot.webhook_url:
            errors.append("Webhook URL обязателен при use_webhook=True")

        # Проверяем SQL логирование
        if self.database.echo:
            warnings.append("SQL логирование включено в production!")

        # Проверяем админов
        if not self.bot.admin_ids:
            warnings.append("Не указаны администраторы бота!")

        # Проверяем ключи безопасности
        if len(self.security.secret_key.get_secret_value()) < 32:
            errors.append("Secret key слишком короткий для production")

        # Выводим предупреждения
        for warning in warnings:
            logger.warning(f"Production warning: {warning}")

        # Если есть ошибки, останавливаем запуск
        if errors:
            for error in errors:
                logger.error(f"Production error: {error}")
            raise ValueError(f"Production validation failed: {'; '.join(errors)}")

    @property
    def is_production(self) -> bool:
        """Проверка, что работаем в production."""
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        """Проверка, что работаем в development."""
        return self.environment == "development"

    @property
    def is_testing(self) -> bool:
        """Проверка, что работаем в testing."""
        return self.environment == "testing"


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