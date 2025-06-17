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
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Callable
from functools import lru_cache

# Проверяем наличие настроек
try:
    from config.settings import settings
except ImportError:
    # Создаем заглушку для разработки
    class Settings:
        environment = "development"
        debug = True
        log_level = "INFO"
        log_file = Path("logs/bot.log")
        logs_dir = Path("logs")
    settings = Settings()


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
        (r'(\d{8,10}:[a-zA-Z0-9_-]{35})', '***TELEGRAM_TOKEN***'),
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
        # JWT токены
        (r'(Bearer\s+)([a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+)', r'\1***JWT_TOKEN***'),
        # UUID
        (r'[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}', '***UUID***'),
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
                text = re.sub(pattern, replacement, text)
        return text


class ColoredFormatter(logging.Formatter):
    """
    Форматтер с цветным выводом для разработки.

    Раскрашивает сообщения в зависимости от уровня логирования
    для удобного чтения в консоли.
    """

    # Маппинг уровней на цвета
    COLORS_MAP = {
        'DEBUG': Colors.GRAY,
        'INFO': Colors.BLUE,
        'WARNING': Colors.YELLOW,
        'ERROR': Colors.RED,
        'CRITICAL': Colors.RED + Colors.BOLD,
    }

    def format(self, record: logging.LogRecord) -> str:
        """Форматирует запись с цветами."""
        # Получаем базовый формат
        log_fmt = super().format(record)

        # Добавляем цвет для уровня
        levelname = record.levelname
        if levelname in self.COLORS_MAP:
            color = self.COLORS_MAP[levelname]
            # Раскрашиваем уровень
            colored_levelname = f"{color}{levelname}{Colors.RESET}"
            log_fmt = log_fmt.replace(levelname, colored_levelname)

            # Раскрашиваем сообщение для ошибок
            if levelname in ['ERROR', 'CRITICAL']:
                # Находим начало сообщения после разделителя
                parts = log_fmt.split(' | ')
                if len(parts) >= 4:
                    parts[-1] = f"{color}{parts[-1]}{Colors.RESET}"
                    log_fmt = ' | '.join(parts)

        return log_fmt


