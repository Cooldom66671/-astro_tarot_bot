"""
Модуль сущности пользователя для Астро-Таро Бота.

Этот модуль содержит базовую бизнес-сущность User без зависимостей
от инфраструктуры (БД, Telegram API). Включает:
- Dataclass с полями пользователя
- Методы валидации данных
- Бизнес-логику (проверка подписки, лимитов)
- Вычисляемые свойства

Использование:
    from core.entities import User
    from datetime import datetime

    # Создание пользователя
    user = User(
        id=1,
        telegram_id=123456789,
        username="john_doe",
        created_at=datetime.now()
    )

    # Проверка подписки
    if user.has_active_subscription:
        # логика для подписчиков
"""

import re
from dataclasses import dataclass, field
from datetime import datetime, date, time, timedelta
from typing import Optional, List, Dict, Any
from enum import Enum

from pydantic import BaseModel, Field, field_validator, model_validator

from config import (
    logger,
    SubscriptionStatus,
    SubscriptionPlan,
    ToneOfVoice,
    Patterns,
    Limits,
    ErrorMessages
)
from core.exceptions import ValidationError, BusinessLogicError


# ===== ВСПОМОГАТЕЛЬНЫЕ КЛАССЫ =====

class BirthData(BaseModel):
    """
    Данные рождения пользователя для астрологических расчетов.

    Использует Pydantic для валидации при создании.
    """

    name: str = Field(
        ...,
        min_length=Limits.MIN_NAME_LENGTH,
        max_length=Limits.MAX_NAME_LENGTH,
        description="Имя для натальной карты"
    )
    date: date = Field(
        ...,
        description="Дата рождения"
    )
    time: Optional[time] = Field(
        None,
        description="Время рождения (опционально)"
    )
    city: str = Field(
        ...,
        max_length=Limits.MAX_CITY_LENGTH,
        description="Город рождения"
    )
    latitude: Optional[float] = Field(
        None,
        ge=-90.0,
        le=90.0,
        description="Широта места рождения"
    )
    longitude: Optional[float] = Field(
        None,
        ge=-180.0,
        le=180.0,
        description="Долгота места рождения"
    )
    timezone: Optional[str] = Field(
        None,
        description="Часовой пояс места рождения"
    )

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Валидация имени."""
        v = v.strip()
        if not re.match(Patterns.NAME, v):
            raise ValueError(ErrorMessages.INVALID_NAME)
        return v

    @field_validator('date')
    @classmethod
    def validate_date(cls, v: date) -> date:
        """Валидация даты рождения."""
        # Проверяем, что дата не в будущем
        if v > date.today():
            raise ValueError("Дата рождения не может быть в будущем")

        # Проверяем разумный диапазон (не старше 150 лет)
        min_date = date.today() - timedelta(days=150 * 365)
        if v < min_date:
            raise ValueError("Некорректная дата рождения")

        return v

    @model_validator(mode='after')
    def validate_coordinates(self) -> 'BirthData':
        """Проверка, что координаты либо обе заданы, либо обе None."""
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("Широта и долгота должны быть указаны вместе")
        return self

    @property
    def has_exact_time(self) -> bool:
        """Проверка наличия точного времени рождения."""
        return self.time is not None

    @property
    def has_coordinates(self) -> bool:
        """Проверка наличия координат."""
        return self.latitude is not None and self.longitude is not None

    @property
    def age_years(self) -> int:
        """Возраст в годах."""
        today = date.today()
        age = today.year - self.date.year

        # Корректировка, если день рождения еще не наступил в этом году
        if (today.month, today.day) < (self.date.month, self.date.day):
            age -= 1

        return age

    def to_display_string(self) -> str:
        """Форматированная строка для отображения."""
        time_str = self.time.strftime("%H:%M") if self.time else "время неизвестно"
        return (
            f"{self.name}\n"
            f"Дата: {self.date.strftime('%d.%m.%Y')}\n"
            f"Время: {time_str}\n"
            f"Место: {self.city}"
        )


class UserSubscription(BaseModel):
    """Информация о подписке пользователя."""

    status: SubscriptionStatus = Field(
        default=SubscriptionStatus.FREE,
        description="Текущий статус подписки"
    )
    plan: SubscriptionPlan = Field(
        default=SubscriptionPlan.FREE,
        description="Тарифный план"
    )
    started_at: Optional[datetime] = Field(
        None,
        description="Дата начала подписки"
    )
    expires_at: Optional[datetime] = Field(
        None,
        description="Дата окончания подписки"
    )
    auto_renewal: bool = Field(
        default=False,
        description="Автопродление включено"
    )

    @property
    def is_active(self) -> bool:
        """Проверка активности подписки."""
        if self.status != SubscriptionStatus.ACTIVE:
            return False

        if self.expires_at and self.expires_at < datetime.now():
            return False

        return True

    @property
    def days_left(self) -> Optional[int]:
        """Количество дней до окончания подписки."""
        if not self.expires_at or not self.is_active:
            return None

        delta = self.expires_at - datetime.now()
        return max(0, delta.days)

    @property
    def is_expiring_soon(self) -> bool:
        """Проверка, что подписка скоро истечет (менее 3 дней)."""
        days = self.days_left
        return days is not None and 0 < days <= 3


class UserSettings(BaseModel):
    """Настройки пользователя."""

    tone_of_voice: ToneOfVoice = Field(
        default=ToneOfVoice.FRIEND,
        description="Тональность общения бота"
    )
    language: str = Field(
        default="ru",
        description="Язык интерфейса"
    )
    notifications_enabled: bool = Field(
        default=True,
        description="Уведомления включены"
    )
    daily_card_reminder: bool = Field(
        default=False,
        description="Напоминание о карте дня"
    )
    reminder_time: Optional[time] = Field(
        None,
        description="Время напоминания"
    )

    @field_validator('language')
    @classmethod
    def validate_language(cls, v: str) -> str:
        """Валидация языка."""
        supported_languages = ["ru", "en"]  # Пока только русский
        if v not in supported_languages:
            raise ValueError(f"Язык {v} не поддерживается")
        return v


# ===== ОСНОВНАЯ СУЩНОСТЬ ПОЛЬЗОВАТЕЛЯ =====

@dataclass
class User:
    """
    Основная бизнес-сущность пользователя.

    Содержит всю бизнес-логику пользователя без привязки
    к конкретной реализации хранилища или API.
    """

    # Основные поля
    id: int
    telegram_id: int
    created_at: datetime

    # Telegram данные
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    language_code: Optional[str] = None
    is_bot: bool = False
    is_premium: bool = False  # Telegram Premium

    # Данные для астрологии
    birth_data: Optional[BirthData] = None

    # Подписка
    subscription: UserSubscription = field(default_factory=UserSubscription)

    # Настройки
    settings: UserSettings = field(default_factory=UserSettings)

    # Статистика использования
    last_activity_at: Optional[datetime] = None
    total_requests: int = 0
    daily_requests: int = 0
    daily_requests_date: Optional[date] = None

    # Флаги
    is_blocked: bool = False
    is_admin: bool = False
    data_processing_consent: bool = False
    data_processing_consent_at: Optional[datetime] = None

    def __post_init__(self):
        """Валидация после создания."""
        logger.debug(f"Создан пользователь: id={self.id}, telegram_id={self.telegram_id}")

        # Валидация обязательных полей
        if self.id <= 0:
            raise ValidationError("id", "ID пользователя должен быть положительным")

        if self.telegram_id <= 0:
            raise ValidationError("telegram_id", "Telegram ID должен быть положительным")

    # ===== СВОЙСТВА =====

    @property
    def full_name(self) -> str:
        """Полное имя пользователя."""
        parts = []
        if self.first_name:
            parts.append(self.first_name)
        if self.last_name:
            parts.append(self.last_name)

        if parts:
            return " ".join(parts)

        return self.username or f"User {self.telegram_id}"

    @property
    def display_name(self) -> str:
        """Имя для отображения."""
        if self.first_name:
            return self.first_name
        if self.username:
            return f"@{self.username}"
        return f"User {self.telegram_id}"

    @property
    def has_birth_data(self) -> bool:
        """Проверка наличия данных рождения."""
        return self.birth_data is not None

    @property
    def has_active_subscription(self) -> bool:
        """Проверка активной подписки."""
        return self.subscription.is_active

    @property
    def subscription_plan(self) -> SubscriptionPlan:
        """Текущий план подписки."""
        return self.subscription.plan

    @property
    def is_free_user(self) -> bool:
        """Проверка, что пользователь на бесплатном тарифе."""
        return self.subscription_plan == SubscriptionPlan.FREE

    @property
    def can_use_premium_features(self) -> bool:
        """Может ли использовать премиум функции."""
        return self.has_active_subscription and not self.is_free_user

    @property
    def days_since_registration(self) -> int:
        """Количество дней с момента регистрации."""
        delta = datetime.now() - self.created_at
        return delta.days

    @property
    def is_new_user(self) -> bool:
        """Новый пользователь (менее 7 дней)."""
        return self.days_since_registration < 7

    @property
    def daily_limit(self) -> int:
        """Дневной лимит запросов в зависимости от подписки."""
        if self.has_active_subscription:
            if self.subscription_plan == SubscriptionPlan.VIP:
                return Limits.MAX_SPREADS_PER_DAY_PREMIUM * 2
            elif self.subscription_plan in [SubscriptionPlan.BASIC, SubscriptionPlan.PREMIUM]:
                return Limits.MAX_SPREADS_PER_DAY_PREMIUM

        return Limits.MAX_SPREADS_PER_DAY_FREE

    # ===== МЕТОДЫ ВАЛИДАЦИИ =====

    def validate_birth_data_required(self) -> None:
        """Проверка, что данные рождения заполнены."""
        if not self.has_birth_data:
            raise BusinessLogicError(
                "Необходимо заполнить данные рождения",
                details={"user_id": self.id}
            )

    def validate_subscription_required(self, feature: str) -> None:
        """Проверка, что есть активная подписка для функции."""
        if not self.has_active_subscription or self.is_free_user:
            from core.exceptions import SubscriptionRequiredError
            raise SubscriptionRequiredError(
                feature=feature,
                current_plan=self.subscription_plan.value
            )

    def validate_not_blocked(self) -> None:
        """Проверка, что пользователь не заблокирован."""
        if self.is_blocked:
            from core.exceptions import AccessDeniedError
            raise AccessDeniedError(
                resource="bot",
                reason="Пользователь заблокирован"
            )

    def validate_consent_given(self) -> None:
        """Проверка согласия на обработку данных."""
        if not self.data_processing_consent:
            raise BusinessLogicError(
                "Требуется согласие на обработку персональных данных",
                details={"user_id": self.id}
            )

    # ===== МЕТОДЫ БИЗНЕС-ЛОГИКИ =====

    def can_generate_daily_card(self) -> bool:
        """Может ли получить карту дня."""
        # Проверяем подписку для множественных карт
        if not self.has_active_subscription:
            # Бесплатные пользователи - одна карта в день
            if self.daily_requests_date == date.today() and self.daily_requests >= 1:
                return False

        return True

    def can_make_spread(self, spread_type: str) -> bool:
        """Может ли сделать расклад определенного типа."""
        # Некоторые расклады только для подписчиков
        premium_spreads = ["celtic_cross", "year_ahead", "chakras"]
        if spread_type in premium_spreads and not self.can_use_premium_features:
            return False

        # Проверяем дневной лимит
        if self.daily_requests_date == date.today():
            if self.daily_requests >= self.daily_limit:
                return False

        return True

    def update_daily_requests(self) -> None:
        """Обновить счетчик дневных запросов."""
        today = date.today()

        if self.daily_requests_date != today:
            # Новый день - сбрасываем счетчик
            self.daily_requests = 1
            self.daily_requests_date = today
        else:
            # Тот же день - увеличиваем счетчик
            self.daily_requests += 1

        # Увеличиваем общий счетчик
        self.total_requests += 1

        logger.info(
            f"Обновлен счетчик запросов пользователя {self.id}: "
            f"daily={self.daily_requests}, total={self.total_requests}"
        )

    def update_activity(self) -> None:
        """Обновить время последней активности."""
        self.last_activity_at = datetime.now()

    def give_consent(self) -> None:
        """Дать согласие на обработку данных."""
        self.data_processing_consent = True
        self.data_processing_consent_at = datetime.now()
        logger.info(f"Пользователь {self.id} дал согласие на обработку данных")

    def revoke_consent(self) -> None:
        """Отозвать согласие на обработку данных."""
        self.data_processing_consent = False
        logger.warning(f"Пользователь {self.id} отозвал согласие на обработку данных")

    def block(self, reason: str) -> None:
        """Заблокировать пользователя."""
        self.is_blocked = True
        logger.warning(f"Пользователь {self.id} заблокирован. Причина: {reason}")

    def unblock(self) -> None:
        """Разблокировать пользователя."""
        self.is_blocked = False
        logger.info(f"Пользователь {self.id} разблокирован")

    def to_dict(self) -> Dict[str, Any]:
        """Преобразовать в словарь для сериализации."""
        return {
            "id": self.id,
            "telegram_id": self.telegram_id,
            "username": self.username,
            "full_name": self.full_name,
            "created_at": self.created_at.isoformat(),
            "has_birth_data": self.has_birth_data,
            "subscription": {
                "status": self.subscription.status.value,
                "plan": self.subscription.plan.value,
                "is_active": self.subscription.is_active,
                "days_left": self.subscription.days_left,
            },
            "settings": {
                "tone_of_voice": self.settings.tone_of_voice.value,
                "language": self.settings.language,
                "notifications_enabled": self.settings.notifications_enabled,
            },
            "is_blocked": self.is_blocked,
            "is_admin": self.is_admin,
        }

    def __str__(self) -> str:
        """Строковое представление."""
        return f"User(id={self.id}, telegram_id={self.telegram_id}, name='{self.display_name}')"

    def __repr__(self) -> str:
        """Представление для отладки."""
        return (
            f"User(id={self.id}, telegram_id={self.telegram_id}, "
            f"username='{self.username}', subscription={self.subscription.status.value})"
        )


# Экспорт
__all__ = ["User", "BirthData", "UserSubscription", "UserSettings"]