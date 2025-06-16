"""
Модуль клавиатур для раздела Таро.

Этот модуль содержит:
- Клавиатуры выбора раскладов
- Интерактивный выбор карт
- Управление историей раскладов
- Клавиатуры для интерпретаций
- Обучающие элементы

Автор: AI Assistant
Дата создания: 2024-12-30
"""

import logging
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
from enum import Enum

from aiogram.types import InlineKeyboardMarkup
from aiogram.filters.callback_data import CallbackData

from .base import (
    InlineKeyboard, PaginatedKeyboard, DynamicMenu,
    ButtonConfig, ButtonStyle
)

# Настройка логирования
logger = logging.getLogger(__name__)


class TarotSection(Enum):
    """Разделы Таро."""
    DAILY_CARD = "daily_card"
    SPREADS = "spreads"
    HISTORY = "history"
    LEARNING = "learning"
    FAVORITES = "favorites"
    DECK_BROWSER = "deck_browser"


class SpreadType(Enum):
    """Типы раскладов."""
    # Бесплатные расклады
    ONE_CARD = "one_card"
    THREE_CARDS = "three_cards"

    # Базовая подписка
    CELTIC_CROSS = "celtic_cross"
    RELATIONSHIP = "relationship"
    CAREER = "career"

    # Премиум подписка
    YEAR_AHEAD = "year_ahead"
    CHAKRAS = "chakras"
    SHADOW_WORK = "shadow_work"
    LIFE_PURPOSE = "life_purpose"

    # VIP подписка
    GRAND_TABLEAU = "grand_tableau"
    ASTROLOGICAL = "astrological"
    CUSTOM = "custom"


class CardSuit(Enum):
    """Масти карт Таро."""
    MAJOR_ARCANA = "major"
    WANDS = "wands"
    CUPS = "cups"
    SWORDS = "swords"
    PENTACLES = "pentacles"


# Callback Data классы
class TarotCallbackData(CallbackData, prefix="tarot"):
    """Основной callback для Таро."""
    action: str  # select, view, draw, interpret
    section: Optional[str] = None
    value: Optional[str] = None
    extra: Optional[str] = None


class SpreadCallbackData(CallbackData, prefix="spread"):
    """Callback для раскладов."""
    action: str  # select, start, position, complete
    spread_type: str
    position: Optional[int] = None
    reading_id: Optional[str] = None


class CardCallbackData(CallbackData, prefix="card"):
    """Callback для карт."""
    action: str  # select, view, flip, favorite
    card_id: Optional[int] = None
    suit: Optional[str] = None
    position: Optional[int] = None
    is_reversed: Optional[bool] = None


class HistoryCallbackData(CallbackData, prefix="history"):
    """Callback для истории."""
    action: str  # view, delete, favorite, share
    reading_id: str
    page: Optional[int] = None


