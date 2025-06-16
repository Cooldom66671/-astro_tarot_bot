"""
Модуль конфигурации логирования для Астро-Таро Бота.

Этот модуль отвечает за:
- Настройку форматов логирования для разных окружений
- Ротацию файлов логов по размеру и времени
- Отправку критических ошибок администратору в Telegram
- Цветное логирование в консоли для разработки
- Структурированное логирование в JSON для production
- Фильтрацию чувствительных данных из логов

Использование:
    from config.logging_config import setup_logging

    # При старте приложения
    setup_logging()

    # В модулях
    import logging
    logger = logging.getLogger(__name__)
"""

import logging
import logging.handlers
import sys
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
from functools import lru_cache

# Импортируем настройки (будет создан позже)
from config.settings import settings


# Цвета для консольного вывода
class Colors:
    """ANSI цвета для красивого вывода в терминал."""
    RESET = '\033[0m'
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    PURPLE = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    GRAY = '\033[90m'

    # Стили
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


class SensitiveDataFilter(logging.Filter):
    """
    Фильтр для скрытия чувствительных данных в логах.

    Заменяет токены, ключи API, пароли и другие sensitive данные
    на замаскированные значения.
    """

    # Паттерны для поиска чувствительных данных
    PATTERNS = [
        # Telegram токены
        (r'(\d{8,10}:[a-zA-Z0-9_-]{35})', 'TELEGRAM_TOKEN'),
        # API ключи (общий паттерн)
        (r'(api[_-]?key["\']?\s*[:=]\s*["\']?)([a-zA-Z0-9_-]{20,})', r'\1***API_KEY***'),
        # Пароли
        (r'(password["\']?\s*[:=]\s*["\']?)([^"\']+)', r'\1***PASSWORD***'),
        # Email адреса (частичное скрытие)
        (r'([a-zA-Z0-9._%+-]+)@([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
         lambda m: f"{m.group(1)[:3]}***@{m.group(2)}"),
        # Номера телефонов
        (r'(\+?\d{1,3}[-.\s]?)?\d{3,4}[-.\s]?\d{3,4}[-.\s]?\d{3,4}', '***PHONE***'),
        # Номера карт
        (r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b', '****-****-****-****'),
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        """Фильтрует и маскирует чувствительные данные."""
        # Маскируем в основном сообщении
        if hasattr(record, 'msg'):
            record.msg = self._mask_sensitive_data(str(record.msg))

        # Маскируем в аргументах
        if hasattr(record, 'args') and record.args:
            record.args = tuple(
                self._mask_sensitive_data(str(arg)) for arg in record.args
            )

        return True

    def _mask_sensitive_data(self, text: str) -> str:
        """Применяет все паттерны для маскировки данных."""
        for pattern, replacement in self.PATTERNS:
            if callable(replacement):
                text = re.sub(pattern, replacement, text)
            else:
                text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
        return text


class ColoredFormatter(logging.Formatter):
    """
    Форматтер с цветным выводом для консоли.

    Использует ANSI цвета для выделения уровней логирования
    и важных частей сообщения.
    """

    # Цвета для разных уровней логирования
    LEVEL_COLORS = {
        'DEBUG': Colors.GRAY,
        'INFO': Colors.GREEN,
        'WARNING': Colors.YELLOW,
        'ERROR': Colors.RED,
        'CRITICAL': Colors.RED + Colors.BOLD,
    }

    def format(self, record: logging.LogRecord) -> str:
        """Форматирует запись с цветами."""
        # Сохраняем оригинальный формат
        original_format = self._style._fmt

        # Получаем цвет для уровня
        level_color = self.LEVEL_COLORS.get(record.levelname, Colors.WHITE)

        # Форматируем время
        time_str = Colors.GRAY + '%(asctime)s' + Colors.RESET

        # Форматируем уровень с цветом
        level_str = level_color + '%(levelname)-8s' + Colors.RESET

        # Форматируем имя модуля
        name_str = Colors.CYAN + '%(name)s' + Colors.RESET

        # Форматируем сообщение
        if record.levelname in ['ERROR', 'CRITICAL']:
            msg_str = level_color + '%(message)s' + Colors.RESET
        else:
            msg_str = '%(message)s'

        # Собираем новый формат
        self._style._fmt = f'{time_str} | {level_str} | {name_str} | {msg_str}'

        # Форматируем запись
        result = super().format(record)

        # Восстанавливаем оригинальный формат
        self._style._fmt = original_format

        return result


class JSONFormatter(logging.Formatter):
    """
    Форматтер для вывода логов в JSON формате.

    Используется в production для структурированного логирования,
    которое легко парсить и анализировать.
    """

    def format(self, record: logging.LogRecord) -> str:
        """Форматирует запись в JSON."""
        log_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
            'message': record.getMessage(),
            'environment': settings.environment,
        }

        # Добавляем exception info если есть
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)

        # Добавляем дополнительные поля из record
        for key, value in record.__dict__.items():
            if key not in ['name', 'msg', 'args', 'created', 'filename',
                           'funcName', 'levelname', 'levelno', 'lineno',
                           'module', 'msecs', 'pathname', 'process',
                           'processName', 'relativeCreated', 'thread',
                           'threadName', 'exc_info', 'exc_text', 'stack_info']:
                log_data[key] = value

        return json.dumps(log_data, ensure_ascii=False)


