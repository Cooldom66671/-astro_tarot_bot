"""
Базовый модуль для форматирования сообщений.

Этот модуль предоставляет:
- Базовые классы для форматирования
- Шаблоны сообщений
- Утилиты для работы с markdown
- Персонализацию сообщений
- Обработку эмодзи и специальных символов

Автор: AI Assistant
Дата создания: 2024-12-30
"""

import logging
import re
from typing import Optional, Dict, Any, List, Union
from datetime import datetime, date, time
from decimal import Decimal
from abc import ABC, abstractmethod
from enum import Enum
import html

# Настройка логирования
logger = logging.getLogger(__name__)


class MessageStyle(Enum):
    """Стили форматирования сообщений."""
    PLAIN = "plain"
    MARKDOWN = "markdown"
    MARKDOWN_V2 = "markdown_v2"
    HTML = "html"


class MessageType(Enum):
    """Типы сообщений."""
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    QUESTION = "question"
    NOTIFICATION = "notification"


class BaseMessage(ABC):
    """Базовый класс для всех сообщений."""

    def __init__(
            self,
            style: MessageStyle = MessageStyle.MARKDOWN_V2,
            max_length: Optional[int] = 4096
    ):
        """
        Инициализация базового сообщения.

        Args:
            style: Стиль форматирования
            max_length: Максимальная длина сообщения
        """
        self.style = style
        self.max_length = max_length
        logger.debug(f"Создано сообщение типа {self.__class__.__name__}")

    @abstractmethod
    async def format(self, **kwargs) -> str:
        """Форматировать сообщение."""
        pass

    def _escape_markdown(self, text: str) -> str:
        """Экранировать специальные символы для Markdown."""
        if self.style == MessageStyle.MARKDOWN_V2:
            # Символы, требующие экранирования в MarkdownV2
            escape_chars = r'_*[]()~`>#+-=|{}.!'
            return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', text)
        elif self.style == MessageStyle.MARKDOWN:
            # Символы для обычного Markdown
            escape_chars = r'*_`['
            return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', text)
        return text

    def _escape_html(self, text: str) -> str:
        """Экранировать HTML символы."""
        return html.escape(text, quote=False)

    def _truncate(self, text: str, suffix: str = "...") -> str:
        """Обрезать текст до максимальной длины."""
        if self.max_length and len(text) > self.max_length:
            return text[:self.max_length - len(suffix)] + suffix
        return text

    def _format_bold(self, text: str) -> str:
        """Форматировать жирный текст."""
        if self.style == MessageStyle.MARKDOWN_V2:
            return f"*{self._escape_markdown(text)}*"
        elif self.style == MessageStyle.MARKDOWN:
            return f"*{text}*"
        elif self.style == MessageStyle.HTML:
            return f"<b>{self._escape_html(text)}</b>"
        return text

    def _format_italic(self, text: str) -> str:
        """Форматировать курсивный текст."""
        if self.style == MessageStyle.MARKDOWN_V2:
            return f"_{self._escape_markdown(text)}_"
        elif self.style == MessageStyle.MARKDOWN:
            return f"_{text}_"
        elif self.style == MessageStyle.HTML:
            return f"<i>{self._escape_html(text)}</i>"
        return text

    def _format_code(self, text: str) -> str:
        """Форматировать моноширинный текст."""
        if self.style == MessageStyle.MARKDOWN_V2:
            return f"`{self._escape_markdown(text)}`"
        elif self.style == MessageStyle.MARKDOWN:
            return f"`{text}`"
        elif self.style == MessageStyle.HTML:
            return f"<code>{self._escape_html(text)}</code>"
        return text

    def _format_pre(self, text: str, language: Optional[str] = None) -> str:
        """Форматировать блок кода."""
        if self.style == MessageStyle.MARKDOWN_V2:
            if language:
                return f"```{language}\n{text}\n```"
            return f"```\n{text}\n```"
        elif self.style == MessageStyle.MARKDOWN:
            return f"```\n{text}\n```"
        elif self.style == MessageStyle.HTML:
            if language:
                return f'<pre><code class="language-{language}">{self._escape_html(text)}</code></pre>'
            return f"<pre>{self._escape_html(text)}</pre>"
        return text

    def _format_link(self, text: str, url: str) -> str:
        """Форматировать ссылку."""
        if self.style in [MessageStyle.MARKDOWN_V2, MessageStyle.MARKDOWN]:
            return f"[{text}]({url})"
        elif self.style == MessageStyle.HTML:
            return f'<a href="{url}">{self._escape_html(text)}</a>'
        return f"{text} ({url})"

    def _format_mention(self, name: str, user_id: int) -> str:
        """Форматировать упоминание пользователя."""
        if self.style == MessageStyle.MARKDOWN_V2:
            return f"[{self._escape_markdown(name)}](tg://user?id={user_id})"
        elif self.style == MessageStyle.MARKDOWN:
            return f"[{name}](tg://user?id={user_id})"
        elif self.style == MessageStyle.HTML:
            return f'<a href="tg://user?id={user_id}">{self._escape_html(name)}</a>'
        return name

    def _format_spoiler(self, text: str) -> str:
        """Форматировать спойлер."""
        if self.style == MessageStyle.MARKDOWN_V2:
            return f"||{self._escape_markdown(text)}||"
        elif self.style == MessageStyle.HTML:
            return f"<span class='tg-spoiler'>{self._escape_html(text)}</span>"
        return text

    def _format_quote(self, text: str) -> str:
        """Форматировать цитату."""
        if self.style == MessageStyle.MARKDOWN_V2:
            lines = text.split('\n')
            return '\n'.join(f">{self._escape_markdown(line)}" for line in lines)
        elif self.style == MessageStyle.HTML:
            return f"<blockquote>{self._escape_html(text)}</blockquote>"
        return f'"{text}"'


