"""
Модуль клавиатур главного меню.

Этот модуль содержит:
- Главное меню с адаптацией под уровень подписки
- Быстрые действия для частых операций
- Индикаторы новых функций
- Персонализированные элементы
- Контекстные подсказки

Автор: AI Assistant
Дата создания: 2024-12-30
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, time
from enum import Enum

from aiogram.types import ReplyKeyboardMarkup, InlineKeyboardMarkup
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder

from .base import (
    BaseKeyboard, ReplyKeyboard, InlineKeyboard,
    ButtonStyle, ButtonConfig, MenuCallbackData,
    BaseCallbackData
)

# Настройка логирования
logger = logging.getLogger(__name__)


class MainMenuSection(Enum):
    """Секции главного меню."""
    TAROT = "tarot"
    ASTROLOGY = "astrology"
    SUBSCRIPTION = "subscription"
    PROFILE = "profile"
    HELP = "help"
    SETTINGS = "settings"
    ADMIN = "admin"


class QuickActionType(Enum):
    """Типы быстрых действий."""
    DAILY_CARD = "daily_card"
    DAILY_HOROSCOPE = "daily_horoscope"
    QUICK_SPREAD = "quick_spread"
    MOON_PHASE = "moon_phase"


class MainMenuCallbackData(BaseCallbackData, prefix="main"):
    """Callback data для главного меню."""
    section: str
    subsection: Optional[str] = None


class QuickActionCallbackData(BaseCallbackData, prefix="quick"):
    """Callback data для быстрых действий."""
    action_type: str
    extra: Optional[str] = None


class MainMenuKeyboard(ReplyKeyboard):
    """Клавиатура главного меню."""

    def __init__(
            self,
            user_subscription: Optional[str] = None,
            is_admin: bool = False,
            show_notifications: bool = True,
            user_name: Optional[str] = None
    ):
        """
        Инициализация главного меню.

        Args:
            user_subscription: Уровень подписки пользователя
            is_admin: Является ли пользователь администратором
            show_notifications: Показывать ли индикаторы уведомлений
            user_name: Имя пользователя для персонализации
        """
        super().__init__(resize_keyboard=True, one_time_keyboard=False)
        self.user_subscription = user_subscription or "free"
        self.is_admin = is_admin
        self.show_notifications = show_notifications
        self.user_name = user_name

        logger.debug(
            f"Создание главного меню: подписка={user_subscription}, "
            f"админ={is_admin}, имя={user_name}"
        )

    async def build(self, **kwargs) -> ReplyKeyboardMarkup:
        """Построить главное меню."""
        # Основные разделы
        self._add_main_sections()

        # Дополнительные разделы для подписчиков
        if self.user_subscription in ["basic", "premium", "vip"]:
            self._add_subscriber_sections()

        # Админ-панель
        if self.is_admin:
            self._add_admin_section()

        # Настройка сетки кнопок
        self._adjust_layout()

        return await super().build(**kwargs)

    def _add_main_sections(self) -> None:
        """Добавить основные разделы меню."""
        # Таро с индикатором новой карты дня
        tarot_text = "🎴 Таро"
        if self.show_notifications and self._has_new_daily_card():
            tarot_text += " 🔴"
        self.add_button(tarot_text)

        # Астрология
        astro_text = "🔮 Астрология"
        if self.show_notifications and self._has_astrological_event():
            astro_text += " ✨"
        self.add_button(astro_text)

        # Подписка с индикатором уровня
        subscription_emoji = self._get_subscription_emoji()
        self.add_button(f"{subscription_emoji} Подписка")

        # Профиль
        self.add_button("👤 Профиль")

        # Помощь и настройки
        self.add_button("ℹ️ Помощь")
        self.add_button("⚙️ Настройки")

    def _add_subscriber_sections(self) -> None:
        """Добавить разделы для подписчиков."""
        if self.user_subscription in ["premium", "vip"]:
            # Эксклюзивные функции для премиум
            self.add_button("⭐ Эксклюзив")

        if self.user_subscription == "vip":
            # VIP функции
            self.add_button("👑 VIP Зона")

    def _add_admin_section(self) -> None:
        """Добавить админ-раздел."""
        self.add_button("🛠 Админ-панель")

    def _adjust_layout(self) -> None:
        """Настроить расположение кнопок."""
        # Основная сетка 2x3
        self.builder.adjust(2, 2, 2)

        # Дополнительные кнопки в отдельных рядах
        if self.user_subscription in ["premium", "vip"]:
            if self.user_subscription == "vip" and self.is_admin:
                # VIP + Admin в одном ряду
                self.builder.adjust(2, 2, 2, 2, 2)
            else:
                # Отдельный ряд для премиум функций
                self.builder.adjust(2, 2, 2, 1)

    def _get_subscription_emoji(self) -> str:
        """Получить эмодзи для уровня подписки."""
        emojis = {
            "free": "💳",
            "basic": "🥉",
            "premium": "🥈",
            "vip": "🥇"
        }
        return emojis.get(self.user_subscription, "💳")

    def _has_new_daily_card(self) -> bool:
        """Проверить, есть ли новая карта дня."""
        # Здесь должна быть реальная проверка из БД
        # Сейчас проверяем по времени
        current_hour = datetime.now().hour
        return 6 <= current_hour <= 10  # Утренние часы

    def _has_astrological_event(self) -> bool:
        """Проверить, есть ли важное астрологическое событие."""
        # Здесь должна быть реальная проверка
        # Например, полнолуние, ретроградный Меркурий и т.д.
        return False


class QuickActionsKeyboard(InlineKeyboard):
    """Клавиатура быстрых действий."""

    def __init__(
            self,
            user_subscription: str = "free",
            current_context: Optional[str] = None
    ):
        """
        Инициализация быстрых действий.

        Args:
            user_subscription: Уровень подписки
            current_context: Текущий контекст (tarot/astrology)
        """
        super().__init__()
        self.user_subscription = user_subscription
        self.current_context = current_context

    async def build(self, **kwargs) -> InlineKeyboardMarkup:
        """Построить клавиатуру быстрых действий."""
        # Карта дня - доступна всем
        self.add_button(
            text="🎴 Карта дня",
            callback_data=QuickActionCallbackData(
                action="execute",
                value=QuickActionType.DAILY_CARD.value
            )
        )

        # Гороскоп дня - доступен всем
        self.add_button(
            text="⭐ Гороскоп дня",
            callback_data=QuickActionCallbackData(
                action="execute",
                value=QuickActionType.DAILY_HOROSCOPE.value
            )
        )

        # Быстрый расклад - для подписчиков
        if self.user_subscription != "free":
            self.add_button(
                text="🔮 Быстрый расклад",
                callback_data=QuickActionCallbackData(
                    action="execute",
                    value=QuickActionType.QUICK_SPREAD.value
                )
            )

        # Фаза луны - для премиум
        if self.user_subscription in ["premium", "vip"]:
            self.add_button(
                text="🌙 Фаза луны",
                callback_data=QuickActionCallbackData(
                    action="execute",
                    value=QuickActionType.MOON_PHASE.value
                )
            )

        # Настройка сетки
        if self.user_subscription == "free":
            self.builder.adjust(2)
        else:
            self.builder.adjust(2, 2)

        return await super().build(**kwargs)


class SectionMenuKeyboard(InlineKeyboard):
    """Клавиатура подразделов."""

    def __init__(
            self,
            section: MainMenuSection,
            user_subscription: str = "free"
    ):
        """
        Инициализация меню раздела.

        Args:
            section: Раздел меню
            user_subscription: Уровень подписки
        """
        super().__init__()
        self.section = section
        self.user_subscription = user_subscription

    async def build(self, **kwargs) -> InlineKeyboardMarkup:
        """Построить меню раздела."""
        if self.section == MainMenuSection.TAROT:
            await self._build_tarot_menu()
        elif self.section == MainMenuSection.ASTROLOGY:
            await self._build_astrology_menu()
        elif self.section == MainMenuSection.SUBSCRIPTION:
            await self._build_subscription_menu()
        elif self.section == MainMenuSection.PROFILE:
            await self._build_profile_menu()
        elif self.section == MainMenuSection.SETTINGS:
            await self._build_settings_menu()

        # Кнопка назад
        self.add_back_button("main_menu")

        return await super().build(**kwargs)

    async def _build_tarot_menu(self) -> None:
        """Построить меню Таро."""
        # Основные функции
        self.add_button(
            text="🎴 Карта дня",
            callback_data=MainMenuCallbackData(
                action="select",
                value=self.section.value,
                page="daily_card"
            )
        )

        self.add_button(
            text="🔮 Расклады",
            callback_data=MainMenuCallbackData(
                action="select",
                value=self.section.value,
                page="spreads"
            )
        )

        # История - для всех
        self.add_button(
            text="📚 История",
            callback_data=MainMenuCallbackData(
                action="select",
                value=self.section.value,
                page="history"
            )
        )

        # Обучение - для подписчиков
        if self.user_subscription != "free":
            self.add_button(
                text="🎓 Обучение",
                callback_data=MainMenuCallbackData(
                    action="select",
                    value=self.section.value,
                    page="learning"
                )
            )

        # Избранное - для премиум
        if self.user_subscription in ["premium", "vip"]:
            self.add_button(
                text="⭐ Избранное",
                callback_data=MainMenuCallbackData(
                    action="select",
                    value=self.section.value,
                    page="favorites"
                )
            )

        self.builder.adjust(2)

    async def _build_astrology_menu(self) -> None:
        """Построить меню Астрологии."""
        # Гороскоп - для всех
        self.add_button(
            text="📅 Гороскоп",
            callback_data=MainMenuCallbackData(
                action="select",
                value=self.section.value,
                page="horoscope"
            )
        )

        # Натальная карта - для подписчиков
        if self.user_subscription != "free":
            self.add_button(
                text="🗺 Натальная карта",
                callback_data=MainMenuCallbackData(
                    action="select",
                    value=self.section.value,
                    page="natal_chart"
                )
            )

        # Транзиты - для премиум
        if self.user_subscription in ["premium", "vip"]:
            self.add_button(
                text="🌌 Транзиты",
                callback_data=MainMenuCallbackData(
                    action="select",
                    value=self.section.value,
                    page="transits"
                )
            )

            self.add_button(
                text="💑 Синастрия",
                callback_data=MainMenuCallbackData(
                    action="select",
                    value=self.section.value,
                    page="synastry"
                )
            )

        # Календарь - для VIP
        if self.user_subscription == "vip":
            self.add_button(
                text="📆 Личный календарь",
                callback_data=MainMenuCallbackData(
                    action="select",
                    value=self.section.value,
                    page="personal_calendar"
                )
            )

        self.builder.adjust(2)

    async def _build_subscription_menu(self) -> None:
        """Построить меню подписки."""
        self.add_button(
            text="💎 Тарифы",
            callback_data=MainMenuCallbackData(
                action="select",
                value=self.section.value,
                page="plans"
            )
        )

        if self.user_subscription != "free":
            self.add_button(
                text="📊 Моя подписка",
                callback_data=MainMenuCallbackData(
                    action="select",
                    value=self.section.value,
                    page="my_subscription"
                )
            )

            self.add_button(
                text="💳 Способы оплаты",
                callback_data=MainMenuCallbackData(
                    action="select",
                    value=self.section.value,
                    page="payment_methods"
                )
            )

        self.add_button(
            text="🎁 Промокод",
            callback_data=MainMenuCallbackData(
                action="select",
                value=self.section.value,
                page="promo"
            )
        )

        self.builder.adjust(2)

    async def _build_profile_menu(self) -> None:
        """Построить меню профиля."""
        self.add_button(
            text="📋 Мои данные",
            callback_data=MainMenuCallbackData(
                action="select",
                value=self.section.value,
                page="my_data"
            )
        )

        self.add_button(
            text="🎂 Данные рождения",
            callback_data=MainMenuCallbackData(
                action="select",
                value=self.section.value,
                page="birth_data"
            )
        )

        self.add_button(
            text="📈 Статистика",
            callback_data=MainMenuCallbackData(
                action="select",
                value=self.section.value,
                page="statistics"
            )
        )

        if self.user_subscription != "free":
            self.add_button(
                text="🏆 Достижения",
                callback_data=MainMenuCallbackData(
                    action="select",
                    value=self.section.value,
                    page="achievements"
                )
            )

        self.builder.adjust(2)

    async def _build_settings_menu(self) -> None:
        """Построить меню настроек."""
        self.add_button(
            text="🔔 Уведомления",
            callback_data=MainMenuCallbackData(
                action="select",
                value=self.section.value,
                page="notifications"
            )
        )

        self.add_button(
            text="🌍 Язык",
            callback_data=MainMenuCallbackData(
                action="select",
                value=self.section.value,
                page="language"
            )
        )

        self.add_button(
            text="🎨 Оформление",
            callback_data=MainMenuCallbackData(
                action="select",
                value=self.section.value,
                page="theme"
            )
        )

        self.add_button(
            text="🔐 Конфиденциальность",
            callback_data=MainMenuCallbackData(
                action="select",
                value=self.section.value,
                page="privacy"
            )
        )

        self.builder.adjust(2)


class WelcomeKeyboard(InlineKeyboard):
    """Клавиатура приветствия для новых пользователей."""

    def __init__(self, user_name: Optional[str] = None):
        """
        Инициализация приветственной клавиатуры.

        Args:
            user_name: Имя пользователя
        """
        super().__init__()
        self.user_name = user_name

    async def build(self, **kwargs) -> InlineKeyboardMarkup:
        """Построить приветственную клавиатуру."""
        # Персонализированное приветствие
        greeting = f"Привет, {self.user_name}! 👋" if self.user_name else "Добро пожаловать! 👋"

        # Начать знакомство
        self.add_button(
            text="🚀 Начать знакомство",
            callback_data="welcome:start"
        )

        # Быстрый старт
        self.add_button(
            text="⚡ Быстрый старт",
            callback_data="welcome:quick_start"
        )

        # О боте
        self.add_button(
            text="ℹ️ О боте",
            callback_data="welcome:about"
        )

        # Ввести промокод
        self.add_button(
            text="🎁 У меня есть промокод",
            callback_data="welcome:promo"
        )

        self.builder.adjust(1, 2, 1)

        return await super().build(**kwargs)


class TimeBasedGreetingKeyboard(InlineKeyboard):
    """Клавиатура с приветствием в зависимости от времени суток."""

    def __init__(self, user_name: Optional[str] = None):
        """
        Инициализация клавиатуры с временным приветствием.

        Args:
            user_name: Имя пользователя
        """
        super().__init__()
        self.user_name = user_name
        self.current_hour = datetime.now().hour

    def _get_time_greeting(self) -> str:
        """Получить приветствие по времени суток."""
        if 5 <= self.current_hour < 12:
            return "Доброе утро"
        elif 12 <= self.current_hour < 17:
            return "Добрый день"
        elif 17 <= self.current_hour < 22:
            return "Добрый вечер"
        else:
            return "Доброй ночи"

    def _get_time_suggestion(self) -> Dict[str, str]:
        """Получить предложение действия по времени."""
        if 6 <= self.current_hour < 10:
            return {
                "text": "☀️ Утренняя карта",
                "action": "morning_card"
            }
        elif 12 <= self.current_hour < 14:
            return {
                "text": "🌞 Дневной прогноз",
                "action": "day_forecast"
            }
        elif 18 <= self.current_hour < 21:
            return {
                "text": "🌙 Вечерняя медитация",
                "action": "evening_meditation"
            }
        elif 21 <= self.current_hour < 24:
            return {
                "text": "✨ Расклад на завтра",
                "action": "tomorrow_spread"
            }
        else:
            return {
                "text": "🔮 Ночной оракул",
                "action": "night_oracle"
            }

    async def build(self, **kwargs) -> InlineKeyboardMarkup:
        """Построить клавиатуру с временным приветствием."""
        # Временное предложение
        suggestion = self._get_time_suggestion()
        self.add_button(
            text=suggestion["text"],
            callback_data=f"time_action:{suggestion['action']}"
        )

        # Стандартные действия
        self.add_button(
            text="🎴 Карта дня",
            callback_data="quick:daily_card"
        )

        self.add_button(
            text="⭐ Гороскоп",
            callback_data="quick:horoscope"
        )

        self.builder.adjust(1, 2)

        return await super().build(**kwargs)


# Функции для быстрого создания меню
async def get_main_menu(
        user_subscription: str = "free",
        is_admin: bool = False,
        user_name: Optional[str] = None
) -> ReplyKeyboardMarkup:
    """
    Получить главное меню.

    Args:
        user_subscription: Уровень подписки
        is_admin: Является ли администратором
        user_name: Имя пользователя

    Returns:
        Клавиатура главного меню
    """
    keyboard = MainMenuKeyboard(
        user_subscription=user_subscription,
        is_admin=is_admin,
        user_name=user_name
    )
    return await keyboard.build()


async def get_section_menu(
        section: MainMenuSection,
        user_subscription: str = "free"
) -> InlineKeyboardMarkup:
    """
    Получить меню раздела.

    Args:
        section: Раздел меню
        user_subscription: Уровень подписки

    Returns:
        Клавиатура раздела
    """
    keyboard = SectionMenuKeyboard(section, user_subscription)
    return await keyboard.build()


async def get_welcome_keyboard(user_name: Optional[str] = None) -> InlineKeyboardMarkup:
    """
    Получить приветственную клавиатуру.

    Args:
        user_name: Имя пользователя

    Returns:
        Приветственная клавиатура
    """
    keyboard = WelcomeKeyboard(user_name)
    return await keyboard.build()


logger.info("Модуль клавиатур главного меню загружен")