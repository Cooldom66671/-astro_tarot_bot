"""
Модель пользователя для PostgreSQL.

Этот модуль содержит:
- Основную модель User с данными из Telegram
- Модель UserBirthData для астрологических данных
- Модель UserSettings для настроек и предпочтений
- Модель UserConsent для согласий на обработку данных
- Индексы и связи между таблицами
"""

from datetime import datetime, date
from typing import Optional, List
from enum import Enum

from sqlalchemy import (
    Column, String, BigInteger, Boolean, Date, Time, Float,
    ForeignKey, UniqueConstraint, CheckConstraint, Index,
    Enum as SQLEnum, JSON, Text
)
from sqlalchemy.orm import relationship, validates
from sqlalchemy.ext.hybrid import hybrid_property

from config import logger, SubscriptionTier, UserRole
from infrastructure.database.models.base import (
    BaseUserModel, TimestampMixin, AuditMixin
)
from core.exceptions import ValidationError


class UserStatus(str, Enum):
    """Статус пользователя в системе."""
    ACTIVE = "active"
    BLOCKED = "blocked"
    DELETED = "deleted"
    SUSPENDED = "suspended"


class User(BaseUserModel, AuditMixin):
    """
    Основная модель пользователя.

    Хранит данные из Telegram и основную информацию о пользователе.
    """

    __tablename__ = "users"

    # Telegram данные
    telegram_id = Column(
        BigInteger,
        unique=True,
        nullable=False,
        index=True,
        comment="Telegram ID пользователя"
    )

    username = Column(
        String(64),
        nullable=True,
        index=True,
        comment="Username в Telegram (без @)"
    )

    first_name = Column(
        String(128),
        nullable=False,
        comment="Имя пользователя в Telegram"
    )

    last_name = Column(
        String(128),
        nullable=True,
        comment="Фамилия пользователя в Telegram"
    )

    language_code = Column(
        String(10),
        nullable=False,
        default="ru",
        comment="Код языка пользователя"
    )

    # Статус и роли
    status = Column(
        SQLEnum(UserStatus),
        nullable=False,
        default=UserStatus.ACTIVE,
        index=True,
        comment="Статус пользователя"
    )

    role = Column(
        SQLEnum(UserRole),
        nullable=False,
        default=UserRole.USER,
        index=True,
        comment="Роль пользователя в системе"
    )

    # Подписка
    subscription_tier = Column(
        SQLEnum(SubscriptionTier),
        nullable=False,
        default=SubscriptionTier.FREE,
        index=True,
        comment="Текущий уровень подписки"
    )

    subscription_expires_at = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="Дата окончания подписки"
    )

    # Статистика использования
    total_readings = Column(
        BigInteger,
        nullable=False,
        default=0,
        comment="Общее количество раскладов"
    )

    daily_readings_count = Column(
        BigInteger,
        nullable=False,
        default=0,
        comment="Количество раскладов сегодня"
    )

    daily_readings_date = Column(
        Date,
        nullable=True,
        comment="Дата последнего сброса дневного счетчика"
    )

    last_activity_at = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="Время последней активности"
    )

    # Реферальная система
    referrer_id = Column(
        BigInteger,
        ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True,
        comment="ID пригласившего пользователя"
    )

    referral_code = Column(
        String(32),
        unique=True,
        nullable=True,
        index=True,
        comment="Уникальный реферальный код"
    )

    # Дополнительные данные
    phone_number = Column(
        String(20),
        nullable=True,
        comment="Номер телефона для связи"
    )

    email = Column(
        String(255),
        nullable=True,
        index=True,
        comment="Email для уведомлений"
    )

    notes = Column(
        Text,
        nullable=True,
        comment="Заметки администратора"
    )

    # Отношения
    birth_data = relationship(
        "UserBirthData",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan"
    )

    settings = relationship(
        "UserSettings",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan"
    )

    consents = relationship(
        "UserConsent",
        back_populates="user",
        cascade="all, delete-orphan"
    )

    referrals = relationship(
        "User",
        backref="referrer",
        foreign_keys=[referrer_id]
    )

    # Ограничения
    __table_args__ = (
        CheckConstraint('daily_readings_count >= 0', name='check_daily_readings_positive'),
        CheckConstraint('total_readings >= 0', name='check_total_readings_positive'),
        Index('idx_user_activity', 'status', 'last_activity_at'),
        Index('idx_user_subscription', 'subscription_tier', 'subscription_expires_at'),
    )

    @validates('email')
    def validate_email(self, key, email):
        """Валидация email адреса."""
        if email:
            import re
            pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(pattern, email):
                raise ValidationError("Некорректный email адрес")
        return email

    @validates('username')
    def validate_username(self, key, username):
        """Валидация username из Telegram."""
        if username:
            # Удаляем @ если есть
            username = username.lstrip('@')
            # Проверяем длину
            if len(username) < 5 or len(username) > 32:
                raise ValidationError("Username должен быть от 5 до 32 символов")
        return username

    @hybrid_property
    def full_name(self) -> str:
        """Полное имя пользователя."""
        parts = [self.first_name]
        if self.last_name:
            parts.append(self.last_name)
        return ' '.join(parts)

    @hybrid_property
    def is_premium(self) -> bool:
        """Проверка наличия активной платной подписки."""
        if self.subscription_tier == SubscriptionTier.FREE:
            return False
        if self.subscription_expires_at:
            return self.subscription_expires_at > datetime.utcnow()
        return False

    @hybrid_property
    def can_use_daily_reading(self) -> bool:
        """Может ли пользователь делать расклады сегодня."""
        # Сброс счетчика если новый день
        today = date.today()
        if self.daily_readings_date != today:
            self.daily_readings_count = 0
            self.daily_readings_date = today

        # Проверка лимитов в зависимости от подписки
        limits = {
            SubscriptionTier.FREE: 3,
            SubscriptionTier.BASIC: 10,
            SubscriptionTier.PREMIUM: 50,
            SubscriptionTier.VIP: 999999  # Безлимит
        }

        return self.daily_readings_count < limits.get(self.subscription_tier, 3)

    def increment_readings_count(self) -> None:
        """Увеличение счетчиков раскладов."""
        self.total_readings += 1
        self.daily_readings_count += 1
        self.last_activity_at = datetime.utcnow()
        logger.debug(f"Пользователь {self.telegram_id}: расклад #{self.total_readings}")

    def block(self, reason: Optional[str] = None) -> None:
        """Блокировка пользователя."""
        self.status = UserStatus.BLOCKED
        if reason:
            self.notes = f"{self.notes or ''}\nЗаблокирован: {reason}"
        logger.warning(f"Пользователь {self.telegram_id} заблокирован: {reason}")

    def __repr__(self) -> str:
        return f"<User(id={self.id}, telegram_id={self.telegram_id}, username={self.username})>"


