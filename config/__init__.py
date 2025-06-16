"""
Пакет конфигурации Астро-Таро Бота.

Этот модуль инициализирует все настройки приложения и предоставляет
удобный интерфейс для импорта конфигурации в других модулях.

При импорте автоматически:
- Загружаются переменные окружения из .env файла
- Настраивается система логирования
- Проверяются критичные настройки
- Создаются необходимые директории

Использование:
    from config import settings, logger

    # Доступ к настройкам
    bot_token = settings.bot.token

    # Логирование
    logger.info("Бот запущен")

    # Константы
    from config import BotCommands, Limits, Emoji
"""

import sys
from pathlib import Path
from typing import TYPE_CHECKING

# Добавляем корневую директорию в Python path для правильных импортов
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Импортируем и настраиваем dotenv для загрузки переменных окружения
try:
    from dotenv import load_dotenv

    # Загружаем .env файл
    env_path = ROOT_DIR / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        print(f"✅ Переменные окружения загружены из {env_path}")
    else:
        print(f"⚠️  Файл {env_path} не найден. Используются системные переменные.")
except ImportError:
    print("⚠️  python-dotenv не установлен. Используются системные переменные окружения.")

# Импортируем настройки
from config.settings import settings, get_settings, Settings

# Настраиваем логирование
from config.logging_config import setup_logging, get_logger, log_event, log_error

# Настраиваем логирование при импорте модуля
setup_logging()

# Получаем logger для этого модуля
logger = get_logger(__name__)

# Логируем успешную инициализацию
logger.info(
    f"Конфигурация инициализирована",
    extra={
        "environment": settings.environment,
        "debug": settings.debug,
        "bot_name": settings.bot.name,
    }
)


# Проверяем критичные настройки
def _check_critical_settings() -> None:
    """Проверяет наличие критичных настроек."""
    warnings = []

    # Проверяем токен бота
    try:
        _ = settings.bot.token.get_secret_value()
    except Exception:
        warnings.append("❌ Токен Telegram бота не установлен!")

    # Проверяем базу данных
    if not settings.database.url:
        warnings.append("❌ URL базы данных не установлен!")

    # Проверяем ключи шифрования в production
    if settings.environment == "production":
        try:
            _ = settings.security.secret_key.get_secret_value()
            _ = settings.security.encryption_key.get_secret_value()
        except Exception:
            warnings.append("❌ Ключи безопасности не установлены для production!")

    # Выводим предупреждения
    if warnings:
        logger.warning(
            "Обнаружены проблемы с конфигурацией:\n" + "\n".join(warnings)
        )


# Проверяем настройки
_check_critical_settings()


# Создаем необходимые директории
def _create_required_directories() -> None:
    """Создает необходимые директории проекта."""
    directories = [
        settings.logs_dir,
        settings.static_dir,
        settings.base_dir / "temp",
        settings.base_dir / "downloads",
    ]

    for directory in directories:
        if not directory.exists():
            directory.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Создана директория: {directory}")


# Создаем директории
_create_required_directories()

# Импортируем все константы для удобного доступа
from config.constants import (
    # Команды
    BotCommands,
    ButtonTexts,
    CallbackPrefixes,

    # Статусы и enum'ы
    SubscriptionStatus,
    SubscriptionPlan,
    ToneOfVoice,
    PaymentStatus,
    TarotSpreadType,
    Planet,
    ZodiacSign,

    # Значения
    Limits,
    Prices,
    Patterns,
    TarotCards,
    Emoji,
    ErrorMessages,
    PromoTexts,
)


# Вспомогательные функции
def get_version() -> str:
    """
    Получить версию приложения.

    Returns:
        str: Версия в формате "major.minor.patch"
    """
    version_file = ROOT_DIR / "VERSION"
    if version_file.exists():
        return version_file.read_text().strip()
    return "0.1.0"  # Версия по умолчанию


def is_production() -> bool:
    """
    Проверить, запущено ли приложение в production окружении.

    Returns:
        bool: True если production
    """
    return settings.environment == "production"


def is_development() -> bool:
    """
    Проверить, запущено ли приложение в development окружении.

    Returns:
        bool: True если development
    """
    return settings.environment == "development"


def is_testing() -> bool:
    """
    Проверить, запущено ли приложение в testing окружении.

    Returns:
        bool: True если testing
    """
    return settings.environment == "testing"


# Словарь с информацией о конфигурации
CONFIG_INFO = {
    "version": get_version(),
    "environment": settings.environment,
    "debug": settings.debug,
    "root_dir": str(ROOT_DIR),
    "logs_dir": str(settings.logs_dir),
    "bot_name": settings.bot.name,
}

# Выводим информацию о конфигурации при импорте в debug режиме
if settings.debug:
    logger.debug(f"Информация о конфигурации: {CONFIG_INFO}")

# Экспортируем все необходимое
__all__ = [
    # Настройки
    "settings",
    "get_settings",
    "Settings",

    # Логирование
    "logger",
    "get_logger",
    "setup_logging",
    "log_event",
    "log_error",

    # Команды и тексты
    "BotCommands",
    "ButtonTexts",
    "CallbackPrefixes",

    # Статусы
    "SubscriptionStatus",
    "SubscriptionPlan",
    "ToneOfVoice",
    "PaymentStatus",
    "TarotSpreadType",
    "Planet",
    "ZodiacSign",

    # Константы
    "Limits",
    "Prices",
    "Patterns",
    "TarotCards",
    "Emoji",
    "ErrorMessages",
    "PromoTexts",

    # Вспомогательные функции
    "get_version",
    "is_production",
    "is_development",
    "is_testing",

    # Информация
    "CONFIG_INFO",
    "ROOT_DIR",
]

# Дополнительная проверка для type checking
if TYPE_CHECKING:
    # Эти импорты только для подсказок типов
    from logging import Logger