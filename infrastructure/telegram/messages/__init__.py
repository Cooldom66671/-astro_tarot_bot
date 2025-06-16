"""
Модуль экспорта всех сообщений Telegram бота.

Этот модуль предоставляет:
- Централизованный экспорт всех классов сообщений
- Фабричные функции для создания сообщений
- Общие шаблоны и константы
- Утилиты форматирования

Автор: AI Assistant
Дата создания: 2024-12-30
"""

import logging
from typing import Optional, Dict, Any, List, Union
from datetime import datetime, date
from enum import Enum

# Базовые компоненты
from .base import (
    # Классы
    BaseMessage,
    TemplateMessage,
    MessageBuilder,
    MessageFormatter,

    # Энумы
    MessageStyle,
    MessageType,

    # Константы
    MessageEmoji
)

# Приветственные сообщения
from .welcome import (
    # Классы
    WelcomeMessage,
    OnboardingMessage,
    WelcomeInfoMessage,

    # Энумы
    WelcomeMessageType,
    OnboardingStep,

    # Функции
    get_welcome_message,
    get_onboarding_message,
    get_info_message,
    get_time_based_greeting,
    get_random_welcome_quote,

    # Константы
    WELCOME_QUOTES
)

# Сообщения Таро
from .tarot import (
    # Классы
    TarotCardMessage,
    TarotSpreadMessage,
    TarotEducationalMessage,
    TarotStatisticsMessage,

    # Энумы
    TarotContext,
    CardPosition,

    # Данные
    SpreadPosition,

    # Функции
    format_card_message,
    format_spread_message,
    format_educational_message,
    format_statistics_message,
    get_random_tarot_quote,

    # Константы
    TarotMessages,
    TAROT_QUOTES
)

# Сообщения астрологии
from .astrology import (
    # Классы
    HoroscopeMessage,
    NatalChartMessage,
    TransitMessage,
    MoonPhaseMessage,
    SynastryMessage,

    # Энумы
    ZodiacSign,
    Planet,
    AspectType,
    MoonPhase,

    # Функции
    format_horoscope_message,
    format_natal_chart_message,
    format_transit_message,
    format_moon_phase_message,
    format_synastry_message,
    get_zodiac_sign_by_date,
    calculate_moon_phase,

    # Константы
    AstrologyMessages
)

# Настройка логирования
logger = logging.getLogger(__name__)


# Фабрика сообщений
class MessageFactory:
    """Фабрика для создания всех типов сообщений."""

    @staticmethod
    async def create_welcome(
            message_type: Union[str, WelcomeMessageType],
            user_data: Optional[Dict[str, Any]] = None
    ) -> str:
        """Создать приветственное сообщение."""
        if isinstance(message_type, str):
            message_type = WelcomeMessageType(message_type)
        return await get_welcome_message(message_type, user_data)

    @staticmethod
    async def create_onboarding(
            step: Union[str, OnboardingStep],
            user_data: Optional[Dict[str, Any]] = None
    ) -> str:
        """Создать сообщение онбординга."""
        if isinstance(step, str):
            step = OnboardingStep(step)
        return await get_onboarding_message(step, user_data)

    @staticmethod
    async def create_tarot_card(
            card_data: Dict[str, Any],
            **kwargs
    ) -> str:
        """Создать сообщение карты Таро."""
        return await format_card_message(card_data, **kwargs)

    @staticmethod
    async def create_tarot_spread(
            spread_type: str,
            cards: List[Dict[str, Any]],
            **kwargs
    ) -> str:
        """Создать сообщение расклада."""
        return await format_spread_message(spread_type, cards, **kwargs)

    @staticmethod
    async def create_horoscope(
            sign: str,
            horoscope_type: str,
            horoscope_data: Dict[str, Any],
            **kwargs
    ) -> str:
        """Создать сообщение гороскопа."""
        return await format_horoscope_message(sign, horoscope_type, horoscope_data, **kwargs)

    @staticmethod
    async def create_natal_chart(
            chart_data: Dict[str, Any],
            section: Optional[str] = None
    ) -> str:
        """Создать сообщение натальной карты."""
        return await format_natal_chart_message(chart_data, section)


