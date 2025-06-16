"""
Модуль клавиатур для раздела астрологии.

Этот модуль содержит:
- Клавиатуры ввода данных рождения
- Выбор типов прогнозов и гороскопов
- Настройки натальной карты
- Управление транзитами и прогрессиями
- Интерфейс синастрии
- Астрологический календарь

Автор: AI Assistant
Дата создания: 2024-12-30
"""

import logging
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, date, time
from enum import Enum
import calendar

from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup
from aiogram.filters.callback_data import CallbackData

from .base import (
    InlineKeyboard, ReplyKeyboard, PaginatedKeyboard,
    ButtonConfig, ButtonStyle
)

# Настройка логирования
logger = logging.getLogger(__name__)


class AstrologySection(Enum):
    """Разделы астрологии."""
    HOROSCOPE = "horoscope"
    NATAL_CHART = "natal_chart"
    TRANSITS = "transits"
    PROGRESSIONS = "progressions"
    SYNASTRY = "synastry"
    SOLAR_RETURN = "solar_return"
    LUNAR_CALENDAR = "lunar_calendar"
    EPHEMERIS = "ephemeris"


class HoroscopeType(Enum):
    """Типы гороскопов."""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"
    LOVE = "love"
    CAREER = "career"
    HEALTH = "health"
    PERSONAL = "personal"


class HouseSystem(Enum):
    """Системы домов."""
    PLACIDUS = "placidus"
    KOCH = "koch"
    EQUAL = "equal"
    WHOLE_SIGN = "whole_sign"
    REGIOMONTANUS = "regiomontanus"
    CAMPANUS = "campanus"


class AspectType(Enum):
    """Типы аспектов."""
    MAJOR = "major"  # Основные
    MINOR = "minor"  # Минорные
    ALL = "all"  # Все


class PlanetSet(Enum):
    """Наборы планет."""
    BASIC = "basic"  # Солнце-Марс
    STANDARD = "standard"  # + социальные
    EXTENDED = "extended"  # + высшие
    FULL = "full"  # + астероиды и точки


# Callback Data классы
class AstrologyCallbackData(CallbackData, prefix="astro"):
    """Основной callback для астрологии."""
    action: str
    section: Optional[str] = None
    value: Optional[str] = None
    extra: Optional[str] = None


class BirthDataCallbackData(CallbackData, prefix="birth"):
    """Callback для данных рождения."""
    action: str  # set_date, set_time, set_place, confirm
    field: Optional[str] = None
    value: Optional[str] = None


class ChartCallbackData(CallbackData, prefix="chart"):
    """Callback для натальной карты."""
    action: str  # generate, settings, aspect, planet
    chart_type: Optional[str] = None
    value: Optional[str] = None


class TransitCallbackData(CallbackData, prefix="transit"):
    """Callback для транзитов."""
    action: str  # show, period, planet, aspect
    period: Optional[str] = None
    planet: Optional[int] = None


class CalendarCallbackData(CallbackData, prefix="calendar"):
    """Callback для календаря."""
    action: str  # navigate, select
    year: int
    month: int
    day: Optional[int] = None


