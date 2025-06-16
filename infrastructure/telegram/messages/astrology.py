"""
Модуль сообщений для раздела астрологии.

Этот модуль содержит:
- Форматирование гороскопов
- Описания натальных карт
- Интерпретации транзитов
- Лунные фазы и календарь
- Синастрия и совместимость

Автор: AI Assistant
Дата создания: 2024-12-30
"""

import logging
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, date, timedelta
from enum import Enum
import math

from .base import (
    BaseMessage, TemplateMessage, MessageBuilder,
    MessageStyle, MessageEmoji, MessageFormatter
)

# Настройка логирования
logger = logging.getLogger(__name__)


class ZodiacSign(Enum):
    """Знаки зодиака."""
    ARIES = ("aries", "Овен", "♈", "21.03-19.04")
    TAURUS = ("taurus", "Телец", "♉", "20.04-20.05")
    GEMINI = ("gemini", "Близнецы", "♊", "21.05-20.06")
    CANCER = ("cancer", "Рак", "♋", "21.06-22.07")
    LEO = ("leo", "Лев", "♌", "23.07-22.08")
    VIRGO = ("virgo", "Дева", "♍", "23.08-22.09")
    LIBRA = ("libra", "Весы", "♎", "23.09-22.10")
    SCORPIO = ("scorpio", "Скорпион", "♏", "23.10-21.11")
    SAGITTARIUS = ("sagittarius", "Стрелец", "♐", "22.11-21.12")
    CAPRICORN = ("capricorn", "Козерог", "♑", "22.12-19.01")
    AQUARIUS = ("aquarius", "Водолей", "♒", "20.01-18.02")
    PISCES = ("pisces", "Рыбы", "♓", "19.02-20.03")

    def __init__(self, code: str, name: str, symbol: str, dates: str):
        self.code = code
        self.rus_name = name
        self.symbol = symbol
        self.dates = dates


class Planet(Enum):
    """Планеты."""
    SUN = ("sun", "Солнце", "☉", "личность")
    MOON = ("moon", "Луна", "☽", "эмоции")
    MERCURY = ("mercury", "Меркурий", "☿", "общение")
    VENUS = ("venus", "Венера", "♀", "любовь")
    MARS = ("mars", "Марс", "♂", "действие")
    JUPITER = ("jupiter", "Юпитер", "♃", "удача")
    SATURN = ("saturn", "Сатурн", "♄", "ограничения")
    URANUS = ("uranus", "Уран", "♅", "перемены")
    NEPTUNE = ("neptune", "Нептун", "♆", "иллюзии")
    PLUTO = ("pluto", "Плутон", "♇", "трансформация")

    def __init__(self, code: str, name: str, symbol: str, sphere: str):
        self.code = code
        self.rus_name = name
        self.symbol = symbol
        self.sphere = sphere


class AspectType(Enum):
    """Типы аспектов."""
    CONJUNCTION = ("conjunction", "Соединение", "☌", 0, "сильный")
    SEXTILE = ("sextile", "Секстиль", "⚹", 60, "гармоничный")
    SQUARE = ("square", "Квадрат", "□", 90, "напряженный")
    TRINE = ("trine", "Трин", "△", 120, "гармоничный")
    OPPOSITION = ("opposition", "Оппозиция", "☍", 180, "напряженный")

    def __init__(self, code: str, name: str, symbol: str, angle: int, nature: str):
        self.code = code
        self.rus_name = name
        self.symbol = symbol
        self.angle = angle
        self.nature = nature


class MoonPhase(Enum):
    """Фазы луны."""
    NEW_MOON = ("new_moon", "Новолуние", "🌑", "начинания")
    WAXING_CRESCENT = ("waxing_crescent", "Растущий серп", "🌒", "рост")
    FIRST_QUARTER = ("first_quarter", "Первая четверть", "🌓", "действие")
    WAXING_GIBBOUS = ("waxing_gibbous", "Растущая луна", "🌔", "развитие")
    FULL_MOON = ("full_moon", "Полнолуние", "🌕", "кульминация")
    WANING_GIBBOUS = ("waning_gibbous", "Убывающая луна", "🌖", "благодарность")
    LAST_QUARTER = ("last_quarter", "Последняя четверть", "🌗", "отпускание")
    WANING_CRESCENT = ("waning_crescent", "Убывающий серп", "🌘", "завершение")

    def __init__(self, code: str, name: str, emoji: str, keywords: str):
        self.code = code
        self.rus_name = name
        self.emoji = emoji
        self.keywords = keywords


