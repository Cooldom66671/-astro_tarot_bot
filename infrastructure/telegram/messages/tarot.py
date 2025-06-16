"""
Модуль сообщений для раздела Таро.

Этот модуль содержит:
- Интерпретации карт Таро
- Описания раскладов
- Форматирование результатов гаданий
- Обучающие материалы
- Контекстные интерпретации

Автор: AI Assistant
Дата создания: 2024-12-30
"""

import logging
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime
from enum import Enum
import random

from .base import (
    BaseMessage, TemplateMessage, MessageBuilder,
    MessageStyle, MessageEmoji, MessageFormatter
)

# Настройка логирования
logger = logging.getLogger(__name__)


class TarotContext(Enum):
    """Контексты интерпретации карт."""
    GENERAL = "general"
    LOVE = "love"
    CAREER = "career"
    HEALTH = "health"
    SPIRITUAL = "spiritual"
    ADVICE = "advice"


class CardPosition(Enum):
    """Положение карты."""
    UPRIGHT = "upright"
    REVERSED = "reversed"


class SpreadPosition:
    """Позиции в раскладах."""

    # Три карты
    THREE_CARDS = {
        1: "Прошлое",
        2: "Настоящее",
        3: "Будущее"
    }

    # Кельтский крест
    CELTIC_CROSS = {
        1: "Текущая ситуация",
        2: "Вызов/Крест",
        3: "Далёкое прошлое",
        4: "Недавнее прошлое",
        5: "Возможное будущее",
        6: "Ближайшее будущее",
        7: "Ваш подход",
        8: "Внешние влияния",
        9: "Надежды и страхи",
        10: "Итог"
    }

    # Отношения
    RELATIONSHIP = {
        1: "Вы",
        2: "Партнёр",
        3: "Основа отношений",
        4: "Прошлое отношений",
        5: "Настоящее отношений",
        6: "Будущее отношений",
        7: "Совет"
    }

    # Карьера
    CAREER = {
        1: "Текущая ситуация",
        2: "Ваши амбиции",
        3: "Препятствия",
        4: "Ваши сильные стороны",
        5: "Внешние факторы",
        6: "Совет"
    }