class TemplateMessage(BaseMessage):
    """Сообщение на основе шаблона."""

    def __init__(
            self,
            template: str,
            style: MessageStyle = MessageStyle.MARKDOWN_V2,
            max_length: Optional[int] = 4096
    ):
        """
        Инициализация шаблонного сообщения.

        Args:
            template: Шаблон сообщения
            style: Стиль форматирования
            max_length: Максимальная длина
        """
        super().__init__(style, max_length)
        self.template = template

    async def format(self, **kwargs) -> str:
        """
        Форматировать сообщение из шаблона.

        Args:
            **kwargs: Параметры для подстановки

        Returns:
            Отформатированное сообщение
        """
        # Обработка специальных типов данных
        formatted_kwargs = {}
        for key, value in kwargs.items():
            formatted_kwargs[key] = self._format_value(value)

        # Подстановка в шаблон
        try:
            message = self.template.format(**formatted_kwargs)
        except KeyError as e:
            logger.error(f"Отсутствует параметр в шаблоне: {e}")
            message = self.template

        return self._truncate(message)

    def _format_value(self, value: Any) -> str:
        """Форматировать значение для подстановки."""
        if isinstance(value, datetime):
            return value.strftime("%d.%m.%Y %H:%M")
        elif isinstance(value, date):
            return value.strftime("%d.%m.%Y")
        elif isinstance(value, time):
            return value.strftime("%H:%M")
        elif isinstance(value, Decimal):
            return f"{value:,.2f}".replace(",", " ")
        elif isinstance(value, (int, float)):
            if value >= 1000:
                return f"{value:,.0f}".replace(",", " ")
            return str(value)
        elif isinstance(value, bool):
            return "✅" if value else "❌"
        elif value is None:
            return "—"
        else:
            # Экранируем текст в зависимости от стиля
            text = str(value)
            if self.style == MessageStyle.MARKDOWN_V2:
                return self._escape_markdown(text)
            elif self.style == MessageStyle.HTML:
                return self._escape_html(text)
            return text


