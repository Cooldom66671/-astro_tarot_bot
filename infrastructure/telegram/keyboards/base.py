"""
Модуль базовых компонентов для создания Telegram клавиатур.

Этот модуль предоставляет:
- Базовые классы для создания клавиатур
- Фабрику кнопок с преднастроенными стилями
- Систему callback data для обработки нажатий
- Пагинацию для длинных списков
- Динамические меню с состоянием
- Утилиты для работы с клавиатурами

Автор: AI Assistant
Дата создания: 2024-12-30
"""

import logging
from typing import List, Optional, Dict, Any, Callable, Union, Tuple
from dataclasses import dataclass, field
from enum import Enum
import json
from abc import ABC, abstractmethod

from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton,
    ReplyKeyboardRemove
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.filters.callback_data import CallbackData

# Настройка логирования
logger = logging.getLogger(__name__)


class ButtonStyle(Enum):
    """Стили кнопок для единообразного оформления."""
    PRIMARY = "primary"  # Основное действие
    SECONDARY = "secondary"  # Второстепенное действие
    SUCCESS = "success"  # Успешное действие
    DANGER = "danger"  # Опасное действие
    INFO = "info"  # Информационная кнопка
    BACK = "back"  # Кнопка назад
    CANCEL = "cancel"  # Кнопка отмены
    CONFIRM = "confirm"  # Кнопка подтверждения


@dataclass
class ButtonConfig:
    """Конфигурация кнопки."""
    text: str
    callback_data: Optional[Union[str, CallbackData]] = None
    url: Optional[str] = None
    style: ButtonStyle = ButtonStyle.PRIMARY
    row_width: int = 1
    emoji: Optional[str] = None

    def get_text(self) -> str:
        """Получить текст кнопки с эмодзи."""
        if self.emoji:
            return f"{self.emoji} {self.text}"

        # Автоматические эмодзи по стилю
        style_emojis = {
            ButtonStyle.PRIMARY: "🔵",
            ButtonStyle.SUCCESS: "✅",
            ButtonStyle.DANGER: "❌",
            ButtonStyle.INFO: "ℹ️",
            ButtonStyle.BACK: "◀️",
            ButtonStyle.CANCEL: "🚫",
            ButtonStyle.CONFIRM: "✔️"
        }

        if self.style in style_emojis:
            return f"{style_emojis[self.style]} {self.text}"

        return self.text


class BaseCallbackData(CallbackData, prefix="base"):
    """Базовый класс для callback data."""
    action: str
    value: Optional[str] = None
    page: Optional[int] = None


class PaginationCallbackData(CallbackData, prefix="page"):
    """Callback data для пагинации."""
    action: str  # next, prev, goto
    page: int
    total: int
    menu_type: str


class MenuCallbackData(CallbackData, prefix="menu"):
    """Callback data для меню."""
    action: str  # select, back, close
    menu_id: str
    item_id: Optional[str] = None
    level: int = 0


class ConfirmCallbackData(CallbackData, prefix="confirm"):
    """Callback data для подтверждения."""
    action: str  # yes, no
    target: str
    value: Optional[str] = None


class BaseKeyboard(ABC):
    """Базовый абстрактный класс для всех клавиатур."""

    def __init__(self):
        """Инициализация базовой клавиатуры."""
        self.builder = None
        logger.debug(f"Инициализирована клавиатура {self.__class__.__name__}")

    @abstractmethod
    async def build(self, **kwargs) -> Union[InlineKeyboardMarkup, ReplyKeyboardMarkup]:
        """Построить клавиатуру."""
        pass

    def add_back_button(self, callback_data: str = "back") -> None:
        """Добавить кнопку 'Назад'."""
        if isinstance(self.builder, InlineKeyboardBuilder):
            self.builder.button(
                text="◀️ Назад",
                callback_data=callback_data
            )

    def add_cancel_button(self, callback_data: str = "cancel") -> None:
        """Добавить кнопку 'Отмена'."""
        if isinstance(self.builder, InlineKeyboardBuilder):
            self.builder.button(
                text="🚫 Отмена",
                callback_data=callback_data
            )


class InlineKeyboard(BaseKeyboard):
    """Базовый класс для inline клавиатур."""

    def __init__(self):
        """Инициализация inline клавиатуры."""
        super().__init__()
        self.builder = InlineKeyboardBuilder()

    async def build(self, **kwargs) -> InlineKeyboardMarkup:
        """Построить inline клавиатуру."""
        return self.builder.as_markup()

    def add_button(
            self,
            text: str,
            callback_data: Optional[Union[str, CallbackData]] = None,
            url: Optional[str] = None,
            row_width: int = 1
    ) -> None:
        """Добавить кнопку в клавиатуру."""
        button = InlineKeyboardButton(text=text)

        if callback_data:
            if isinstance(callback_data, CallbackData):
                button.callback_data = callback_data.pack()
            else:
                button.callback_data = callback_data
        elif url:
            button.url = url
        else:
            raise ValueError("Необходимо указать callback_data или url")

        self.builder.add(button)

        if row_width > 1:
            self.builder.adjust(row_width)

    def add_buttons_from_config(self, configs: List[ButtonConfig]) -> None:
        """Добавить кнопки из конфигурации."""
        for config in configs:
            self.add_button(
                text=config.get_text(),
                callback_data=config.callback_data,
                url=config.url,
                row_width=config.row_width
            )