# Общие шаблоны сообщений
class CommonMessages:
    """Общие сообщения для всех разделов."""

    # Ошибки
    ERROR_GENERIC = """
❌ Произошла ошибка

Пожалуйста, попробуйте позже или обратитесь в поддержку.
"""

    ERROR_NOT_FOUND = """
❌ Не найдено

Запрашиваемая информация не найдена.
"""

    ERROR_ACCESS_DENIED = """
🔒 Доступ запрещён

У вас нет доступа к этой функции.
"""

    ERROR_LIMIT_REACHED = """
⚠️ Достигнут лимит

Вы достигли дневного лимита использования.
Попробуйте завтра или оформите подписку.
"""

    # Загрузка
    LOADING = "⏳ Загрузка..."
    PROCESSING = "⚙️ Обработка..."
    CALCULATING = "🧮 Вычисление..."
    GENERATING = "✨ Генерация..."

    # Успех
    SUCCESS_SAVED = "✅ Сохранено"
    SUCCESS_DELETED = "✅ Удалено"
    SUCCESS_UPDATED = "✅ Обновлено"
    SUCCESS_SENT = "✅ Отправлено"

    # Подтверждения
    CONFIRM_DELETE = """
❓ Подтвердите удаление

Вы уверены, что хотите удалить?
Это действие нельзя отменить.
"""

    CONFIRM_CANCEL = """
❓ Подтвердите отмену

Вы уверены, что хотите отменить?
Все несохранённые данные будут потеряны.
"""

    # Помощь
    HELP_COMMAND_NOT_FOUND = """
❓ Команда не найдена

Используйте /help для просмотра доступных команд.
"""

    HELP_CONTACT_SUPPORT = """
🆘 Обратитесь в поддержку

Если у вас возникли проблемы, напишите нам:
@astrotaro_support
"""

    # Подписка
    SUBSCRIPTION_REQUIRED = """
⭐ Требуется подписка

Эта функция доступна только с подпиской.
Оформите подписку для полного доступа!
"""

    SUBSCRIPTION_EXPIRED = """
⏰ Подписка истекла

Ваша подписка истекла.
Продлите подписку, чтобы продолжить использование.
"""

    # Обслуживание
    MAINTENANCE_MODE = """
🛠 Технические работы

Бот временно недоступен.
Мы работаем над улучшениями!
Попробуйте позже.
"""


# Шаблоны для быстрого создания
class MessageTemplates:
    """Шаблоны сообщений с подстановкой."""

    # Приветствия
    GREETING = TemplateMessage(
        "Привет, {name}! 👋\n\n{message}",
        MessageStyle.MARKDOWN_V2
    )

    # Уведомления
    NOTIFICATION = TemplateMessage(
        "🔔 {title}\n\n{content}\n\n{footer}",
        MessageStyle.MARKDOWN_V2
    )

    # Результаты
    RESULT = TemplateMessage(
        "📊 {title}\n\n{result}\n\nВремя: {duration}",
        MessageStyle.MARKDOWN_V2
    )

    # Ошибки
    ERROR = TemplateMessage(
        "❌ Ошибка: {error_type}\n\n{error_message}\n\nКод: {error_code}",
        MessageStyle.MARKDOWN_V2
    )

    # Платежи
    PAYMENT = TemplateMessage(
        "💳 Платёж #{payment_id}\n\nСумма: {amount} ₽\nСтатус: {status}\nДата: {date}",
        MessageStyle.MARKDOWN_V2
    )


