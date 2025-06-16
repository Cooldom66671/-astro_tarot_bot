"""
Модуль экспорта всех клавиатур Telegram бота.

Этот модуль предоставляет:
- Централизованный экспорт всех клавиатур
- Фабричные функции для быстрого создания
- Общие утилиты и константы
- Типы для type hints

Автор: AI Assistant
Дата создания: 2024-12-30
"""

import logging
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from decimal import Decimal

from aiogram.types import (
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove
)

# Базовые компоненты
from .base import (
    # Классы
    BaseKeyboard,
    InlineKeyboard,
    ReplyKeyboard,
    PaginatedKeyboard,
    DynamicMenu,
    ConfirmationKeyboard,
    KeyboardFactory,

    # Типы и энумы
    ButtonStyle,
    ButtonConfig,

    # Callback Data
    BaseCallbackData,
    PaginationCallbackData,
    MenuCallbackData,
    ConfirmCallbackData,
    RefreshCallbackData,  # ДОБАВЛЕН ИМПОРТ

    # Утилиты
    parse_callback_data,
    build_callback_data,
    log_keyboard_creation
)

# Главное меню
from .main_menu import (
    # Классы
    MainMenuKeyboard,
    QuickActionsKeyboard,
    SectionMenuKeyboard,
    WelcomeKeyboard,
    TimeBasedGreetingKeyboard,

    # Энумы
    MainMenuSection,
    QuickActionType,

    # Callback Data
    MainMenuCallbackData,
    QuickActionCallbackData,

    # Функции
    get_main_menu,
    get_section_menu,
    get_welcome_keyboard
)

# Таро
from .tarot import (
    # Классы
    SpreadSelectionKeyboard,
    CardSelectionKeyboard,
    ReadingResultKeyboard,
    TarotHistoryKeyboard,
    CardDetailKeyboard,
    TarotLearningKeyboard,

    # Энумы
    TarotSection,
    SpreadType,
    CardSuit,

    # Callback Data
    TarotCallbackData,
    SpreadCallbackData,
    CardCallbackData,
    HistoryCallbackData,

    # Функции
    get_spread_selection_keyboard,
    get_card_selection_keyboard,
    get_reading_result_keyboard
)

# Астрология
from .astrology import (
    # Классы
    BirthDataKeyboard,
    HoroscopeMenuKeyboard,
    NatalChartKeyboard,
    ChartSettingsKeyboard,
    TransitsKeyboard,
    SynastryKeyboard,
    LunarCalendarKeyboard,

    # Энумы
    AstrologySection,
    HoroscopeType,
    HouseSystem,
    AspectType,
    PlanetSet,

    # Callback Data
    AstrologyCallbackData,
    BirthDataCallbackData,
    ChartCallbackData,
    TransitCallbackData,
    CalendarCallbackData,

    # Функции
    get_birth_data_keyboard,
    get_horoscope_menu,
    get_natal_chart_keyboard,
    get_lunar_calendar
)

# Подписка
from .subscription import (
    # Классы
    SubscriptionPlansKeyboard,
    PaymentMethodKeyboard,
    CurrentSubscriptionKeyboard,
    PromoCodeKeyboard,
    PaymentHistoryKeyboard,
    PaymentMethodsManagementKeyboard,
    SubscriptionCancellationKeyboard,

    # Энумы
    SubscriptionPlan,
    PaymentProvider,
    PaymentPeriod,

    # Callback Data
    SubscriptionCallbackData,
    PaymentCallbackData,
    PromoCallbackData,
    AutoRenewalCallbackData,

    # Функции
    get_subscription_plans_keyboard,
    get_payment_method_keyboard,
    get_current_subscription_keyboard,
    get_promo_code_keyboard
)

# Настройка логирования
logger = logging.getLogger(__name__)


