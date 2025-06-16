"""
Модели для астрологических расчетов и хранения данных.

Этот модуль содержит:
- Модель NatalChart для натальных карт
- Модель PlanetPosition для позиций планет
- Модель AspectData для аспектов между планетами
- Модель HouseData для домов гороскопа
- Модель Transit для транзитов
- Модель Synastry для синастрий
- Модель AstroForecast для прогнозов
"""

from datetime import datetime, date
from typing import Optional, List
from enum import Enum
from decimal import Decimal

from sqlalchemy import (
    Column, String, BigInteger, Boolean, DateTime, Text,
    ForeignKey, UniqueConstraint, CheckConstraint, Index,
    Enum as SQLEnum, JSON, Integer, Float, Numeric, Date
)
from sqlalchemy.orm import relationship, validates
from sqlalchemy.ext.hybrid import hybrid_property

from config import logger
from infrastructure.database.models.base import (
    BaseModel, TimestampMixin, BaseCachedModel
)
from core.exceptions import ValidationError


class Planet(str, Enum):
    """Планеты и точки."""
    SUN = "sun"  # Солнце
    MOON = "moon"  # Луна
    MERCURY = "mercury"  # Меркурий
    VENUS = "venus"  # Венера
    MARS = "mars"  # Марс
    JUPITER = "jupiter"  # Юпитер
    SATURN = "saturn"  # Сатурн
    URANUS = "uranus"  # Уран
    NEPTUNE = "neptune"  # Нептун
    PLUTO = "pluto"  # Плутон
    NORTH_NODE = "north_node"  # Северный узел
    SOUTH_NODE = "south_node"  # Южный узел
    CHIRON = "chiron"  # Хирон
    LILITH = "lilith"  # Черная Луна
    ASC = "asc"  # Асцендент
    MC = "mc"  # Середина неба


class ZodiacSign(str, Enum):
    """Знаки зодиака."""
    ARIES = "aries"  # Овен
    TAURUS = "taurus"  # Телец
    GEMINI = "gemini"  # Близнецы
    CANCER = "cancer"  # Рак
    LEO = "leo"  # Лев
    VIRGO = "virgo"  # Дева
    LIBRA = "libra"  # Весы
    SCORPIO = "scorpio"  # Скорпион
    SAGITTARIUS = "sagittarius"  # Стрелец
    CAPRICORN = "capricorn"  # Козерог
    AQUARIUS = "aquarius"  # Водолей
    PISCES = "pisces"  # Рыбы


class AspectType(str, Enum):
    """Типы аспектов."""
    CONJUNCTION = "conjunction"  # Соединение 0°
    SEXTILE = "sextile"  # Секстиль 60°
    SQUARE = "square"  # Квадрат 90°
    TRINE = "trine"  # Трин 120°
    OPPOSITION = "opposition"  # Оппозиция 180°
    QUINCUNX = "quincunx"  # Квинконс 150°
    SEMISEXTILE = "semisextile"  # Полусекстиль 30°
    SEMISQUARE = "semisquare"  # Полуквадрат 45°
    SESQUIQUADRATE = "sesquiquadrate"  # Полутораквадрат 135°


class HouseSystem(str, Enum):
    """Системы домов."""
    PLACIDUS = "placidus"
    KOCH = "koch"
    EQUAL = "equal"
    WHOLE_SIGN = "whole_sign"
    REGIOMONTANUS = "regiomontanus"
    CAMPANUS = "campanus"


class ForecastType(str, Enum):
    """Типы прогнозов."""
    DAILY = "daily"  # Ежедневный
    WEEKLY = "weekly"  # Еженедельный
    MONTHLY = "monthly"  # Ежемесячный
    YEARLY = "yearly"  # Годовой
    TRANSIT = "transit"  # Транзиты
    PROGRESSION = "progression"  # Прогрессии


