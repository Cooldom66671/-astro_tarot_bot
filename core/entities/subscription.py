"""
Модуль сущности подписки для Астро-Таро Бота.

Этот модуль содержит бизнес-сущность Subscription для управления
подписками пользователей. Включает:
- Тарифные планы и их характеристики
- Расчет стоимости с учетом скидок
- Управление промокодами
- История платежей
- Логику автопродления

Использование:
    from core.entities import Subscription, PlanFeatures
    from datetime import datetime

    # Создание подписки
    subscription = Subscription(
        id=1,
        user_id=123,
        plan=SubscriptionPlan.PREMIUM,
        started_at=datetime.now()
    )

    # Расчет стоимости с промокодом
    price = subscription.calculate_price(
        period_months=12,
        promo_code="NEWYEAR2025"
    )
"""
import re
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, List, Dict, Any, Tuple
from enum import Enum

from pydantic import BaseModel, Field, validator

from config import (
    logger,
    SubscriptionPlan,
    SubscriptionStatus,
    PaymentStatus,
    Prices,
    Limits,
    Patterns
)
from core.exceptions import (
    ValidationError,
    BusinessLogicError,
    InvalidStateTransitionError
)


# ===== ХАРАКТЕРИСТИКИ ТАРИФНЫХ ПЛАНОВ =====

@dataclass
class PlanFeatures:
    """Характеристики тарифного плана."""

    # Основные параметры
    name: str
    display_name: str
    description: str
    monthly_price: Decimal

    # Лимиты
    daily_spreads_limit: int
    max_partners: int
    max_forecast_days: int

    # Функции
    full_natal_chart: bool = False
    pdf_reports: bool = False
    compatibility_analysis: bool = False
    extended_forecasts: bool = False
    priority_support: bool = False
    custom_spreads: bool = False

    # Дополнительные возможности
    api_access: bool = False
    data_export: bool = False
    remove_ads: bool = True

    def get_features_list(self) -> List[str]:
        """Получить список доступных функций."""
        features = []

        if self.full_natal_chart:
            features.append("✅ Полный разбор натальной карты")
        if self.pdf_reports:
            features.append("📄 PDF-отчеты для скачивания")
        if self.compatibility_analysis:
            features.append("💕 Анализ совместимости")
        if self.extended_forecasts:
            features.append("🔮 Расширенные прогнозы")
        if self.priority_support:
            features.append("⚡ Приоритетная поддержка")
        if self.custom_spreads:
            features.append("🎴 Уникальные расклады Таро")
        if self.api_access:
            features.append("🔌 API доступ")
        if self.data_export:
            features.append("💾 Экспорт данных")

        features.append(f"📊 До {self.daily_spreads_limit} раскладов в день")
        features.append(f"👥 До {self.max_partners} партнеров")

        return features


# Определяем характеристики всех планов
PLAN_FEATURES: Dict[SubscriptionPlan, PlanFeatures] = {
    SubscriptionPlan.FREE: PlanFeatures(
        name="free",
        display_name="Бесплатный",
        description="Базовые возможности для знакомства с ботом",
        monthly_price=Decimal("0"),
        daily_spreads_limit=Limits.MAX_SPREADS_PER_DAY_FREE,
        max_partners=Limits.MAX_PARTNERS_FREE,
        max_forecast_days=Limits.MAX_FORECAST_DAYS_FREE,
        remove_ads=False
    ),

    SubscriptionPlan.BASIC: PlanFeatures(
        name="basic",
        display_name="Базовый",
        description="Основные функции для начинающих",
        monthly_price=Prices.BASIC_MONTHLY,
        daily_spreads_limit=5,
        max_partners=3,
        max_forecast_days=7,
        full_natal_chart=True,
        compatibility_analysis=True
    ),

    SubscriptionPlan.PREMIUM: PlanFeatures(
        name="premium",
        display_name="Премиум",
        description="Расширенные возможности для увлеченных",
        monthly_price=Prices.PREMIUM_MONTHLY,
        daily_spreads_limit=Limits.MAX_SPREADS_PER_DAY_PREMIUM,
        max_partners=Limits.MAX_PARTNERS_PREMIUM,
        max_forecast_days=30,
        full_natal_chart=True,
        pdf_reports=True,
        compatibility_analysis=True,
        extended_forecasts=True,
        custom_spreads=True
    ),

    SubscriptionPlan.VIP: PlanFeatures(
        name="vip",
        display_name="VIP",
        description="Максимальные возможности без ограничений",
        monthly_price=Prices.VIP_MONTHLY,
        daily_spreads_limit=999,  # Практически без лимита
        max_partners=999,
        max_forecast_days=365,
        full_natal_chart=True,
        pdf_reports=True,
        compatibility_analysis=True,
        extended_forecasts=True,
        priority_support=True,
        custom_spreads=True,
        api_access=True,
        data_export=True
    )
}


