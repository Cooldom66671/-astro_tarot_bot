"""
Модели для управления подписками и платежами.

Этот модуль содержит:
- Модель Subscription для активных подписок
- Модель Payment для истории платежей
- Модель PromoCode для промокодов и скидок
- Модель SubscriptionPlan для тарифных планов
- Модель PaymentMethod для сохраненных способов оплаты
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional
from enum import Enum
import secrets
import string

from sqlalchemy import (
    Column, String, BigInteger, Boolean, DateTime, Numeric,
    ForeignKey, UniqueConstraint, CheckConstraint, Index,
    Enum as SQLEnum, JSON, Integer
)
from sqlalchemy.orm import relationship, validates
from sqlalchemy.ext.hybrid import hybrid_property

from config import logger, SubscriptionTier
from infrastructure.database.models.base import (
    BaseTransactionModel, TimestampMixin, BaseModel
)
from core.exceptions import ValidationError


class PaymentStatus(str, Enum):
    """Статус платежа."""
    PENDING = "pending"  # Ожидает оплаты
    PROCESSING = "processing"  # В обработке
    SUCCEEDED = "succeeded"  # Успешно оплачен
    FAILED = "failed"  # Ошибка оплаты
    CANCELLED = "cancelled"  # Отменен
    REFUNDED = "refunded"  # Возвращен


class PaymentProvider(str, Enum):
    """Платежный провайдер."""
    YOOKASSA = "yookassa"
    CRYPTOBOT = "cryptobot"
    TELEGRAM_STARS = "telegram_stars"
    MANUAL = "manual"  # Ручное начисление админом


class PromoCodeType(str, Enum):
    """Тип промокода."""
    PERCENTAGE = "percentage"  # Процентная скидка
    FIXED = "fixed"  # Фиксированная скидка
    TRIAL = "trial"  # Пробный период
    UPGRADE = "upgrade"  # Апгрейд тарифа


class SubscriptionPlan(BaseModel, TimestampMixin):
    """
    Тарифные планы подписок.

    Централизованное хранение информации о планах.
    """

    __tablename__ = "subscription_plans"

    tier = Column(
        SQLEnum(SubscriptionTier),
        unique=True,
        nullable=False,
        comment="Уровень подписки"
    )

    name = Column(
        String(100),
        nullable=False,
        comment="Название плана"
    )

    description = Column(
        String(500),
        nullable=True,
        comment="Описание плана"
    )

    # Цены
    monthly_price = Column(
        Numeric(10, 2),
        nullable=False,
        comment="Цена за месяц в рублях"
    )

    yearly_price = Column(
        Numeric(10, 2),
        nullable=True,
        comment="Цена за год в рублях"
    )

    # Лимиты
    daily_readings_limit = Column(
        Integer,
        nullable=False,
        comment="Лимит раскладов в день"
    )

    monthly_readings_limit = Column(
        Integer,
        nullable=True,
        comment="Лимит раскладов в месяц"
    )

    # Возможности
    features = Column(
        JSON,
        nullable=False,
        default=dict,
        comment="Список возможностей плана"
    )

    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Активен ли план для продажи"
    )

    sort_order = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Порядок сортировки"
    )

    # Ограничения
    __table_args__ = (
        CheckConstraint('monthly_price >= 0', name='check_monthly_price_positive'),
        CheckConstraint('daily_readings_limit >= 0', name='check_daily_limit_positive'),
    )

    def __repr__(self) -> str:
        return f"<SubscriptionPlan(tier={self.tier}, price={self.monthly_price})>"


class Subscription(BaseModel, TimestampMixin):
    """
    Активные подписки пользователей.

    Отслеживает текущие подписки и их состояние.
    """

    __tablename__ = "subscriptions"

    user_id = Column(
        BigInteger,
        ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False,
        comment="ID пользователя"
    )

    tier = Column(
        SQLEnum(SubscriptionTier),
        nullable=False,
        comment="Уровень подписки"
    )

    # Период действия
    started_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        comment="Начало подписки"
    )

    expires_at = Column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="Окончание подписки"
    )

    # Автопродление
    is_auto_renew = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="Автопродление включено"
    )

    next_payment_date = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Дата следующего платежа"
    )

    # Связь с платежом
    payment_id = Column(
        BigInteger,
        ForeignKey('payments.id', ondelete='SET NULL'),
        nullable=True,
        comment="ID платежа за подписку"
    )

    # Промокод
    promo_code_id = Column(
        BigInteger,
        ForeignKey('promo_codes.id', ondelete='SET NULL'),
        nullable=True,
        comment="Использованный промокод"
    )

    # Статус
    is_trial = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="Пробная подписка"
    )

    is_cancelled = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="Подписка отменена"
    )

    cancelled_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Время отмены подписки"
    )

    # Отношения
    user = relationship("User", backref="subscriptions")
    payment = relationship("Payment", backref="subscription")
    promo_code = relationship("PromoCode", backref="subscriptions")

    # Ограничения
    __table_args__ = (
        Index('idx_subscription_active', 'user_id', 'expires_at'),
        Index('idx_subscription_renewal', 'is_auto_renew', 'next_payment_date'),
        CheckConstraint('expires_at > started_at', name='check_subscription_period'),
    )

    @hybrid_property
    def is_active(self) -> bool:
        """Активна ли подписка."""
        if self.is_cancelled:
            return False
        return self.expires_at > datetime.utcnow()

    @hybrid_property
    def days_remaining(self) -> int:
        """Дней до окончания подписки."""
        if not self.is_active:
            return 0
        delta = self.expires_at - datetime.utcnow()
        return max(0, delta.days)

    def cancel(self, immediate: bool = False) -> None:
        """
        Отмена подписки.

        Args:
            immediate: Отменить немедленно или в конце периода
        """
        self.is_cancelled = True
        self.cancelled_at = datetime.utcnow()
        self.is_auto_renew = False

        if immediate:
            self.expires_at = datetime.utcnow()

        logger.info(f"Подписка {self.id} отменена для пользователя {self.user_id}")

    def __repr__(self) -> str:
        return f"<Subscription(id={self.id}, user_id={self.user_id}, tier={self.tier})>"


class Payment(BaseTransactionModel):
    """
    История платежей.

    Хранит все платежные транзакции.
    """

    __tablename__ = "payments"

    user_id = Column(
        BigInteger,
        ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False,
        comment="ID пользователя"
    )

    # Детали платежа
    amount = Column(
        Numeric(10, 2),
        nullable=False,
        comment="Сумма платежа в рублях"
    )

    currency = Column(
        String(3),
        nullable=False,
        default="RUB",
        comment="Валюта платежа"
    )

    status = Column(
        SQLEnum(PaymentStatus),
        nullable=False,
        default=PaymentStatus.PENDING,
        index=True,
        comment="Статус платежа"
    )

    provider = Column(
        SQLEnum(PaymentProvider),
        nullable=False,
        comment="Платежный провайдер"
    )

    # Внешние идентификаторы
    provider_payment_id = Column(
        String(255),
        nullable=True,
        unique=True,
        comment="ID платежа у провайдера"
    )

    provider_order_id = Column(
        String(255),
        nullable=True,
        comment="ID заказа у провайдера"
    )

    # Детали подписки
    subscription_tier = Column(
        SQLEnum(SubscriptionTier),
        nullable=False,
        comment="Оплачиваемый тариф"
    )

    subscription_period_days = Column(
        Integer,
        nullable=False,
        comment="Период подписки в днях"
    )

    # Платежная информация
    payment_method_id = Column(
        BigInteger,
        ForeignKey('payment_methods.id', ondelete='SET NULL'),
        nullable=True,
        comment="Сохраненный способ оплаты"
    )

    # Временные метки
    paid_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Время успешной оплаты"
    )

    failed_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Время неудачной оплаты"
    )

    # Дополнительные данные
    metadata = Column(
        JSON,
        nullable=True,
        default=dict,
        comment="Метаданные платежа"
    )

    error_message = Column(
        String(500),
        nullable=True,
        comment="Сообщение об ошибке"
    )

    receipt_url = Column(
        String(500),
        nullable=True,
        comment="Ссылка на чек"
    )

    # Отношения
    user = relationship("User", backref="payments")
    payment_method = relationship("PaymentMethod", backref="payments")

    # Ограничения
    __table_args__ = (
        CheckConstraint('amount > 0', name='check_payment_amount_positive'),
        CheckConstraint('subscription_period_days > 0', name='check_period_positive'),
        Index('idx_payment_status', 'status', 'created_at'),
        Index('idx_payment_provider', 'provider', 'provider_payment_id'),
    )

    def mark_as_paid(self) -> None:
        """Отметка платежа как успешного."""
        self.status = PaymentStatus.SUCCEEDED
        self.paid_at = datetime.utcnow()
        logger.info(f"Платеж {self.uuid} успешно оплачен")

    def mark_as_failed(self, error: str) -> None:
        """Отметка платежа как неудачного."""
        self.status = PaymentStatus.FAILED
        self.failed_at = datetime.utcnow()
        self.error_message = error
        logger.error(f"Платеж {self.uuid} не прошел: {error}")

    def __repr__(self) -> str:
        return f"<Payment(uuid={self.uuid}, amount={self.amount}, status={self.status})>"


class PromoCode(BaseModel, TimestampMixin):
    """
    Промокоды и скидки.

    Управление промо-акциями и скидками.
    """

    __tablename__ = "promo_codes"

    code = Column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
        comment="Код промокода"
    )

    type = Column(
        SQLEnum(PromoCodeType),
        nullable=False,
        comment="Тип промокода"
    )

    # Значение скидки
    discount_percent = Column(
        Integer,
        nullable=True,
        comment="Процент скидки (для percentage)"
    )

    discount_amount = Column(
        Numeric(10, 2),
        nullable=True,
        comment="Сумма скидки (для fixed)"
    )

    trial_days = Column(
        Integer,
        nullable=True,
        comment="Дней пробного периода (для trial)"
    )

    # Ограничения использования
    max_uses = Column(
        Integer,
        nullable=True,
        comment="Максимум использований"
    )

    used_count = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Количество использований"
    )

    max_uses_per_user = Column(
        Integer,
        nullable=False,
        default=1,
        comment="Максимум использований одним пользователем"
    )

    # Период действия
    valid_from = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        comment="Начало действия"
    )

    valid_until = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="Окончание действия"
    )

    # Применимость
    applicable_tiers = Column(
        JSON,
        nullable=True,
        comment="К каким тарифам применим"
    )

    min_amount = Column(
        Numeric(10, 2),
        nullable=True,
        comment="Минимальная сумма для применения"
    )

    # Статус
    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Активен ли промокод"
    )

    # Создатель
    created_by_admin_id = Column(
        BigInteger,
        nullable=True,
        comment="ID админа, создавшего промокод"
    )

    description = Column(
        String(500),
        nullable=True,
        comment="Описание промокода"
    )

    # Ограничения
    __table_args__ = (
        CheckConstraint('discount_percent >= 0 AND discount_percent <= 100',
                        name='check_discount_percent_range'),
        CheckConstraint('used_count >= 0', name='check_used_count_positive'),
        Index('idx_promo_active', 'is_active', 'valid_until'),
    )

    @validates('code')
    def validate_code(self, key, code):
        """Валидация и форматирование кода."""
        # Приводим к верхнему регистру
        code = code.upper().strip()

        # Проверяем формат
        if not code or len(code) < 3 or len(code) > 20:
            raise ValidationError("Промокод должен быть от 3 до 20 символов")

        # Только буквы, цифры и дефис
        allowed = set(string.ascii_uppercase + string.digits + '-')
        if not all(c in allowed for c in code):
            raise ValidationError("Промокод может содержать только буквы, цифры и дефис")

        return code

    @hybrid_property
    def is_valid(self) -> bool:
        """Действителен ли промокод."""
        if not self.is_active:
            return False

        now = datetime.utcnow()

        # Проверка периода действия
        if self.valid_from > now:
            return False
        if self.valid_until and self.valid_until < now:
            return False

        # Проверка лимита использований
        if self.max_uses and self.used_count >= self.max_uses:
            return False

        return True

    def calculate_discount(self, original_amount: Decimal) -> Decimal:
        """
        Расчет суммы скидки.

        Args:
            original_amount: Исходная сумма

        Returns:
            Сумма скидки
        """
        if self.type == PromoCodeType.PERCENTAGE:
            return original_amount * Decimal(self.discount_percent) / 100
        elif self.type == PromoCodeType.FIXED:
            return min(self.discount_amount, original_amount)
        else:
            return Decimal(0)

    @classmethod
    def generate_code(cls, length: int = 8) -> str:
        """Генерация случайного промокода."""
        alphabet = string.ascii_uppercase + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(length))

    def __repr__(self) -> str:
        return f"<PromoCode(code={self.code}, type={self.type})>"


class PaymentMethod(BaseModel, TimestampMixin):
    """
    Сохраненные способы оплаты.

    Для рекуррентных платежей.
    """

    __tablename__ = "payment_methods"

    user_id = Column(
        BigInteger,
        ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False,
        comment="ID пользователя"
    )

    provider = Column(
        SQLEnum(PaymentProvider),
        nullable=False,
        comment="Платежный провайдер"
    )

    # Токен/ID способа оплаты у провайдера
    provider_method_id = Column(
        String(255),
        nullable=False,
        comment="ID способа оплаты у провайдера"
    )

    # Маскированные данные для отображения
    card_last4 = Column(
        String(4),
        nullable=True,
        comment="Последние 4 цифры карты"
    )

    card_brand = Column(
        String(50),
        nullable=True,
        comment="Бренд карты (Visa, MasterCard)"
    )

    # Статус
    is_default = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="Способ оплаты по умолчанию"
    )

    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Активен ли способ оплаты"
    )

    expires_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Срок действия карты"
    )

    # Отношения
    user = relationship("User", backref="payment_methods")

    # Ограничения
    __table_args__ = (
        UniqueConstraint('user_id', 'provider', 'provider_method_id',
                         name='uq_user_payment_method'),
        Index('idx_payment_method_default', 'user_id', 'is_default'),
    )

    def __repr__(self) -> str:
        return f"<PaymentMethod(id={self.id}, user_id={self.user_id}, last4={self.card_last4})>"