# Универсальные фабричные функции
class Keyboards:
    """Фабрика для создания всех типов клавиатур."""

    @staticmethod
    async def main_menu(
            user_subscription: str = "free",
            is_admin: bool = False,
            user_name: Optional[str] = None
    ) -> ReplyKeyboardMarkup:
        """Получить главное меню."""
        return await get_main_menu(user_subscription, is_admin, user_name)

    @staticmethod
    async def remove() -> ReplyKeyboardRemove:
        """Удалить клавиатуру."""
        return KeyboardFactory.get_remove_keyboard()

    @staticmethod
    async def yes_no(
            target: str,
            value: Optional[str] = None
    ) -> InlineKeyboardMarkup:
        """Получить клавиатуру Да/Нет."""
        return await KeyboardFactory.get_yes_no_keyboard(target, value)

    @staticmethod
    async def back(callback_data: str = "back") -> InlineKeyboardMarkup:
        """Получить клавиатуру с кнопкой Назад."""
        return await KeyboardFactory.get_back_keyboard(callback_data)

    @staticmethod
    async def cancel(callback_data: str = "cancel") -> InlineKeyboardMarkup:
        """Получить клавиатуру с кнопкой Отмена."""
        keyboard = InlineKeyboard()
        keyboard.add_cancel_button(callback_data)
        return await keyboard.build()

    @staticmethod
    async def close() -> InlineKeyboardMarkup:
        """Получить клавиатуру с кнопкой Закрыть."""
        keyboard = InlineKeyboard()
        keyboard.add_button(
            text="❌ Закрыть",
            callback_data="close"
        )
        return await keyboard.build()

    @staticmethod
    async def menu_button() -> InlineKeyboardMarkup:
        """Получить клавиатуру с кнопкой перехода в меню."""
        keyboard = InlineKeyboard()
        keyboard.add_button(
            text="📋 Главное меню",
            callback_data="main_menu"
        )
        return await keyboard.build()

    @staticmethod
    async def welcome(user_name: Optional[str] = None) -> InlineKeyboardMarkup:
        """Получить приветственную клавиатуру."""
        return await get_welcome_keyboard(user_name)

    @staticmethod
    async def quick_actions(
            user_subscription: str = "free",
            context: Optional[str] = None
    ) -> InlineKeyboardMarkup:
        """Получить клавиатуру быстрых действий."""
        keyboard = QuickActionsKeyboard(user_subscription, context)
        return await keyboard.build()

    @staticmethod
    async def section_menu(
            section: Union[str, MainMenuSection],
            user_subscription: str = "free"
    ) -> InlineKeyboardMarkup:
        """Получить меню раздела."""
        if isinstance(section, str):
            section = MainMenuSection(section)
        return await get_section_menu(section, user_subscription)

    @staticmethod
    def subscription_offer() -> InlineKeyboardMarkup:
        """Получить клавиатуру с предложением подписки."""
        keyboard = InlineKeyboard()
        keyboard.add_button(
            text="⭐ Оформить подписку",
            callback_data=SubscriptionCallbackData(action="plans").pack()
        )
        keyboard.add_button(
            text="◀️ Назад",
            callback_data="back"
        )
        keyboard.builder.adjust(1, 1)
        return keyboard.builder.as_markup()


# Контекстные клавиатуры
class ContextKeyboards:
    """Клавиатуры, зависящие от контекста."""

    @staticmethod
    async def get_for_state(
            state_name: str,
            context: Dict[str, Any]
    ) -> Union[InlineKeyboardMarkup, ReplyKeyboardMarkup, None]:
        """
        Получить клавиатуру для текущего состояния.

        Args:
            state_name: Название состояния FSM
            context: Контекст с данными

        Returns:
            Подходящая клавиатура или None
        """
        # Маппинг состояний на клавиатуры
        state_keyboards = {
            # Регистрация
            "Registration:waiting_birth_date": lambda: get_birth_data_keyboard(
                context.get("birth_data"),
                "date"
            ),
            "Registration:waiting_birth_time": lambda: get_birth_data_keyboard(
                context.get("birth_data"),
                "time"
            ),
            "Registration:waiting_birth_place": lambda: get_birth_data_keyboard(
                context.get("birth_data"),
                "place"
            ),

            # Таро
            "TarotReading:selecting_spread": lambda: get_spread_selection_keyboard(
                context.get("user_subscription", "free")
            ),
            "TarotReading:selecting_cards": lambda: get_card_selection_keyboard(
                SpreadType(context["spread_type"]),
                context["current_position"],
                context["total_positions"],
                context.get("selected_cards", [])
            ),

            # Подписка
            "Subscription:selecting_plan": lambda: get_subscription_plans_keyboard(
                context.get("current_plan", "free"),
                context.get("selected_period", "monthly")
            ),
            "Subscription:selecting_payment": lambda: get_payment_method_keyboard(
                context["amount"],
                context["plan"],
                context["period"],
                context.get("saved_methods")
            )
        }

        # Получаем функцию создания клавиатуры
        keyboard_func = state_keyboards.get(state_name)

        if keyboard_func:
            try:
                return await keyboard_func()
            except Exception as e:
                logger.error(f"Ошибка создания клавиатуры для {state_name}: {e}")
                return None

        return None