class TarotCardMessage(BaseMessage):
    """Класс для создания сообщений о картах Таро."""

    def __init__(
            self,
            card_data: Dict[str, Any],
            position: CardPosition = CardPosition.UPRIGHT,
            context: TarotContext = TarotContext.GENERAL,
            spread_position: Optional[str] = None,
            style: MessageStyle = MessageStyle.MARKDOWN_V2
    ):
        """
        Инициализация сообщения карты.

        Args:
            card_data: Данные карты
            position: Положение карты
            context: Контекст интерпретации
            spread_position: Позиция в раскладе
            style: Стиль форматирования
        """
        super().__init__(style)
        self.card_data = card_data
        self.position = position
        self.context = context
        self.spread_position = spread_position

        logger.debug(f"Создание сообщения для карты {card_data.get('name')}")

    async def format(self, **kwargs) -> str:
        """Форматировать сообщение о карте."""
        builder = MessageBuilder(self.style)

        # Заголовок с названием карты
        self._add_card_header(builder)

        # Основное значение
        self._add_general_meaning(builder)

        # Контекстное значение
        if self.context != TarotContext.GENERAL:
            self._add_context_meaning(builder)

        # Ключевые слова
        self._add_keywords(builder)

        # Совет дня (если это карта дня)
        if kwargs.get("is_daily_card"):
            self._add_daily_advice(builder)

        # Дополнительная информация
        if kwargs.get("show_extended"):
            self._add_extended_info(builder)

        return builder.build()

    def _add_card_header(self, builder: MessageBuilder) -> None:
        """Добавить заголовок карты."""
        card_name = self.card_data.get("name", "Неизвестная карта")
        arcana = self.card_data.get("arcana", "")

        # Эмодзи для арканов
        arcana_emoji = "🌟" if arcana == "major" else "🎴"

        # Название карты
        header = f"{arcana_emoji} {card_name}"

        # Положение карты
        if self.position == CardPosition.REVERSED:
            header += " (Перевёрнутая)"

        builder.add_bold(header).add_line()

        # Позиция в раскладе
        if self.spread_position:
            builder.add_italic(f"Позиция: {self.spread_position}").add_line()

        builder.add_separator().add_line()

    def _add_general_meaning(self, builder: MessageBuilder) -> None:
        """Добавить общее значение карты."""
        if self.position == CardPosition.UPRIGHT:
            meaning = self.card_data.get("meaning_upright", "")
        else:
            meaning = self.card_data.get("meaning_reversed", "")

        if meaning:
            builder.add_line(meaning)
            builder.add_empty_line()

    def _add_context_meaning(self, builder: MessageBuilder) -> None:
        """Добавить контекстное значение."""
        context_meanings = self.card_data.get("context_meanings", {})
        context_meaning = context_meanings.get(self.context.value, {})

        if self.position == CardPosition.UPRIGHT:
            meaning = context_meaning.get("upright", "")
        else:
            meaning = context_meaning.get("reversed", "")

        if meaning:
            # Заголовок контекста
            context_titles = {
                TarotContext.LOVE: "💕 В отношениях",
                TarotContext.CAREER: "💼 В карьере",
                TarotContext.HEALTH: "🌿 В здоровье",
                TarotContext.SPIRITUAL: "🧘 В духовном развитии",
                TarotContext.ADVICE: "💡 Совет"
            }

            title = context_titles.get(self.context, "Значение")
            builder.add_bold(title).add_line()
            builder.add_line(meaning)
            builder.add_empty_line()

    def _add_keywords(self, builder: MessageBuilder) -> None:
        """Добавить ключевые слова."""
        if self.position == CardPosition.UPRIGHT:
            keywords = self.card_data.get("keywords_upright", [])
        else:
            keywords = self.card_data.get("keywords_reversed", [])

        if keywords:
            builder.add_bold("🔑 Ключевые слова:").add_line()
            builder.add_text(", ".join(keywords))
            builder.add_empty_line()

    def _add_daily_advice(self, builder: MessageBuilder) -> None:
        """Добавить совет дня."""
        builder.add_bold("💫 Совет на сегодня:").add_line()

        # Советы в зависимости от карты и положения
        if self.position == CardPosition.UPRIGHT:
            advice = self.card_data.get("daily_advice_upright", "")
        else:
            advice = self.card_data.get("daily_advice_reversed", "")

        if not advice:
            # Генерируем общий совет
            advice = self._generate_daily_advice()

        builder.add_italic(advice).add_line()
        builder.add_empty_line()

    def _add_extended_info(self, builder: MessageBuilder) -> None:
        """Добавить расширенную информацию."""
        # Астрологическое соответствие
        astro = self.card_data.get("astrology")
        if astro:
            builder.add_text("🌌 ").add_bold("Астрология: ")
            builder.add_text(astro).add_line()

        # Стихия
        element = self.card_data.get("element")
        if element:
            elements = {
                "fire": "🔥 Огонь",
                "water": "💧 Вода",
                "air": "💨 Воздух",
                "earth": "🌍 Земля",
                "spirit": "✨ Дух"
            }
            builder.add_text(f"{elements.get(element, element)}").add_line()

        # Номер карты
        number = self.card_data.get("number")
        if number is not None:
            builder.add_text("🔢 ").add_bold("Номер: ")
            builder.add_text(str(number)).add_line()

    def _generate_daily_advice(self) -> str:
        """Генерировать общий совет дня."""
        if self.position == CardPosition.UPRIGHT:
            advices = [
                "Сегодня благоприятный день для новых начинаний",
                "Доверьтесь своей интуиции",
                "Время действовать решительно",
                "Откройтесь новым возможностям",
                "Прислушайтесь к своему внутреннему голосу"
            ]
        else:
            advices = [
                "Будьте внимательны к деталям",
                "Время для переосмысления",
                "Не спешите с решениями",
                "Обратите внимание на то, что упускаете",
                "Возможно, стоит взглянуть на ситуацию с другой стороны"
            ]

        return random.choice(advices)