class NatalChart(BaseCachedModel):
    """
    Натальные карты пользователей.

    Хранит рассчитанные астрологические карты.
    """

    __tablename__ = "natal_charts"

    user_id = Column(
        BigInteger,
        ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False,
        comment="ID пользователя"
    )

    # Данные рождения (дублируются для быстрого доступа)
    birth_datetime = Column(
        DateTime(timezone=True),
        nullable=False,
        comment="Дата и время рождения"
    )

    birth_place = Column(
        String(255),
        nullable=False,
        comment="Место рождения"
    )

    latitude = Column(
        Float,
        nullable=False,
        comment="Широта"
    )

    longitude = Column(
        Float,
        nullable=False,
        comment="Долгота"
    )

    timezone = Column(
        String(50),
        nullable=False,
        comment="Часовой пояс"
    )

    # Система домов
    house_system = Column(
        SQLEnum(HouseSystem),
        nullable=False,
        default=HouseSystem.PLACIDUS,
        comment="Система домов"
    )

    # Рассчитанные данные
    calculation_time = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        comment="Время расчета"
    )

    calculation_library = Column(
        String(50),
        nullable=True,
        comment="Библиотека для расчета"
    )

    # Основные точки
    asc_degree = Column(
        Numeric(5, 2),
        nullable=False,
        comment="Градус асцендента"
    )

    mc_degree = Column(
        Numeric(5, 2),
        nullable=False,
        comment="Градус MC"
    )

    # Дополнительные данные
    chart_data = Column(
        JSON,
        nullable=True,
        comment="Полные данные карты"
    )

    interpretation_cache = Column(
        JSON,
        nullable=True,
        comment="Кэш интерпретаций"
    )

    # Статистика
    view_count = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Количество просмотров"
    )

    last_viewed_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Последний просмотр"
    )

    # Отношения
    user = relationship("User", backref="natal_charts")
    planet_positions = relationship(
        "PlanetPosition",
        back_populates="natal_chart",
        cascade="all, delete-orphan"
    )
    aspects = relationship(
        "AspectData",
        back_populates="natal_chart",
        cascade="all, delete-orphan"
    )
    houses = relationship(
        "HouseData",
        back_populates="natal_chart",
        cascade="all, delete-orphan"
    )

    # Ограничения
    __table_args__ = (
        CheckConstraint('latitude >= -90 AND latitude <= 90',
                        name='check_natal_latitude'),
        CheckConstraint('longitude >= -180 AND longitude <= 180',
                        name='check_natal_longitude'),
        Index('idx_natal_user_date', 'user_id', 'birth_datetime'),
    )

    @hybrid_property
    def sun_sign(self) -> Optional[str]:
        """Солнечный знак из позиций планет."""
        sun_position = next(
            (p for p in self.planet_positions if p.planet == Planet.SUN),
            None
        )
        return sun_position.zodiac_sign if sun_position else None

    @hybrid_property
    def moon_sign(self) -> Optional[str]:
        """Лунный знак из позиций планет."""
        moon_position = next(
            (p for p in self.planet_positions if p.planet == Planet.MOON),
            None
        )
        return moon_position.zodiac_sign if moon_position else None

    def increment_views(self) -> None:
        """Увеличение счетчика просмотров."""
        self.view_count += 1
        self.last_viewed_at = datetime.utcnow()

    def __repr__(self) -> str:
        return f"<NatalChart(id={self.id}, user_id={self.user_id})>"