# Утилиты для работы с клавиатурами
class KeyboardUtils:
    """Утилиты для работы с клавиатурами."""

    @staticmethod
    def extract_callback_action(callback_data: str) -> str:
        """
        Извлечь действие из callback data.

        Args:
            callback_data: Строка callback data

        Returns:
            Действие
        """
        parsed = parse_callback_data(callback_data)
        return parsed.get("action", "unknown")

    @staticmethod
    def build_navigation_callback(
            section: str,
            page: Optional[str] = None,
            **kwargs
    ) -> str:
        """
        Построить callback для навигации.

        Args:
            section: Раздел
            page: Страница
            **kwargs: Дополнительные параметры

        Returns:
            Строка callback data
        """
        data = {
            "section": section,
            "page": page,
            **kwargs
        }
        return build_callback_data("navigate", **data)

    @staticmethod
    async def create_paginated_menu(
            items: List[Any],
            item_formatter: callable,
            page: int = 1,
            page_size: int = 10,
            menu_type: str = "default"
    ) -> InlineKeyboardMarkup:
        """
        Создать пагинированное меню.

        Args:
            items: Список элементов
            item_formatter: Функция форматирования элемента
            page: Текущая страница
            page_size: Размер страницы
            menu_type: Тип меню

        Returns:
            Клавиатура с пагинацией
        """
        keyboard = PaginatedKeyboard(items, page_size, page, menu_type)

        # Добавляем элементы текущей страницы
        for item in keyboard.get_page_items():
            text, callback_data = item_formatter(item)
            keyboard.add_button(text, callback_data)

        # Добавляем пагинацию
        if keyboard.total_pages > 1:
            keyboard.add_pagination_buttons()

        return await keyboard.build()


# Константы для клавиатур
class KeyboardConstants:
    """Константы для клавиатур."""

    # Максимальные размеры
    MAX_INLINE_BUTTONS_PER_ROW = 8
    MAX_REPLY_BUTTONS_PER_ROW = 3
    MAX_CALLBACK_DATA_LENGTH = 64

    # Эмодзи для кнопок
    EMOJI = {
        "back": "◀️",
        "forward": "▶️",
        "up": "⬆️",
        "down": "⬇️",
        "confirm": "✅",
        "cancel": "❌",
        "edit": "✏️",
        "delete": "🗑",
        "info": "ℹ️",
        "settings": "⚙️",
        "star": "⭐",
        "lock": "🔒",
        "unlock": "🔓",
        "warning": "⚠️",
        "question": "❓",
        "money": "💰",
        "gift": "🎁",
        "calendar": "📅",
        "clock": "🕐",
        "location": "📍",
        "search": "🔍",
        "refresh": "🔄"
    }

    # Текстовые шаблоны
    TEXTS = {
        "back": "{emoji} Назад",
        "cancel": "{emoji} Отмена",
        "confirm": "{emoji} Подтвердить",
        "yes": "{emoji} Да",
        "no": "{emoji} Нет",
        "save": "{emoji} Сохранить",
        "edit": "{emoji} Изменить",
        "delete": "{emoji} Удалить",
        "more": "Ещё...",
        "loading": "⏳ Загрузка...",
        "error": "❌ Ошибка",
        "success": "✅ Успешно",
        "locked": "🔒 Недоступно",
        "premium": "⭐ Premium",
        "page": "Страница {current}/{total}"
    }


