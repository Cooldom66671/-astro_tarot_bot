"""
Модуль сущности натальной карты для Астро-Таро Бота.

Этот модуль содержит бизнес-сущности для работы с астрологическими
данными и натальными картами. Включает:
- Позиции планет в знаках и домах
- Аспекты между планетами
- Система домов гороскопа
- Фиктивные точки (Лилит, Узлы)
- Астрологические вычисления

Использование:
    from core.entities import BirthChart, Planet, Aspect
    from datetime import datetime

    # Создание натальной карты
    chart = BirthChart(
        birth_date=datetime(1990, 5, 15, 14, 30),
        latitude=55.7558,
        longitude=37.6173,
        timezone="Europe/Moscow"
    )

    # Получение позиции планеты
    sun_position = chart.get_planet_position(Planet.SUN)
"""

from dataclasses import dataclass, field
from datetime import datetime, date, time
from decimal import Decimal
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum, auto
import math

from pydantic import BaseModel, Field, validator

from config import (
    logger,
    Planet,
    ZodiacSign,
    Emoji
)
from core.exceptions import ValidationError, BusinessLogicError


# ===== АСТРОЛОГИЧЕСКИЕ КОНСТАНТЫ =====

class AspectType(str, Enum):
    """Типы аспектов между планетами."""
    CONJUNCTION = "conjunction"  # Соединение (0°)
    SEXTILE = "sextile"  # Секстиль (60°)
    SQUARE = "square"  # Квадрат (90°)
    TRINE = "trine"  # Трин (120°)
    OPPOSITION = "opposition"  # Оппозиция (180°)
    # Минорные аспекты
    SEMISEXTILE = "semisextile"  # Полусекстиль (30°)
    SEMISQUARE = "semisquare"  # Полуквадрат (45°)
    SESQUIQUADRATE = "sesquiquadrate"  # Полутораквадрат (135°)
    QUINCUNX = "quincunx"  # Квинконс (150°)


class HouseSystem(str, Enum):
    """Системы домов."""
    PLACIDUS = "placidus"  # Плацидус (по умолчанию)
    KOCH = "koch"  # Кох
    EQUAL = "equal"  # Равнодомная
    WHOLE_SIGN = "whole_sign"  # Полнознаковая
    REGIOMONTANUS = "regiomontanus"  # Региомонтан
    CAMPANUS = "campanus"  # Кампанус


class Element(str, Enum):
    """Стихии знаков зодиака."""
    FIRE = "fire"  # Огонь: Овен, Лев, Стрелец
    EARTH = "earth"  # Земля: Телец, Дева, Козерог
    AIR = "air"  # Воздух: Близнецы, Весы, Водолей
    WATER = "water"  # Вода: Рак, Скорпион, Рыбы


class Quality(str, Enum):
    """Качества (модальности) знаков."""
    CARDINAL = "cardinal"  # Кардинальные: Овен, Рак, Весы, Козерог
    FIXED = "fixed"  # Фиксированные: Телец, Лев, Скорпион, Водолей
    MUTABLE = "mutable"  # Мутабельные: Близнецы, Дева, Стрелец, Рыбы


# Характеристики знаков зодиака
SIGN_PROPERTIES = {
    ZodiacSign.ARIES: {"element": Element.FIRE, "quality": Quality.CARDINAL, "ruler": Planet.MARS},
    ZodiacSign.TAURUS: {"element": Element.EARTH, "quality": Quality.FIXED, "ruler": Planet.VENUS},
    ZodiacSign.GEMINI: {"element": Element.AIR, "quality": Quality.MUTABLE, "ruler": Planet.MERCURY},
    ZodiacSign.CANCER: {"element": Element.WATER, "quality": Quality.CARDINAL, "ruler": Planet.MOON},
    ZodiacSign.LEO: {"element": Element.FIRE, "quality": Quality.FIXED, "ruler": Planet.SUN},
    ZodiacSign.VIRGO: {"element": Element.EARTH, "quality": Quality.MUTABLE, "ruler": Planet.MERCURY},
    ZodiacSign.LIBRA: {"element": Element.AIR, "quality": Quality.CARDINAL, "ruler": Planet.VENUS},
    ZodiacSign.SCORPIO: {"element": Element.WATER, "quality": Quality.FIXED, "ruler": Planet.PLUTO},
    ZodiacSign.SAGITTARIUS: {"element": Element.FIRE, "quality": Quality.MUTABLE, "ruler": Planet.JUPITER},
    ZodiacSign.CAPRICORN: {"element": Element.EARTH, "quality": Quality.CARDINAL, "ruler": Planet.SATURN},
    ZodiacSign.AQUARIUS: {"element": Element.AIR, "quality": Quality.FIXED, "ruler": Planet.URANUS},
    ZodiacSign.PISCES: {"element": Element.WATER, "quality": Quality.MUTABLE, "ruler": Planet.NEPTUNE},
}