class HoroscopeMessage(BaseMessage):
    """Класс для создания сообщений гороскопов."""

    def __init__(
            self,
            sign: ZodiacSign,
            horoscope_type: str,
            horoscope_data: Dict[str, Any],
            is_personal: bool = False,
            style: MessageStyle = MessageStyle.MARKDOWN_V2
    ):
        """
        Инициализация сообщения гороскопа.

        Args:
            sign: Знак зодиака
            horoscope_type: Тип гороскопа (daily, weekly, etc.)
            horoscope_data: Данные гороскопа
            is_personal: Персональный ли гороскоп
            style: Стиль форматирования
        """
        super().__init__(style)
        self.sign = sign
        self.horoscope_type = horoscope_type
        self.horoscope_data = horoscope_data
        self.is_personal = is_personal

        logger.debug(f"Создание гороскопа для {sign.rus_name}")

    async def format(self, **kwargs) -> str:
        """Форматировать сообщение гороскопа."""
        builder = MessageBuilder(self.style)

        # Заголовок
        self._add_header(builder)

        # Основной прогноз
        self._add_main_forecast(builder)

        # Сферы жизни
        self._add_life_spheres(builder)

        # Советы
        self._add_advice(builder)

        # Числа и цвета
        self._add_lucky_items(builder)

        # Рейтинг дня (для ежедневного)
        if self.horoscope_type == "daily":
            self._add_day_rating(builder)

        return builder.build()

    def _add_header(self, builder: MessageBuilder) -> None:
        """Добавить заголовок гороскопа."""
        # Тип гороскопа
        type_names = {
            "daily": "на сегодня",
            "weekly": "на неделю",
            "monthly": "на месяц",
            "yearly": "на год",
            "love": "любовный",
            "career": "деловой"
        }

        type_name = type_names.get(self.horoscope_type, "")
        personal_prefix = "Персональный " if self.is_personal else ""

        # Заголовок
        header = f"{self.sign.symbol} {personal_prefix}Гороскоп {type_name}"
        builder.add_bold(header).add_line()

        # Для персонального - имя
        if self.is_personal and "user_name" in self.horoscope_data:
            builder.add_italic(f"для {self.horoscope_data['user_name']}").add_line()

        # Период
        if "period" in self.horoscope_data:
            builder.add_text(f"📅 {self.horoscope_data['period']}").add_line()

        builder.add_separator().add_line()

    def _add_main_forecast(self, builder: MessageBuilder) -> None:
        """Добавить основной прогноз."""
        forecast = self.horoscope_data.get("main_forecast", "")

        if forecast:
            # Разбиваем на абзацы
            paragraphs = forecast.split("\n\n")
            for paragraph in paragraphs:
                builder.add_line(paragraph)
                builder.add_empty_line()

    def _add_life_spheres(self, builder: MessageBuilder) -> None:
        """Добавить прогноз по сферам жизни."""
        spheres = self.horoscope_data.get("spheres", {})

        if spheres:
            builder.add_bold("🎯 По сферам жизни:").add_line()
            builder.add_empty_line()

            sphere_emojis = {
                "love": "💕",
                "career": "💼",
                "health": "🌿",
                "finance": "💰",
                "family": "👨‍👩‍👧‍👦"
            }

            for sphere, forecast in spheres.items():
                emoji = sphere_emojis.get(sphere, "•")
                sphere_names = {
                    "love": "Любовь",
                    "career": "Карьера",
                    "health": "Здоровье",
                    "finance": "Финансы",
                    "family": "Семья"
                }

                name = sphere_names.get(sphere, sphere)
                builder.add_text(f"{emoji} ").add_bold(f"{name}:")
                builder.add_text(f" {forecast}").add_line()

            builder.add_empty_line()

    def _add_advice(self, builder: MessageBuilder) -> None:
        """Добавить советы."""
        advice = self.horoscope_data.get("advice", "")

        if advice:
            builder.add_bold("💡 Совет:").add_line()
            builder.add_italic(advice).add_line()
            builder.add_empty_line()

    def _add_lucky_items(self, builder: MessageBuilder) -> None:
        """Добавить счастливые числа и цвета."""
        lucky_items = self.horoscope_data.get("lucky_items", {})

        if lucky_items:
            items_text = []

            if "numbers" in lucky_items:
                numbers = ", ".join(str(n) for n in lucky_items["numbers"])
                items_text.append(f"🔢 Числа: {numbers}")

            if "colors" in lucky_items:
                colors = ", ".join(lucky_items["colors"])
                items_text.append(f"🎨 Цвета: {colors}")

            if "time" in lucky_items:
                items_text.append(f"⏰ Время: {lucky_items['time']}")

            if items_text:
                builder.add_text(" | ".join(items_text)).add_line()
                builder.add_empty_line()

    def _add_day_rating(self, builder: MessageBuilder) -> None:
        """Добавить рейтинг дня."""
        ratings = self.horoscope_data.get("ratings", {})

        if ratings:
            builder.add_bold("📊 Рейтинг дня:").add_line()

            for category, rating in ratings.items():
                stars = "⭐" * rating + "☆" * (5 - rating)
                category_names = {
                    "overall": "Общий",
                    "love": "Любовь",
                    "work": "Работа",
                    "health": "Здоровье"
                }

                name = category_names.get(category, category)
                builder.add_text(f"{name}: {stars}").add_line()