# Декораторы для клавиатур
def keyboard_error_handler(default_keyboard: Optional[callable] = None):
    """
    Декоратор для обработки ошибок при создании клавиатур.

    Args:
        default_keyboard: Функция для создания клавиатуры по умолчанию
    """

    def decorator(func):
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                logger.error(f"Ошибка в {func.__name__}: {e}")

                if default_keyboard:
                    return await default_keyboard()

                # Возвращаем минимальную клавиатуру с кнопкой назад
                keyboard = InlineKeyboard()
                keyboard.add_back_button()
                return await keyboard.build()

        return wrapper

    return decorator


# Функция инициализации модуля
def init_keyboards():
    """Инициализировать модуль клавиатур."""
    logger.info("Модуль клавиатур инициализирован")

    # Проверяем импорты
    modules = [
        "base", "main_menu", "tarot",
        "astrology", "subscription"
    ]

    for module in modules:
        try:
            __import__(f"infrastructure.telegram.keyboards.{module}")
            logger.debug(f"Модуль {module} загружен успешно")
        except ImportError as e:
            logger.error(f"Ошибка загрузки модуля {module}: {e}")


# Экспорт всех компонентов
__all__ = [
    # Фабрики
    "Keyboards",
    "ContextKeyboards",
    "KeyboardUtils",
    "KeyboardConstants",

    # Базовые классы
    "BaseKeyboard",
    "InlineKeyboard",
    "ReplyKeyboard",
    "PaginatedKeyboard",
    "DynamicMenu",
    "ConfirmationKeyboard",
    "KeyboardFactory",

    # Главное меню
    "MainMenuKeyboard",
    "QuickActionsKeyboard",
    "SectionMenuKeyboard",
    "WelcomeKeyboard",
    "TimeBasedGreetingKeyboard",
    "MainMenuSection",
    "QuickActionType",

    # Таро
    "SpreadSelectionKeyboard",
    "CardSelectionKeyboard",
    "ReadingResultKeyboard",
    "TarotHistoryKeyboard",
    "CardDetailKeyboard",
    "TarotLearningKeyboard",
    "TarotSection",
    "SpreadType",
    "CardSuit",

    # Астрология
    "BirthDataKeyboard",
    "HoroscopeMenuKeyboard",
    "NatalChartKeyboard",
    "ChartSettingsKeyboard",
    "TransitsKeyboard",
    "SynastryKeyboard",
    "LunarCalendarKeyboard",
    "AstrologySection",
    "HoroscopeType",
    "HouseSystem",

    # Подписка
    "SubscriptionPlansKeyboard",
    "PaymentMethodKeyboard",
    "CurrentSubscriptionKeyboard",
    "PromoCodeKeyboard",
    "PaymentHistoryKeyboard",
    "SubscriptionPlan",
    "PaymentProvider",
    "PaymentPeriod",

    # Callback Data
    "BaseCallbackData",
    "PaginationCallbackData",
    "MenuCallbackData",
    "ConfirmCallbackData",
    "RefreshCallbackData",  # ДОБАВЛЕН В ЭКСПОРТ
    "MainMenuCallbackData",
    "QuickActionCallbackData",
    "TarotCallbackData",
    "SpreadCallbackData",
    "CardCallbackData",
    "AstrologyCallbackData",
    "BirthDataCallbackData",
    "SubscriptionCallbackData",
    "PaymentCallbackData",

    # Функции
    "get_main_menu",
    "get_section_menu",
    "get_welcome_keyboard",
    "get_birth_data_keyboard",
    "get_promo_code_keyboard",

    # Утилиты
    "parse_callback_data",
    "build_callback_data",
    "keyboard_error_handler"
]

# Инициализация при импорте
init_keyboards()
logger.info("Модуль клавиатур Telegram бота загружен полностью")