# Утилиты для работы с сообщениями
class MessageUtils:
    """Утилиты для работы с сообщениями."""

    @staticmethod
    def create_progress_bar(current: int, total: int, length: int = 10) -> str:
        """
        Создать прогресс-бар.

        Args:
            current: Текущее значение
            total: Максимальное значение
            length: Длина бара

        Returns:
            Строка прогресс-бара
        """
        if total == 0:
            return "░" * length

        filled = int(length * current / total)
        empty = length - filled

        return "▓" * filled + "░" * empty

    @staticmethod
    def create_rating_stars(rating: float, max_rating: int = 5) -> str:
        """
        Создать рейтинг звёздами.

        Args:
            rating: Рейтинг
            max_rating: Максимальный рейтинг

        Returns:
            Строка со звёздами
        """
        full_stars = int(rating)
        half_star = 1 if rating - full_stars >= 0.5 else 0
        empty_stars = max_rating - full_stars - half_star

        result = "⭐" * full_stars
        if half_star:
            result += "✨"
        result += "☆" * empty_stars

        return result

    @staticmethod
    def truncate_message(text: str, max_length: int = 4096) -> str:
        """
        Обрезать сообщение до максимальной длины.

        Args:
            text: Текст сообщения
            max_length: Максимальная длина

        Returns:
            Обрезанный текст
        """
        if len(text) <= max_length:
            return text

        # Обрезаем с учётом многоточия
        truncated = text[:max_length - 3] + "..."

        # Пытаемся обрезать по последнему переносу строки
        last_newline = truncated.rfind('\n', 0, -3)
        if last_newline > max_length // 2:  # Если нашли перенос в разумном месте
            truncated = truncated[:last_newline] + "\n..."

        return truncated

    @staticmethod
    def split_long_message(text: str, max_length: int = 4096) -> List[str]:
        """
        Разбить длинное сообщение на части.

        Args:
            text: Текст сообщения
            max_length: Максимальная длина части

        Returns:
            Список частей
        """
        if len(text) <= max_length:
            return [text]

        parts = []
        current_part = ""

        # Разбиваем по абзацам
        paragraphs = text.split('\n\n')

        for paragraph in paragraphs:
            # Если абзац сам по себе слишком длинный
            if len(paragraph) > max_length:
                # Разбиваем по предложениям
                sentences = paragraph.split('. ')
                for sentence in sentences:
                    if len(current_part) + len(sentence) + 2 <= max_length:
                        if current_part:
                            current_part += ". " + sentence
                        else:
                            current_part = sentence
                    else:
                        if current_part:
                            parts.append(current_part + ".")
                        current_part = sentence
            else:
                # Проверяем, влезет ли абзац
                if len(current_part) + len(paragraph) + 2 <= max_length:
                    if current_part:
                        current_part += "\n\n" + paragraph
                    else:
                        current_part = paragraph
                else:
                    if current_part:
                        parts.append(current_part)
                    current_part = paragraph

        # Добавляем последнюю часть
        if current_part:
            parts.append(current_part)

        return parts


# Константы сообщений
class MessageConstants:
    """Константы для сообщений."""

    # Максимальные длины
    MAX_MESSAGE_LENGTH = 4096
    MAX_CAPTION_LENGTH = 1024
    MAX_CALLBACK_DATA_LENGTH = 64

    # Таймауты
    TYPING_DURATION = 2  # Секунды

    # Эмодзи по категориям
    EMOJI_CATEGORIES = {
        "success": ["✅", "✔️", "👍", "🎉", "🌟"],
        "error": ["❌", "⚠️", "🚫", "❗", "⛔"],
        "info": ["ℹ️", "💡", "📋", "📌", "🔍"],
        "loading": ["⏳", "⏰", "🔄", "⚙️", "🔧"],
        "question": ["❓", "❔", "🤔", "💭", "🗨️"],
        "warning": ["⚠️", "🚨", "📣", "🔔", "❗"],
        "money": ["💰", "💵", "💳", "💎", "🏦"],
        "time": ["⏰", "🕐", "📅", "📆", "⏱"],
        "magic": ["✨", "🔮", "🌟", "💫", "🌙"],
        "love": ["❤️", "💕", "💖", "💗", "💝"]
    }

    # Стили текста
    TEXT_STYLES = {
        "bold": "*{}*",
        "italic": "_{}_",
        "code": "`{}`",
        "pre": "```\n{}\n```",
        "quote": ">{}"
    }