class NatalChartMessage(BaseMessage):
    """Класс для создания сообщений натальной карты."""

    def __init__(
            self,
            chart_data: Dict[str, Any],
            section: Optional[str] = None,
            style: MessageStyle = MessageStyle.MARKDOWN_V2
    ):
        """
        Инициализация сообщения натальной карты.

        Args:
            chart_data: Данные натальной карты
            section: Конкретный раздел карты
            style: Стиль форматирования
        """
        super().__init__(style)
        self.chart_data = chart_data
        self.section = section

        logger.debug(f"Создание сообщения натальной карты, раздел: {section}")

    async def format(self, **kwargs) -> str:
        """Форматировать сообщение натальной карты."""
        builder = MessageBuilder(self.style)

        if not self.section:
            # Общий обзор
            return self._format_overview(builder)
        elif self.section == "planets_in_signs":
            return self._format_planets_in_signs(builder)
        elif self.section == "planets_in_houses":
            return self._format_planets_in_houses(builder)
        elif self.section == "aspects":
            return self._format_aspects(builder)
        elif self.section == "summary":
            return self._format_summary(builder)

        return builder.build()

    def _format_overview(self, builder: MessageBuilder) -> str:
        """Форматировать общий обзор."""
        user_name = self.chart_data.get("user_name", "")
        birth_date = self.chart_data.get("birth_date", "")
        birth_time = self.chart_data.get("birth_time", "")
        birth_place = self.chart_data.get("birth_place", "")

        builder.add_bold("🗺 Ваша натальная карта").add_line()

        if user_name:
            builder.add_italic(user_name).add_line()

        builder.add_separator().add_line()

        # Данные рождения
        builder.add_bold("📋 Данные рождения:").add_line()
        builder.add_text(f"📅 Дата: {birth_date}").add_line()
        builder.add_text(f"⏰ Время: {birth_time}").add_line()
        builder.add_text(f"📍 Место: {birth_place}").add_line()

        builder.add_empty_line()

        # Основные показатели
        builder.add_bold("🌟 Основные показатели:").add_line()

        # Солнце, Луна, Асцендент
        sun = self.chart_data.get("sun_sign", "")
        moon = self.chart_data.get("moon_sign", "")
        asc = self.chart_data.get("ascendant", "")

        if sun:
            builder.add_text(f"☉ Солнце в {sun}").add_line()
        if moon:
            builder.add_text(f"☽ Луна в {moon}").add_line()
        if asc:
            builder.add_text(f"↗️ Асцендент в {asc}").add_line()

        builder.add_empty_line()

        # Доминанты
        dominants = self.chart_data.get("dominants", {})
        if dominants:
            builder.add_bold("🎯 Доминанты:").add_line()

            if "element" in dominants:
                builder.add_text(f"Стихия: {dominants['element']}").add_line()
            if "quality" in dominants:
                builder.add_text(f"Качество: {dominants['quality']}").add_line()
            if "hemisphere" in dominants:
                builder.add_text(f"Полусфера: {dominants['hemisphere']}").add_line()

        return builder.build()

    def _format_planets_in_signs(self, builder: MessageBuilder) -> str:
        """Форматировать планеты в знаках."""
        builder.add_bold("🪐 Планеты в знаках").add_line()
        builder.add_separator().add_line()

        planets = self.chart_data.get("planets", [])

        for planet_data in planets:
            planet_name = planet_data.get("name", "")
            sign = planet_data.get("sign", "")
            degree = planet_data.get("degree", 0)
            is_retrograde = planet_data.get("is_retrograde", False)

            # Планета и знак
            planet_line = f"{planet_name} в {sign} "
            planet_line += f"({degree}°)"

            if is_retrograde:
                planet_line += " ℞"

            builder.add_bold(planet_line).add_line()

            # Интерпретация
            interpretation = planet_data.get("interpretation", "")
            if interpretation:
                builder.add_line(interpretation)

            builder.add_empty_line()

        return builder.build()

    def _format_planets_in_houses(self, builder: MessageBuilder) -> str:
        """Форматировать планеты в домах."""
        builder.add_bold("🏠 Планеты в домах").add_line()
        builder.add_separator().add_line()

        houses = self.chart_data.get("houses", [])

        for house_data in houses:
            house_num = house_data.get("number", 0)
            sign = house_data.get("sign", "")
            planets = house_data.get("planets", [])

            # Заголовок дома
            house_meanings = {
                1: "Личность",
                2: "Ресурсы",
                3: "Общение",
                4: "Дом и семья",
                5: "Творчество",
                6: "Работа и здоровье",
                7: "Партнерство",
                8: "Трансформация",
                9: "Философия",
                10: "Карьера",
                11: "Дружба",
                12: "Подсознание"
            }

            meaning = house_meanings.get(house_num, "")
            builder.add_bold(f"{house_num} дом - {meaning}").add_line()
            builder.add_text(f"Знак: {sign}").add_line()

            if planets:
                builder.add_text("Планеты: ")
                builder.add_text(", ".join(planets)).add_line()

                # Интерпретация
                interpretation = house_data.get("interpretation", "")
                if interpretation:
                    builder.add_empty_line()
                    builder.add_line(interpretation)
            else:
                builder.add_text("Планет нет").add_line()

            builder.add_empty_line()

        return builder.build()

    def _format_aspects(self, builder: MessageBuilder) -> str:
        """Форматировать аспекты."""
        builder.add_bold("📐 Основные аспекты").add_line()
        builder.add_separator().add_line()

        aspects = self.chart_data.get("aspects", [])

        # Группируем по типу аспекта
        grouped_aspects = {}
        for aspect in aspects:
            aspect_type = aspect.get("type", "")
            if aspect_type not in grouped_aspects:
                grouped_aspects[aspect_type] = []
            grouped_aspects[aspect_type].append(aspect)

        # Выводим по группам
        aspect_order = ["conjunction", "trine", "sextile", "square", "opposition"]

        for aspect_type in aspect_order:
            if aspect_type in grouped_aspects:
                # Находим соответствующий AspectType
                for at in AspectType:
                    if at.code == aspect_type:
                        builder.add_bold(f"{at.symbol} {at.rus_name}").add_line()
                        break

                for aspect in grouped_aspects[aspect_type]:
                    planet1 = aspect.get("planet1", "")
                    planet2 = aspect.get("planet2", "")
                    orb = aspect.get("orb", 0)

                    builder.add_text(f"• {planet1} - {planet2} ")
                    builder.add_text(f"(орбис {orb}°)").add_line()

                builder.add_empty_line()

        return builder.build()

    def _format_summary(self, builder: MessageBuilder) -> str:
        """Форматировать общее резюме."""
        builder.add_bold("📊 Общий анализ личности").add_line()
        builder.add_separator().add_line()

        summary = self.chart_data.get("summary", {})

        # Сильные стороны
        strengths = summary.get("strengths", [])
        if strengths:
            builder.add_bold("💪 Сильные стороны:").add_line()
            builder.add_list(strengths)
            builder.add_empty_line()

        # Области развития
        challenges = summary.get("challenges", [])
        if challenges:
            builder.add_bold("🎯 Области для развития:").add_line()
            builder.add_list(challenges)
            builder.add_empty_line()

        # Жизненная задача
        life_purpose = summary.get("life_purpose", "")
        if life_purpose:
            builder.add_bold("🌟 Жизненная задача:").add_line()
            builder.add_line(life_purpose)
            builder.add_empty_line()

        # Совет
        advice = summary.get("advice", "")
        if advice:
            builder.add_bold("💡 Совет:").add_line()
            builder.add_italic(advice)

        return builder.build()


