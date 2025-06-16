"""
Модели для работы с картами Таро и раскладами.

Этот модуль содержит:
- Модель TarotCard для справочника карт
- Модель TarotDeck для различных колод
- Модель TarotSpread для типов раскладов
- Модель TarotReading для истории раскладов пользователей
- Модель SavedReading для избранных раскладов
"""

from datetime import datetime
from typing import Optional, List, Dict
from enum import Enum

from sqlalchemy import (
    Column, String, BigInteger, Boolean, DateTime, Text,
    ForeignKey, UniqueConstraint, CheckConstraint, Index,
    Enum as SQLEnum, JSON, Integer, Float
)
from sqlalchemy.orm import relationship, validates
from sqlalchemy.ext.hybrid import hybrid_property

from config import logger
from infrastructure.database.models.base import (
    BaseModel, TimestampMixin, SoftDeleteMixin
)
from core.exceptions import ValidationError


class CardType(str, Enum):
    """Тип карты Таро."""
    MAJOR_ARCANA = "major_arcana"  # Старшие арканы (0-21)
    WANDS = "wands"  # Жезлы/Посохи
    CUPS = "cups"  # Кубки/Чаши
    SWORDS = "swords"  # Мечи
    PENTACLES = "pentacles"  # Пентакли/Монеты


class ReadingType(str, Enum):
    """Тип расклада."""
    CARD_OF_DAY = "card_of_day"  # Карта дня
    THREE_CARDS = "three_cards"  # Три карты
    CELTIC_CROSS = "celtic_cross"  # Кельтский крест
    RELATIONSHIP = "relationship"  # Отношения
    CAREER = "career"  # Карьера
    YES_NO = "yes_no"  # Да/Нет
    CUSTOM = "custom"  # Пользовательский


class TarotDeck(BaseModel, TimestampMixin):
    """
    Колоды карт Таро.

    Справочник различных колод (Райдер-Уэйт, Таро Тота и др.)
    """

    __tablename__ = "tarot_decks"

    code = Column(
        String(50),
        unique=True,
        nullable=False,
        comment="Код колоды"
    )

    name = Column(
        String(100),
        nullable=False,
        comment="Название колоды"
    )

    description = Column(
        Text,
        nullable=True,
        comment="Описание колоды"
    )

    author = Column(
        String(100),
        nullable=True,
        comment="Автор/создатель колоды"
    )

    year_created = Column(
        Integer,
        nullable=True,
        comment="Год создания"
    )

    image_style = Column(
        String(50),
        nullable=True,
        comment="Стиль изображений"
    )

    is_default = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="Колода по умолчанию"
    )

    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Доступна ли колода"
    )

    # Отношения
    cards = relationship("TarotCard", back_populates="deck")

    def __repr__(self) -> str:
        return f"<TarotDeck(code={self.code}, name={self.name})>"