class UserBirthData(BaseUserModel):
    """
    Данные рождения пользователя для астрологических расчетов.

    Хранит время, место и координаты рождения.
    """

    __tablename__ = "user_birth_data"

    user_id = Column(
        BigInteger,
        ForeignKey('users.id', ondelete='CASCADE'),
        unique=True,
        nullable=False,
        comment="ID пользователя"
    )

    # Дата и время рождения
    birth_date = Column(
        Date,
        nullable=False,
        comment="Дата рождения"
    )

    birth_time = Column(
        Time,
        nullable=True,
        comment="Время рождения (может быть неизвестно)"
    )

    is_birth_time_exact = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Точное ли время рождения"
    )

    # Место рождения
    birth_place = Column(
        String(255),
        nullable=False,
        comment="Название места рождения"
    )

    birth_country = Column(
        String(100),
        nullable=True,
        comment="Страна рождения"
    )

    # Координаты
    latitude = Column(
        Float,
        nullable=False,
        comment="Широта места рождения"
    )

    longitude = Column(
        Float,
        nullable=False,
        comment="Долгота места рождения"
    )

    timezone = Column(
        String(50),
        nullable=False,
        default="UTC",
        comment="Часовой пояс места рождения"
    )

    # Кэш натальной карты
    natal_chart_cache = Column(
        JSON,
        nullable=True,
        comment="Кэшированная натальная карта"
    )

    natal_chart_updated_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Время последнего обновления натальной карты"
    )

    # Отношения
    user = relationship("User", back_populates="birth_data")

    # Ограничения
    __table_args__ = (
        CheckConstraint('latitude >= -90 AND latitude <= 90', name='check_latitude_range'),
        CheckConstraint('longitude >= -180 AND longitude <= 180', name='check_longitude_range'),
        Index('idx_birth_location', 'latitude', 'longitude'),
    )

    @validates('birth_date')
    def validate_birth_date(self, key, birth_date):
        """Валидация даты рождения."""
        if birth_date > date.today():
            raise ValidationError("Дата рождения не может быть в будущем")

        min_date = date(1900, 1, 1)
        if birth_date < min_date:
            raise ValidationError("Дата рождения слишком ранняя")

        return birth_date

    @hybrid_property
    def age_years(self) -> int:
        """Возраст в годах."""
        today = date.today()
        age = today.year - self.birth_date.year

        # Корректировка если день рождения еще не наступил
        if today.month < self.birth_date.month or \
                (today.month == self.birth_date.month and today.day < self.birth_date.day):
            age -= 1

        return age

    @hybrid_property
    def zodiac_sign(self) -> str:
        """Знак зодиака по дате рождения."""
        day = self.birth_date.day
        month = self.birth_date.month

        signs = [
            (3, 21, "Овен"), (4, 20, "Телец"), (5, 21, "Близнецы"),
            (6, 21, "Рак"), (7, 23, "Лев"), (8, 23, "Дева"),
            (9, 23, "Весы"), (10, 23, "Скорпион"), (11, 22, "Стрелец"),
            (12, 22, "Козерог"), (1, 20, "Водолей"), (2, 19, "Рыбы")
        ]

        for end_month, end_day, sign in signs:
            if month == end_month and day < end_day:
                return sign
            elif month == end_month - 1 or (month == 12 and end_month == 1):
                return sign

        return "Неизвестно"

    def __repr__(self) -> str:
        return f"<UserBirthData(user_id={self.user_id}, birth_date={self.birth_date})>"


