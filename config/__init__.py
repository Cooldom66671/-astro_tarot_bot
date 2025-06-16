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

# Проверка версии Python
if sys.version_info < (3, 10):
    print("❌ Ошибка: Требуется Python 3.10 или выше")
    print(f"Текущая версия: {sys.version}")
    sys.exit(1)

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

# Импортируем настройки с проверкой
try:
    from config.settings import settings, get_settings, Settings
except ImportError as e:
    print(f"❌ Критическая ошибка: Не удалось импортировать настройки: {e}")
    sys.exit(1)

# Настраиваем логирование с проверкой
try:
    from config.logging_config import setup_logging, get_logger, log_event, log_error
except ImportError as e:
    print(f"❌ Критическая ошибка: Не удалось импортировать модуль логирования: {e}")
    sys.exit(1)

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
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    }
)


# Проверяем критичные настройки
def _check_critical_settings() -> None:
    """Проверяет наличие критичных настроек."""
    warnings = []
    errors = []

    # Проверяем токен бота
    try:
        if hasattr(settings.bot, 'token'):
            if hasattr(settings.bot.token, 'get_secret_value'):
                token = settings.bot.token.get_secret_value()
                if not token:
                    errors.append("❌ Токен Telegram бота пустой!")
            else:
                # Если это не SecretStr, проверяем напрямую
                if not settings.bot.token:
                    errors.append("❌ Токен Telegram бота не установлен!")
        else:
            errors.append("❌ Настройка bot.token отсутствует!")
    except AttributeError as e:
        errors.append(f"❌ Ошибка при проверке токена бота: {e}")
    except Exception as e:
        errors.append(f"❌ Неожиданная ошибка при проверке токена: {e}")

    # Проверяем базу данных
    try:
        if not hasattr(settings, 'database') or not settings.database.url:
            warnings.append("⚠️ URL базы данных не установлен!")
    except AttributeError:
        warnings.append("⚠️ Настройки базы данных отсутствуют!")

    # Проверяем ключи шифрования в production
    if settings.environment == "production":
        try:
            if hasattr(settings, 'security'):
                if hasattr(settings.security, 'secret_key'):
                    if hasattr(settings.security.secret_key, 'get_secret_value'):
                        secret_key = settings.security.secret_key.get_secret_value()
                        if not secret_key:
                            errors.append("❌ Secret key пустой для production!")
                    elif not settings.security.secret_key:
                        errors.append("❌ Secret key не установлен для production!")
                else:
                    errors.append("❌ Настройка security.secret_key отсутствует!")

                if hasattr(settings.security, 'encryption_key'):
                    if hasattr(settings.security.encryption_key, 'get_secret_value'):
                        enc_key = settings.security.encryption_key.get_secret_value()
                        if not enc_key:
                            errors.append("❌ Encryption key пустой для production!")
                    elif not settings.security.encryption_key:
                        errors.append("❌ Encryption key не установлен для production!")
                else:
                    errors.append("❌ Настройка security.encryption_key отсутствует!")
            else:
                errors.append("❌ Настройки безопасности отсутствуют для production!")
        except Exception as e:
            errors.append(f"❌ Ошибка при проверке ключей безопасности: {e}")

    # Проверяем критичные директории
    try:
        if hasattr(settings, 'logs_dir') and not settings.logs_dir.exists():
            warnings.append(f"⚠️ Директория логов не существует: {settings.logs_dir}")
    except Exception:
        warnings.append("⚠️ Не удалось проверить директорию логов")

    # Выводим ошибки и предупреждения
    if errors:
        logger.error(
            "Обнаружены критические ошибки конфигурации:\n" + "\n".join(errors)
        )
        # В production прерываем выполнение при критических ошибках
        if settings.environment == "production":
            sys.exit(1)

    if warnings:
        logger.warning(
            "Обнаружены проблемы с конфигурацией:\n" + "\n".join(warnings)
        )


# Создаем необходимые директории
def _create_required_directories() -> None:
    """Создает необходимые директории проекта."""
    directories = [
        settings.logs_dir,
        settings.static_dir,
        settings.base_dir / "temp",
        settings.base_dir / "downloads",
        settings.base_dir / "backups",
    ]

    for directory in directories:
        try:
            if not directory.exists():
                directory.mkdir(parents=True, exist_ok=True)
                logger.debug(f"Создана директория: {directory}")
        except Exception as e:
            logger.error(f"Не удалось создать директорию {directory}: {e}")


# Импортируем все константы для удобного доступа с проверкой
try:
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
except ImportError as e:
    logger.error(f"Не удалось импортировать константы: {e}")
    # Создаем пустые классы-заглушки чтобы не ломать импорты
    class BotCommands: pass
    class ButtonTexts: pass
    class CallbackPrefixes: pass
    class SubscriptionStatus: pass
    class SubscriptionPlan: pass
    class ToneOfVoice: pass
    class PaymentStatus: pass
    class TarotSpreadType: pass
    class Planet: pass
    class ZodiacSign: pass
    class Limits: pass
    class Prices: pass
    class Patterns: pass
    class TarotCards: pass
    class Emoji: pass
    class ErrorMessages: pass
    class PromoTexts: pass


# Вспомогательные функции
def get_version() -> str:
    """
    Получить версию приложения.

    Returns:
        str: Версия в формате "major.minor.patch"
    """
    version_file = ROOT_DIR / "VERSION"
    if version_file.exists():
        try:
            return version_file.read_text().strip()
        except Exception as e:
            logger.warning(f"Не удалось прочитать файл версии: {e}")
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


def initialize_config() -> None:
    """
    Инициализация конфигурации приложения.

    Вызывается автоматически при импорте модуля,
    но может быть вызвана повторно при необходимости.
    """
    _check_critical_settings()
    _create_required_directories()
    logger.info("Конфигурация полностью инициализирована")


# Словарь с информацией о конфигурации
CONFIG_INFO = {
    "version": get_version(),
    "environment": settings.environment,
    "debug": settings.debug,
    "root_dir": str(ROOT_DIR),
    "logs_dir": str(settings.logs_dir),
    "bot_name": settings.bot.name,
    "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
}

# Выполняем инициализацию при импорте
initialize_config()

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
    "initialize_config",

    # Информация
    "CONFIG_INFO",
    "ROOT_DIR",
]

# Дополнительная проверка для type checking
if TYPE_CHECKING:
    # Эти импорты только для подсказок типов
    from logging import Logger