class TarotCard(BaseModel, TimestampMixin):
    """
    Карты Таро.

    Справочник всех карт с их значениями.
    """

    __tablename__ = "tarot_cards"

    deck_id = Column(
        BigInteger,
        ForeignKey('tarot_decks.id', ondelete='CASCADE'),
        nullable=False,
        comment="ID колоды"
    )

    # Идентификация карты
    card_number = Column(
        Integer,
        nullable=False,
        comment="Номер карты (0-77)"
    )

    card_type = Column(
        SQLEnum(CardType),
        nullable=False,
        comment="Тип карты"
    )

    name = Column(
        String(100),
        nullable=False,
        comment="Название карты"
    )

    alternative_names = Column(
        JSON,
        nullable=True,
        comment="Альтернативные названия"
    )

    # Символика и значения
    keywords_upright = Column(
        JSON,
        nullable=False,
        comment="Ключевые слова в прямом положении"
    )

    keywords_reversed = Column(
        JSON,
        nullable=False,
        comment="Ключевые слова в перевернутом положении"
    )

    # Описания
    description = Column(
        Text,
        nullable=True,
        comment="Общее описание карты"
    )

    meaning_upright = Column(
        Text,
        nullable=False,
        comment="Значение в прямом положении"
    )

    meaning_reversed = Column(
        Text,
        nullable=False,
        comment="Значение в перевернутом положении"
    )

    # Дополнительные аспекты
    love_upright = Column(
        Text,
        nullable=True,
        comment="Значение для любви (прямое)"
    )

    love_reversed = Column(
        Text,
        nullable=True,
        comment="Значение для любви (перевернутое)"
    )

    career_upright = Column(
        Text,
        nullable=True,
        comment="Значение для карьеры (прямое)"
    )

    career_reversed = Column(
        Text,
        nullable=True,
        comment="Значение для карьеры (перевернутое)"
    )

    # Астрологические соответствия
    astrological_correspondence = Column(
        String(100),
        nullable=True,
        comment="Астрологическое соответствие"
    )

    element = Column(
        String(20),
        nullable=True,
        comment="Стихия карты"
    )

    # Изображения
    image_url = Column(
        String(500),
        nullable=True,
        comment="URL изображения карты"
    )

    # Отношения
    deck = relationship("TarotDeck", back_populates="cards")

    # Ограничения
    __table_args__ = (
        UniqueConstraint('deck_id', 'card_number', name='uq_deck_card_number'),
        CheckConstraint('card_number >= 0 AND card_number <= 77',
                        name='check_card_number_range'),
        Index('idx_card_lookup', 'deck_id', 'card_type', 'card_number'),
    )

    @hybrid_property
    def full_name(self) -> str:
        """Полное название с номером."""
        if self.card_type == CardType.MAJOR_ARCANA:
            return f"{self.card_number}. {self.name}"
        else:
            # Для младших арканов
            suit_names = {
                CardType.WANDS: "Жезлов",
                CardType.CUPS: "Кубков",
                CardType.SWORDS: "Мечей",
                CardType.PENTACLES: "Пентаклей"
            }
            suit = suit_names.get(self.card_type, "")

            # Преобразование номера в название
            if self.card_number % 14 == 1:
                return f"Туз {suit}"
            elif self.card_number % 14 == 11:
                return f"Паж {suit}"
            elif self.card_number % 14 == 12:
                return f"Рыцарь {suit}"
            elif self.card_number % 14 == 13:
                return f"Королева {suit}"
            elif self.card_number % 14 == 0:
                return f"Король {suit}"
            else:
                return f"{self.card_number % 14} {suit}"

    def __repr__(self) -> str:
        return f"<TarotCard(number={self.card_number}, name={self.name})>"


class TarotSpread(BaseModel, TimestampMixin):
    """
    Типы раскладов Таро.

    Определяет структуру и позиции карт в раскладе.
    """

    __tablename__ = "tarot_spreads"

    code = Column(
        String(50),
        unique=True,
        nullable=False,
        comment="Код расклада"
    )

    name = Column(
        String(100),
        nullable=False,
        comment="Название расклада"
    )

    description = Column(
        Text,
        nullable=True,
        comment="Описание расклада"
    )

    card_count = Column(
        Integer,
        nullable=False,
        comment="Количество карт"
    )

    # Позиции карт
    positions = Column(
        JSON,
        nullable=False,
        comment="Описание позиций карт"
    )

    # Категория и использование
    category = Column(
        String(50),
        nullable=True,
        comment="Категория расклада"
    )

    difficulty_level = Column(
        Integer,
        nullable=False,
        default=1,
        comment="Уровень сложности (1-5)"
    )

    is_premium = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="Только для премиум подписки"
    )

    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Доступен ли расклад"
    )

    # Статистика
    usage_count = Column(
        BigInteger,
        nullable=False,
        default=0,
        comment="Количество использований"
    )

    # Ограничения
    __table_args__ = (
        CheckConstraint('card_count > 0 AND card_count <= 78',
                        name='check_spread_card_count'),
        CheckConstraint('difficulty_level >= 1 AND difficulty_level <= 5',
                        name='check_difficulty_range'),
    )

    def __repr__(self) -> str:
        return f"<TarotSpread(code={self.code}, cards={self.card_count})>"