class TarotSpreadMessage(BaseMessage):
    """Класс для создания сообщений о раскладах."""

    def __init__(
            self,
            spread_type: str,
            cards: List[Dict[str, Any]],
            question: Optional[str] = None,
            interpretation: Optional[str] = None,
            style: MessageStyle = MessageStyle.MARKDOWN_V2
    ):
        """
        Инициализация сообщения расклада.

        Args:
            spread_type: Тип расклада
            cards: Список карт с позициями
            question: Вопрос пользователя
            interpretation: Общая интерпретация
            style: Стиль форматирования
        """
        super().__init__(style)
        self.spread_type = spread_type
        self.cards = cards
        self.question = question
        self.interpretation = interpretation

        logger.debug(f"Создание сообщения расклада {spread_type}")

    async def format(self, **kwargs) -> str:
        """Форматировать сообщение расклада."""
        builder = MessageBuilder(self.style)

        # Заголовок расклада
        self._add_spread_header(builder)

        # Вопрос (если есть)
        if self.question:
            self._add_question(builder)

        # Карты расклада
        self._add_cards_summary(builder)

        # Общая интерпретация
        if self.interpretation:
            self._add_interpretation(builder)

        # Резюме
        self._add_summary(builder)

        return builder.build()

    def _add_spread_header(self, builder: MessageBuilder) -> None:
        """Добавить заголовок расклада."""
        spread_names = {
            "one_card": "🎴 Карта дня",
            "three_cards": "🎯 Три карты",
            "celtic_cross": "✨ Кельтский крест",
            "relationship": "💕 Расклад на отношения",
            "career": "💼 Карьерный расклад",
            "year_ahead": "📅 Год вперёд",
            "chakras": "🧘 Расклад Чакры",
            "shadow_work": "🌑 Работа с тенью",
            "life_purpose": "🌟 Жизненное предназначение"
        }

        spread_name = spread_names.get(self.spread_type, "Расклад")
        builder.add_bold(spread_name).add_line()

        # Время расклада
        timestamp = datetime.now().strftime("%d.%m.%Y %H:%M")
        builder.add_italic(f"📅 {timestamp}").add_line()

        builder.add_separator().add_line()

    def _add_question(self, builder: MessageBuilder) -> None:
        """Добавить вопрос пользователя."""
        builder.add_bold("❓ Ваш вопрос:").add_line()
        builder.add_quote(self.question).add_line()
        builder.add_empty_line()

    def _add_cards_summary(self, builder: MessageBuilder) -> None:
        """Добавить краткую информацию о картах."""
        builder.add_bold("🎴 Выпавшие карты:").add_line()
        builder.add_empty_line()

        # Получаем позиции для типа расклада
        positions = self._get_spread_positions()

        for i, card in enumerate(self.cards, 1):
            position_name = positions.get(i, f"Позиция {i}")
            card_name = card.get("name", "Неизвестная карта")
            is_reversed = card.get("is_reversed", False)

            # Формируем строку карты
            if is_reversed:
                card_str = f"{card_name} (R)"
            else:
                card_str = card_name

            builder.add_text(f"{i}. ").add_bold(position_name)
            builder.add_text(": ").add_text(card_str)
            builder.add_line()

        builder.add_empty_line()

    def _add_interpretation(self, builder: MessageBuilder) -> None:
        """Добавить общую интерпретацию."""
        builder.add_bold("🔮 Интерпретация:").add_line()
        builder.add_empty_line()

        # Разбиваем интерпретацию на абзацы
        paragraphs = self.interpretation.split("\n\n")
        for paragraph in paragraphs:
            builder.add_line(paragraph)
            builder.add_empty_line()

    def _add_summary(self, builder: MessageBuilder) -> None:
        """Добавить резюме расклада."""
        builder.add_bold("📌 Резюме:").add_line()

        # Генерируем краткое резюме на основе карт
        summary_points = self._generate_summary_points()
        builder.add_list(summary_points)

        builder.add_empty_line()

        # Рекомендация
        builder.add_italic("💡 Помните: карты показывают возможности, а не предопределённость. ")
        builder.add_italic("Ваши решения и действия формируют будущее.")

    def _get_spread_positions(self) -> Dict[int, str]:
        """Получить позиции для типа расклада."""
        if self.spread_type == "three_cards":
            return SpreadPosition.THREE_CARDS
        elif self.spread_type == "celtic_cross":
            return SpreadPosition.CELTIC_CROSS
        elif self.spread_type == "relationship":
            return SpreadPosition.RELATIONSHIP
        elif self.spread_type == "career":
            return SpreadPosition.CAREER
        else:
            # Для остальных раскладов генерируем простые позиции
            return {i: f"Карта {i}" for i in range(1, len(self.cards) + 1)}

    def _generate_summary_points(self) -> List[str]:
        """Генерировать ключевые пункты резюме."""
        # Анализируем карты для генерации резюме
        major_count = sum(1 for card in self.cards if card.get("arcana") == "major")
        reversed_count = sum(1 for card in self.cards if card.get("is_reversed"))

        points = []

        # Анализ по старшим арканам
        if major_count >= len(self.cards) // 2:
            points.append("Ситуация имеет важное кармическое значение")

        # Анализ по перевёрнутым картам
        if reversed_count >= len(self.cards) // 2:
            points.append("Необходимо переосмысление и внутренняя работа")
        elif reversed_count == 0:
            points.append("Энергии текут свободно и гармонично")

        # Дополнительные пункты по типу расклада
        if self.spread_type == "relationship":
            points.append("Фокус на взаимопонимании и общении")
        elif self.spread_type == "career":
            points.append("Время для профессионального роста")

        # Если пунктов мало, добавляем общие
        if len(points) < 2:
            points.extend([
                "Доверьтесь процессу развития событий",
                "Следуйте интуиции в принятии решений"
            ])

        return points[:3]  # Максимум 3 пункта