class BirthDataKeyboard(InlineKeyboard):
    """Клавиатура ввода данных рождения."""

    def __init__(
            self,
            current_data: Optional[Dict[str, Any]] = None,
            editing_field: Optional[str] = None
    ):
        """
        Инициализация клавиатуры данных рождения.

        Args:
            current_data: Текущие данные
            editing_field: Редактируемое поле
        """
        super().__init__()
        self.current_data = current_data or {}
        self.editing_field = editing_field

        logger.debug(f"Создание клавиатуры данных рождения, поле: {editing_field}")

    async def build(self, **kwargs) -> InlineKeyboardMarkup:
        """Построить клавиатуру."""
        if self.editing_field:
            # Режим редактирования конкретного поля
            if self.editing_field == "date":
                await self._build_date_input()
            elif self.editing_field == "time":
                await self._build_time_input()
            elif self.editing_field == "place":
                await self._build_place_input()
        else:
            # Общий вид с текущими данными
            await self._build_summary()

        return await super().build(**kwargs)

    async def _build_summary(self) -> None:
        """Построить сводку данных."""
        # Дата рождения
        date_text = "📅 Дата: "
        if "birth_date" in self.current_data:
            date_obj = self.current_data["birth_date"]
            date_text += date_obj.strftime("%d.%m.%Y")
        else:
            date_text += "Не указана ❗"

        self.add_button(
            text=date_text,
            callback_data=BirthDataCallbackData(
                action="edit",
                field="date"
            )
        )

        # Время рождения
        time_text = "⏰ Время: "
        if "birth_time" in self.current_data:
            time_obj = self.current_data["birth_time"]
            time_text += time_obj.strftime("%H:%M")
            if self.current_data.get("time_unknown"):
                time_text += " (неточное)"
        else:
            time_text += "Не указано"

        self.add_button(
            text=time_text,
            callback_data=BirthDataCallbackData(
                action="edit",
                field="time"
            )
        )

        # Место рождения
        place_text = "📍 Место: "
        if "birth_place" in self.current_data:
            place_text += self.current_data["birth_place"]["name"]
        else:
            place_text += "Не указано ❗"

        self.add_button(
            text=place_text,
            callback_data=BirthDataCallbackData(
                action="edit",
                field="place"
            )
        )

        self.builder.adjust(1)

        # Кнопки действий
        if self._is_data_complete():
            self.add_button(
                text="✅ Сохранить",
                callback_data=BirthDataCallbackData(
                    action="confirm"
                )
            )

            self.add_button(
                text="🔄 Пересчитать карту",
                callback_data=ChartCallbackData(
                    action="generate",
                    chart_type="natal"
                )
            )

            self.builder.adjust(1, 1, 1, 2)
        else:
            self.add_button(
                text="❌ Заполните все поля",
                callback_data="noop"
            )
            self.builder.adjust(1, 1, 1, 1)

        # Дополнительные опции
        self.add_button(
            text="🌍 Часовой пояс: " + self.current_data.get("timezone", "UTC"),
            callback_data=BirthDataCallbackData(
                action="edit",
                field="timezone"
            )
        )

        self.add_back_button("astro:main")

    async def _build_date_input(self) -> None:
        """Построить ввод даты."""
        # Используем календарь
        today = date.today()
        selected_date = self.current_data.get("birth_date", today)

        # Заголовок
        self.add_button(
            text=f"📅 Выберите дату рождения",
            callback_data="noop"
        )

        # Быстрый выбор года
        current_year = selected_date.year
        year_buttons = []

        # Декады для быстрого перехода
        for decade_start in range(1920, 2030, 10):
            if decade_start <= current_year < decade_start + 10:
                text = f"[{decade_start}s]"
            else:
                text = f"{decade_start}s"

            year_buttons.append((text, decade_start))

        for text, year in year_buttons[-6:]:  # Последние 6 декад
            self.add_button(
                text=text,
                callback_data=f"birth:year:{year}"
            )

        # Навигация по годам
        self.add_button(
            text="◀️",
            callback_data=f"birth:year:{current_year - 1}"
        )

        self.add_button(
            text=str(current_year),
            callback_data="noop"
        )

        self.add_button(
            text="▶️",
            callback_data=f"birth:year:{current_year + 1}"
        )

        # Месяцы
        months = [
            "Янв", "Фев", "Мар", "Апр", "Май", "Июн",
            "Июл", "Авг", "Сен", "Окт", "Ноя", "Дек"
        ]

        for i, month_name in enumerate(months, 1):
            style = "[{}]" if selected_date.month == i else "{}"
            self.add_button(
                text=style.format(month_name),
                callback_data=f"birth:month:{i}"
            )

        # Календарная сетка дней
        cal = calendar.monthcalendar(current_year, selected_date.month)

        # Дни недели
        weekdays = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
        for day_name in weekdays:
            self.add_button(text=day_name, callback_data="noop")

        # Дни месяца
        for week in cal:
            for day in week:
                if day == 0:
                    self.add_button(text=" ", callback_data="noop")
                else:
                    if day == selected_date.day:
                        text = f"[{day}]"
                    else:
                        text = str(day)

                    self.add_button(
                        text=text,
                        callback_data=BirthDataCallbackData(
                            action="set_date",
                            value=f"{current_year}-{selected_date.month:02d}-{day:02d}"
                        )
                    )

        # Настройка сетки
        self.builder.adjust(
            1,  # Заголовок
            6,  # Декады
            3,  # Навигация по годам
            6, 6,  # Месяцы
            7,  # Дни недели
            *([7] * len(cal))  # Недели
        )

        # Кнопки управления
        self.add_button(
            text="❌ Отмена",
            callback_data=BirthDataCallbackData(action="cancel")
        )

        if "birth_date" in self.current_data:
            self.add_button(
                text="✅ Готово",
                callback_data=BirthDataCallbackData(action="back")
            )

    async def _build_time_input(self) -> None:
        """Построить ввод времени."""
        current_time = self.current_data.get("birth_time", time(12, 0))

        # Заголовок
        self.add_button(
            text=f"⏰ Время рождения: {current_time.strftime('%H:%M')}",
            callback_data="noop"
        )

        # Часы
        self.add_button(text="Часы:", callback_data="noop")

        for h in range(0, 24, 3):
            hour_range = f"{h:02d}-{h + 2:02d}"
            if h <= current_time.hour < h + 3:
                hour_range = f"[{hour_range}]"

            self.add_button(
                text=hour_range,
                callback_data=f"birth:hour_range:{h}"
            )

        # Точный выбор часа
        start_hour = (current_time.hour // 3) * 3
        for h in range(start_hour, min(start_hour + 3, 24)):
            text = f"{h:02d}"
            if h == current_time.hour:
                text = f"[{text}]"

            self.add_button(
                text=text,
                callback_data=f"birth:hour:{h}"
            )

        # Минуты
        self.add_button(text="Минуты:", callback_data="noop")

        for m in range(0, 60, 15):
            text = f":{m:02d}"
            if m <= current_time.minute < m + 15:
                text = f"[{text}]"

            self.add_button(
                text=text,
                callback_data=f"birth:minute_range:{m}"
            )

        # Точный выбор минут
        start_min = (current_time.minute // 15) * 15
        for m in range(start_min, min(start_min + 15, 60), 5):
            text = f":{m:02d}"
            if m == current_time.minute:
                text = f"[{text}]"

            self.add_button(
                text=text,
                callback_data=f"birth:minute:{m}"
            )

        # Настройка сетки
        self.builder.adjust(
            1,  # Заголовок
            1, 8,  # Часы заголовок + диапазоны
            3,  # Точные часы
            1, 4,  # Минуты заголовок + диапазоны
            3  # Точные минуты
        )

        # Специальные опции
        self.add_button(
            text="🤷 Время неизвестно",
            callback_data=BirthDataCallbackData(
                action="time_unknown"
            )
        )

        self.add_button(
            text="🌅 Восход (~6:00)",
            callback_data=BirthDataCallbackData(
                action="set_time",
                value="06:00"
            )
        )

        self.add_button(
            text="☀️ Полдень (12:00)",
            callback_data=BirthDataCallbackData(
                action="set_time",
                value="12:00"
            )
        )

        self.add_button(
            text="🌇 Закат (~18:00)",
            callback_data=BirthDataCallbackData(
                action="set_time",
                value="18:00"
            )
        )

        # Кнопки управления
        self.add_button(
            text="✅ Готово",
            callback_data=BirthDataCallbackData(action="back")
        )

        self.builder.adjust(
            1, 8, 3, 1, 4, 3,  # Основная сетка
            1, 3,  # Специальные опции
            1  # Готово
        )

    async def _build_place_input(self) -> None:
        """Построить ввод места."""
        # Здесь должен быть поиск городов через API
        # Сейчас показываем популярные города

        self.add_button(
            text="🔍 Поиск места рождения",
            callback_data="noop"
        )

        # Популярные города России
        cities = [
            ("Москва", "55.7558", "37.6173"),
            ("Санкт-Петербург", "59.9311", "30.3609"),
            ("Новосибирск", "55.0084", "82.9357"),
            ("Екатеринбург", "56.8389", "60.6057"),
            ("Казань", "55.8304", "49.0661"),
            ("Нижний Новгород", "56.2965", "43.9361"),
            ("Челябинск", "55.1644", "61.4368"),
            ("Самара", "53.2415", "50.2212"),
            ("Омск", "54.9885", "73.3242"),
            ("Ростов-на-Дону", "47.2357", "39.7015")
        ]

        for city_name, lat, lon in cities:
            self.add_button(
                text=f"📍 {city_name}",
                callback_data=BirthDataCallbackData(
                    action="set_place",
                    value=f"{city_name}|{lat}|{lon}"
                )
            )

        self.builder.adjust(1, 2, 2, 2, 2, 2)

        # Ввод координат вручную
        self.add_button(
            text="🌍 Ввести координаты",
            callback_data=BirthDataCallbackData(
                action="input_coords"
            )
        )

        self.add_button(
            text="🗺 Выбрать на карте",
            callback_data=BirthDataCallbackData(
                action="map_select"
            )
        )

        self.add_back_button(
            BirthDataCallbackData(action="back").pack()
        )

    def _is_data_complete(self) -> bool:
        """Проверить полноту данных."""
        required = ["birth_date", "birth_place"]
        return all(field in self.current_data for field in required)


class HoroscopeMenuKeyboard(InlineKeyboard):
    """Клавиатура меню гороскопов."""

    def __init__(
            self,
            user_subscription: str = "free",
            has_birth_data: bool = False
    ):
        """
        Инициализация меню гороскопов.

        Args:
            user_subscription: Уровень подписки
            has_birth_data: Есть ли данные рождения
        """
        super().__init__()
        self.user_subscription = user_subscription
        self.has_birth_data = has_birth_data

    async def build(self, **kwargs) -> InlineKeyboardMarkup:
        """Построить меню гороскопов."""
        # Общие гороскопы - для всех
        self.add_button(
            text="📅 На сегодня",
            callback_data=AstrologyCallbackData(
                action="horoscope",
                section=HoroscopeType.DAILY.value
            )
        )

        self.add_button(
            text="📆 На неделю",
            callback_data=AstrologyCallbackData(
                action="horoscope",
                section=HoroscopeType.WEEKLY.value
            )
        )

        # Расширенные - для подписчиков
        if self.user_subscription != "free":
            self.add_button(
                text="🗓 На месяц",
                callback_data=AstrologyCallbackData(
                    action="horoscope",
                    section=HoroscopeType.MONTHLY.value
                )
            )

            self.add_button(
                text="🎆 На год",
                callback_data=AstrologyCallbackData(
                    action="horoscope",
                    section=HoroscopeType.YEARLY.value
                )
            )

        # Тематические - для премиум
        if self.user_subscription in ["premium", "vip"]:
            self.add_button(
                text="💕 Любовный",
                callback_data=AstrologyCallbackData(
                    action="horoscope",
                    section=HoroscopeType.LOVE.value
                )
            )

            self.add_button(
                text="💼 Деловой",
                callback_data=AstrologyCallbackData(
                    action="horoscope",
                    section=HoroscopeType.CAREER.value
                )
            )

        # Персональный - если есть данные
        if self.has_birth_data and self.user_subscription != "free":
            self.add_button(
                text="⭐ Персональный",
                callback_data=AstrologyCallbackData(
                    action="horoscope",
                    section=HoroscopeType.PERSONAL.value
                )
            )
        elif not self.has_birth_data:
            self.add_button(
                text="🔒 Персональный (нужны данные)",
                callback_data=BirthDataCallbackData(action="request")
            )

        # Настройка сетки
        if self.user_subscription == "free":
            self.builder.adjust(2, 1)
        elif self.user_subscription == "basic":
            self.builder.adjust(2, 2, 1)
        else:
            self.builder.adjust(2, 2, 2, 1)

        self.add_back_button("astro:main")

        return await super().build(**kwargs)


class NatalChartKeyboard(InlineKeyboard):
    """Клавиатура натальной карты."""

    def __init__(
            self,
            has_chart: bool = False,
            chart_settings: Optional[Dict[str, Any]] = None
    ):
        """
        Инициализация клавиатуры натальной карты.

        Args:
            has_chart: Построена ли карта
            chart_settings: Текущие настройки
        """
        super().__init__()
        self.has_chart = has_chart
        self.chart_settings = chart_settings or {
            "house_system": HouseSystem.PLACIDUS,
            "planet_set": PlanetSet.STANDARD,
            "aspect_type": AspectType.MAJOR
        }

    async def build(self, **kwargs) -> InlineKeyboardMarkup:
        """Построить клавиатуру."""
        if not self.has_chart:
            # Карта не построена
            self.add_button(
                text="🔮 Построить натальную карту",
                callback_data=ChartCallbackData(
                    action="generate",
                    chart_type="natal"
                )
            )

            self.add_button(
                text="📝 Ввести данные рождения",
                callback_data=BirthDataCallbackData(action="request")
            )
        else:
            # Карта построена - показываем опции
            self.add_button(
                text="📊 Общий анализ",
                callback_data=ChartCallbackData(
                    action="analyze",
                    chart_type="general"
                )
            )

            self.add_button(
                text="🪐 Планеты в знаках",
                callback_data=ChartCallbackData(
                    action="planets",
                    chart_type="signs"
                )
            )

            self.add_button(
                text="🏠 Планеты в домах",
                callback_data=ChartCallbackData(
                    action="planets",
                    chart_type="houses"
                )
            )

            self.add_button(
                text="📐 Аспекты",
                callback_data=ChartCallbackData(
                    action="aspects"
                )
            )

            # Дополнительные функции для премиум
            if self.chart_settings["planet_set"] in [PlanetSet.EXTENDED, PlanetSet.FULL]:
                self.add_button(
                    text="🌟 Фиксированные звезды",
                    callback_data=ChartCallbackData(
                        action="fixed_stars"
                    )
                )

                self.add_button(
                    text="☄️ Астероиды",
                    callback_data=ChartCallbackData(
                        action="asteroids"
                    )
                )

            # Настройки
            self.add_button(
                text="⚙️ Настройки карты",
                callback_data=ChartCallbackData(
                    action="settings"
                )
            )

            # Экспорт
            self.add_button(
                text="💾 Сохранить",
                callback_data=ChartCallbackData(
                    action="save"
                )
            )

            self.add_button(
                text="📤 Поделиться",
                callback_data=ChartCallbackData(
                    action="share"
                )
            )

        # Настройка сетки
        if self.has_chart:
            self.builder.adjust(1, 2, 2, 2, 1, 2)
        else:
            self.builder.adjust(1, 1)

        self.add_back_button("astro:main")

        return await super().build(**kwargs)


class ChartSettingsKeyboard(InlineKeyboard):
    """Клавиатура настроек карты."""

    def __init__(self, current_settings: Dict[str, Any]):
        """
        Инициализация настроек.

        Args:
            current_settings: Текущие настройки
        """
        super().__init__()
        self.settings = current_settings

    async def build(self, **kwargs) -> InlineKeyboardMarkup:
        """Построить клавиатуру настроек."""
        # Система домов
        self.add_button(
            text=f"🏠 Дома: {self._get_house_system_name()}",
            callback_data="chart:settings:houses"
        )

        # Набор планет
        self.add_button(
            text=f"🪐 Планеты: {self._get_planet_set_name()}",
            callback_data="chart:settings:planets"
        )

        # Аспекты
        self.add_button(
            text=f"📐 Аспекты: {self._get_aspect_type_name()}",
            callback_data="chart:settings:aspects"
        )

        # Орбисы
        self.add_button(
            text="🎯 Орбисы",
            callback_data="chart:settings:orbs"
        )

        # Отображение
        self.add_button(
            text="🎨 Внешний вид",
            callback_data="chart:settings:display"
        )

        # Сброс
        self.add_button(
            text="🔄 По умолчанию",
            callback_data="chart:settings:reset"
        )

        # Применить
        self.add_button(
            text="✅ Применить",
            callback_data="chart:settings:apply"
        )

        self.builder.adjust(1, 1, 1, 2, 2)

        self.add_back_button("chart:main")

        return await super().build(**kwargs)

    def _get_house_system_name(self) -> str:
        """Получить название системы домов."""
        names = {
            HouseSystem.PLACIDUS: "Плацидус",
            HouseSystem.KOCH: "Кох",
            HouseSystem.EQUAL: "Равнодомная",
            HouseSystem.WHOLE_SIGN: "Знак=Дом",
            HouseSystem.REGIOMONTANUS: "Региомонтан",
            HouseSystem.CAMPANUS: "Кампанус"
        }
        return names.get(self.settings["house_system"], "Плацидус")

    def _get_planet_set_name(self) -> str:
        """Получить название набора планет."""
        names = {
            PlanetSet.BASIC: "Базовый",
            PlanetSet.STANDARD: "Стандарт",
            PlanetSet.EXTENDED: "Расширенный",
            PlanetSet.FULL: "Полный"
        }
        return names.get(self.settings["planet_set"], "Стандарт")

    def _get_aspect_type_name(self) -> str:
        """Получить название типа аспектов."""
        names = {
            AspectType.MAJOR: "Основные",
            AspectType.MINOR: "Минорные",
            AspectType.ALL: "Все"
        }
        return names.get(self.settings["aspect_type"], "Основные")


class TransitsKeyboard(InlineKeyboard):
    """Клавиатура транзитов."""

    def __init__(
            self,
            period: str = "today",
            selected_planets: Optional[List[int]] = None
    ):
        """
        Инициализация клавиатуры транзитов.

        Args:
            period: Период транзитов
            selected_planets: Выбранные планеты
        """
        super().__init__()
        self.period = period
        self.selected_planets = selected_planets or []

    async def build(self, **kwargs) -> InlineKeyboardMarkup:
        """Построить клавиатуру."""
        # Периоды
        periods = [
            ("Сегодня", "today"),
            ("Неделя", "week"),
            ("Месяц", "month"),
            ("Год", "year")
        ]

        for text, period_value in periods:
            if period_value == self.period:
                text = f"[{text}]"

            self.add_button(
                text=text,
                callback_data=TransitCallbackData(
                    action="period",
                    period=period_value
                )
            )

        self.builder.adjust(4)

        # Важные транзиты
        self.add_button(
            text="⚡ Важные транзиты",
            callback_data=TransitCallbackData(
                action="important"
            )
        )

        # Транзиты по планетам
        self.add_button(
            text="🪐 По планетам",
            callback_data=TransitCallbackData(
                action="by_planet"
            )
        )

        # Транзиты по домам
        self.add_button(
            text="🏠 По домам",
            callback_data=TransitCallbackData(
                action="by_house"
            )
        )

        # Календарь транзитов
        self.add_button(
            text="📅 Календарь",
            callback_data=TransitCallbackData(
                action="calendar"
            )
        )

        # Настройки
        self.add_button(
            text="⚙️ Настройки",
            callback_data=TransitCallbackData(
                action="settings"
            )
        )

        self.builder.adjust(4, 1, 2, 2)

        self.add_back_button("astro:main")

        return await super().build(**kwargs)


class SynastryKeyboard(InlineKeyboard):
    """Клавиатура синастрии."""

    def __init__(
            self,
            has_partner_data: bool = False,
            synastry_type: str = "basic"
    ):
        """
        Инициализация клавиатуры синастрии.

        Args:
            has_partner_data: Есть ли данные партнера
            synastry_type: Тип синастрии
        """
        super().__init__()
        self.has_partner_data = has_partner_data
        self.synastry_type = synastry_type

    async def build(self, **kwargs) -> InlineKeyboardMarkup:
        """Построить клавиатуру."""
        if not self.has_partner_data:
            # Нет данных партнера
            self.add_button(
                text="👤 Ввести данные партнера",
                callback_data="synastry:partner_data"
            )

            self.add_button(
                text="📚 Что такое синастрия?",
                callback_data="synastry:info"
            )
        else:
            # Есть данные - показываем анализ
            self.add_button(
                text="💕 Общая совместимость",
                callback_data="synastry:general"
            )

            self.add_button(
                text="❤️ Любовь и чувства",
                callback_data="synastry:love"
            )

            self.add_button(
                text="🤝 Дружба и общение",
                callback_data="synastry:friendship"
            )

            self.add_button(
                text="💰 Деловая совместимость",
                callback_data="synastry:business"
            )

            self.add_button(
                text="🔥 Сексуальная совместимость",
                callback_data="synastry:sexual"
            )

            self.add_button(
                text="⚡ Кармические связи",
                callback_data="synastry:karmic"
            )

            # Дополнительно
            self.add_button(
                text="📊 Детальный анализ",
                callback_data="synastry:detailed"
            )

            self.add_button(
                text="👥 Сменить партнера",
                callback_data="synastry:change_partner"
            )

        # Настройка сетки
        if self.has_partner_data:
            self.builder.adjust(1, 2, 2, 2, 2)
        else:
            self.builder.adjust(1, 1)

        self.add_back_button("astro:main")

        return await super().build(**kwargs)


class LunarCalendarKeyboard(InlineKeyboard):
    """Клавиатура лунного календаря."""

    def __init__(
            self,
            year: int,
            month: int,
            show_details: bool = True
    ):
        """
        Инициализация лунного календаря.

        Args:
            year: Год
            month: Месяц
            show_details: Показывать ли детали
        """
        super().__init__()
        self.year = year
        self.month = month
        self.show_details = show_details

    async def build(self, **kwargs) -> InlineKeyboardMarkup:
        """Построить календарь."""
        # Навигация по месяцам
        self.add_button(
            text="◀️",
            callback_data=CalendarCallbackData(
                action="navigate",
                year=self.year if self.month > 1 else self.year - 1,
                month=self.month - 1 if self.month > 1 else 12
            )
        )

        month_names = [
            "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
            "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"
        ]

        self.add_button(
            text=f"{month_names[self.month - 1]} {self.year}",
            callback_data="noop"
        )

        self.add_button(
            text="▶️",
            callback_data=CalendarCallbackData(
                action="navigate",
                year=self.year if self.month < 12 else self.year + 1,
                month=self.month + 1 if self.month < 12 else 1
            )
        )

        self.builder.adjust(3)

        # Текущая фаза луны
        self.add_button(
            text="🌙 Текущая фаза",
            callback_data="lunar:current_phase"
        )

        # Календарная сетка
        if self.show_details:
            # Дни недели
            weekdays = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
            for day_name in weekdays:
                self.add_button(text=day_name, callback_data="noop")

            # Дни месяца с фазами
            cal = calendar.monthcalendar(self.year, self.month)

            for week in cal:
                for day in week:
                    if day == 0:
                        self.add_button(text=" ", callback_data="noop")
                    else:
                        # Здесь должен быть расчет фазы луны
                        moon_phase = self._get_moon_emoji(day)

                        self.add_button(
                            text=f"{day} {moon_phase}",
                            callback_data=CalendarCallbackData(
                                action="select",
                                year=self.year,
                                month=self.month,
                                day=day
                            )
                        )

            # Настройка сетки с календарем
            self.builder.adjust(
                3,  # Навигация
                1,  # Текущая фаза
                7,  # Дни недели
                *([7] * len(cal))  # Недели
            )

        # Функции календаря
        self.add_button(
            text="🌱 Садовый календарь",
            callback_data="lunar:gardening"
        )

        self.add_button(
            text="💇 Стрижка волос",
            callback_data="lunar:haircut"
        )

        self.add_button(
            text="💰 Финансы",
            callback_data="lunar:finance"
        )

        self.add_button(
            text="❤️ Отношения",
            callback_data="lunar:relationships"
        )

        # Подписка на уведомления
        self.add_button(
            text="🔔 Уведомления о фазах",
            callback_data="lunar:notifications"
        )

        self.builder.adjust(2, 2, 1)

        self.add_back_button("astro:main")

        return await super().build(**kwargs)

    def _get_moon_emoji(self, day: int) -> str:
        """Получить эмодзи фазы луны для дня."""
        # Упрощенный расчет для примера
        phase = (day - 1) % 8
        emojis = ["🌑", "🌒", "🌓", "🌔", "🌕", "🌖", "🌗", "🌘"]
        return emojis[phase]


# Функции для быстрого создания клавиатур
async def get_birth_data_keyboard(
        current_data: Optional[Dict[str, Any]] = None,
        editing_field: Optional[str] = None
) -> InlineKeyboardMarkup:
    """Получить клавиатуру данных рождения."""
    keyboard = BirthDataKeyboard(current_data, editing_field)
    return await keyboard.build()


async def get_horoscope_menu(
        user_subscription: str = "free",
        has_birth_data: bool = False
) -> InlineKeyboardMarkup:
    """Получить меню гороскопов."""
    keyboard = HoroscopeMenuKeyboard(user_subscription, has_birth_data)
    return await keyboard.build()


async def get_natal_chart_keyboard(
        has_chart: bool = False,
        chart_settings: Optional[Dict[str, Any]] = None
) -> InlineKeyboardMarkup:
    """Получить клавиатуру натальной карты."""
    keyboard = NatalChartKeyboard(has_chart, chart_settings)
    return await keyboard.build()


async def get_lunar_calendar(
        year: int = None,
        month: int = None
) -> InlineKeyboardMarkup:
    """Получить лунный календарь."""
    if not year or not month:
        now = datetime.now()
        year = now.year
        month = now.month

    keyboard = LunarCalendarKeyboard(year, month)
    return await keyboard.build()


logger.info("Модуль клавиатур астрологии загружен")