# ===== ПРОМОКОДЫ =====

class PromoCodeType(str, Enum):
    """Типы промокодов."""
    PERCENTAGE = "percentage"  # Процентная скидка
    FIXED = "fixed"  # Фиксированная скидка
    TRIAL = "trial"  # Пробный период
    UPGRADE = "upgrade"  # Апгрейд плана


@dataclass
class PromoCode:
    """Промокод."""

    code: str
    type: PromoCodeType
    value: Decimal  # Процент или сумма скидки
    description: str

    # Ограничения
    valid_from: datetime
    valid_until: datetime
    max_uses: Optional[int] = None
    used_count: int = 0
    min_amount: Optional[Decimal] = None  # Минимальная сумма заказа
    allowed_plans: Optional[List[SubscriptionPlan]] = None  # Для каких планов

    # Флаги
    is_active: bool = True
    first_time_only: bool = False  # Только для новых пользователей

    def validate_code(self, code: str) -> bool:
        """Проверить формат кода."""
        return bool(re.match(Patterns.PROMO_CODE, code.upper()))

    def is_valid(self) -> bool:
        """Проверить валидность промокода."""
        now = datetime.now()

        # Проверяем активность
        if not self.is_active:
            return False

        # Проверяем даты
        if now < self.valid_from or now > self.valid_until:
            return False

        # Проверяем количество использований
        if self.max_uses and self.used_count >= self.max_uses:
            return False

        return True

    def can_apply_to_plan(self, plan: SubscriptionPlan) -> bool:
        """Можно ли применить к плану."""
        if not self.allowed_plans:
            return True
        return plan in self.allowed_plans

    def calculate_discount(self, amount: Decimal) -> Decimal:
        """Рассчитать скидку."""
        if self.type == PromoCodeType.PERCENTAGE:
            discount = amount * (self.value / 100)
        elif self.type == PromoCodeType.FIXED:
            discount = min(self.value, amount)
        else:
            discount = Decimal("0")

        return discount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


# ===== ИСТОРИЯ ПЛАТЕЖЕЙ =====

@dataclass
class Payment:
    """Информация о платеже."""

    id: str  # ID от платежной системы
    subscription_id: int
    amount: Decimal
    currency: str = "RUB"
    status: PaymentStatus = PaymentStatus.PENDING

    # Детали
    description: str = ""
    payment_method: Optional[str] = None
    promo_code: Optional[str] = None
    discount_amount: Decimal = Decimal("0")

    # Временные метки
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    paid_at: Optional[datetime] = None

    # Данные от платежной системы
    provider_data: Dict[str, Any] = field(default_factory=dict)

    @property
    def final_amount(self) -> Decimal:
        """Итоговая сумма с учетом скидки."""
        return self.amount - self.discount_amount

    @property
    def is_successful(self) -> bool:
        """Успешный платеж."""
        return self.status == PaymentStatus.SUCCEEDED

    @property
    def is_pending(self) -> bool:
        """Ожидает оплаты."""
        return self.status in [PaymentStatus.PENDING, PaymentStatus.PROCESSING]

    def to_receipt_text(self) -> str:
        """Текст чека для пользователя."""
        lines = [
            f"🧾 Чек №{self.id[:8]}",
            f"Дата: {self.created_at.strftime('%d.%m.%Y %H:%M')}",
            f"Описание: {self.description}",
            f"Сумма: {self.amount} {self.currency}"
        ]

        if self.discount_amount > 0:
            lines.append(f"Скидка: -{self.discount_amount} {self.currency}")
            lines.append(f"Итого: {self.final_amount} {self.currency}")

        if self.payment_method:
            lines.append(f"Способ оплаты: {self.payment_method}")

        lines.append(f"Статус: {self._get_status_text()}")

        return "\n".join(lines)

    def _get_status_text(self) -> str:
        """Текст статуса для пользователя."""
        status_texts = {
            PaymentStatus.PENDING: "⏳ Ожидает оплаты",
            PaymentStatus.PROCESSING: "⏳ Обрабатывается",
            PaymentStatus.SUCCEEDED: "✅ Оплачено",
            PaymentStatus.FAILED: "❌ Ошибка оплаты",
            PaymentStatus.CANCELLED: "❌ Отменено",
            PaymentStatus.REFUNDED: "💸 Возвращено"
        }
        return status_texts.get(self.status, "Неизвестно")