class TarotEducationalMessage(BaseMessage):
    """Класс для создания обучающих сообщений о Таро."""

    def __init__(
            self,
            topic: str,
            content_type: str = "lesson",
            style: MessageStyle = MessageStyle.MARKDOWN_V2
    ):
        """
        Инициализация обучающего сообщения.

        Args:
            topic: Тема обучения
            content_type: Тип контента (lesson, tip, history)
            style: Стиль форматирования
        """
        super().__init__(style)
        self.topic = topic
        self.content_type = content_type

    async def format(self, **kwargs) -> str:
        """Форматировать обучающее сообщение."""
        builder = MessageBuilder(self.style)

        if self.content_type == "lesson":
            return self._format_lesson(builder)
        elif self.content_type == "tip":
            return self._format_tip(builder)
        elif self.content_type == "history":
            return self._format_history(builder)

        return builder.build()

    def _format_lesson(self, builder: MessageBuilder) -> str:
        """Форматировать урок."""
        lessons = {
            "intro": {
                "title": "Введение в Таро",
                "content": [
                    "Таро — это система символов, помогающая понять себя и ситуацию.",
                    "",
                    "**Структура колоды:**",
                    "• 78 карт всего",
                    "• 22 Старших Аркана (главные архетипы)",
                    "• 56 Младших Арканов (повседневные ситуации)",
                    "",
                    "**Младшие Арканы делятся на:**",
                    "• Жезлы (Огонь) — действие, энергия",
                    "• Кубки (Вода) — эмоции, чувства",
                    "• Мечи (Воздух) — мысли, конфликты",
                    "• Пентакли (Земля) — материальное, результаты"
                ]
            },
            "reading_basics": {
                "title": "Основы чтения карт",
                "content": [
                    "**Как читать карты:**",
                    "",
                    "1. **Сформулируйте вопрос**",
                    "   Чёткий вопрос — половина ответа",
                    "",
                    "2. **Выберите расклад**",
                    "   От простого к сложному",
                    "",
                    "3. **Интерпретируйте символы**",
                    "   Карты говорят языком образов",
                    "",
                    "4. **Свяжите в историю**",
                    "   Карты рассказывают единую историю",
                    "",
                    "💡 Совет: Доверяйте первому впечатлению!"
                ]
            },
            "reversed_cards": {
                "title": "Перевёрнутые карты",
                "content": [
                    "Перевёрнутые карты — это не всегда негатив!",
                    "",
                    "**Варианты толкования:**",
                    "• Внутренний процесс",
                    "• Блокировка энергии",
                    "• Теневая сторона",
                    "• Ослабление влияния",
                    "• Задержка или препятствие",
                    "",
                    "**Пример:**",
                    "Солнце (прямая) — радость, успех",
                    "Солнце (перевёрнутая) — внутренняя радость, скрытый успех"
                ]
            }
        }

        lesson = lessons.get(self.topic, lessons["intro"])

        builder.add_bold(f"📚 {lesson['title']}").add_line()
        builder.add_separator().add_line()

        for line in lesson["content"]:
            if line.startswith("**") and line.endswith("**"):
                # Выделенный текст
                text = line.strip("**")
                builder.add_bold(text).add_line()
            elif line.startswith("•"):
                # Элемент списка
                builder.add_text("  ").add_line(line)
            elif line.startswith("   "):
                # Подпункт
                builder.add_text("    ").add_italic(line.strip()).add_line()
            else:
                builder.add_line(line)

        return builder.build()

    def _format_tip(self, builder: MessageBuilder) -> str:
        """Форматировать совет."""
        tips = {
            "daily": [
                "💡 Делайте расклад в спокойной обстановке",
                "💡 Ведите дневник своих раскладов",
                "💡 Изучайте одну карту в день",
                "💡 Медитируйте на карту перед сном",
                "💡 Сравнивайте разные колоды"
            ],
            "interpretation": [
                "💡 Обращайте внимание на цвета и символы",
                "💡 Учитывайте позицию карты в раскладе",
                "💡 Связывайте карты в единую историю",
                "💡 Доверяйте интуиции",
                "💡 Практика — ключ к мастерству"
            ]
        }

        tip_list = tips.get(self.topic, tips["daily"])
        tip = random.choice(tip_list)

        builder.add_bold("Совет дня").add_line()
        builder.add_separator().add_line()
        builder.add_line(tip)

        return builder.build()

    def _format_history(self, builder: MessageBuilder) -> str:
        """Форматировать историческую справку."""
        builder.add_bold("📜 История Таро").add_line()
        builder.add_separator().add_line()

        builder.add_line("Таро появилось в Италии в XV веке как карточная игра.")
        builder.add_line("Эзотерическое значение карты приобрели в XVIII веке.")
        builder.add_empty_line()

        builder.add_bold("Ключевые даты:").add_line()
        builder.add_list([
            "1440 — первые упоминания",
            "1781 — Кур де Жебелен связал Таро с Египтом",
            "1910 — колода Райдера-Уэйта",
            "Сегодня — сотни различных колод"
        ])

        return builder.build()