class TransitMessage(BaseMessage):
    """Класс для создания сообщений о транзитах."""

    def __init__(
            self,
            transits: List[Dict[str, Any]],
            period: str,
            style: MessageStyle = MessageStyle.MARKDOWN_V2
    ):
        """
        Инициализация сообщения транзитов.

        Args:
            transits: Список транзитов
            period: Период транзитов
            style: Стиль форматирования
        """
        super().__init__(style)
        self.transits = transits
        self.period = period

    async def format(self, **kwargs) -> str:
        """Форматировать сообщение транзитов."""
        builder = MessageBuilder(self.style)

        # Заголовок
        period_names = {
            "today": "на сегодня",
            "week": "на неделю",
            "month": "на месяц",
            "year": "на год"
        }

        period_name = period_names.get(self.period, self.period)
        builder.add_bold(f"🌌 Транзиты {period_name}").add_line()
        builder.add_separator().add_line()

        if not self.transits:
            builder.add_italic("Значимых транзитов в этот период нет").add_line()
            return builder.build()

        # Группируем транзиты по важности
        important_transits = []
        regular_transits = []

        for transit in self.transits:
            if transit.get("is_important", False):
                important_transits.append(transit)
            else:
                regular_transits.append(transit)

        # Важные транзиты
        if important_transits:
            builder.add_bold("⚡ Важные транзиты:").add_line()
            builder.add_empty_line()

            for transit in important_transits:
                self._format_transit(builder, transit, detailed=True)
                builder.add_empty_line()

        # Обычные транзиты
        if regular_transits:
            builder.add_bold("🌟 Другие транзиты:").add_line()
            builder.add_empty_line()

            for transit in regular_transits:
                self._format_transit(builder, transit, detailed=False)

        # Общий совет
        builder.add_empty_line()
        builder.add_italic("💡 Используйте благоприятные транзиты для важных дел!")

        return builder.build()

    def _format_transit(self, builder: MessageBuilder, transit: Dict[str, Any], detailed: bool) -> None:
        """Форматировать отдельный транзит."""
        transiting_planet = transit.get("transiting_planet", "")
        aspect = transit.get("aspect", "")
        natal_planet = transit.get("natal_planet", "")
        date_range = transit.get("date_range", "")

        # Заголовок транзита
        transit_text = f"{transiting_planet} {aspect} {natal_planet}"

        if detailed:
            builder.add_bold(transit_text).add_line()
            if date_range:
                builder.add_text(f"📅 {date_range}").add_line()

            # Интерпретация
            interpretation = transit.get("interpretation", "")
            if interpretation:
                builder.add_line(interpretation)

            # Сферы влияния
            spheres = transit.get("spheres", [])
            if spheres:
                builder.add_text("Сферы влияния: ")
                builder.add_text(", ".join(spheres)).add_line()
        else:
            # Краткий формат
            builder.add_text(f"• {transit_text}")
            if date_range:
                builder.add_text(f" ({date_range})")
            builder.add_line()