class MessageBuilder:
    """Построитель сложных сообщений."""

    def __init__(
            self,
            style: MessageStyle = MessageStyle.MARKDOWN_V2,
            max_length: Optional[int] = 4096
    ):
        """
        Инициализация построителя.

        Args:
            style: Стиль форматирования
            max_length: Максимальная длина
        """
        self.style = style
        self.max_length = max_length
        self.parts: List[str] = []
        self._base_message = BaseMessage(style, max_length)

    def add_line(self, text: str = "") -> 'MessageBuilder':
        """Добавить строку."""
        self.parts.append(text)
        return self

    def add_text(self, text: str) -> 'MessageBuilder':
        """Добавить текст без переноса."""
        if self.parts and self.parts[-1]:
            self.parts[-1] += text
        else:
            self.parts.append(text)
        return self

    def add_bold(self, text: str) -> 'MessageBuilder':
        """Добавить жирный текст."""
        formatted = self._base_message._format_bold(text)
        return self.add_text(formatted)

    def add_italic(self, text: str) -> 'MessageBuilder':
        """Добавить курсивный текст."""
        formatted = self._base_message._format_italic(text)
        return self.add_text(formatted)

    def add_code(self, text: str) -> 'MessageBuilder':
        """Добавить моноширинный текст."""
        formatted = self._base_message._format_code(text)
        return self.add_text(formatted)

    def add_pre(self, text: str, language: Optional[str] = None) -> 'MessageBuilder':
        """Добавить блок кода."""
        formatted = self._base_message._format_pre(text, language)
        return self.add_line(formatted)

    def add_link(self, text: str, url: str) -> 'MessageBuilder':
        """Добавить ссылку."""
        formatted = self._base_message._format_link(text, url)
        return self.add_text(formatted)

    def add_mention(self, name: str, user_id: int) -> 'MessageBuilder':
        """Добавить упоминание."""
        formatted = self._base_message._format_mention(name, user_id)
        return self.add_text(formatted)

    def add_spoiler(self, text: str) -> 'MessageBuilder':
        """Добавить спойлер."""
        formatted = self._base_message._format_spoiler(text)
        return self.add_text(formatted)

    def add_quote(self, text: str) -> 'MessageBuilder':
        """Добавить цитату."""
        formatted = self._base_message._format_quote(text)
        return self.add_line(formatted)

    def add_separator(self, char: str = "—", length: int = 20) -> 'MessageBuilder':
        """Добавить разделитель."""
        separator = char * length
        if self.style == MessageStyle.MARKDOWN_V2:
            separator = self._base_message._escape_markdown(separator)
        return self.add_line(separator)

    def add_list(
            self,
            items: List[str],
            bullet: str = "•",
            indent: int = 2
    ) -> 'MessageBuilder':
        """Добавить список."""
        indent_str = " " * indent
        for item in items:
            if self.style == MessageStyle.MARKDOWN_V2:
                item = self._base_message._escape_markdown(item)
                bullet_escaped = self._base_message._escape_markdown(bullet)
                self.add_line(f"{indent_str}{bullet_escaped} {item}")
            else:
                self.add_line(f"{indent_str}{bullet} {item}")
        return self

    def add_key_value(
            self,
            key: str,
            value: Any,
            separator: str = ": "
    ) -> 'MessageBuilder':
        """Добавить пару ключ-значение."""
        formatted_value = self._format_value(value)
        self.add_bold(key).add_text(separator).add_text(formatted_value)
        return self.add_line()

    def add_table(
            self,
            headers: List[str],
            rows: List[List[Any]],
            align: str = "left"
    ) -> 'MessageBuilder':
        """Добавить простую таблицу."""
        # Вычисляем максимальную ширину колонок
        col_widths = [len(h) for h in headers]

        for row in rows:
            for i, cell in enumerate(row):
                col_widths[i] = max(col_widths[i], len(str(cell)))

        # Форматируем заголовки
        header_row = " | ".join(
            h.ljust(w) if align == "left" else h.rjust(w)
            for h, w in zip(headers, col_widths)
        )

        if self.style == MessageStyle.MARKDOWN_V2:
            header_row = self._base_message._escape_markdown(header_row)

        self.add_code(header_row).add_line()

        # Разделитель
        separator = "-+-".join("-" * w for w in col_widths)
        if self.style == MessageStyle.MARKDOWN_V2:
            separator = self._base_message._escape_markdown(separator)
        self.add_code(separator).add_line()

        # Строки данных
        for row in rows:
            formatted_row = " | ".join(
                str(cell).ljust(w) if align == "left" else str(cell).rjust(w)
                for cell, w in zip(row, col_widths)
            )
            if self.style == MessageStyle.MARKDOWN_V2:
                formatted_row = self._base_message._escape_markdown(formatted_row)
            self.add_code(formatted_row).add_line()

        return self

    def add_empty_line(self, count: int = 1) -> 'MessageBuilder':
        """Добавить пустые строки."""
        for _ in range(count):
            self.add_line()
        return self

    def _format_value(self, value: Any) -> str:
        """Форматировать значение."""
        if isinstance(value, datetime):
            return value.strftime("%d.%m.%Y %H:%M")
        elif isinstance(value, date):
            return value.strftime("%d.%m.%Y")
        elif isinstance(value, time):
            return value.strftime("%H:%M")
        elif isinstance(value, Decimal):
            return f"{value:,.2f}".replace(",", " ")
        elif isinstance(value, bool):
            return "✅" if value else "❌"
        elif value is None:
            return "—"
        else:
            text = str(value)
            if self.style == MessageStyle.MARKDOWN_V2:
                return self._base_message._escape_markdown(text)
            elif self.style == MessageStyle.HTML:
                return self._base_message._escape_html(text)
            return text

    def build(self) -> str:
        """Построить финальное сообщение."""
        message = "\n".join(self.parts)

        if self.max_length and len(message) > self.max_length:
            message = message[:self.max_length - 3] + "..."

        return message