# Орбисы для аспектов (в градусах)
ASPECT_ORBS = {
    AspectType.CONJUNCTION: 10.0,
    AspectType.OPPOSITION: 10.0,
    AspectType.TRINE: 8.0,
    AspectType.SQUARE: 8.0,
    AspectType.SEXTILE: 6.0,
    AspectType.SEMISEXTILE: 3.0,
    AspectType.SEMISQUARE: 3.0,
    AspectType.SESQUIQUADRATE: 3.0,
    AspectType.QUINCUNX: 5.0,
}

# Точные углы аспектов
ASPECT_ANGLES = {
    AspectType.CONJUNCTION: 0,
    AspectType.SEMISEXTILE: 30,
    AspectType.SEMISQUARE: 45,
    AspectType.SEXTILE: 60,
    AspectType.SQUARE: 90,
    AspectType.TRINE: 120,
    AspectType.SESQUIQUADRATE: 135,
    AspectType.QUINCUNX: 150,
    AspectType.OPPOSITION: 180,
}


# ===== ВСПОМОГАТЕЛЬНЫЕ КЛАССЫ =====

@dataclass
class PlanetPosition:
    """Позиция планеты в карте."""

    planet: Planet
    longitude: float  # Эклиптическая долгота (0-360°)
    latitude: float  # Эклиптическая широта
    distance: float  # Расстояние от Земли
    speed: float  # Скорость движения

    # Вычисляемые поля
    sign: Optional[ZodiacSign] = None
    sign_degree: Optional[float] = None  # Градус внутри знака (0-30°)
    house: Optional[int] = None  # Номер дома (1-12)
    is_retrograde: bool = False

    def __post_init__(self):
        """Вычисляем знак и градус."""
        self.sign = self._calculate_sign()
        self.sign_degree = self._calculate_sign_degree()
        self.is_retrograde = self.speed < 0

    def _calculate_sign(self) -> ZodiacSign:
        """Определить знак зодиака по долготе."""
        signs = list(ZodiacSign)
        sign_index = int(self.longitude / 30)
        return signs[sign_index]

    def _calculate_sign_degree(self) -> float:
        """Вычислить градус внутри знака."""
        return self.longitude % 30

    @property
    def formatted_position(self) -> str:
        """Форматированная позиция."""
        degree = int(self.sign_degree)
        minute = int((self.sign_degree - degree) * 60)
        retrograde = " ℞" if self.is_retrograde else ""

        return f"{Emoji.PLANETS.get(self.planet.value, '')} {self.planet.value.capitalize()} {degree}°{minute:02d}' {Emoji.ZODIAC_SIGNS.get(self.sign.value, '')}{retrograde}"

    @property
    def element(self) -> Element:
        """Стихия знака, в котором находится планета."""
        return SIGN_PROPERTIES[self.sign]["element"]

    @property
    def quality(self) -> Quality:
        """Качество знака, в котором находится планета."""
        return SIGN_PROPERTIES[self.sign]["quality"]