class TarotStatisticsMessage(BaseMessage):
    """Класс для создания сообщений статистики."""

    def __init__(
            self,
            stats_data: Dict[str, Any],
            period: str = "all_time",
            style: MessageStyle = MessageStyle.MARKDOWN_V2
    ):
        """
        Инициализация сообщения статистики.

        Args:
            stats_data: Данные статистики
            period: Период статистики
            style: Стиль форматирования
        """
        super().__init__(style)
        self.stats_data = stats_data
        self.period = period

    async def format(self, **kwargs) -> str:
        """Форматировать сообщение статистики."""
        builder = MessageBuilder(self.style)

        # Заголовок
        period_names = {
            "all_time": "За всё время",
            "month": "За месяц",
            "week": "За неделю",
            "today": "Сегодня"
        }

        period_name = period_names.get(self.period, "Статистика")
        builder.add_bold(f"📊 Ваша статистика Таро").add_line()
        builder.add_italic(period_name).add_line()
        builder.add_separator().add_line()

        # Основные показатели
        total_readings = self.stats_data.get("total_readings", 0)
        favorite_spread = self.stats_data.get("favorite_spread", "Три карты")
        most_common_card = self.stats_data.get("most_common_card", {})

        builder.add_key_value("Всего раскладов", total_readings)
        builder.add_key_value("Любимый расклад", favorite_spread)

        if most_common_card:
            card_text = f"{most_common_card['name']} ({most_common_card['count']} раз)"
            builder.add_key_value("Частая карта", card_text)

        builder.add_empty_line()

        # Распределение по арканам
        arcana_stats = self.stats_data.get("arcana_distribution", {})
        if arcana_stats:
            builder.add_bold("📊 Распределение арканов:").add_line()
            major_percent = arcana_stats.get("major_percent", 0)
            minor_percent = arcana_stats.get("minor_percent", 0)

            builder.add_text(f"Старшие: {major_percent}% | Младшие: {minor_percent}%")
            builder.add_line()
            builder.add_empty_line()

        # Топ карт
        top_cards = self.stats_data.get("top_cards", [])
        if top_cards:
            builder.add_bold("🎴 Топ-5 карт:").add_line()
            for i, card in enumerate(top_cards[:5], 1):
                builder.add_text(f"{i}. {card['name']} — {card['count']} раз")
                builder.add_line()

        return builder.build()