class MessageFormatter:
    """Утилиты для форматирования сообщений."""

    @staticmethod
    def format_number(
            number: Union[int, float, Decimal],
            decimals: int = 0,
            currency: Optional[str] = None
    ) -> str:
        """
        Форматировать число.

        Args:
            number: Число
            decimals: Количество знаков после запятой
            currency: Валюта

        Returns:
            Отформатированное число
        """
        if decimals > 0:
            formatted = f"{number:,.{decimals}f}".replace(",", " ")
        else:
            formatted = f"{number:,.0f}".replace(",", " ")

        if currency:
            formatted += f" {currency}"

        return formatted

    @staticmethod
    def format_datetime(
            dt: datetime,
            format_str: str = "%d.%m.%Y %H:%M",
            relative: bool = False
    ) -> str:
        """
        Форматировать дату/время.

        Args:
            dt: Дата/время
            format_str: Формат вывода
            relative: Использовать относительное время

        Returns:
            Отформатированная дата
        """
        if relative:
            now = datetime.now()
            delta = now - dt

            if delta.days == 0:
                if delta.seconds < 60:
                    return "только что"
                elif delta.seconds < 3600:
                    minutes = delta.seconds // 60
                    return f"{minutes} мин. назад"
                else:
                    hours = delta.seconds // 3600
                    return f"{hours} ч. назад"
            elif delta.days == 1:
                return "вчера"
            elif delta.days < 7:
                return f"{delta.days} дн. назад"
            elif delta.days < 30:
                weeks = delta.days // 7
                return f"{weeks} нед. назад"
            elif delta.days < 365:
                months = delta.days // 30
                return f"{months} мес. назад"
            else:
                years = delta.days // 365
                return f"{years} г. назад"

        return dt.strftime(format_str)

    @staticmethod
    def format_duration(seconds: int) -> str:
        """
        Форматировать длительность.

        Args:
            seconds: Секунды

        Returns:
            Отформатированная длительность
        """
        if seconds < 60:
            return f"{seconds} сек."
        elif seconds < 3600:
            minutes = seconds // 60
            remaining = seconds % 60
            if remaining:
                return f"{minutes} мин. {remaining} сек."
            return f"{minutes} мин."
        elif seconds < 86400:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            if minutes:
                return f"{hours} ч. {minutes} мин."
            return f"{hours} ч."
        else:
            days = seconds // 86400
            hours = (seconds % 86400) // 3600
            if hours:
                return f"{days} дн. {hours} ч."
            return f"{days} дн."

    @staticmethod
    def format_percentage(
            value: Union[int, float],
            decimals: int = 1,
            show_sign: bool = False
    ) -> str:
        """
        Форматировать процент.

        Args:
            value: Значение
            decimals: Знаков после запятой
            show_sign: Показывать знак +

        Returns:
            Отформатированный процент
        """
        formatted = f"{value:.{decimals}f}%"

        if show_sign and value > 0:
            formatted = f"+{formatted}"

        return formatted

    @staticmethod
    def pluralize(
            count: int,
            form1: str,
            form2: str,
            form3: str
    ) -> str:
        """
        Склонение слова по числу.

        Args:
            count: Количество
            form1: Форма для 1 (день)
            form2: Форма для 2-4 (дня)
            form3: Форма для 5+ (дней)

        Returns:
            Правильная форма слова
        """
        if count % 10 == 1 and count % 100 != 11:
            return form1
        elif 2 <= count % 10 <= 4 and not 12 <= count % 100 <= 14:
            return form2
        else:
            return form3


# Предопределённые эмодзи для сообщений
class MessageEmoji:
    """Эмодзи для различных типов сообщений."""

    # Статусы
    SUCCESS = "✅"
    ERROR = "❌"
    WARNING = "⚠️"
    INFO = "ℹ️"
    QUESTION = "❓"
    LOADING = "⏳"
    DONE = "✔️"

    # Действия
    EDIT = "✏️"
    DELETE = "🗑"
    SAVE = "💾"
    CANCEL = "🚫"
    REFRESH = "🔄"
    SEARCH = "🔍"
    SETTINGS = "⚙️"

    # Навигация
    BACK = "◀️"
    FORWARD = "▶️"
    UP = "⬆️"
    DOWN = "⬇️"
    HOME = "🏠"

    # Разделы
    TAROT = "🎴"
    ASTROLOGY = "🔮"
    HOROSCOPE = "⭐"
    MOON = "🌙"
    SUN = "☀️"

    # Подписка
    PREMIUM = "💎"
    VIP = "👑"
    MONEY = "💰"
    GIFT = "🎁"
    DISCOUNT = "🏷"

    # Время
    CALENDAR = "📅"
    CLOCK = "🕐"
    ALARM = "⏰"
    TIMER = "⏱"

    # Общение
    MESSAGE = "💬"
    NOTIFICATION = "🔔"
    EMAIL = "📧"
    PHONE = "📞"

    # Прочее
    STAR = "⭐"
    HEART = "❤️"
    FIRE = "🔥"
    SPARKLES = "✨"
    LOCK = "🔒"
    UNLOCK = "🔓"
    KEY = "🔑"
    FLAG = "🚩"
    PIN = "📌"
    BOOKMARK = "🔖"


logger.info("Модуль базовых сообщений загружен")