class SpreadSelectionKeyboard(InlineKeyboard):
    """Клавиатура выбора расклада."""

    # Информация о раскладах
    SPREAD_INFO = {
        SpreadType.ONE_CARD: {
            "name": "Карта дня",
            "emoji": "🎴",
            "description": "Совет или предупреждение на сегодня",
            "positions": 1,
            "duration": "2-3 мин",
            "level": "free"
        },
        SpreadType.THREE_CARDS: {
            "name": "Три карты",
            "emoji": "🎯",
            "description": "Прошлое - Настоящее - Будущее",
            "positions": 3,
            "duration": "5-7 мин",
            "level": "free"
        },
        SpreadType.CELTIC_CROSS: {
            "name": "Кельтский крест",
            "emoji": "✨",
            "description": "Классический подробный расклад",
            "positions": 10,
            "duration": "15-20 мин",
            "level": "basic"
        },
        SpreadType.RELATIONSHIP: {
            "name": "Отношения",
            "emoji": "💕",
            "description": "Анализ отношений и совместимости",
            "positions": 7,
            "duration": "10-15 мин",
            "level": "basic"
        },
        SpreadType.CAREER: {
            "name": "Карьера",
            "emoji": "💼",
            "description": "Профессиональный путь и финансы",
            "positions": 6,
            "duration": "10-12 мин",
            "level": "basic"
        },
        SpreadType.YEAR_AHEAD: {
            "name": "Год вперед",
            "emoji": "📅",
            "description": "Прогноз на 12 месяцев",
            "positions": 13,
            "duration": "25-30 мин",
            "level": "premium"
        },
        SpreadType.CHAKRAS: {
            "name": "Чакры",
            "emoji": "🧘",
            "description": "Энергетический баланс",
            "positions": 7,
            "duration": "15-20 мин",
            "level": "premium"
        },
        SpreadType.SHADOW_WORK: {
            "name": "Работа с тенью",
            "emoji": "🌑",
            "description": "Глубинная психология",
            "positions": 8,
            "duration": "20-25 мин",
            "level": "premium"
        },
        SpreadType.LIFE_PURPOSE: {
            "name": "Жизненное предназначение",
            "emoji": "🌟",
            "description": "Ваш путь и миссия",
            "positions": 9,
            "duration": "20-25 мин",
            "level": "premium"
        },
        SpreadType.GRAND_TABLEAU: {
            "name": "Большой расклад",
            "emoji": "👑",
            "description": "Полный анализ всех сфер жизни",
            "positions": 36,
            "duration": "45-60 мин",
            "level": "vip"
        },
        SpreadType.ASTROLOGICAL: {
            "name": "Астрологический",
            "emoji": "🌌",
            "description": "Расклад по домам гороскопа",
            "positions": 12,
            "duration": "30-40 мин",
            "level": "vip"
        }
    }

    def __init__(
            self,
            user_subscription: str = "free",
            show_descriptions: bool = True,
            category_filter: Optional[str] = None
    ):
        """
        Инициализация клавиатуры выбора расклада.

        Args:
            user_subscription: Уровень подписки пользователя
            show_descriptions: Показывать ли описания
            category_filter: Фильтр по категории
        """
        super().__init__()
        self.user_subscription = user_subscription
        self.show_descriptions = show_descriptions
        self.category_filter = category_filter

        logger.debug(f"Создание клавиатуры раскладов для подписки {user_subscription}")

    def _get_available_spreads(self) -> List[SpreadType]:
        """Получить доступные расклады для уровня подписки."""
        subscription_levels = {
            "free": ["free"],
            "basic": ["free", "basic"],
            "premium": ["free", "basic", "premium"],
            "vip": ["free", "basic", "premium", "vip"]
        }

        allowed_levels = subscription_levels.get(self.user_subscription, ["free"])

        available = []
        for spread_type, info in self.SPREAD_INFO.items():
            if info["level"] in allowed_levels:
                if not self.category_filter or self._matches_category(spread_type):
                    available.append(spread_type)

        return available

    def _matches_category(self, spread_type: SpreadType) -> bool:
        """Проверить, соответствует ли расклад категории."""
        categories = {
            "quick": [SpreadType.ONE_CARD, SpreadType.THREE_CARDS],
            "relationship": [SpreadType.RELATIONSHIP],
            "career": [SpreadType.CAREER],
            "spiritual": [SpreadType.CHAKRAS, SpreadType.SHADOW_WORK, SpreadType.LIFE_PURPOSE],
            "complex": [SpreadType.CELTIC_CROSS, SpreadType.GRAND_TABLEAU, SpreadType.ASTROLOGICAL]
        }

        return spread_type in categories.get(self.category_filter, [])

    async def build(self, **kwargs) -> InlineKeyboardMarkup:
        """Построить клавиатуру выбора расклада."""
        available_spreads = self._get_available_spreads()

        for spread_type in available_spreads:
            info = self.SPREAD_INFO[spread_type]

            # Текст кнопки
            button_text = f"{info['emoji']} {info['name']}"

            # Добавляем информацию о количестве карт и времени
            if self.show_descriptions:
                button_text += f" ({info['positions']} карт)"

            self.add_button(
                text=button_text,
                callback_data=SpreadCallbackData(
                    action="select",
                    spread_type=spread_type.value
                )
            )

        # Добавляем недоступные расклады с блокировкой
        locked_spreads = self._get_locked_spreads()
        for spread_type in locked_spreads:
            info = self.SPREAD_INFO[spread_type]
            button_text = f"🔒 {info['name']}"

            self.add_button(
                text=button_text,
                callback_data=SpreadCallbackData(
                    action="locked",
                    spread_type=spread_type.value
                )
            )

        # Настройка сетки
        self.builder.adjust(1)

        # Категории раскладов (если не применен фильтр)
        if not self.category_filter:
            self._add_category_buttons()

        # Кнопка назад
        self.add_back_button("tarot:main")

        return await super().build(**kwargs)

    def _get_locked_spreads(self) -> List[SpreadType]:
        """Получить заблокированные расклады."""
        all_spreads = set(self.SPREAD_INFO.keys())
        available = set(self._get_available_spreads())
        locked = list(all_spreads - available)

        # Показываем только несколько заблокированных для мотивации
        return locked[:2]

    def _add_category_buttons(self) -> None:
        """Добавить кнопки категорий."""
        self.builder.adjust(1)  # Предыдущие кнопки в один столбец

        # Добавляем разделитель
        self.add_button(
            text="— Категории —",
            callback_data="noop"
        )

        categories = [
            ("⚡ Быстрые", "quick"),
            ("💕 Отношения", "relationship"),
            ("💼 Карьера", "career"),
            ("🧘 Духовные", "spiritual")
        ]

        for text, category in categories:
            self.add_button(
                text=text,
                callback_data=f"tarot:category:{category}"
            )

        self.builder.adjust(1, 1, 2, 2)  # Категории по 2 в ряд