@dataclass
class Aspect:
    """Аспект между двумя планетами."""

    planet1: Planet
    planet2: Planet
    type: AspectType
    angle: float  # Фактический угол между планетами
    orb: float  # Отклонение от точного аспекта

    @property
    def is_exact(self) -> bool:
        """Точный аспект (орб < 1°)."""
        return abs(self.orb) < 1.0

    @property
    def is_applying(self) -> bool:
        """Сходящийся аспект."""
        # Упрощенная логика - требует скорости планет
        return self.orb < 0

    @property
    def is_separating(self) -> bool:
        """Расходящийся аспект."""
        return not self.is_applying

    @property
    def strength(self) -> str:
        """Сила аспекта."""
        if abs(self.orb) < 1:
            return "очень сильный"
        elif abs(self.orb) < 3:
            return "сильный"
        elif abs(self.orb) < 5:
            return "средний"
        else:
            return "слабый"

    @property
    def nature(self) -> str:
        """Природа аспекта."""
        harmonious = [AspectType.TRINE, AspectType.SEXTILE, AspectType.CONJUNCTION]
        tense = [AspectType.SQUARE, AspectType.OPPOSITION]

        if self.type in harmonious:
            return "гармоничный"
        elif self.type in tense:
            return "напряженный"
        else:
            return "нейтральный"

    @property
    def formatted_aspect(self) -> str:
        """Форматированное представление аспекта."""
        symbols = {
            AspectType.CONJUNCTION: "☌",
            AspectType.SEXTILE: "⚹",
            AspectType.SQUARE: "□",
            AspectType.TRINE: "△",
            AspectType.OPPOSITION: "☍",
            AspectType.SEMISEXTILE: "⚺",
            AspectType.SEMISQUARE: "∠",
            AspectType.SESQUIQUADRATE: "⚼",
            AspectType.QUINCUNX: "⚻",
        }

        symbol = symbols.get(self.type, "")
        p1_emoji = Emoji.PLANETS.get(self.planet1.value, "")
        p2_emoji = Emoji.PLANETS.get(self.planet2.value, "")

        return f"{p1_emoji} {symbol} {p2_emoji} ({abs(self.orb):.1f}°)"


@dataclass
class House:
    """Дом гороскопа."""

    number: int  # 1-12
    cusp_longitude: float  # Долгота куспида
    sign: ZodiacSign  # Знак на куспиде
    ruler: Planet  # Управитель дома
    planets: List[Planet] = field(default_factory=list)  # Планеты в доме

    @property
    def is_empty(self) -> bool:
        """Пустой дом (без планет)."""
        return len(self.planets) == 0

    @property
    def is_stellium(self) -> bool:
        """Стеллиум (3+ планеты)."""
        return len(self.planets) >= 3

    @property
    def house_meaning(self) -> str:
        """Значение дома."""
        meanings = {
            1: "Личность, внешность, первое впечатление",
            2: "Финансы, ценности, таланты",
            3: "Коммуникации, обучение, близкое окружение",
            4: "Дом, семья, корни",
            5: "Творчество, дети, удовольствия",
            6: "Здоровье, работа, повседневность",
            7: "Партнерство, брак, открытые враги",
            8: "Трансформации, кризисы, чужие ресурсы",
            9: "Философия, путешествия, высшее образование",
            10: "Карьера, статус, достижения",
            11: "Друзья, группы, мечты",
            12: "Подсознание, тайны, изоляция"
        }
        return meanings.get(self.number, "")


# ===== ОСНОВНАЯ СУЩНОСТЬ НАТАЛЬНОЙ КАРТЫ =====