class PlanetPosition(BaseModel):
    """
    Позиции планет в натальной карте.

    Хранит точные координаты каждой планеты.
    """

    __tablename__ = "planet_positions"

    natal_chart_id = Column(
        BigInteger,
        ForeignKey('natal_charts.id', ondelete='CASCADE'),
        nullable=False,
        comment="ID натальной карты"
    )

    planet = Column(
        SQLEnum(Planet),
        nullable=False,
        comment="Планета"
    )

    # Позиция в зодиаке
    zodiac_sign = Column(
        SQLEnum(ZodiacSign),
        nullable=False,
        comment="Знак зодиака"
    )

    degree = Column(
        Numeric(5, 2),
        nullable=False,
        comment="Градус в знаке (0-29.99)"
    )

    absolute_degree = Column(
        Numeric(5, 2),
        nullable=False,
        comment="Абсолютный градус (0-359.99)"
    )

    # Дом
    house = Column(
        Integer,
        nullable=False,
        comment="Номер дома (1-12)"
    )

    # Движение
    is_retrograde = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="Ретроградное движение"
    )

    speed = Column(
        Numeric(8, 5),
        nullable=True,
        comment="Скорость движения"
    )

    # Дополнительные данные
    declination = Column(
        Numeric(5, 2),
        nullable=True,
        comment="Склонение"
    )

    # Отношения
    natal_chart = relationship("NatalChart", back_populates="planet_positions")

    # Ограничения
    __table_args__ = (
        UniqueConstraint('natal_chart_id', 'planet',
                         name='uq_chart_planet'),
        CheckConstraint('degree >= 0 AND degree < 30',
                        name='check_degree_range'),
        CheckConstraint('absolute_degree >= 0 AND absolute_degree < 360',
                        name='check_absolute_degree_range'),
        CheckConstraint('house >= 1 AND house <= 12',
                        name='check_house_range'),
        Index('idx_planet_position', 'natal_chart_id', 'planet'),
    )

    @hybrid_property
    def position_string(self) -> str:
        """Строковое представление позиции."""
        degree_int = int(self.degree)
        degree_min = int((self.degree - degree_int) * 60)

        zodiac_symbols = {
            ZodiacSign.ARIES: "♈", ZodiacSign.TAURUS: "♉",
            ZodiacSign.GEMINI: "♊", ZodiacSign.CANCER: "♋",
            ZodiacSign.LEO: "♌", ZodiacSign.VIRGO: "♍",
            ZodiacSign.LIBRA: "♎", ZodiacSign.SCORPIO: "♏",
            ZodiacSign.SAGITTARIUS: "♐", ZodiacSign.CAPRICORN: "♑",
            ZodiacSign.AQUARIUS: "♒", ZodiacSign.PISCES: "♓"
        }

        symbol = zodiac_symbols.get(self.zodiac_sign, "")
        retro = " R" if self.is_retrograde else ""

        return f"{degree_int}°{degree_min:02d}' {symbol}{retro}"

    def __repr__(self) -> str:
        return f"<PlanetPosition({self.planet} at {self.position_string})>"


class AspectData(BaseModel):
    """
    Аспекты между планетами.

    Хранит углы между планетами и их интерпретации.
    """

    __tablename__ = "aspect_data"

    natal_chart_id = Column(
        BigInteger,
        ForeignKey('natal_charts.id', ondelete='CASCADE'),
        nullable=False,
        comment="ID натальной карты"
    )

    # Планеты в аспекте
    planet1 = Column(
        SQLEnum(Planet),
        nullable=False,
        comment="Первая планета"
    )

    planet2 = Column(
        SQLEnum(Planet),
        nullable=False,
        comment="Вторая планета"
    )

    # Аспект
    aspect_type = Column(
        SQLEnum(AspectType),
        nullable=False,
        comment="Тип аспекта"
    )

    angle = Column(
        Numeric(5, 2),
        nullable=False,
        comment="Точный угол"
    )

    orb = Column(
        Numeric(4, 2),
        nullable=False,
        comment="Орбис (отклонение)"
    )

    # Сила аспекта
    strength = Column(
        Integer,
        nullable=False,
        default=50,
        comment="Сила аспекта (0-100)"
    )

    is_applying = Column(
        Boolean,
        nullable=True,
        comment="Сходящийся аспект"
    )

    # Отношения
    natal_chart = relationship("NatalChart", back_populates="aspects")

    # Ограничения
    __table_args__ = (
        CheckConstraint('angle >= 0 AND angle <= 360',
                        name='check_aspect_angle'),
        CheckConstraint('orb >= 0', name='check_orb_positive'),
        CheckConstraint('strength >= 0 AND strength <= 100',
                        name='check_strength_range'),
        Index('idx_aspect_chart', 'natal_chart_id', 'aspect_type'),
    )

    def __repr__(self) -> str:
        return f"<AspectData({self.planet1} {self.aspect_type} {self.planet2})>"