# ===== ОСНОВНАЯ СУЩНОСТЬ ПОДПИСКИ =====

@dataclass
class Subscription:
    """
    Сущность подписки пользователя.

    Управляет всей логикой подписок, платежей и тарифных планов.
    """

    # Основные поля
    id: int
    user_id: int
    plan: SubscriptionPlan = SubscriptionPlan.FREE
    status: SubscriptionStatus = SubscriptionStatus.FREE

    # Временные метки
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None

    # Автопродление
    auto_renewal: bool = False
    next_payment_date: Optional[date] = None
    payment_method_id: Optional[str] = None  # ID сохраненного способа оплаты

    # История
    payments: List[Payment] = field(default_factory=list)
    status_history: List[Tuple[SubscriptionStatus, datetime]] = field(default_factory=list)

    # Промокоды
    applied_promo_codes: List[str] = field(default_factory=list)

    def __post_init__(self):
        """Инициализация после создания."""
        logger.debug(f"Создана подписка: id={self.id}, user_id={self.user_id}, plan={self.plan}")

        # Добавляем начальный статус в историю
        if not self.status_history:
            self.status_history.append((self.status, self.created_at))

    # ===== СВОЙСТВА =====

    @property
    def features(self) -> PlanFeatures:
        """Характеристики текущего плана."""
        return PLAN_FEATURES[self.plan]

    @property
    def is_active(self) -> bool:
        """Активна ли подписка."""
        if self.status != SubscriptionStatus.ACTIVE:
            return False

        if self.expires_at and datetime.now() > self.expires_at:
            return False

        return True

    @property
    def is_free(self) -> bool:
        """Бесплатный план."""
        return self.plan == SubscriptionPlan.FREE

    @property
    def days_left(self) -> Optional[int]:
        """Дней до окончания."""
        if not self.expires_at or not self.is_active:
            return None

        delta = self.expires_at - datetime.now()
        return max(0, delta.days)

    @property
    def is_expiring_soon(self) -> bool:
        """Скоро истекает (менее 3 дней)."""
        days = self.days_left
        return days is not None and 0 < days <= 3

    @property
    def total_spent(self) -> Decimal:
        """Общая потраченная сумма."""
        return sum(
            p.final_amount for p in self.payments
            if p.is_successful
        )

    @property
    def successful_payments_count(self) -> int:
        """Количество успешных платежей."""
        return sum(1 for p in self.payments if p.is_successful)

    @property
    def has_saved_payment_method(self) -> bool:
        """Есть ли сохраненный способ оплаты."""
        return self.payment_method_id is not None

    # ===== МЕТОДЫ РАСЧЕТА СТОИМОСТИ =====

    def calculate_price(
            self,
            plan: Optional[SubscriptionPlan] = None,
            period_months: int = 1,
            promo_code: Optional[PromoCode] = None
    ) -> Tuple[Decimal, Decimal]:
        """
        Рассчитать стоимость подписки.

        Args:
            plan: План подписки (если None - текущий)
            period_months: Период в месяцах
            promo_code: Промокод

        Returns:
            Tuple[цена_без_скидки, цена_со_скидкой]
        """
        if plan is None:
            plan = self.plan

        # Базовая цена
        features = PLAN_FEATURES[plan]
        base_price = features.monthly_price * period_months

        # Скидка за длительный период
        if period_months >= 12:
            yearly_discount = base_price * Prices.ANNUAL_DISCOUNT
            base_price -= yearly_discount

        # Промокод
        discount = Decimal("0")
        if promo_code and promo_code.is_valid():
            if promo_code.can_apply_to_plan(plan):
                if promo_code.min_amount is None or base_price >= promo_code.min_amount:
                    discount = promo_code.calculate_discount(base_price)

        final_price = base_price - discount

        # Округляем до копеек
        base_price = base_price.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        final_price = final_price.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        return base_price, final_price

    # ===== МЕТОДЫ УПРАВЛЕНИЯ СТАТУСОМ =====

    def can_transition_to(self, new_status: SubscriptionStatus) -> bool:
        """Можно ли перейти в новый статус."""
        allowed_transitions = {
            SubscriptionStatus.FREE: [
                SubscriptionStatus.ACTIVE
            ],
            SubscriptionStatus.ACTIVE: [
                SubscriptionStatus.EXPIRED,
                SubscriptionStatus.CANCELLED,
                SubscriptionStatus.SUSPENDED
            ],
            SubscriptionStatus.EXPIRED: [
                SubscriptionStatus.ACTIVE
            ],
            SubscriptionStatus.CANCELLED: [
                SubscriptionStatus.ACTIVE
            ],
            SubscriptionStatus.SUSPENDED: [
                SubscriptionStatus.ACTIVE,
                SubscriptionStatus.CANCELLED
            ]
        }

        allowed = allowed_transitions.get(self.status, [])
        return new_status in allowed

    def change_status(self, new_status: SubscriptionStatus) -> None:
        """Изменить статус подписки."""
        if not self.can_transition_to(new_status):
            raise InvalidStateTransitionError(
                entity_type="Subscription",
                current_state=self.status.value,
                target_state=new_status.value,
                allowed_states=[s.value for s in self._get_allowed_statuses()]
            )

        old_status = self.status
        self.status = new_status
        self.status_history.append((new_status, datetime.now()))

        logger.info(
            f"Подписка {self.id} изменила статус: {old_status.value} -> {new_status.value}"
        )

        # Дополнительные действия при смене статуса
        if new_status == SubscriptionStatus.CANCELLED:
            self.cancelled_at = datetime.now()
            self.auto_renewal = False

    def _get_allowed_statuses(self) -> List[SubscriptionStatus]:
        """Получить разрешенные статусы."""
        # Эта логика дублирует can_transition_to, но нужна для сообщения об ошибке
        transitions_map = {
            SubscriptionStatus.FREE: [SubscriptionStatus.ACTIVE],
            SubscriptionStatus.ACTIVE: [
                SubscriptionStatus.EXPIRED,
                SubscriptionStatus.CANCELLED,
                SubscriptionStatus.SUSPENDED
            ],
            SubscriptionStatus.EXPIRED: [SubscriptionStatus.ACTIVE],
            SubscriptionStatus.CANCELLED: [SubscriptionStatus.ACTIVE],
            SubscriptionStatus.SUSPENDED: [
                SubscriptionStatus.ACTIVE,
                SubscriptionStatus.CANCELLED
            ]
        }
        return transitions_map.get(self.status, [])

    # ===== МЕТОДЫ АКТИВАЦИИ И ПРОДЛЕНИЯ =====

    def activate(
            self,
            plan: SubscriptionPlan,
            period_months: int = 1,
            payment: Optional[Payment] = None
    ) -> None:
        """
        Активировать подписку.

        Args:
            plan: Тарифный план
            period_months: Период в месяцах
            payment: Информация о платеже
        """
        self.plan = plan
        self.started_at = datetime.now()
        self.expires_at = self.started_at + timedelta(days=30 * period_months)
        self.change_status(SubscriptionStatus.ACTIVE)

        if payment:
            self.payments.append(payment)

        logger.info(
            f"Подписка {self.id} активирована: план={plan.value}, "
            f"период={period_months}мес, истекает={self.expires_at}"
        )

    def extend(self, period_months: int = 1, payment: Optional[Payment] = None) -> None:
        """Продлить подписку."""
        if not self.expires_at:
            raise BusinessLogicError("Невозможно продлить подписку без даты окончания")

        # Продлеваем от текущей даты окончания или от сегодня, если уже истекла
        base_date = max(self.expires_at, datetime.now())
        self.expires_at = base_date + timedelta(days=30 * period_months)

        if self.status == SubscriptionStatus.EXPIRED:
            self.change_status(SubscriptionStatus.ACTIVE)

        if payment:
            self.payments.append(payment)

        logger.info(f"Подписка {self.id} продлена до {self.expires_at}")

    def cancel(self, immediate: bool = False) -> None:
        """
        Отменить подписку.

        Args:
            immediate: Отменить немедленно или в конце периода
        """
        self.auto_renewal = False

        if immediate:
            self.change_status(SubscriptionStatus.CANCELLED)
            self.expires_at = datetime.now()
        else:
            # Подписка будет активна до конца оплаченного периода
            logger.info(f"Подписка {self.id} будет отменена {self.expires_at}")

    def suspend(self, reason: str) -> None:
        """Приостановить подписку."""
        self.change_status(SubscriptionStatus.SUSPENDED)
        logger.warning(f"Подписка {self.id} приостановлена. Причина: {reason}")

    # ===== МЕТОДЫ ПРОВЕРКИ ДОСТУПА =====

    def has_feature(self, feature: str) -> bool:
        """Проверить доступность функции."""
        if not self.is_active:
            return False

        features_dict = {
            "full_natal_chart": self.features.full_natal_chart,
            "pdf_reports": self.features.pdf_reports,
            "compatibility_analysis": self.features.compatibility_analysis,
            "extended_forecasts": self.features.extended_forecasts,
            "priority_support": self.features.priority_support,
            "custom_spreads": self.features.custom_spreads,
            "api_access": self.features.api_access,
            "data_export": self.features.data_export,
        }

        return features_dict.get(feature, False)

    def check_daily_limit(self, current_count: int) -> bool:
        """Проверить дневной лимит."""
        return current_count < self.features.daily_spreads_limit

    def check_partners_limit(self, current_count: int) -> bool:
        """Проверить лимит партнеров."""
        return current_count < self.features.max_partners

    # ===== МЕТОДЫ РАБОТЫ С ПЛАТЕЖАМИ =====

    def add_payment(self, payment: Payment) -> None:
        """Добавить платеж."""
        self.payments.append(payment)
        logger.info(f"Добавлен платеж {payment.id} к подписке {self.id}")

    def get_last_payment(self) -> Optional[Payment]:
        """Получить последний платеж."""
        if not self.payments:
            return None
        return sorted(self.payments, key=lambda p: p.created_at)[-1]

    def get_successful_payments(self) -> List[Payment]:
        """Получить успешные платежи."""
        return [p for p in self.payments if p.is_successful]

    # ===== СЕРИАЛИЗАЦИЯ =====

    def to_dict(self) -> Dict[str, Any]:
        """Преобразовать в словарь."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "plan": self.plan.value,
            "status": self.status.value,
            "is_active": self.is_active,
            "features": self.features.get_features_list(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "days_left": self.days_left,
            "auto_renewal": self.auto_renewal,
            "total_spent": str(self.total_spent),
            "payments_count": self.successful_payments_count,
        }

    def __str__(self) -> str:
        """Строковое представление."""
        return f"Subscription(id={self.id}, user={self.user_id}, plan={self.plan.value}, status={self.status.value})"


# Экспорт
__all__ = [
    "Subscription",
    "PlanFeatures",
    "PLAN_FEATURES",
    "PromoCode",
    "PromoCodeType",
    "Payment",
]