class MoonPhaseMessage(BaseMessage):
    """Класс для создания сообщений о фазах луны."""

    def __init__(
            self,
            phase_data: Dict[str, Any],
            include_calendar: bool = False,
            style: MessageStyle = MessageStyle.MARKDOWN_V2
    ):
        """
        Инициализация сообщения фазы луны.

        Args:
            phase_data: Данные о фазе луны
            include_calendar: Включать ли календарь
            style: Стиль форматирования
        """
        super().__init__(style)
        self.phase_data = phase_data
        self.include_calendar = include_calendar

    async def format(self, **kwargs) -> str:
        """Форматировать сообщение о фазе луны."""
        builder = MessageBuilder(self.style)

        # Определяем текущую фазу
        phase_name = self.phase_data.get("phase_name", "")
        phase_emoji = self.phase_data.get("phase_emoji", "🌙")
        illumination = self.phase_data.get("illumination", 0)

        # Заголовок
        builder.add_bold(f"{phase_emoji} Луна сегодня").add_line()
        builder.add_separator().add_line()

        # Фаза и освещенность
        builder.add_text(f"Фаза: ").add_bold(phase_name).add_line()
        builder.add_text(f"Освещенность: {illumination}%").add_line()

        # Знак зодиака
        moon_sign = self.phase_data.get("moon_sign", "")
        if moon_sign:
            builder.add_text(f"Луна в знаке: {moon_sign}").add_line()

        builder.add_empty_line()

        # Рекомендации для фазы
        self._add_phase_recommendations(builder)

        # Календарь (если нужен)
        if self.include_calendar:
            self._add_lunar_calendar(builder)

        return builder.build()

    def _add_phase_recommendations(self, builder: MessageBuilder) -> None:
        """Добавить рекомендации для фазы."""
        recommendations = self.phase_data.get("recommendations", {})

        if recommendations:
            builder.add_bold("📋 Рекомендации:").add_line()
            builder.add_empty_line()

            # По категориям
            categories = [
                ("general", "🌟 Общие", "general"),
                ("health", "🌿 Здоровье", "health"),
                ("beauty", "💄 Красота", "beauty"),
                ("garden", "🌱 Сад и огород", "garden"),
                ("business", "💼 Дела", "business")
            ]

            for key, title, _ in categories:
                if key in recommendations and recommendations[key]:
                    builder.add_bold(title).add_line()

                    if isinstance(recommendations[key], list):
                        builder.add_list(recommendations[key])
                    else:
                        builder.add_line(recommendations[key])

                    builder.add_empty_line()

    def _add_lunar_calendar(self, builder: MessageBuilder) -> None:
        """Добавить лунный календарь."""
        calendar_data = self.phase_data.get("calendar", {})

        if calendar_data:
            builder.add_bold("📅 Ближайшие фазы:").add_line()
            builder.add_empty_line()

            phases = calendar_data.get("upcoming_phases", [])
            for phase in phases[:4]:  # Максимум 4 фазы
                date = phase.get("date", "")
                name = phase.get("name", "")
                emoji = phase.get("emoji", "🌙")

                builder.add_text(f"{emoji} {date} — {name}").add_line()