class CardSelectionKeyboard(PaginatedKeyboard):
    """Клавиатура выбора карт для расклада."""

    def __init__(
            self,
            spread_type: SpreadType,
            position: int,
            total_positions: int,
            selected_cards: List[int],
            suit_filter: Optional[CardSuit] = None,
            page: int = 1
    ):
        """
        Инициализация клавиатуры выбора карт.

        Args:
            spread_type: Тип расклада
            position: Текущая позиция
            total_positions: Всего позиций
            selected_cards: Уже выбранные карты
            suit_filter: Фильтр по масти
            page: Текущая страница
        """
        # Генерируем список доступных карт
        available_cards = self._get_available_cards(selected_cards, suit_filter)

        super().__init__(
            items=available_cards,
            page_size=8,
            current_page=page,
            menu_type="card_selection"
        )

        self.spread_type = spread_type
        self.position = position
        self.total_positions = total_positions
        self.suit_filter = suit_filter

    def _get_available_cards(
            self,
            selected_cards: List[int],
            suit_filter: Optional[CardSuit]
    ) -> List[Dict[str, Any]]:
        """Получить список доступных карт."""
        # Здесь должна быть реальная загрузка из БД
        # Сейчас генерируем тестовые данные

        cards = []

        # Старшие арканы
        if not suit_filter or suit_filter == CardSuit.MAJOR_ARCANA:
            major_arcana = [
                {"id": 0, "name": "Дурак", "suit": "major"},
                {"id": 1, "name": "Маг", "suit": "major"},
                {"id": 2, "name": "Верховная Жрица", "suit": "major"},
                {"id": 3, "name": "Императрица", "suit": "major"},
                {"id": 4, "name": "Император", "suit": "major"},
                {"id": 5, "name": "Иерофант", "suit": "major"},
                {"id": 6, "name": "Влюбленные", "suit": "major"},
                {"id": 7, "name": "Колесница", "suit": "major"},
                {"id": 8, "name": "Сила", "suit": "major"},
                {"id": 9, "name": "Отшельник", "suit": "major"},
                {"id": 10, "name": "Колесо Фортуны", "suit": "major"},
                # И так далее...
            ]
            cards.extend(major_arcana)

        # Фильтруем уже выбранные
        available = [c for c in cards if c["id"] not in selected_cards]

        return available

    async def build(self, **kwargs) -> InlineKeyboardMarkup:
        """Построить клавиатуру выбора карт."""
        # Заголовок с позицией
        self.add_button(
            text=f"Позиция {self.position} из {self.total_positions}",
            callback_data="noop"
        )

        # Карты текущей страницы
        page_cards = self.get_page_items()

        for card in page_cards:
            # Определяем эмодзи для масти
            suit_emoji = {
                "major": "🌟",
                "wands": "🔥",
                "cups": "💧",
                "swords": "⚔️",
                "pentacles": "💰"
            }.get(card["suit"], "🎴")

            self.add_button(
                text=f"{suit_emoji} {card['name']}",
                callback_data=CardCallbackData(
                    action="select",
                    card_id=card["id"],
                    position=self.position
                )
            )

        # Настройка сетки для карт
        self.builder.adjust(1, 2, 2, 2, 2)  # Заголовок отдельно, карты по 2

        # Фильтры по мастям
        self._add_suit_filters()

        # Пагинация
        if self.total_pages > 1:
            self.add_pagination_buttons()

        # Случайная карта
        self.add_button(
            text="🎲 Случайная карта",
            callback_data=CardCallbackData(
                action="random",
                position=self.position
            )
        )

        # Отмена
        self.add_button(
            text="❌ Отменить расклад",
            callback_data=SpreadCallbackData(
                action="cancel",
                spread_type=self.spread_type.value
            )
        )

        return await super().build(**kwargs)

    def _add_suit_filters(self) -> None:
        """Добавить фильтры по мастям."""
        # Текущая позиция builder
        current_row_items = len(self.builder._markup)

        suit_buttons = [
            ("🌟", CardSuit.MAJOR_ARCANA),
            ("🔥", CardSuit.WANDS),
            ("💧", CardSuit.CUPS),
            ("⚔️", CardSuit.SWORDS),
            ("💰", CardSuit.PENTACLES)
        ]

        for emoji, suit in suit_buttons:
            # Выделяем активный фильтр
            text = f"[{emoji}]" if self.suit_filter == suit else emoji

            self.add_button(
                text=text,
                callback_data=f"card:filter:{suit.value}"
            )

        # Добавляем кнопку сброса фильтра
        if self.suit_filter:
            self.add_button(
                text="❌",
                callback_data="card:filter:none"
            )

            # 6 кнопок в ряд
            self.builder.adjust(*([2] * (current_row_items // 2)), 6)
        else:
            # 5 кнопок в ряд
            self.builder.adjust(*([2] * (current_row_items // 2)), 5)


class ReadingResultKeyboard(InlineKeyboard):
    """Клавиатура результата расклада."""

    def __init__(
            self,
            reading_id: str,
            spread_type: SpreadType,
            is_favorite: bool = False,
            can_save: bool = True,
            show_learning: bool = True
    ):
        """
        Инициализация клавиатуры результата.

        Args:
            reading_id: ID расклада
            spread_type: Тип расклада
            is_favorite: В избранном ли
            can_save: Можно ли сохранить
            show_learning: Показывать ли обучение
        """
        super().__init__()
        self.reading_id = reading_id
        self.spread_type = spread_type
        self.is_favorite = is_favorite
        self.can_save = can_save
        self.show_learning = show_learning

    async def build(self, **kwargs) -> InlineKeyboardMarkup:
        """Построить клавиатуру результата."""
        # Основные действия
        if self.can_save:
            favorite_text = "⭐ В избранном" if self.is_favorite else "⭐ В избранное"
            self.add_button(
                text=favorite_text,
                callback_data=HistoryCallbackData(
                    action="favorite",
                    reading_id=self.reading_id
                )
            )

        # Поделиться
        self.add_button(
            text="📤 Поделиться",
            callback_data=HistoryCallbackData(
                action="share",
                reading_id=self.reading_id
            )
        )

        # Детальный просмотр карт
        self.add_button(
            text="🔍 Подробнее о картах",
            callback_data=f"reading:cards:{self.reading_id}"
        )

        # Новый расклад
        self.add_button(
            text="🔄 Новый расклад",
            callback_data=SpreadCallbackData(
                action="new",
                spread_type=self.spread_type.value
            )
        )

        # Обучающие материалы
        if self.show_learning:
            self.add_button(
                text="📚 Узнать больше",
                callback_data=f"learning:spread:{self.spread_type.value}"
            )

        # Обратная связь
        self.add_button(
            text="💬 Оставить отзыв",
            callback_data=f"feedback:reading:{self.reading_id}"
        )

        # Настройка сетки
        self.builder.adjust(2, 1, 2, 1)

        return await super().build(**kwargs)


class TarotHistoryKeyboard(PaginatedKeyboard):
    """Клавиатура истории раскладов."""

    def __init__(
            self,
            readings: List[Dict[str, Any]],
            page: int = 1,
            filter_type: Optional[str] = None
    ):
        """
        Инициализация клавиатуры истории.

        Args:
            readings: Список раскладов
            page: Текущая страница
            filter_type: Фильтр по типу
        """
        super().__init__(
            items=readings,
            page_size=5,
            current_page=page,
            menu_type="tarot_history"
        )
        self.filter_type = filter_type

    async def build(self, **kwargs) -> InlineKeyboardMarkup:
        """Построить клавиатуру истории."""
        # Фильтры
        self._add_filters()

        # Расклады текущей страницы
        page_readings = self.get_page_items()

        if not page_readings:
            self.add_button(
                text="📭 История пуста",
                callback_data="noop"
            )
        else:
            for reading in page_readings:
                # Форматируем дату
                date_str = reading["created_at"].strftime("%d.%m %H:%M")
                spread_name = SpreadSelectionKeyboard.SPREAD_INFO.get(
                    SpreadType(reading["spread_type"]),
                    {"name": "Расклад", "emoji": "🎴"}
                )

                # Текст кнопки
                button_text = f"{spread_name['emoji']} {date_str} - {spread_name['name']}"
                if reading.get("is_favorite"):
                    button_text = f"⭐ {button_text}"

                self.add_button(
                    text=button_text,
                    callback_data=HistoryCallbackData(
                        action="view",
                        reading_id=reading["id"]
                    )
                )

        # Настройка сетки
        filter_count = 3 if not self.filter_type else 4
        self.builder.adjust(filter_count, *([1] * len(page_readings)))

        # Пагинация
        if self.total_pages > 1:
            self.add_pagination_buttons()

        # Статистика
        self.add_button(
            text="📊 Статистика",
            callback_data="tarot:statistics"
        )

        # Назад
        self.add_back_button("tarot:main")

        return await super().build(**kwargs)

    def _add_filters(self) -> None:
        """Добавить фильтры истории."""
        filters = [
            ("Все", None),
            ("⭐", "favorites"),
            ("🕐", "recent")
        ]

        if self.filter_type:
            filters.append(("❌", "clear"))

        for text, filter_value in filters:
            # Выделяем активный фильтр
            if filter_value == self.filter_type:
                text = f"[{text}]"

            callback_data = f"history:filter:{filter_value or 'all'}"
            self.add_button(text=text, callback_data=callback_data)


class CardDetailKeyboard(InlineKeyboard):
    """Клавиатура детального просмотра карты."""

    def __init__(
            self,
            card_id: int,
            card_name: str,
            is_reversed: bool = False,
            in_reading: bool = False,
            reading_id: Optional[str] = None,
            position: Optional[int] = None
    ):
        """
        Инициализация клавиатуры карты.

        Args:
            card_id: ID карты
            card_name: Название карты
            is_reversed: Перевернута ли
            in_reading: В контексте расклада
            reading_id: ID расклада
            position: Позиция в раскладе
        """
        super().__init__()
        self.card_id = card_id
        self.card_name = card_name
        self.is_reversed = is_reversed
        self.in_reading = in_reading
        self.reading_id = reading_id
        self.position = position

    async def build(self, **kwargs) -> InlineKeyboardMarkup:
        """Построить клавиатуру детального просмотра."""
        # Переворот карты
        flip_text = "🔄 Перевернуть" if not self.is_reversed else "🔄 Прямое положение"
        self.add_button(
            text=flip_text,
            callback_data=CardCallbackData(
                action="flip",
                card_id=self.card_id,
                is_reversed=not self.is_reversed
            )
        )

        # Значения
        self.add_button(
            text="📖 Все значения",
            callback_data=f"card:meanings:{self.card_id}"
        )

        # Обучение
        self.add_button(
            text="🎓 Изучить карту",
            callback_data=f"learning:card:{self.card_id}"
        )

        # В избранное
        self.add_button(
            text="⭐ В любимые карты",
            callback_data=f"card:favorite:{self.card_id}"
        )

        # Если в контексте расклада
        if self.in_reading and self.reading_id:
            # Вернуться к раскладу
            self.add_button(
                text="↩️ К раскладу",
                callback_data=f"reading:view:{self.reading_id}"
            )

            # Соседние карты
            if self.position and self.position > 1:
                self.add_button(
                    text="◀️",
                    callback_data=f"reading:card:{self.reading_id}:{self.position - 1}"
                )

            self.add_button(
                text=f"Позиция {self.position}",
                callback_data="noop"
            )

            # Здесь нужна проверка на максимальную позицию
            self.add_button(
                text="▶️",
                callback_data=f"reading:card:{self.reading_id}:{self.position + 1}"
            )
        else:
            # Назад к браузеру карт
            self.add_back_button("tarot:deck")

        # Настройка сетки
        if self.in_reading:
            self.builder.adjust(2, 2, 1, 3)
        else:
            self.builder.adjust(2, 2, 1)

        return await super().build(**kwargs)


class TarotLearningKeyboard(DynamicMenu):
    """Клавиатура обучающих материалов."""

    def __init__(self, section: Optional[str] = None):
        """
        Инициализация обучающего меню.

        Args:
            section: Текущий раздел обучения
        """
        menu_id = f"learning_{section}" if section else "learning_main"
        super().__init__(menu_id=menu_id, level=0 if not section else 1)
        self.section = section

    async def build(self, **kwargs) -> InlineKeyboardMarkup:
        """Построить обучающее меню."""
        if not self.section:
            # Главное меню обучения
            self.add_menu_item("basics", "Основы Таро", "📚")
            self.add_menu_item("major_arcana", "Старшие Арканы", "🌟", submenu=True)
            self.add_menu_item("minor_arcana", "Младшие Арканы", "🎴", submenu=True)
            self.add_menu_item("spreads", "Расклады", "📊", submenu=True)
            self.add_menu_item("interpretation", "Интерпретация", "🔮")
            self.add_menu_item("practice", "Практика", "🎯")
            self.add_menu_item("history", "История Таро", "📜")
            self.add_menu_item("ethics", "Этика гадания", "⚖️")

        elif self.section == "major_arcana":
            # Подменю Старших Арканов
            self.add_menu_item("fool_magician", "0-I: Дурак и Маг", "🎭")
            self.add_menu_item("priestess_empress", "II-III: Жрица и Императрица", "👑")
            self.add_menu_item("emperor_hierophant", "IV-V: Император и Иерофант", "🏛")
            # И так далее...

        # Навигация
        self.add_navigation_buttons(show_back=self.level > 0)

        return await super().build(**kwargs)


# Вспомогательные функции для быстрого создания клавиатур
async def get_spread_selection_keyboard(
        user_subscription: str = "free",
        category: Optional[str] = None
) -> InlineKeyboardMarkup:
    """Получить клавиатуру выбора расклада."""
    keyboard = SpreadSelectionKeyboard(
        user_subscription=user_subscription,
        category_filter=category
    )
    return await keyboard.build()


async def get_card_selection_keyboard(
        spread_type: SpreadType,
        position: int,
        total_positions: int,
        selected_cards: List[int],
        suit_filter: Optional[CardSuit] = None,
        page: int = 1
) -> InlineKeyboardMarkup:
    """Получить клавиатуру выбора карт."""
    keyboard = CardSelectionKeyboard(
        spread_type=spread_type,
        position=position,
        total_positions=total_positions,
        selected_cards=selected_cards,
        suit_filter=suit_filter,
        page=page
    )
    return await keyboard.build()


async def get_reading_result_keyboard(
        reading_id: str,
        spread_type: SpreadType,
        is_favorite: bool = False,
        can_save: bool = True
) -> InlineKeyboardMarkup:
    """Получить клавиатуру результата расклада."""
    keyboard = ReadingResultKeyboard(
        reading_id=reading_id,
        spread_type=spread_type,
        is_favorite=is_favorite,
        can_save=can_save
    )
    return await keyboard.build()


logger.info("Модуль клавиатур Таро загружен")