# Функции для быстрого создания сообщений
async def format_card_message(
        card_data: Dict[str, Any],
        position: str = "upright",
        context: str = "general",
        spread_position: Optional[str] = None,
        **kwargs
) -> str:
    """
    Форматировать сообщение карты.

    Args:
        card_data: Данные карты
        position: Положение карты
        context: Контекст интерпретации
        spread_position: Позиция в раскладе
        **kwargs: Дополнительные параметры

    Returns:
        Отформатированное сообщение
    """
    message = TarotCardMessage(
        card_data=card_data,
        position=CardPosition(position),
        context=TarotContext(context),
        spread_position=spread_position
    )
    return await message.format(**kwargs)


async def format_spread_message(
        spread_type: str,
        cards: List[Dict[str, Any]],
        question: Optional[str] = None,
        interpretation: Optional[str] = None
) -> str:
    """
    Форматировать сообщение расклада.

    Args:
        spread_type: Тип расклада
        cards: Список карт
        question: Вопрос пользователя
        interpretation: Интерпретация

    Returns:
        Отформатированное сообщение
    """
    message = TarotSpreadMessage(
        spread_type=spread_type,
        cards=cards,
        question=question,
        interpretation=interpretation
    )
    return await message.format()


async def format_educational_message(
        topic: str,
        content_type: str = "lesson"
) -> str:
    """
    Форматировать обучающее сообщение.

    Args:
        topic: Тема
        content_type: Тип контента

    Returns:
        Отформатированное сообщение
    """
    message = TarotEducationalMessage(topic, content_type)
    return await message.format()


async def format_statistics_message(
        stats_data: Dict[str, Any],
        period: str = "all_time"
) -> str:
    """
    Форматировать сообщение статистики.

    Args:
        stats_data: Данные статистики
        period: Период

    Returns:
        Отформатированное сообщение
    """
    message = TarotStatisticsMessage(stats_data, period)
    return await message.format()


# Предопределённые сообщения
class TarotMessages:
    """Предопределённые сообщения для Таро."""

    # Приветствия для раздела
    SECTION_WELCOME = """
🎴 Добро пожаловать в мир Таро!

Здесь ты можешь:
• Получить карту дня
• Сделать различные расклады
• Изучить значения карт
• Посмотреть историю гаданий

Что тебя интересует?
"""

    # Подготовка к раскладу
    SPREAD_PREPARATION = """
🕯 Подготовка к раскладу...

Сделай глубокий вдох и сосредоточься на своём вопросе.
Карты откроют то, что тебе нужно знать.

✨ Перемешиваю колоду...
"""

    # После расклада
    SPREAD_COMPLETE = """
✅ Расклад завершён!

Помни: карты показывают возможности, а не неизбежность.
Твои решения формируют будущее.

Сохранить расклад в избранное?
"""

    # Ошибки
    ERROR_DAILY_LIMIT = """
⚠️ Достигнут дневной лимит раскладов

В бесплатной версии доступно 3 расклада в день.
Следующий расклад будет доступен завтра.

Хочешь неограниченные расклады? Оформи подписку!
"""

    ERROR_PREMIUM_SPREAD = """
🔒 Этот расклад доступен только с подпиской

Расклад "{spread_name}" — эксклюзивная функция.
Оформи подписку, чтобы получить доступ!
"""


# Цитаты о Таро
TAROT_QUOTES = [
    "«Таро — это зеркало души» — Алистер Кроули",
    "«Карты не предсказывают будущее, они помогают его создать»",
    "«В каждой карте скрыта вселенная смыслов»",
    "«Таро — это язык подсознания»",
    "«Мудрость приходит через символы»",
    "«Карты — это ключи к внутренним дверям»",
    "«Таро учит нас видеть невидимое»",
    "«Каждый расклад — это медитация»"
]


def get_random_tarot_quote() -> str:
    """Получить случайную цитату о Таро."""
    return random.choice(TAROT_QUOTES)


logger.info("Модуль сообщений Таро загружен")