class HouseData(BaseModel):
    """
    Дома гороскопа.

    Хранит куспиды домов и планеты в них.
    """

    __tablename__ = "house_data"

    natal_chart_id = Column(
        BigInteger,
        ForeignKey('natal_charts.id', ondelete='CASCADE'),
        nullable=False,
        comment="ID натальной карты"
    )

    house_number = Column(
        Integer,
        nullable=False,
        comment="Номер дома (1-12)"
    )

    # Куспид дома
    cusp_degree = Column(
        Numeric(5, 2),
        nullable=False,
        comment="Градус куспида"
    )

    cusp_sign = Column(
        SQLEnum(ZodiacSign),
        nullable=False,
        comment="Знак на куспиде"
    )

    # Управитель дома
    ruler_planet = Column(
        SQLEnum(Planet),
        nullable=True,
        comment="Планета-управитель"
    )

    # Планеты в доме
    planets_in_house = Column(
        JSON,
        nullable=True,
        default=list,
        comment="Список планет в доме"
    )

    # Отношения
    natal_chart = relationship("NatalChart", back_populates="houses")

    # Ограничения
    __table_args__ = (
        UniqueConstraint('natal_chart_id', 'house_number',
                         name='uq_chart_house'),
        CheckConstraint('house_number >= 1 AND house_number <= 12',
                        name='check_house_number'),
        CheckConstraint('cusp_degree >= 0 AND cusp_degree < 360',
                        name='check_cusp_degree'),
        Index('idx_house_chart', 'natal_chart_id', 'house_number'),
    )

    def __repr__(self) -> str:
        return f"<HouseData(house={self.house_number}, cusp={self.cusp_sign})>"


class Transit(BaseModel, TimestampMixin):
    """
    Транзиты планет.

    Текущие положения планет относительно натальной карты.
    """

    __tablename__ = "transits"

    natal_chart_id = Column(
        BigInteger,
        ForeignKey('natal_charts.id', ondelete='CASCADE'),
        nullable=False,
        comment="ID натальной карты"
    )

    # Период транзита
    start_date = Column(
        Date,
        nullable=False,
        comment="Начало транзита"
    )

    exact_date = Column(
        Date,
        nullable=True,
        comment="Точная дата транзита"
    )

    end_date = Column(
        Date,
        nullable=False,
        comment="Окончание транзита"
    )

    # Транзитная планета
    transit_planet = Column(
        SQLEnum(Planet),
        nullable=False,
        comment="Транзитная планета"
    )

    # Натальная точка
    natal_point = Column(
        SQLEnum(Planet),
        nullable=False,
        comment="Натальная планета/точка"
    )

    # Аспект
    aspect_type = Column(
        SQLEnum(AspectType),
        nullable=False,
        comment="Тип аспекта"
    )

    # Важность
    importance = Column(
        Integer,
        nullable=False,
        default=50,
        comment="Важность транзита (0-100)"
    )

    # Интерпретация
    interpretation = Column(
        Text,
        nullable=True,
        comment="Интерпретация транзита"
    )

    # Отношения
    natal_chart = relationship("NatalChart", backref="transits")

    # Ограничения
    __table_args__ = (
        CheckConstraint('end_date >= start_date',
                        name='check_transit_dates'),
        CheckConstraint('importance >= 0 AND importance <= 100',
                        name='check_transit_importance'),
        Index('idx_transit_dates', 'natal_chart_id', 'start_date', 'end_date'),
        Index('idx_transit_exact', 'exact_date', 'importance'),
    )

    def __repr__(self) -> str:
        return f"<Transit({self.transit_planet} {self.aspect_type} {self.natal_point})>"