@dataclass
class BirthChart:
    """
    Натальная карта.

    Содержит все астрологические данные и методы для их расчета.
    Примечание: реальные расчеты требуют астрономической библиотеки
    (например, pyswisseph), здесь представлена структура данных.
    """

    # Данные рождения
    birth_date: datetime
    latitude: float
    longitude: float
    timezone: str
    house_system: HouseSystem = HouseSystem.PLACIDUS

    # Вычисляемые данные
    planets: Dict[Planet, PlanetPosition] = field(default_factory=dict)
    houses: List[House] = field(default_factory=list)
    aspects: List[Aspect] = field(default_factory=list)

    # Особые точки
    ascendant: Optional[float] = None  # ASC
    midheaven: Optional[float] = None  # MC
    descendant: Optional[float] = None  # DSC
    imum_coeli: Optional[float] = None  # IC
    vertex: Optional[float] = None

    # Метаданные
    calculated_at: Optional[datetime] = None
    calculation_method: str = "simplified"  # Для демо версии

    def __post_init__(self):
        """Инициализация после создания."""
        logger.debug(
            f"Создана натальная карта для {self.birth_date} "
            f"в {self.latitude}, {self.longitude}"
        )

        # Валидация координат
        if not -90 <= self.latitude <= 90:
            raise ValidationError("latitude", "Широта должна быть от -90 до 90")

        if not -180 <= self.longitude <= 180:
            raise ValidationError("longitude", "Долгота должна быть от -180 до 180")

    # ===== МЕТОДЫ РАСЧЕТА =====

    def calculate(self) -> None:
        """
        Рассчитать все элементы натальной карты.

        В реальном приложении здесь будет вызов астрономической
        библиотеки для точных расчетов.
        """
        logger.info("Начат расчет натальной карты")

        # Заглушка для демонстрации структуры
        self._calculate_planets()
        self._calculate_houses()
        self._calculate_aspects()
        self._calculate_special_points()

        self.calculated_at = datetime.now()
        logger.info("Расчет натальной карты завершен")

    def _calculate_planets(self) -> None:
        """Рассчитать позиции планет."""
        # Демо-данные для примера структуры
        # В реальности здесь будут астрономические вычисления

        demo_positions = {
            Planet.SUN: PlanetPosition(
                planet=Planet.SUN,
                longitude=55.5,  # 25° Тельца
                latitude=0.0,
                distance=1.0,
                speed=0.98
            ),
            Planet.MOON: PlanetPosition(
                planet=Planet.MOON,
                longitude=120.3,  # 0° Льва
                latitude=2.1,
                distance=0.0026,
                speed=13.2
            ),
            # ... остальные планеты
        }

        for planet, position in demo_positions.items():
            # Определяем дом для каждой планеты
            position.house = self._calculate_planet_house(position.longitude)
            self.planets[planet] = position

    def _calculate_houses(self) -> None:
        """Рассчитать дома гороскопа."""
        # Демо-расчет домов
        # В реальности используется выбранная система домов

        for i in range(1, 13):
            # Упрощенный расчет куспидов
            cusp_longitude = (self.ascendant or 0) + (i - 1) * 30
            cusp_longitude = cusp_longitude % 360

            # Определяем знак на куспиде
            sign_index = int(cusp_longitude / 30)
            sign = list(ZodiacSign)[sign_index]

            house = House(
                number=i,
                cusp_longitude=cusp_longitude,
                sign=sign,
                ruler=SIGN_PROPERTIES[sign]["ruler"]
            )

            # Добавляем планеты в дом
            for planet, position in self.planets.items():
                if position.house == i:
                    house.planets.append(planet)

            self.houses.append(house)

    def _calculate_aspects(self) -> None:
        """Рассчитать аспекты между планетами."""
        planets_list = list(self.planets.keys())

        for i, planet1 in enumerate(planets_list):
            for planet2 in planets_list[i + 1:]:
                aspect = self._check_aspect(planet1, planet2)
                if aspect:
                    self.aspects.append(aspect)

    def _check_aspect(self, planet1: Planet, planet2: Planet) -> Optional[Aspect]:
        """Проверить наличие аспекта между планетами."""
        pos1 = self.planets[planet1]
        pos2 = self.planets[planet2]

        # Вычисляем угол между планетами
        angle = abs(pos1.longitude - pos2.longitude)
        if angle > 180:
            angle = 360 - angle

        # Проверяем все возможные аспекты
        for aspect_type, exact_angle in ASPECT_ANGLES.items():
            orb = abs(angle - exact_angle)
            max_orb = ASPECT_ORBS[aspect_type]

            if orb <= max_orb:
                return Aspect(
                    planet1=planet1,
                    planet2=planet2,
                    type=aspect_type,
                    angle=angle,
                    orb=angle - exact_angle
                )

        return None

    def _calculate_special_points(self) -> None:
        """Рассчитать особые точки."""
        # Демо-расчет
        # ASC обычно рассчитывается из времени и места рождения
        self.ascendant = 15.0  # Например, 15° Овна
        self.midheaven = (self.ascendant + 270) % 360
        self.descendant = (self.ascendant + 180) % 360
        self.imum_coeli = (self.ascendant + 90) % 360

    def _calculate_planet_house(self, longitude: float) -> int:
        """Определить дом для планеты по её долготе."""
        # Упрощенный метод для равнодомной системы
        # В реальности зависит от системы домов

        if not self.houses:
            # Если дома еще не рассчитаны, используем простое деление
            house_size = 30  # Для равнодомной системы
            asc = self.ascendant or 0

            adjusted_long = (longitude - asc + 360) % 360
            return int(adjusted_long / house_size) + 1

        # Если дома рассчитаны, ищем по куспидам
        for i, house in enumerate(self.houses):
            next_cusp = self.houses[(i + 1) % 12].cusp_longitude

            if house.cusp_longitude <= longitude < next_cusp:
                return house.number
            elif house.cusp_longitude > next_cusp:  # Переход через 0°
                if longitude >= house.cusp_longitude or longitude < next_cusp:
                    return house.number

        return 1  # По умолчанию

    # ===== МЕТОДЫ АНАЛИЗА =====

    def get_planet_position(self, planet: Planet) -> Optional[PlanetPosition]:
        """Получить позицию планеты."""
        return self.planets.get(planet)

    def get_planets_in_sign(self, sign: ZodiacSign) -> List[Planet]:
        """Получить планеты в знаке."""
        result = []
        for planet, position in self.planets.items():
            if position.sign == sign:
                result.append(planet)
        return result

    def get_planets_in_house(self, house_number: int) -> List[Planet]:
        """Получить планеты в доме."""
        if 1 <= house_number <= 12:
            return self.houses[house_number - 1].planets
        return []

    def get_aspects_for_planet(self, planet: Planet) -> List[Aspect]:
        """Получить все аспекты планеты."""
        return [
            aspect for aspect in self.aspects
            if aspect.planet1 == planet or aspect.planet2 == planet
        ]

    def get_element_distribution(self) -> Dict[Element, int]:
        """Распределение планет по стихиям."""
        distribution = {element: 0 for element in Element}

        for position in self.planets.values():
            element = position.element
            distribution[element] += 1

        return distribution

    def get_quality_distribution(self) -> Dict[Quality, int]:
        """Распределение планет по качествам."""
        distribution = {quality: 0 for quality in Quality}

        for position in self.planets.values():
            quality = position.quality
            distribution[quality] += 1

        return distribution

    def get_dominant_element(self) -> Element:
        """Доминирующая стихия."""
        distribution = self.get_element_distribution()
        return max(distribution, key=distribution.get)

    def get_dominant_quality(self) -> Quality:
        """Доминирующее качество."""
        distribution = self.get_quality_distribution()
        return max(distribution, key=distribution.get)

    def has_stellium(self) -> List[Tuple[ZodiacSign, List[Planet]]]:
        """Найти стеллиумы (3+ планеты в одном знаке)."""
        stelliums = []

        for sign in ZodiacSign:
            planets = self.get_planets_in_sign(sign)
            if len(planets) >= 3:
                stelliums.append((sign, planets))

        return stelliums

    def get_chart_pattern(self) -> Optional[str]:
        """Определить конфигурацию карты."""
        # Упрощенная логика определения паттернов
        # В реальности требует сложного анализа аспектов

        aspects_count = len(self.aspects)

        if aspects_count > 20:
            return "Брызги"  # Splash
        elif aspects_count > 15:
            return "Связка"  # Bundle
        elif aspects_count > 10:
            return "Чаша"  # Bowl
        else:
            return "Качели"  # Seesaw

    # ===== ГЕНЕРАЦИЯ ОТЧЕТОВ =====

    def get_summary(self) -> Dict[str, Any]:
        """Получить краткую сводку по карте."""
        sun_pos = self.get_planet_position(Planet.SUN)
        moon_pos = self.get_planet_position(Planet.MOON)
        asc_sign = self._get_ascendant_sign()

        return {
            "sun_sign": sun_pos.sign.value if sun_pos else None,
            "moon_sign": moon_pos.sign.value if moon_pos else None,
            "ascendant_sign": asc_sign.value if asc_sign else None,
            "dominant_element": self.get_dominant_element().value,
            "dominant_quality": self.get_dominant_quality().value,
            "total_aspects": len(self.aspects),
            "chart_pattern": self.get_chart_pattern(),
            "stelliums": [
                {"sign": sign.value, "planets": [p.value for p in planets]}
                for sign, planets in self.has_stellium()
            ]
        }

    def _get_ascendant_sign(self) -> Optional[ZodiacSign]:
        """Получить знак Асцендента."""
        if self.ascendant is None:
            return None

        sign_index = int(self.ascendant / 30)
        return list(ZodiacSign)[sign_index]

    def to_dict(self) -> Dict[str, Any]:
        """Преобразовать в словарь."""
        return {
            "birth_date": self.birth_date.isoformat(),
            "location": {
                "latitude": self.latitude,
                "longitude": self.longitude,
                "timezone": self.timezone
            },
            "house_system": self.house_system.value,
            "special_points": {
                "ascendant": self.ascendant,
                "midheaven": self.midheaven,
                "descendant": self.descendant,
                "imum_coeli": self.imum_coeli
            },
            "summary": self.get_summary(),
            "calculated_at": self.calculated_at.isoformat() if self.calculated_at else None
        }


# Экспорт
__all__ = [
    "BirthChart",
    "PlanetPosition",
    "Aspect",
    "House",
    "AspectType",
    "HouseSystem",
    "Element",
    "Quality",
    "SIGN_PROPERTIES",
    "ASPECT_ORBS",
    "ASPECT_ANGLES",
]