class TarotReading(BaseModel, TimestampMixin, SoftDeleteMixin):
    """
    История раскладов пользователей.

    Хранит все выполненные расклады с интерпретациями.
    """

    __tablename__ = "tarot_readings"

    user_id = Column(
        BigInteger,
        ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False,
        comment="ID пользователя"
    )

    spread_id = Column(
        BigInteger,
        ForeignKey('tarot_spreads.id', ondelete='SET NULL'),
        nullable=True,
        comment="ID типа расклада"
    )

    deck_id = Column(
        BigInteger,
        ForeignKey('tarot_decks.id', ondelete='SET NULL'),
        nullable=True,
        comment="ID использованной колоды"
    )

    # Тип и вопрос
    reading_type = Column(
        SQLEnum(ReadingType),
        nullable=False,
        index=True,
        comment="Тип расклада"
    )

    question = Column(
        Text,
        nullable=True,
        comment="Вопрос пользователя"
    )

    # Выпавшие карты
    cards_drawn = Column(
        JSON,
        nullable=False,
        comment="Выпавшие карты с позициями"
    )

    # Интерпретация
    interpretation = Column(
        Text,
        nullable=True,
        comment="Интерпретация расклада"
    )

    interpretation_model = Column(
        String(50),
        nullable=True,
        comment="Модель LLM для интерпретации"
    )

    interpretation_tokens = Column(
        Integer,
        nullable=True,
        comment="Использовано токенов"
    )

    # Дополнительные данные
    context_data = Column(
        JSON,
        nullable=True,
        comment="Контекст расклада"
    )

    # Оценка и обратная связь
    user_rating = Column(
        Integer,
        nullable=True,
        comment="Оценка пользователя (1-5)"
    )

    user_feedback = Column(
        Text,
        nullable=True,
        comment="Отзыв пользователя"
    )

    is_favorite = Column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Добавлено в избранное"
    )

    # Время выполнения
    duration_seconds = Column(
        Float,
        nullable=True,
        comment="Время генерации в секундах"
    )

    # Отношения
    user = relationship("User", backref="tarot_readings")
    spread = relationship("TarotSpread", backref="readings")
    deck = relationship("TarotDeck", backref="readings")
    saved_reading = relationship(
        "SavedReading",
        back_populates="reading",
        uselist=False
    )

    # Ограничения
    __table_args__ = (
        CheckConstraint('user_rating >= 1 AND user_rating <= 5',
                        name='check_rating_range'),
        Index('idx_reading_user_date', 'user_id', 'created_at'),
        Index('idx_reading_favorites', 'user_id', 'is_favorite'),
    )

    @validates('cards_drawn')
    def validate_cards_drawn(self, key, cards_drawn):
        """Валидация выпавших карт."""
        if not isinstance(cards_drawn, list):
            raise ValidationError("cards_drawn должен быть списком")

        # Проверка структуры
        for card in cards_drawn:
            if not isinstance(card, dict):
                raise ValidationError("Каждая карта должна быть словарем")

            required_keys = {'card_id', 'position', 'is_reversed'}
            if not required_keys.issubset(card.keys()):
                raise ValidationError(f"Карта должна содержать ключи: {required_keys}")

        return cards_drawn

    @hybrid_property
    def cards_summary(self) -> str:
        """Краткое описание выпавших карт."""
        if not self.cards_drawn:
            return "Нет карт"

        count = len(self.cards_drawn)
        reversed_count = sum(1 for card in self.cards_drawn if card.get('is_reversed'))

        return f"{count} карт{'а' if count == 1 else ''} ({reversed_count} перевернут{'а' if reversed_count == 1 else 'ых'})"

    def add_to_favorites(self) -> None:
        """Добавление в избранное."""
        self.is_favorite = True
        logger.info(f"Расклад {self.id} добавлен в избранное")

    def __repr__(self) -> str:
        return f"<TarotReading(id={self.id}, user_id={self.user_id}, type={self.reading_type})>"


class SavedReading(BaseModel, TimestampMixin):
    """
    Сохраненные расклады.

    Расширенная информация для избранных раскладов.
    """

    __tablename__ = "saved_readings"

    reading_id = Column(
        BigInteger,
        ForeignKey('tarot_readings.id', ondelete='CASCADE'),
        unique=True,
        nullable=False,
        comment="ID расклада"
    )

    user_id = Column(
        BigInteger,
        ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False,
        comment="ID пользователя"
    )

    # Пользовательские данные
    title = Column(
        String(200),
        nullable=True,
        comment="Название от пользователя"
    )

    notes = Column(
        Text,
        nullable=True,
        comment="Заметки пользователя"
    )

    tags = Column(
        JSON,
        nullable=True,
        default=list,
        comment="Теги для организации"
    )

    # Напоминания
    reminder_date = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Дата напоминания"
    )

    reminder_sent = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="Отправлено ли напоминание"
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
    reading = relationship("TarotReading", back_populates="saved_reading")
    user = relationship("User", backref="saved_readings")

    # Ограничения
    __table_args__ = (
        Index('idx_saved_user_date', 'user_id', 'created_at'),
        Index('idx_saved_reminder', 'reminder_date', 'reminder_sent'),
    )

    def increment_views(self) -> None:
        """Увеличение счетчика просмотров."""
        self.view_count += 1
        self.last_viewed_at = datetime.utcnow()

    def __repr__(self) -> str:
        return f"<SavedReading(reading_id={self.reading_id}, title={self.title})>"