class Synastry(BaseModel, TimestampMixin):
    """
    Синастрии (совместимость).

    Сравнение двух натальных карт.
    """

    __tablename__ = "synastries"

    # Две натальные карты
    chart1_id = Column(
        BigInteger,
        ForeignKey('natal_charts.id', ondelete='CASCADE'),
        nullable=False,
        comment="ID первой карты"
    )

    chart2_id = Column(
        BigInteger,
        ForeignKey('natal_charts.id', ondelete='CASCADE'),
        nullable=False,
        comment="ID второй карты"
    )

    # Тип отношений
    relationship_type = Column(
        String(50),
        nullable=True,
        comment="Тип отношений (любовь, дружба, бизнес)"
    )

    # Общая совместимость
    overall_score = Column(
        Integer,
        nullable=True,
        comment="Общий балл совместимости (0-100)"
    )

    # Детальные оценки
    romantic_score = Column(
        Integer,
        nullable=True,
        comment="Романтическая совместимость"
    )

    friendship_score = Column(
        Integer,
        nullable=True,
        comment="Дружеская совместимость"
    )

    business_score = Column(
        Integer,
        nullable=True,
        comment="Деловая совместимость"
    )

    # Аспекты между картами
    inter_aspects = Column(
        JSON,
        nullable=True,
        comment="Аспекты между картами"
    )

    # Анализ
    strengths = Column(
        JSON,
        nullable=True,
        comment="Сильные стороны"
    )

    challenges = Column(
        JSON,
        nullable=True,
        comment="Сложности"
    )

    interpretation = Column(
        Text,
        nullable=True,
        comment="Полная интерпретация"
    )

    # Отношения
    chart1 = relationship("NatalChart", foreign_keys=[chart1_id])
    chart2 = relationship("NatalChart", foreign_keys=[chart2_id])

    # Ограничения
    __table_args__ = (
        UniqueConstraint('chart1_id', 'chart2_id',
                         name='uq_synastry_charts'),
        CheckConstraint('chart1_id != chart2_id',
                        name='check_different_charts'),
        Index('idx_synastry_charts', 'chart1_id', 'chart2_id'),
    )

    def __repr__(self) -> str:
        return f"<Synastry(chart1={self.chart1_id}, chart2={self.chart2_id})>"


class AstroForecast(BaseModel, TimestampMixin):
    """
    Астрологические прогнозы.

    Персональные прогнозы на различные периоды.
    """

    __tablename__ = "astro_forecasts"

    user_id = Column(
        BigInteger,
        ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False,
        comment="ID пользователя"
    )

    natal_chart_id = Column(
        BigInteger,
        ForeignKey('natal_charts.id', ondelete='SET NULL'),
        nullable=True,
        comment="ID натальной карты"
    )

    # Тип и период
    forecast_type = Column(
        SQLEnum(ForecastType),
        nullable=False,
        comment="Тип прогноза"
    )

    period_start = Column(
        Date,
        nullable=False,
        comment="Начало периода"
    )

    period_end = Column(
        Date,
        nullable=False,
        comment="Конец периода"
    )

    # Содержание прогноза
    general_forecast = Column(
        Text,
        nullable=True,
        comment="Общий прогноз"
    )

    love_forecast = Column(
        Text,
        nullable=True,
        comment="Прогноз для любви"
    )

    career_forecast = Column(
        Text,
        nullable=True,
        comment="Прогноз для карьеры"
    )

    health_forecast = Column(
        Text,
        nullable=True,
        comment="Прогноз для здоровья"
    )

    # Рекомендации
    lucky_days = Column(
        JSON,
        nullable=True,
        comment="Удачные дни"
    )

    warnings = Column(
        JSON,
        nullable=True,
        comment="Предупреждения"
    )

    advice = Column(
        JSON,
        nullable=True,
        comment="Советы"
    )

    # Статистика
    is_sent = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="Отправлен ли прогноз"
    )

    sent_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Время отправки"
    )

    # Отношения
    user = relationship("User", backref="astro_forecasts")
    natal_chart = relationship("NatalChart", backref="forecasts")

    # Ограничения
    __table_args__ = (
        CheckConstraint('period_end >= period_start',
                        name='check_forecast_period'),
        Index('idx_forecast_user_period', 'user_id', 'period_start', 'period_end'),
        Index('idx_forecast_send', 'is_sent', 'period_start'),
    )

    def __repr__(self) -> str:
        return f"<AstroForecast(user_id={self.user_id}, type={self.forecast_type})>"