class ReplyKeyboard(BaseKeyboard):
    """Базовый класс для reply клавиатур."""

    def __init__(self, resize_keyboard: bool = True, one_time_keyboard: bool = False):
        """
        Инициализация reply клавиатуры.

        Args:
            resize_keyboard: Автоподстройка размера
            one_time_keyboard: Скрыть после использования
        """
        super().__init__()
        self.builder = ReplyKeyboardBuilder()
        self.resize_keyboard = resize_keyboard
        self.one_time_keyboard = one_time_keyboard

    async def build(self, **kwargs) -> ReplyKeyboardMarkup:
        """Построить reply клавиатуру."""
        return self.builder.as_markup(
            resize_keyboard=self.resize_keyboard,
            one_time_keyboard=self.one_time_keyboard
        )

    def add_button(
            self,
            text: str,
            request_contact: bool = False,
            request_location: bool = False,
            row_width: int = 1
    ) -> None:
        """Добавить кнопку в клавиатуру."""
        button = KeyboardButton(
            text=text,
            request_contact=request_contact,
            request_location=request_location
        )

        self.builder.add(button)

        if row_width > 1:
            self.builder.adjust(row_width)


class PaginatedKeyboard(InlineKeyboard):
    """Клавиатура с поддержкой пагинации."""

    def __init__(
            self,
            items: List[Any],
            page_size: int = 10,
            current_page: int = 1,
            menu_type: str = "default"
    ):
        """
        Инициализация пагинированной клавиатуры.

        Args:
            items: Список элементов
            page_size: Количество элементов на странице
            current_page: Текущая страница
            menu_type: Тип меню для callback
        """
        super().__init__()
        self.items = items
        self.page_size = page_size
        self.current_page = current_page
        self.menu_type = menu_type
        self.total_pages = (len(items) + page_size - 1) // page_size

        logger.debug(
            f"Создана пагинированная клавиатура: "
            f"страница {current_page}/{self.total_pages}, "
            f"элементов {len(items)}"
        )

    def get_page_items(self) -> List[Any]:
        """Получить элементы текущей страницы."""
        start_idx = (self.current_page - 1) * self.page_size
        end_idx = start_idx + self.page_size
        return self.items[start_idx:end_idx]

    def add_pagination_buttons(self) -> None:
        """Добавить кнопки пагинации."""
        buttons = []

        # Кнопка "Назад"
        if self.current_page > 1:
            buttons.append(
                InlineKeyboardButton(
                    text="◀️",
                    callback_data=PaginationCallbackData(
                        action="prev",
                        page=self.current_page - 1,
                        total=self.total_pages,
                        menu_type=self.menu_type
                    ).pack()
                )
            )

        # Информация о странице
        buttons.append(
            InlineKeyboardButton(
                text=f"{self.current_page}/{self.total_pages}",
                callback_data="noop"
            )
        )

        # Кнопка "Вперед"
        if self.current_page < self.total_pages:
            buttons.append(
                InlineKeyboardButton(
                    text="▶️",
                    callback_data=PaginationCallbackData(
                        action="next",
                        page=self.current_page + 1,
                        total=self.total_pages,
                        menu_type=self.menu_type
                    ).pack()
                )
            )

        # Добавляем кнопки в одну строку
        for button in buttons:
            self.builder.add(button)

        self.builder.adjust(len(buttons))


class DynamicMenu(InlineKeyboard):
    """Динамическое многоуровневое меню."""

    def __init__(self, menu_id: str, level: int = 0):
        """
        Инициализация динамического меню.

        Args:
            menu_id: Идентификатор меню
            level: Уровень вложенности
        """
        super().__init__()
        self.menu_id = menu_id
        self.level = level
        self.menu_items: List[Dict[str, Any]] = []

        logger.debug(f"Создано динамическое меню {menu_id} уровня {level}")

    def add_menu_item(
            self,
            item_id: str,
            text: str,
            emoji: Optional[str] = None,
            submenu: bool = False
    ) -> None:
        """Добавить пункт меню."""
        display_text = f"{emoji} {text}" if emoji else text

        self.add_button(
            text=display_text + (" ▶️" if submenu else ""),
            callback_data=MenuCallbackData(
                action="select",
                menu_id=self.menu_id,
                item_id=item_id,
                level=self.level + 1 if submenu else self.level
            ).pack()
        )

        self.menu_items.append({
            "id": item_id,
            "text": text,
            "emoji": emoji,
            "submenu": submenu
        })

    def add_navigation_buttons(self, show_back: bool = True) -> None:
        """Добавить навигационные кнопки."""
        nav_buttons = []

        if show_back and self.level > 0:
            nav_buttons.append(
                InlineKeyboardButton(
                    text="◀️ Назад",
                    callback_data=MenuCallbackData(
                        action="back",
                        menu_id=self.menu_id,
                        level=self.level - 1
                    ).pack()
                )
            )

        nav_buttons.append(
            InlineKeyboardButton(
                text="❌ Закрыть",
                callback_data=MenuCallbackData(
                    action="close",
                    menu_id=self.menu_id,
                    level=0
                ).pack()
            )
        )

        for button in nav_buttons:
            self.builder.add(button)

        self.builder.adjust(len(nav_buttons))