class TelegramHandler(logging.Handler):
    """
    Handler для отправки критических ошибок в Telegram.

    Отправляет сообщения об ошибках администратору бота
    для быстрого реагирования на проблемы в production.
    """

    def __init__(self, admin_chat_id: Optional[int] = None):
        """
        Инициализация handler.

        Args:
            admin_chat_id: ID чата администратора в Telegram
        """
        super().__init__()
        self.admin_chat_id = admin_chat_id
        self._bot = None  # Будет инициализирован позже

    async def emit_async(self, record: logging.LogRecord) -> None:
        """Асинхронная отправка сообщения в Telegram."""
        if not self.admin_chat_id or not self._bot:
            return

        try:
            # Форматируем сообщение для Telegram
            message = f"""
🚨 <b>{record.levelname}</b> в {record.name}

<b>Время:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
<b>Модуль:</b> {record.module}:{record.lineno}
<b>Функция:</b> {record.funcName}

<b>Сообщение:</b>
<code>{record.getMessage()[:3000]}</code>
"""

            # Добавляем traceback если есть
            if record.exc_info:
                exc_text = self.format(record)[-1000:]  # Последние 1000 символов
                message += f"\n<b>Traceback:</b>\n<pre>{exc_text}</pre>"

            # Отправляем сообщение
            await self._bot.send_message(
                chat_id=self.admin_chat_id,
                text=message,
                parse_mode="HTML"
            )

        except Exception as e:
            # Логируем ошибку отправки в stderr
            sys.stderr.write(f"Failed to send log to Telegram: {e}\n")

    def emit(self, record: logging.LogRecord) -> None:
        """Синхронная обертка для emit."""
        # В синхронном контексте просто пропускаем
        # Реальная отправка будет в async версии
        pass


def setup_logging() -> None:
    """
    Настраивает систему логирования для всего приложения.

    Конфигурирует:
    - Консольный вывод с цветами для разработки
    - Файловый вывод с ротацией для production
    - JSON логирование для структурированного анализа
    - Отправку критических ошибок в Telegram
    """
    # Получаем корневой logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.log_level))

    # Удаляем существующие handlers
    root_logger.handlers = []

    # Добавляем фильтр для чувствительных данных
    sensitive_filter = SensitiveDataFilter()

    # 1. Консольный handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG if settings.debug else logging.INFO)

    if settings.environment == "development":
        # Цветной формат для разработки
        console_formatter = ColoredFormatter(
            '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
            datefmt='%H:%M:%S'
        )
    else:
        # JSON формат для production
        console_formatter = JSONFormatter()

    console_handler.setFormatter(console_formatter)
    console_handler.addFilter(sensitive_filter)
    root_logger.addHandler(console_handler)

    # 2. Файловый handler с ротацией по размеру
    if settings.log_file:
        settings.log_file.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.handlers.RotatingFileHandler(
            filename=str(settings.log_file),
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.INFO)

        # Всегда используем JSON для файлов
        file_formatter = JSONFormatter()
        file_handler.setFormatter(file_formatter)
        file_handler.addFilter(sensitive_filter)
        root_logger.addHandler(file_handler)

    # 3. Handler для ошибок с ротацией по времени
    error_log_file = settings.logs_dir / "errors.log"
    error_handler = logging.handlers.TimedRotatingFileHandler(
        filename=str(error_log_file),
        when='midnight',
        interval=1,
        backupCount=30,  # Храним 30 дней
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(JSONFormatter())
    error_handler.addFilter(sensitive_filter)
    root_logger.addHandler(error_handler)

    # 4. Telegram handler для критических ошибок (будет настроен позже)
    # telegram_handler = TelegramHandler()
    # telegram_handler.setLevel(logging.CRITICAL)
    # root_logger.addHandler(telegram_handler)

    # Настройка логирования для сторонних библиотек
    logging.getLogger('aiogram').setLevel(logging.INFO)
    logging.getLogger('asyncio').setLevel(logging.WARNING)
    logging.getLogger('sqlalchemy.engine').setLevel(
        logging.INFO if settings.database.echo else logging.WARNING
    )

    # Отключаем дебаг логи от некоторых библиотек
    for logger_name in ['urllib3', 'httpx', 'httpcore']:
        logging.getLogger(logger_name).setLevel(logging.WARNING)

    # Логируем успешную настройку
    logger = logging.getLogger(__name__)
    logger.info(
        f"Логирование настроено для окружения '{settings.environment}' "
        f"с уровнем '{settings.log_level}'"
    )


@lru_cache()
def get_logger(name: str) -> logging.Logger:
    """
    Получить logger с заданным именем.

    Args:
        name: Имя logger'а (обычно __name__)

    Returns:
        logging.Logger: Настроенный logger
    """
    return logging.getLogger(name)


# Вспомогательные функции для структурированного логирования
def log_event(logger: logging.Logger, event: str, **kwargs) -> None:
    """
    Логирует событие со структурированными данными.

    Args:
        logger: Logger для записи
        event: Название события
        **kwargs: Дополнительные данные события
    """
    logger.info(event, extra={'event_type': event, 'event_data': kwargs})


def log_error(logger: logging.Logger, error: Exception, **kwargs) -> None:
    """
    Логирует ошибку со структурированными данными.

    Args:
        logger: Logger для записи
        error: Исключение
        **kwargs: Дополнительные данные контекста
    """
    logger.error(
        f"{error.__class__.__name__}: {str(error)}",
        exc_info=True,
        extra={
            'error_type': error.__class__.__name__,
            'error_context': kwargs
        }
    )


__all__ = [
    "setup_logging",
    "get_logger",
    "log_event",
    "log_error",
    "SensitiveDataFilter",
    "ColoredFormatter",
    "JSONFormatter",
    "TelegramHandler",
]