class UserSettings(BaseUserModel):
    """
    Настройки и предпочтения пользователя.

    Хранит персональные настройки для работы бота.
    """

    __tablename__ = "user_settings"

    user_id = Column(
        BigInteger,
        ForeignKey('users.id', ondelete='CASCADE'),
        unique=True,
        nullable=False,
        comment="ID пользователя"
    )

    # Настройки уведомлений
    notifications_enabled = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Включены ли уведомления"
    )

    daily_horoscope_enabled = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="Получать ли ежедневный гороскоп"
    )

    daily_horoscope_time = Column(
        Time,
        nullable=True,
        comment="Время отправки ежедневного гороскопа"
    )

    # Настройки контента
    preferred_tarot_deck = Column(
        String(50),
        nullable=False,
        default="rider_waite",
        comment="Предпочитаемая колода Таро"
    )

    interpretation_style = Column(
        String(50),
        nullable=False,
        default="detailed",
        comment="Стиль интерпретации (краткий/подробный)"
    )

    # Настройки конфиденциальности
    save_readings_history = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Сохранять ли историю раскладов"
    )

    share_data_for_improvements = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="Разрешить использование данных для улучшения"
    )

    # Кастомные настройки
    custom_settings = Column(
        JSON,
        nullable=True,
        default=dict,
        comment="Дополнительные настройки в JSON"
    )

    # Отношения
    user = relationship("User", back_populates="settings")

    def __repr__(self) -> str:
        return f"<UserSettings(user_id={self.user_id})>"


class UserConsent(TimestampMixin):
    """
    Согласия пользователя на обработку данных.

    Для соответствия 152-ФЗ и GDPR.
    """

    __tablename__ = "user_consents"

    id = Column(
        BigInteger,
        primary_key=True,
        autoincrement=True
    )

    user_id = Column(
        BigInteger,
        ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False,
        comment="ID пользователя"
    )

    consent_type = Column(
        String(50),
        nullable=False,
        comment="Тип согласия"
    )

    is_granted = Column(
        Boolean,
        nullable=False,
        comment="Дано ли согласие"
    )

    granted_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Время получения согласия"
    )

    revoked_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Время отзыва согласия"
    )

    ip_address = Column(
        String(45),
        nullable=True,
        comment="IP адрес при даче согласия"
    )

    user_agent = Column(
        String(255),
        nullable=True,
        comment="User agent при даче согласия"
    )

    # Отношения
    user = relationship("User", back_populates="consents")

    # Ограничения
    __table_args__ = (
        UniqueConstraint('user_id', 'consent_type', name='uq_user_consent_type'),
        Index('idx_consent_lookup', 'user_id', 'consent_type', 'is_granted'),
    )

    def __repr__(self) -> str:
        return f"<UserConsent(user_id={self.user_id}, type={self.consent_type}, granted={self.is_granted})>"