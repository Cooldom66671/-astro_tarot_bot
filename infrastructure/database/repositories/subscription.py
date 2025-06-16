"""
Репозиторий для работы с подписками и платежами.

Этот модуль содержит:
- Управление подписками пользователей
- Обработку платежей и транзакций
- Работу с промокодами и скидками
- Автопродление подписок
- Управление способами оплаты
- Статистику и отчеты по платежам
"""

from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, date, timedelta
from decimal import Decimal
import secrets
import string

from sqlalchemy import select, func, and_, or_, update, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload

from config import logger, SubscriptionTier, PaymentStatus, PaymentProvider
from core.interfaces.repository import (
    ISubscriptionRepository, QueryOptions, Pagination, Page
)
from infrastructure.database.models import (
    User, Subscription, Payment, PromoCode, SubscriptionPlan,
    PaymentMethod, PromoCodeType
)
from infrastructure.database.repositories.base import BaseRepository
from core.exceptions import (
    EntityNotFoundError, ValidationError,
    InvalidStateTransitionError, PaymentError
)


class SubscriptionRepository(BaseRepository[Subscription], ISubscriptionRepository):
    """
    Репозиторий для работы с подписками и платежами.

    Управляет жизненным циклом подписок и платежными операциями.
    """

    def __init__(self, session: AsyncSession):
        """
        Инициализация репозитория подписок.

        Args:
            session: Сессия БД
        """
        super().__init__(session, Subscription)

    # Работа с тарифными планами

    async def get_subscription_plans(
            self,
            active_only: bool = True
    ) -> List[SubscriptionPlan]:
        """
        Получение списка тарифных планов.

        Args:
            active_only: Только активные планы

        Returns:
            Список тарифных планов
        """
        query = select(SubscriptionPlan)

        if active_only:
            query = query.where(SubscriptionPlan.is_active == True)

        query = query.order_by(SubscriptionPlan.sort_order, SubscriptionPlan.monthly_price)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_plan_by_tier(
            self,
            tier: SubscriptionTier
    ) -> Optional[SubscriptionPlan]:
        """
        Получение плана по уровню подписки.

        Args:
            tier: Уровень подписки

        Returns:
            Найденный план или None
        """
        query = select(SubscriptionPlan).where(
            and_(
                SubscriptionPlan.tier == tier,
                SubscriptionPlan.is_active == True
            )
        )

        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    # Управление подписками

    async def get_user_active_subscription(
            self,
            user_id: int
    ) -> Optional[Subscription]:
        """
        Получение активной подписки пользователя.

        Args:
            user_id: ID пользователя

        Returns:
            Активная подписка или None
        """
        query = select(Subscription).where(
            and_(
                Subscription.user_id == user_id,
                Subscription.expires_at > datetime.utcnow(),
                Subscription.is_cancelled == False
            )
        ).options(
            selectinload(Subscription.payment),
            selectinload(Subscription.promo_code)
        ).order_by(Subscription.expires_at.desc())

        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def create_subscription(
            self,
            user_id: int,
            tier: SubscriptionTier,
            period_days: int,
            payment_id: Optional[int] = None,
            promo_code_id: Optional[int] = None,
            is_trial: bool = False,
            is_auto_renew: bool = False
    ) -> Subscription:
        """
        Создание новой подписки.

        Args:
            user_id: ID пользователя
            tier: Уровень подписки
            period_days: Период в днях
            payment_id: ID платежа
            promo_code_id: ID промокода
            is_trial: Пробная подписка
            is_auto_renew: Автопродление

        Returns:
            Созданная подписка
        """
        # Проверяем существующую активную подписку
        existing = await self.get_user_active_subscription(user_id)
        if existing:
            # Отменяем старую подписку
            existing.is_cancelled = True
            existing.cancelled_at = datetime.utcnow()
            logger.info(f"Отменена существующая подписка {existing.id}")

        # Создаем новую подписку
        started_at = datetime.utcnow()
        expires_at = started_at + timedelta(days=period_days)

        subscription = await self.create(
            user_id=user_id,
            tier=tier,
            started_at=started_at,
            expires_at=expires_at,
            is_auto_renew=is_auto_renew,
            next_payment_date=expires_at if is_auto_renew else None,
            payment_id=payment_id,
            promo_code_id=promo_code_id,
            is_trial=is_trial
        )

        # Обновляем пользователя
        user_update = update(User).where(User.id == user_id).values(
            subscription_tier=tier,
            subscription_expires_at=expires_at
        )
        await self.session.execute(user_update)

        logger.info(f"Создана подписка {tier} для пользователя {user_id} на {period_days} дней")

        return subscription

    async def extend_subscription(
            self,
            subscription_id: int,
            additional_days: int,
            payment_id: Optional[int] = None
    ) -> Subscription:
        """
        Продление существующей подписки.

        Args:
            subscription_id: ID подписки
            additional_days: Дополнительные дни
            payment_id: ID платежа за продление

        Returns:
            Продленная подписка
        """
        subscription = await self.get_by_id_or_fail(subscription_id)

        # Новая дата окончания
        new_expires_at = subscription.expires_at + timedelta(days=additional_days)
        subscription.expires_at = new_expires_at

        if subscription.is_auto_renew:
            subscription.next_payment_date = new_expires_at

        # Обновляем платеж если указан
        if payment_id:
            subscription.payment_id = payment_id

        # Обновляем пользователя
        user_update = update(User).where(
            User.id == subscription.user_id
        ).values(
            subscription_expires_at=new_expires_at
        )
        await self.session.execute(user_update)

        await self.session.flush()
        logger.info(f"Подписка {subscription_id} продлена на {additional_days} дней")

        return subscription

    async def cancel_subscription(
            self,
            subscription_id: int,
            immediate: bool = False,
            reason: Optional[str] = None
    ) -> Subscription:
        """
        Отмена подписки.

        Args:
            subscription_id: ID подписки
            immediate: Немедленная отмена
            reason: Причина отмены

        Returns:
            Отмененная подписка
        """
        subscription = await self.get_by_id_or_fail(subscription_id)

        if subscription.is_cancelled:
            raise InvalidStateTransitionError(
                "Подписка уже отменена",
                current_state="cancelled"
            )

        subscription.is_cancelled = True
        subscription.cancelled_at = datetime.utcnow()
        subscription.is_auto_renew = False
        subscription.next_payment_date = None

        if immediate:
            subscription.expires_at = datetime.utcnow()

            # Обновляем пользователя на FREE
            user_update = update(User).where(
                User.id == subscription.user_id
            ).values(
                subscription_tier=SubscriptionTier.FREE,
                subscription_expires_at=None
            )
            await self.session.execute(user_update)

        await self.session.flush()
        logger.info(f"Подписка {subscription_id} отменена{' немедленно' if immediate else ''}")

        return subscription

    async def toggle_auto_renewal(
            self,
            subscription_id: int,
            enable: bool
    ) -> Subscription:
        """
        Включение/отключение автопродления.

        Args:
            subscription_id: ID подписки
            enable: Включить автопродление

        Returns:
            Обновленная подписка
        """
        subscription = await self.get_by_id_or_fail(subscription_id)

        subscription.is_auto_renew = enable

        if enable:
            subscription.next_payment_date = subscription.expires_at
        else:
            subscription.next_payment_date = None

        await self.session.flush()
        logger.info(f"Автопродление подписки {subscription_id} {'включено' if enable else 'отключено'}")

        return subscription

    # Работа с платежами

    async def create_payment(
            self,
            user_id: int,
            amount: Decimal,
            provider: PaymentProvider,
            subscription_tier: SubscriptionTier,
            subscription_period_days: int,
            payment_method_id: Optional[int] = None,
            metadata: Optional[Dict[str, Any]] = None
    ) -> Payment:
        """
        Создание нового платежа.

        Args:
            user_id: ID пользователя
            amount: Сумма платежа
            provider: Платежный провайдер
            subscription_tier: Оплачиваемый тариф
            subscription_period_days: Период подписки
            payment_method_id: ID способа оплаты
            metadata: Дополнительные данные

        Returns:
            Созданный платеж
        """
        payment = Payment(
            user_id=user_id,
            amount=amount,
            currency="RUB",
            status=PaymentStatus.PENDING,
            provider=provider,
            subscription_tier=subscription_tier,
            subscription_period_days=subscription_period_days,
            payment_method_id=payment_method_id,
            metadata=metadata or {}
        )

        self.session.add(payment)
        await self.session.flush()

        logger.info(
            f"Создан платеж {payment.uuid} на {amount} RUB "
            f"для пользователя {user_id}"
        )

        return payment

    async def update_payment_status(
            self,
            payment_id: int,
            status: PaymentStatus,
            provider_payment_id: Optional[str] = None,
            provider_order_id: Optional[str] = None,
            error_message: Optional[str] = None,
            receipt_url: Optional[str] = None
    ) -> Payment:
        """
        Обновление статуса платежа.

        Args:
            payment_id: ID платежа
            status: Новый статус
            provider_payment_id: ID у провайдера
            provider_order_id: ID заказа у провайдера
            error_message: Сообщение об ошибке
            receipt_url: Ссылка на чек

        Returns:
            Обновленный платеж
        """
        payment = await self._get_payment_by_id(payment_id)

        # Проверка валидности перехода статуса
        if payment.status == PaymentStatus.SUCCEEDED:
            raise InvalidStateTransitionError(
                "Нельзя изменить статус успешного платежа",
                current_state=payment.status.value
            )

        payment.status = status

        if provider_payment_id:
            payment.provider_payment_id = provider_payment_id
        if provider_order_id:
            payment.provider_order_id = provider_order_id
        if receipt_url:
            payment.receipt_url = receipt_url

        # Обработка по статусу
        if status == PaymentStatus.SUCCEEDED:
            payment.paid_at = datetime.utcnow()

            # Создаем/продлеваем подписку
            await self._process_successful_payment(payment)

        elif status == PaymentStatus.FAILED:
            payment.failed_at = datetime.utcnow()
            payment.error_message = error_message

        elif status == PaymentStatus.CANCELLED:
            payment.error_message = "Платеж отменен пользователем"

        await self.session.flush()
        logger.info(f"Статус платежа {payment.uuid} изменен на {status.value}")

        return payment

    async def _get_payment_by_id(self, payment_id: int) -> Payment:
        """Получение платежа по ID с проверкой."""
        query = select(Payment).where(Payment.id == payment_id)
        result = await self.session.execute(query)
        payment = result.scalar_one_or_none()

        if not payment:
            raise EntityNotFoundError(
                f"Платеж {payment_id} не найден",
                entity_type="Payment",
                entity_id=payment_id
            )

        return payment

    async def _process_successful_payment(self, payment: Payment) -> None:
        """
        Обработка успешного платежа.

        Args:
            payment: Успешный платеж
        """
        # Проверяем существующую подписку
        existing = await self.get_user_active_subscription(payment.user_id)

        if existing and existing.tier == payment.subscription_tier:
            # Продлеваем существующую
            await self.extend_subscription(
                existing.id,
                payment.subscription_period_days,
                payment.id
            )
        else:
            # Создаем новую
            await self.create_subscription(
                user_id=payment.user_id,
                tier=payment.subscription_tier,
                period_days=payment.subscription_period_days,
                payment_id=payment.id,
                is_auto_renew=payment.payment_method_id is not None
            )

    async def get_payment_by_provider_id(
            self,
            provider: PaymentProvider,
            provider_payment_id: str
    ) -> Optional[Payment]:
        """
        Получение платежа по ID провайдера.

        Args:
            provider: Платежный провайдер
            provider_payment_id: ID у провайдера

        Returns:
            Найденный платеж или None
        """
        query = select(Payment).where(
            and_(
                Payment.provider == provider,
                Payment.provider_payment_id == provider_payment_id
            )
        )

        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_user_payments(
            self,
            user_id: int,
            status: Optional[PaymentStatus] = None,
            pagination: Optional[Pagination] = None
    ) -> List[Payment]:
        """
        Получение платежей пользователя.

        Args:
            user_id: ID пользователя
            status: Фильтр по статусу
            pagination: Параметры пагинации

        Returns:
            Список платежей
        """
        query = select(Payment).where(Payment.user_id == user_id)

        if status:
            query = query.where(Payment.status == status)

        query = query.order_by(Payment.created_at.desc())

        if pagination:
            offset = (pagination.page - 1) * pagination.size
            query = query.offset(offset).limit(pagination.size)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    # Работа с промокодами

    async def get_promo_code(self, code: str) -> Optional[PromoCode]:
        """
        Получение промокода по коду.

        Args:
            code: Код промокода

        Returns:
            Найденный промокод или None
        """
        query = select(PromoCode).where(
            PromoCode.code == code.upper().strip()
        )

        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def validate_promo_code(
            self,
            code: str,
            user_id: int,
            subscription_tier: SubscriptionTier,
            amount: Decimal
    ) -> Tuple[bool, Optional[str]]:
        """
        Валидация промокода.

        Args:
            code: Код промокода
            user_id: ID пользователя
            subscription_tier: Тариф для применения
            amount: Сумма заказа

        Returns:
            Кортеж (валиден, сообщение_об_ошибке)
        """
        promo = await self.get_promo_code(code)

        if not promo:
            return False, "Промокод не найден"

        if not promo.is_active:
            return False, "Промокод неактивен"

        # Проверка периода действия
        now = datetime.utcnow()
        if promo.valid_from > now:
            return False, "Промокод еще не активен"

        if promo.valid_until and promo.valid_until < now:
            return False, "Промокод истек"

        # Проверка лимита использований
        if promo.max_uses and promo.used_count >= promo.max_uses:
            return False, "Промокод исчерпан"

        # Проверка использований пользователем
        user_uses = await self._count_user_promo_uses(user_id, promo.id)
        if user_uses >= promo.max_uses_per_user:
            return False, f"Вы уже использовали этот промокод {user_uses} раз(а)"

        # Проверка применимости к тарифу
        if promo.applicable_tiers:
            if subscription_tier.value not in promo.applicable_tiers:
                return False, "Промокод не применим к этому тарифу"

        # Проверка минимальной суммы
        if promo.min_amount and amount < promo.min_amount:
            return False, f"Минимальная сумма для промокода: {promo.min_amount} RUB"

        return True, None

    async def _count_user_promo_uses(
            self,
            user_id: int,
            promo_code_id: int
    ) -> int:
        """Подсчет использований промокода пользователем."""
        query = select(func.count(Payment.id)).join(
            Subscription,
            Payment.id == Subscription.payment_id
        ).where(
            and_(
                Payment.user_id == user_id,
                Subscription.promo_code_id == promo_code_id
            )
        )

        result = await self.session.execute(query)
        return result.scalar() or 0

    async def apply_promo_code(
            self,
            promo_code_id: int,
            original_amount: Decimal
    ) -> Tuple[Decimal, Decimal]:
        """
        Применение промокода к сумме.

        Args:
            promo_code_id: ID промокода
            original_amount: Исходная сумма

        Returns:
            Кортеж (скидка, финальная_сумма)
        """
        promo = await self.get_by_id_or_fail(promo_code_id)

        discount = Decimal(0)

        if promo.type == PromoCodeType.PERCENTAGE:
            discount = original_amount * Decimal(promo.discount_percent) / 100
        elif promo.type == PromoCodeType.FIXED:
            discount = min(promo.discount_amount, original_amount)

        final_amount = max(original_amount - discount, Decimal(0))

        # Увеличиваем счетчик использований
        promo.used_count += 1

        logger.info(f"Применен промокод {promo.code}: скидка {discount} RUB")

        return discount, final_amount

    async def create_promo_code(
            self,
            code: Optional[str] = None,
            type: PromoCodeType = PromoCodeType.PERCENTAGE,
            discount_percent: Optional[int] = None,
            discount_amount: Optional[Decimal] = None,
            trial_days: Optional[int] = None,
            max_uses: Optional[int] = None,
            valid_days: int = 30,
            applicable_tiers: Optional[List[str]] = None,
            description: Optional[str] = None
    ) -> PromoCode:
        """
        Создание нового промокода.

        Args:
            code: Код (генерируется если не указан)
            type: Тип промокода
            discount_percent: Процент скидки
            discount_amount: Сумма скидки
            trial_days: Дни триала
            max_uses: Максимум использований
            valid_days: Срок действия в днях
            applicable_tiers: Применимые тарифы
            description: Описание

        Returns:
            Созданный промокод
        """
        if not code:
            code = PromoCode.generate_code()

        valid_until = datetime.utcnow() + timedelta(days=valid_days)

        promo = PromoCode(
            code=code.upper(),
            type=type,
            discount_percent=discount_percent,
            discount_amount=discount_amount,
            trial_days=trial_days,
            max_uses=max_uses,
            valid_until=valid_until,
            applicable_tiers=applicable_tiers,
            description=description
        )

        self.session.add(promo)
        await self.session.flush()

        logger.info(f"Создан промокод {promo.code} типа {type.value}")

        return promo

    # Управление способами оплаты

    async def save_payment_method(
            self,
            user_id: int,
            provider: PaymentProvider,
            provider_method_id: str,
            card_last4: Optional[str] = None,
            card_brand: Optional[str] = None,
            is_default: bool = False
    ) -> PaymentMethod:
        """
        Сохранение способа оплаты.

        Args:
            user_id: ID пользователя
            provider: Платежный провайдер
            provider_method_id: ID у провайдера
            card_last4: Последние 4 цифры карты
            card_brand: Бренд карты
            is_default: Сделать основным

        Returns:
            Сохраненный способ оплаты
        """
        # Проверяем существование
        existing = await self._get_payment_method(
            user_id, provider, provider_method_id
        )

        if existing:
            # Обновляем существующий
            existing.is_active = True
            if is_default:
                await self._set_default_payment_method(user_id, existing.id)
            return existing

        # Создаем новый
        payment_method = PaymentMethod(
            user_id=user_id,
            provider=provider,
            provider_method_id=provider_method_id,
            card_last4=card_last4,
            card_brand=card_brand,
            is_default=is_default
        )

        self.session.add(payment_method)

        if is_default:
            await self._set_default_payment_method(user_id, payment_method.id)

        await self.session.flush()
        logger.info(f"Сохранен способ оплаты для пользователя {user_id}")

        return payment_method

    async def _get_payment_method(
            self,
            user_id: int,
            provider: PaymentProvider,
            provider_method_id: str
    ) -> Optional[PaymentMethod]:
        """Получение способа оплаты по уникальным полям."""
        query = select(PaymentMethod).where(
            and_(
                PaymentMethod.user_id == user_id,
                PaymentMethod.provider == provider,
                PaymentMethod.provider_method_id == provider_method_id
            )
        )

        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def _set_default_payment_method(
            self,
            user_id: int,
            method_id: int
    ) -> None:
        """Установка способа оплаты по умолчанию."""
        # Сбрасываем текущий default
        reset_query = update(PaymentMethod).where(
            and_(
                PaymentMethod.user_id == user_id,
                PaymentMethod.id != method_id
            )
        ).values(is_default=False)

        await self.session.execute(reset_query)

    async def get_user_payment_methods(
            self,
            user_id: int,
            active_only: bool = True
    ) -> List[PaymentMethod]:
        """
        Получение способов оплаты пользователя.

        Args:
            user_id: ID пользователя
            active_only: Только активные

        Returns:
            Список способов оплаты
        """
        query = select(PaymentMethod).where(
            PaymentMethod.user_id == user_id
        )

        if active_only:
            query = query.where(PaymentMethod.is_active == True)

        query = query.order_by(
            PaymentMethod.is_default.desc(),
            PaymentMethod.created_at.desc()
        )

        result = await self.session.execute(query)
        return list(result.scalars().all())

    # Статистика

    async def get_revenue_statistics(
            self,
            start_date: Optional[date] = None,
            end_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """
        Статистика по доходам.

        Args:
            start_date: Начальная дата
            end_date: Конечная дата

        Returns:
            Словарь со статистикой
        """
        # Базовый запрос для успешных платежей
        base_query = select(Payment).where(
            Payment.status == PaymentStatus.SUCCEEDED
        )

        if start_date:
            base_query = base_query.where(Payment.paid_at >= start_date)
        if end_date:
            base_query = base_query.where(Payment.paid_at <= end_date)

        # Общая сумма
        total_query = select(func.sum(Payment.amount)).select_from(
            base_query.subquery()
        )
        total_result = await self.session.execute(total_query)
        total_revenue = total_result.scalar() or Decimal(0)

        # По тарифам
        by_tier_query = select(
            Payment.subscription_tier,
            func.count(Payment.id),
            func.sum(Payment.amount)
        ).where(
            Payment.status == PaymentStatus.SUCCEEDED
        ).group_by(Payment.subscription_tier)

        if start_date:
            by_tier_query = by_tier_query.where(Payment.paid_at >= start_date)
        if end_date:
            by_tier_query = by_tier_query.where(Payment.paid_at <= end_date)

        by_tier_result = await self.session.execute(by_tier_query)

        revenue_by_tier = {}
        for tier, count, amount in by_tier_result:
            revenue_by_tier[tier.value] = {
                "count": count,
                "amount": float(amount or 0)
            }

        # Количество активных подписок
        active_subs_query = select(
            Subscription.tier,
            func.count(Subscription.id)
        ).where(
            and_(
                Subscription.expires_at > datetime.utcnow(),
                Subscription.is_cancelled == False
            )
        ).group_by(Subscription.tier)

        active_subs_result = await self.session.execute(active_subs_query)

        active_subscriptions = {}
        for tier, count in active_subs_result:
            active_subscriptions[tier.value] = count

        return {
            "total_revenue": float(total_revenue),
            "revenue_by_tier": revenue_by_tier,
            "active_subscriptions": active_subscriptions,
            "period": {
                "start": start_date.isoformat() if start_date else None,
                "end": end_date.isoformat() if end_date else None
            }
        }

    async def get_expiring_subscriptions(
            self,
            days_ahead: int = 3
    ) -> List[Subscription]:
        """
        Получение подписок, истекающих в ближайшие дни.

        Args:
            days_ahead: Дней вперед

        Returns:
            Список истекающих подписок
        """
        expiry_date = datetime.utcnow() + timedelta(days=days_ahead)

        query = select(Subscription).where(
            and_(
                Subscription.expires_at <= expiry_date,
                Subscription.expires_at > datetime.utcnow(),
                Subscription.is_cancelled == False,
                Subscription.is_auto_renew == False
            )
        ).options(
            selectinload(Subscription.user)
        )

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_subscriptions_for_renewal(self) -> List[Subscription]:
        """
        Получение подписок для автопродления.

        Returns:
            Список подписок для продления
        """
        query = select(Subscription).where(
            and_(
                Subscription.is_auto_renew == True,
                Subscription.is_cancelled == False,
                Subscription.next_payment_date <= datetime.utcnow()
            )
        ).options(
            selectinload(Subscription.user)
        )

        result = await self.session.execute(query)
        return list(result.scalars().all())