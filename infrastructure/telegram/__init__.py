"""
Модуль Telegram интерфейса.

Этот модуль объединяет все компоненты для работы с Telegram:
- Клавиатуры
- Сообщения
- Обработчики (будут добавлены позже)
- Состояния (будут добавлены позже)

Автор: AI Assistant
Дата создания: 2024-12-30
"""

import logging

# Импорт всех клавиатур
from .keyboards import (
    # Фабрики
    Keyboards,
    KeyboardFactory,

    # Базовые классы
    BaseKeyboard,
    InlineKeyboard,
    ReplyKeyboard,

    # Главное меню
    MainMenuKeyboard,
    get_main_menu,

    # Таро
    SpreadSelectionKeyboard,
    TarotSection,
    SpreadType,

    # Астрология
    BirthDataKeyboard,
    HoroscopeType,
    ZodiacSign,

    # Подписка
    SubscriptionPlansKeyboard,
    SubscriptionPlan,
    PaymentProvider
)

# Импорт всех сообщений
from .messages import (
    # Фабрики
    MessageFactory,
    MessageManager,

    # Базовые классы
    MessageBuilder,
    MessageFormatter,

    # Общие
    CommonMessages,
    MessageEmoji,

    # Приветствие
    get_welcome_message,
    get_time_based_greeting,

    # Таро
    format_card_message,
    format_spread_message,

    # Астрология
    format_horoscope_message,
    get_zodiac_sign_by_date
)

# Настройка логирования
logger = logging.getLogger(__name__)

# Версия модуля
__version__ = "1.0.0"

# Список всех экспортируемых имен
__all__ = [
    # Клавиатуры
    "Keyboards",
    "KeyboardFactory",
    "MainMenuKeyboard",
    "get_main_menu",

    # Сообщения
    "MessageFactory",
    "MessageManager",
    "MessageBuilder",
    "CommonMessages",

    # Функции
    "get_welcome_message",
    "format_card_message",
    "format_horoscope_message"
]

logger.info(f"Telegram модуль v{__version__} загружен")