# Менеджер сообщений
class MessageManager:
    """Менеджер для управления сообщениями."""

    def __init__(self, default_style: MessageStyle = MessageStyle.MARKDOWN_V2):
        """
        Инициализация менеджера.

        Args:
            default_style: Стиль по умолчанию
        """
        self.default_style = default_style
        self.factory = MessageFactory()
        self.templates = MessageTemplates()
        self.utils = MessageUtils()

        logger.debug("MessageManager инициализирован")

    async def create(self, message_type: str, **kwargs) -> str:
        """
        Создать сообщение любого типа.

        Args:
            message_type: Тип сообщения
            **kwargs: Параметры сообщения

        Returns:
            Отформатированное сообщение
        """
        # Маппинг типов на методы фабрики
        creators = {
            "welcome": self.factory.create_welcome,
            "onboarding": self.factory.create_onboarding,
            "tarot_card": self.factory.create_tarot_card,
            "tarot_spread": self.factory.create_tarot_spread,
            "horoscope": self.factory.create_horoscope,
            "natal_chart": self.factory.create_natal_chart
        }

        creator = creators.get(message_type)
        if creator:
            return await creator(**kwargs)

        # Если тип не найден, возвращаем ошибку
        logger.warning(f"Неизвестный тип сообщения: {message_type}")
        return CommonMessages.ERROR_GENERIC

    def format_error(self, error: Exception) -> str:
        """
        Форматировать сообщение об ошибке.

        Args:
            error: Исключение

        Returns:
            Отформатированное сообщение
        """
        error_type = type(error).__name__
        error_message = str(error)

        # Определяем тип ошибки для пользователя
        user_errors = {
            "ValueError": "Неверные данные",
            "KeyError": "Отсутствуют данные",
            "PermissionError": "Нет доступа",
            "TimeoutError": "Превышено время ожидания"
        }

        user_error_type = user_errors.get(error_type, "Системная ошибка")

        # Логируем полную ошибку
        logger.error(f"{error_type}: {error_message}", exc_info=True)

        # Возвращаем пользователю безопасное сообщение
        return self.templates.ERROR.format(
            error_type=user_error_type,
            error_message="Обратитесь в поддержку, если ошибка повторится",
            error_code=f"ERR_{hash(error_message) % 10000:04d}"
        )


# Декораторы для сообщений
def with_typing(duration: int = 2):
    """
    Декоратор для имитации набора текста.

    Args:
        duration: Длительность набора в секундах
    """

    def decorator(func):
        async def wrapper(message, *args, **kwargs):
            # Отправляем действие "печатает"
            await message.answer_chat_action("typing")

            # Ждём
            import asyncio
            await asyncio.sleep(duration)

            # Выполняем функцию
            return await func(message, *args, **kwargs)

        return wrapper

    return decorator


def split_if_long(max_length: int = 4096):
    """
    Декоратор для автоматического разбиения длинных сообщений.

    Args:
        max_length: Максимальная длина одного сообщения
    """

    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Получаем сообщение
            text = await func(*args, **kwargs)

            # Если не строка, возвращаем как есть
            if not isinstance(text, str):
                return text

            # Разбиваем если нужно
            if len(text) > max_length:
                return MessageUtils.split_long_message(text, max_length)

            return text

        return wrapper

    return decorator


# Экспорт всех компонентов
__all__ = [
    # Фабрики и менеджеры
    "MessageFactory",
    "MessageManager",

    # Базовые классы
    "BaseMessage",
    "TemplateMessage",
    "MessageBuilder",
    "MessageFormatter",

    # Приветственные сообщения
    "WelcomeMessage",
    "OnboardingMessage",
    "WelcomeInfoMessage",
    "WelcomeMessageType",
    "OnboardingStep",

    # Таро
    "TarotCardMessage",
    "TarotSpreadMessage",
    "TarotEducationalMessage",
    "TarotStatisticsMessage",
    "TarotContext",
    "CardPosition",

    # Астрология
    "HoroscopeMessage",
    "NatalChartMessage",
    "TransitMessage",
    "MoonPhaseMessage",
    "SynastryMessage",
    "ZodiacSign",
    "Planet",
    "MoonPhase",

    # Константы и шаблоны
    "CommonMessages",
    "MessageTemplates",
    "MessageConstants",
    "MessageEmoji",

    # Утилиты
    "MessageUtils",
    "MessageStyle",
    "MessageType",

    # Функции
    "get_welcome_message",
    "get_time_based_greeting",
    "get_zodiac_sign_by_date",
    "calculate_moon_phase",

    # Декораторы
    "with_typing",
    "split_if_long"
]

# Инициализация
logger.info("Модуль сообщений Telegram бота загружен полностью")