class ConfirmationKeyboard(InlineKeyboard):
    """Клавиатура подтверждения действия."""

    def __init__(self, target: str, value: Optional[str] = None):
        """
        Инициализация клавиатуры подтверждения.

        Args:
            target: Цель подтверждения
            value: Дополнительное значение
        """
        super().__init__()
        self.target = target
        self.value = value

    async def build(self, **kwargs) -> InlineKeyboardMarkup:
        """Построить клавиатуру подтверждения."""
        self.add_button(
            text="✅ Да",
            callback_data=ConfirmCallbackData(
                action="yes",
                target=self.target,
                value=self.value
            ).pack()
        )

        self.add_button(
            text="❌ Нет",
            callback_data=ConfirmCallbackData(
                action="no",
                target=self.target,
                value=self.value
            ).pack()
        )

        self.builder.adjust(2)

        return await super().build(**kwargs)


# Фабрика для быстрого создания стандартных клавиатур
class KeyboardFactory:
    """Фабрика для создания стандартных клавиатур."""

    @staticmethod
    def get_main_menu() -> ReplyKeyboardMarkup:
        """Получить главное меню."""
        keyboard = ReplyKeyboard()

        keyboard.add_button("🎴 Таро", row_width=2)
        keyboard.add_button("🔮 Астрология", row_width=2)
        keyboard.add_button("💳 Подписка", row_width=2)
        keyboard.add_button("👤 Профиль", row_width=2)
        keyboard.add_button("ℹ️ Помощь", row_width=2)
        keyboard.add_button("⚙️ Настройки", row_width=2)

        return keyboard.builder.as_markup(resize_keyboard=True)

    @staticmethod
    def get_remove_keyboard() -> ReplyKeyboardRemove:
        """Получить объект для удаления клавиатуры."""
        return ReplyKeyboardRemove()

    @staticmethod
    async def get_yes_no_keyboard(
            target: str,
            value: Optional[str] = None
    ) -> InlineKeyboardMarkup:
        """Получить клавиатуру Да/Нет."""
        keyboard = ConfirmationKeyboard(target, value)
        return await keyboard.build()

    @staticmethod
    async def get_back_keyboard(callback_data: str = "back") -> InlineKeyboardMarkup:
        """Получить клавиатуру с кнопкой Назад."""
        keyboard = InlineKeyboard()
        keyboard.add_back_button(callback_data)
        return await keyboard.build()


# Утилиты для работы с callback data
def parse_callback_data(callback_data: str) -> Dict[str, Any]:
    """
    Распарсить callback data.

    Args:
        callback_data: Строка callback data

    Returns:
        Словарь с данными
    """
    try:
        # Пробуем как JSON
        return json.loads(callback_data)
    except json.JSONDecodeError:
        # Если не JSON, пробуем разбить по разделителю
        parts = callback_data.split(":")
        if len(parts) >= 2:
            return {
                "action": parts[0],
                "value": parts[1] if len(parts) > 1 else None,
                "extra": parts[2:] if len(parts) > 2 else []
            }

        # Возвращаем как есть
        return {"action": callback_data}


def build_callback_data(action: str, **kwargs) -> str:
    """
    Построить callback data.

    Args:
        action: Действие
        **kwargs: Дополнительные параметры

    Returns:
        Строка callback data
    """
    data = {"action": action, **kwargs}

    # Упрощенный формат для простых случаев
    if len(kwargs) == 0:
        return action
    elif len(kwargs) == 1 and "value" in kwargs:
        return f"{action}:{kwargs['value']}"

    # JSON для сложных случаев
    return json.dumps(data, ensure_ascii=False, separators=(',', ':'))


# Декоратор для автоматического логирования создания клавиатур
def log_keyboard_creation(func: Callable) -> Callable:
    """Декоратор для логирования создания клавиатур."""

    async def wrapper(*args, **kwargs):
        keyboard_type = args[0].__class__.__name__ if args else "Unknown"
        logger.debug(f"Создание клавиатуры {keyboard_type}")

        try:
            result = await func(*args, **kwargs)
            logger.debug(f"Клавиатура {keyboard_type} успешно создана")
            return result
        except Exception as e:
            logger.error(f"Ошибка при создании клавиатуры {keyboard_type}: {e}")
            raise

    return wrapper


logger.info("Модуль базовых клавиатур загружен")