class SynastryMessage(BaseMessage):
    """Класс для создания сообщений синастрии."""

    def __init__(
            self,
            synastry_data: Dict[str, Any],
            style: MessageStyle = MessageStyle.MARKDOWN_V2
    ):
        """
        Инициализация сообщения синастрии.

        Args:
            synastry_data: Данные синастрии
            style: Стиль форматирования
        """
        super().__init__(style)
        self.synastry_data = synastry_data

    async def format(self, **kwargs) -> str:
        """Форматировать сообщение синастрии."""
        builder = MessageBuilder(self.style)

        # Заголовок
        person1 = self.synastry_data.get("person1_name", "Партнер 1")
        person2 = self.synastry_data.get("person2_name", "Партнер 2")

        builder.add_bold(f"💑 Совместимость").add_line()
        builder.add_text(f"{person1} и {person2}").add_line()
        builder.add_separator().add_line()

        # Общий рейтинг
        overall_rating = self.synastry_data.get("overall_rating", 0)
        builder.add_bold("Общая совместимость: ")
        builder.add_text(f"{overall_rating}/10 ")
        builder.add_text("⭐" * (overall_rating // 2)).add_line()
        builder.add_empty_line()

        # По сферам
        spheres = self.synastry_data.get("spheres", {})
        if spheres:
            builder.add_bold("По сферам жизни:").add_line()
            builder.add_empty_line()

            sphere_info = [
                ("emotional", "💕 Эмоциональная связь"),
                ("intellectual", "🧠 Интеллектуальная совместимость"),
                ("physical", "🔥 Физическое притяжение"),
                ("values", "💎 Общие ценности"),
                ("communication", "💬 Общение"),
                ("longterm", "🏡 Долгосрочные перспективы")
            ]

            for key, title in sphere_info:
                if key in spheres:
                    rating = spheres[key].get("rating", 0)
                    description = spheres[key].get("description", "")

                    builder.add_bold(title).add_line()
                    builder.add_text("Оценка: ")
                    builder.add_text("⭐" * rating).add_line()

                    if description:
                        builder.add_line(description)

                    builder.add_empty_line()

        # Сильные стороны
        strengths = self.synastry_data.get("strengths", [])
        if strengths:
            builder.add_bold("💪 Сильные стороны союза:").add_line()
            builder.add_list(strengths)
            builder.add_empty_line()

        # Области для работы
        challenges = self.synastry_data.get("challenges", [])
        if challenges:
            builder.add_bold("🎯 Над чем стоит поработать:").add_line()
            builder.add_list(challenges)
            builder.add_empty_line()

        # Совет
        advice = self.synastry_data.get("advice", "")
        if advice:
            builder.add_bold("💡 Совет:").add_line()
            builder.add_italic(advice)

        return builder.build()


# Функции для быстрого создания сообщений
async def format_horoscope_message(
        sign: str,
        horoscope_type: str,
        horoscope_data: Dict[str, Any],
        is_personal: bool = False
) -> str:
    """Форматировать сообщение гороскопа."""
    # Находим знак зодиака
    zodiac_sign = None
    for zs in ZodiacSign:
        if zs.code == sign:
            zodiac_sign = zs
            break

    if not zodiac_sign:
        zodiac_sign = ZodiacSign.ARIES  # По умолчанию

    message = HoroscopeMessage(
        sign=zodiac_sign,
        horoscope_type=horoscope_type,
        horoscope_data=horoscope_data,
        is_personal=is_personal
    )
    return await message.format()


async def format_natal_chart_message(
        chart_data: Dict[str, Any],
        section: Optional[str] = None
) -> str:
    """Форматировать сообщение натальной карты."""
    message = NatalChartMessage(chart_data, section)
    return await message.format()


async def format_transit_message(
        transits: List[Dict[str, Any]],
        period: str = "today"
) -> str:
    """Форматировать сообщение транзитов."""
    message = TransitMessage(transits, period)
    return await message.format()


async def format_moon_phase_message(
        phase_data: Dict[str, Any],
        include_calendar: bool = False
) -> str:
    """Форматировать сообщение фазы луны."""
    message = MoonPhaseMessage(phase_data, include_calendar)
    return await message.format()


async def format_synastry_message(
        synastry_data: Dict[str, Any]
) -> str:
    """Форматировать сообщение синастрии."""
    message = SynastryMessage(synastry_data)
    return await message.format()


# Вспомогательные функции
def get_zodiac_sign_by_date(birth_date: date) -> ZodiacSign:
    """
    Определить знак зодиака по дате рождения.

    Args:
        birth_date: Дата рождения

    Returns:
        Знак зодиака
    """
    day = birth_date.day
    month = birth_date.month

    # Границы знаков зодиака
    if (month == 3 and day >= 21) or (month == 4 and day <= 19):
        return ZodiacSign.ARIES
    elif (month == 4 and day >= 20) or (month == 5 and day <= 20):
        return ZodiacSign.TAURUS
    elif (month == 5 and day >= 21) or (month == 6 and day <= 20):
        return ZodiacSign.GEMINI
    elif (month == 6 and day >= 21) or (month == 7 and day <= 22):
        return ZodiacSign.CANCER
    elif (month == 7 and day >= 23) or (month == 8 and day <= 22):
        return ZodiacSign.LEO
    elif (month == 8 and day >= 23) or (month == 9 and day <= 22):
        return ZodiacSign.VIRGO
    elif (month == 9 and day >= 23) or (month == 10 and day <= 22):
        return ZodiacSign.LIBRA
    elif (month == 10 and day >= 23) or (month == 11 and day <= 21):
        return ZodiacSign.SCORPIO
    elif (month == 11 and day >= 22) or (month == 12 and day <= 21):
        return ZodiacSign.SAGITTARIUS
    elif (month == 12 and day >= 22) or (month == 1 and day <= 19):
        return ZodiacSign.CAPRICORN
    elif (month == 1 and day >= 20) or (month == 2 and day <= 18):
        return ZodiacSign.AQUARIUS
    else:
        return ZodiacSign.PISCES


def calculate_moon_phase(date_obj: date) -> MoonPhase:
    """
    Вычислить фазу луны для даты (упрощенный алгоритм).

    Args:
        date_obj: Дата

    Returns:
        Фаза луны
    """
    # Это упрощенный алгоритм для примера
    # В реальности нужно использовать точные астрономические расчеты

    year = date_obj.year
    month = date_obj.month
    day = date_obj.day

    if month < 3:
        year -= 1
        month += 12

    a = year // 100
    b = a // 4
    c = 2 - a + b
    e = int(365.25 * (year + 4716))
    f = int(30.6001 * (month + 1))
    jd = c + day + e + f - 1524.5

    # Новолуние 2000-01-06
    days_since_new = (jd - 2451549.5) % 29.53059

    phase = days_since_new / 29.53059

    if phase < 0.0625:
        return MoonPhase.NEW_MOON
    elif phase < 0.1875:
        return MoonPhase.WAXING_CRESCENT
    elif phase < 0.3125:
        return MoonPhase.FIRST_QUARTER
    elif phase < 0.4375:
        return MoonPhase.WAXING_GIBBOUS
    elif phase < 0.5625:
        return MoonPhase.FULL_MOON
    elif phase < 0.6875:
        return MoonPhase.WANING_GIBBOUS
    elif phase < 0.8125:
        return MoonPhase.LAST_QUARTER
    elif phase < 0.9375:
        return MoonPhase.WANING_CRESCENT
    else:
        return MoonPhase.NEW_MOON


# Предопределённые сообщения
class AstrologyMessages:
    """Предопределённые сообщения для астрологии."""

    # Приветствие раздела
    SECTION_WELCOME = """
🔮 Добро пожаловать в мир Астрологии!

Здесь ты можешь:
• Получить персональный гороскоп
• Построить натальную карту
• Узнать текущие транзиты
• Проверить совместимость
• Следить за фазами луны

Что тебя интересует?
"""

    # Необходимы данные рождения
    BIRTH_DATA_REQUIRED = """
📋 Для этой функции необходимы данные рождения

Пожалуйста, укажите:
• Дату рождения
• Время рождения (желательно точное)
• Место рождения

Это поможет сделать расчёты максимально точными.
"""

    # Расчёт карты
    CALCULATING_CHART = """
🌌 Рассчитываю вашу натальную карту...

Это займёт несколько секунд.
Анализирую положения планет на момент вашего рождения.
"""

    # Ошибки
    ERROR_INVALID_TIME = """
⚠️ Неверный формат времени

Пожалуйста, укажите время в формате ЧЧ:ММ
Например: 14:30
"""

    ERROR_PREMIUM_FEATURE = """
🔒 Эта функция доступна с подпиской

{feature_name} — эксклюзивная возможность.
Оформите подписку для полного доступа!
"""


logger.info("Модуль сообщений астрологии загружен")