class JSONFormatter(logging.Formatter):
    """
    JSON форматтер для структурированного логирования.

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
            'environment': getattr(settings, 'environment', 'unknown'),
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
                           'threadName', 'exc_info', 'exc_text', 'stack_info',
                           'getMessage']:
                try:
                    # Пытаемся сериализовать в JSON
                    json.dumps(value)
                    log_data[key] = value
                except (TypeError, ValueError):
                    # Если не получается, преобразуем в строку
                    log_data[key] = str(value)

        return json.dumps(log_data, ensure_ascii=False, default=str)


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
        self.admin_chat_id = admin_chat_id or getattr(settings, 'developer_id', None)
        self._bot = None  # Будет инициализирован позже
        self._queue = asyncio.Queue(maxsize=100)
        self._task = None

    def set_bot(self, bot) -> None:
        """Устанавливает экземпляр бота для отправки сообщений."""
        self._bot = bot
        # Запускаем обработчик очереди
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._process_queue())

    async def _process_queue(self) -> None:
        """Обрабатывает очередь сообщений."""
        while True:
            try:
                record = await self._queue.get()
                await self._send_to_telegram(record)
            except Exception as e:
                # Логируем ошибку в stderr чтобы избежать рекурсии
                print(f"Error in TelegramHandler: {e}", file=sys.stderr)

    async def _send_to_telegram(self, record: logging.LogRecord) -> None:
        """Отправляет сообщение в Telegram."""
        if not self._bot or not self.admin_chat_id:
            return

        try:
            # Форматируем сообщение
            message = self._format_telegram_message(record)

            # Отправляем сообщение
            await self._bot.send_message(
                chat_id=self.admin_chat_id,
                text=message,
                parse_mode='HTML',
                disable_notification=False
            )
        except Exception as e:
            # Логируем ошибку в stderr
            print(f"Failed to send log to Telegram: {e}", file=sys.stderr)

    def _format_telegram_message(self, record: logging.LogRecord) -> str:
        """Форматирует сообщение для Telegram."""
        # Эмодзи для уровней
        emoji_map = {
            'ERROR': '❌',
            'CRITICAL': '🚨'
        }
        emoji = emoji_map.get(record.levelname, '⚠️')

        # Форматируем сообщение
        message = (
            f"{emoji} <b>{record.levelname}</b>\n\n"
            f"<b>Время:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"<b>Модуль:</b> <code>{record.name}</code>\n"
            f"<b>Функция:</b> <code>{record.funcName}:{record.lineno}</code>\n\n"
            f"<b>Сообщение:</b>\n{record.getMessage()[:1000]}"
        )

        # Добавляем информацию об исключении
        if record.exc_info:
            exc_text = self.format(record)[-1000:]  # Последние 1000 символов
            message += f"\n\n<b>Исключение:</b>\n<pre>{exc_text}</pre>"

        return message

    def emit(self, record: logging.LogRecord) -> None:
        """Обрабатывает запись лога."""
        # Добавляем в очередь для асинхронной отправки
        try:
            self._queue.put_nowait(record)
        except asyncio.QueueFull:
            # Если очередь полная, пропускаем
            pass


def setup_logging() -> None:
    """
    Настраивает систему логирования для приложения.

    Конфигурирует:
    - Консольный вывод с цветами для разработки
    - Файловый вывод с ротацией для production
    - JSON логирование для структурированного анализа
    - Отправку критических ошибок в Telegram
    """
    # Получаем корневой logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, getattr(settings, 'log_level', 'INFO')))

    # Удаляем существующие handlers
    root_logger.handlers = []

    # Добавляем фильтр для чувствительных данных
    sensitive_filter = SensitiveDataFilter()

    # 1. Консольный handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG if getattr(settings, 'debug', False) else logging.INFO)

    if getattr(settings, 'environment', 'development') == "development":
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
    log_file = getattr(settings, 'log_file', Path("logs/bot.log"))
    if log_file:
        log_file = Path(log_file)
        log_file.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.handlers.RotatingFileHandler(
            filename=str(log_file),
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
    logs_dir = getattr(settings, 'logs_dir', Path("logs"))
    error_log_file = Path(logs_dir) / "errors.log"
    error_log_file.parent.mkdir(parents=True, exist_ok=True)

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
    if getattr(settings, 'environment', 'development') == "production":
        telegram_handler = TelegramHandler()
        telegram_handler.setLevel(logging.CRITICAL)
        telegram_handler.addFilter(sensitive_filter)
        root_logger.addHandler(telegram_handler)

    # Настройка логирования для сторонних библиотек
    logging.getLogger('aiogram').setLevel(logging.INFO)
    logging.getLogger('asyncio').setLevel(logging.WARNING)

    # Для SQLAlchemy
    if hasattr(settings, 'database') and hasattr(settings.database, 'echo'):
        logging.getLogger('sqlalchemy.engine').setLevel(
            logging.INFO if settings.database.echo else logging.WARNING
        )
    else:
        logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)

    # Отключаем дебаг логи от некоторых библиотек
    for logger_name in ['urllib3', 'httpx', 'httpcore', 'aiohttp']:
        logging.getLogger(logger_name).setLevel(logging.WARNING)

    # Логируем успешную настройку
    logger = logging.getLogger(__name__)
    logger.info(
        f"Логирование настроено для окружения '{getattr(settings, 'environment', 'unknown')}' "
        f"с уровнем '{getattr(settings, 'log_level', 'INFO')}'"
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


def log_performance(logger: logging.Logger, operation: str, duration: float, **kwargs) -> None:
    """
    Логирует метрики производительности.

    Args:
        logger: Logger для записи
        operation: Название операции
        duration: Длительность в секундах
        **kwargs: Дополнительные метрики
    """
    logger.info(
        f"Performance: {operation} completed in {duration:.3f}s",
        extra={
            'metric_type': 'performance',
            'operation': operation,
            'duration_seconds': duration,
            'metrics': kwargs
        }
    )


# Создаем глобальный telegram handler для использования в других модулях
telegram_handler = TelegramHandler()


__all__ = [
    "setup_logging",
    "get_logger",
    "log_event",
    "log_error",
    "log_performance",
    "SensitiveDataFilter",
    "ColoredFormatter",
    "JSONFormatter",
    "TelegramHandler",
    "telegram_handler",
]