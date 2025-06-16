"""
Модуль клавиатур для управления подпиской.

Этот модуль содержит:
- Выбор тарифных планов
- Способы оплаты
- Управление автопродлением
- Ввод и активация промокодов
- История платежей
- Управление платежными методами

Автор: AI Assistant
Дата создания: 2024-12-30
"""

import logging
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum

from aiogram.types import InlineKeyboardMarkup
from aiogram.filters.callback_data import CallbackData

from .base import (
    InlineKeyboard, PaginatedKeyboard,
    ButtonConfig, ButtonStyle
)

# Настройка логирования
logger = logging.getLogger(__name__)


class SubscriptionPlan(Enum):
    """Тарифные планы."""
    FREE = "free"
    BASIC = "basic"
    PREMIUM = "premium"
    VIP = "vip"


class PaymentProvider(Enum):
    """Платежные провайдеры."""
    YOOKASSA = "yookassa"
    TINKOFF = "tinkoff"
    SBERBANK = "sberbank"
    CRYPTO = "crypto"
    STARS = "stars"  # Telegram Stars


class PaymentPeriod(Enum):
    """Периоды оплаты."""
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"


# Callback Data классы
class SubscriptionCallbackData(CallbackData, prefix="sub"):
    """Основной callback для подписки."""
    action: str
    plan: Optional[str] = None
    period: Optional[str] = None
    value: Optional[str] = None


class PaymentCallbackData(CallbackData, prefix="pay"):
    """Callback для платежей."""
    action: str  # select_method, confirm, cancel
    provider: Optional[str] = None
    amount: Optional[str] = None
    payment_id: Optional[str] = None


class PromoCallbackData(CallbackData, prefix="promo"):
    """Callback для промокодов."""
    action: str  # apply, cancel
    code: Optional[str] = None


class AutoRenewalCallbackData(CallbackData, prefix="renewal"):
    """Callback для автопродления."""
    action: str  # enable, disable, change_method
    value: Optional[bool] = None


class SubscriptionPlansKeyboard(InlineKeyboard):
    """Клавиатура выбора тарифного плана."""

    # Информация о тарифах
    PLAN_INFO = {
        SubscriptionPlan.FREE: {
            "name": "Бесплатный",
            "emoji": "🆓",
            "features": [
                "1 карта дня",
                "3 простых расклада в день",
                "Общий гороскоп",
                "Базовая поддержка"
            ],
            "limits": {
                "daily_cards": 1,
                "daily_spreads": 3,
                "spread_types": ["one_card", "three_cards"]
            },
            "prices": {
                PaymentPeriod.MONTHLY: Decimal("0"),
                PaymentPeriod.QUARTERLY: Decimal("0"),
                PaymentPeriod.YEARLY: Decimal("0")
            }
        },
        SubscriptionPlan.BASIC: {
            "name": "Базовый",
            "emoji": "🥉",
            "features": [
                "Неограниченные карты дня",
                "10 раскладов в день",
                "Классические расклады",
                "Персональный гороскоп",
                "История раскладов"
            ],
            "limits": {
                "daily_cards": -1,  # Неограниченно
                "daily_spreads": 10,
                "spread_types": ["one_card", "three_cards", "celtic_cross", "relationship", "career"]
            },
            "prices": {
                PaymentPeriod.MONTHLY: Decimal("299"),
                PaymentPeriod.QUARTERLY: Decimal("799"),  # Скидка ~11%
                PaymentPeriod.YEARLY: Decimal("2990")  # Скидка ~17%
            }
        },
        SubscriptionPlan.PREMIUM: {
            "name": "Премиум",
            "emoji": "🥈",
            "features": [
                "Все возможности Базового +",
                "Неограниченные расклады",
                "Эксклюзивные расклады",
                "Натальная карта",
                "Транзиты и прогрессии",
                "Лунный календарь",
                "Приоритетная поддержка"
            ],
            "limits": {
                "daily_cards": -1,
                "daily_spreads": -1,
                "spread_types": "all"
            },
            "prices": {
                PaymentPeriod.MONTHLY: Decimal("599"),
                PaymentPeriod.QUARTERLY: Decimal("1599"),  # Скидка ~11%
                PaymentPeriod.YEARLY: Decimal("5990")  # Скидка ~17%
            }
        },
        SubscriptionPlan.VIP: {
            "name": "VIP",
            "emoji": "🥇",
            "features": [
                "Все возможности Премиум +",
                "Персональный астролог",
                "Индивидуальные расклады",
                "Синастрия пар",
                "API доступ",
                "Ранний доступ к функциям",
                "VIP чат поддержки"
            ],
            "limits": {
                "daily_cards": -1,
                "daily_spreads": -1,
                "spread_types": "all",
                "personal_astrologer": True
            },
            "prices": {
                PaymentPeriod.MONTHLY: Decimal("1499"),
                PaymentPeriod.QUARTERLY: Decimal("3999"),  # Скидка ~11%
                PaymentPeriod.YEARLY: Decimal("14990")  # Скидка ~17%
            }
        }
    }

    def __init__(
            self,
            current_plan: SubscriptionPlan = SubscriptionPlan.FREE,
            selected_period: PaymentPeriod = PaymentPeriod.MONTHLY,
            show_features: bool = True,
            promo_code: Optional[str] = None,
            promo_discount: Optional[int] = None
    ):
        """
        Инициализация клавиатуры тарифов.

        Args:
            current_plan: Текущий тариф
            selected_period: Выбранный период
            show_features: Показывать ли возможности
            promo_code: Применённый промокод
            promo_discount: Скидка по промокоду (%)
        """
        super().__init__()
        self.current_plan = current_plan
        self.selected_period = selected_period
        self.show_features = show_features
        self.promo_code = promo_code
        self.promo_discount = promo_discount

        logger.debug(f"Создание клавиатуры тарифов: текущий={current_plan.value}")

    async def build(self, **kwargs) -> InlineKeyboardMarkup:
        """Построить клавиатуру тарифов."""
        # Выбор периода оплаты
        self._add_period_selector()

        # Тарифные планы
        for plan in SubscriptionPlan:
            if plan == SubscriptionPlan.FREE:
                continue  # Не показываем бесплатный в списке покупки

            self._add_plan_button(plan)

        # Промокод
        if self.promo_code:
            self.add_button(
                text=f"🎁 Промокод: {self.promo_code} (-{self.promo_discount}%)",
                callback_data=PromoCallbackData(
                    action="remove",
                    code=self.promo_code
                )
            )
        else:
            self.add_button(
                text="🎁 У меня есть промокод",
                callback_data=PromoCallbackData(action="enter")
            )

        # Сравнение тарифов
        self.add_button(
            text="📊 Сравнить тарифы",
            callback_data=SubscriptionCallbackData(
                action="compare"
            )
        )

        # Вопросы
        self.add_button(
            text="❓ Частые вопросы",
            callback_data=SubscriptionCallbackData(
                action="faq"
            )
        )

        # Настройка сетки
        self.builder.adjust(3, 1, 1, 1, 1, 2)

        self.add_back_button("main_menu")

        return await super().build(**kwargs)

    def _add_period_selector(self) -> None:
        """Добавить выбор периода."""
        periods = [
            (PaymentPeriod.MONTHLY, "Месяц"),
            (PaymentPeriod.QUARTERLY, "3 месяца"),
            (PaymentPeriod.YEARLY, "Год")
        ]

        for period, name in periods:
            # Подсчитываем среднюю скидку
            if period == PaymentPeriod.QUARTERLY:
                discount = "−11%"
            elif period == PaymentPeriod.YEARLY:
                discount = "−17%"
            else:
                discount = ""

            text = name
            if discount:
                text += f" {discount}"

            if period == self.selected_period:
                text = f"✓ {text}"

            self.add_button(
                text=text,
                callback_data=SubscriptionCallbackData(
                    action="period",
                    period=period.value
                )
            )

    def _add_plan_button(self, plan: SubscriptionPlan) -> None:
        """Добавить кнопку тарифа."""
        info = self.PLAN_INFO[plan]
        price = info["prices"][self.selected_period]

        # Применяем скидку промокода
        if self.promo_discount:
            discounted_price = price * (100 - self.promo_discount) / 100
            price_text = f"~{int(price)}~ {int(discounted_price)} ₽"
        else:
            price_text = f"{int(price)} ₽"

        # Текст кнопки
        button_text = f"{info['emoji']} {info['name']} — {price_text}"

        # Добавляем метку для текущего тарифа
        if plan == self.current_plan:
            button_text = f"✓ {button_text} (текущий)"
            callback_action = "current"
        else:
            callback_action = "select"

        # Популярный тариф
        if plan == SubscriptionPlan.PREMIUM:
            button_text = f"⭐ {button_text}"

        self.add_button(
            text=button_text,
            callback_data=SubscriptionCallbackData(
                action=callback_action,
                plan=plan.value,
                period=self.selected_period.value
            )
        )


class PaymentMethodKeyboard(InlineKeyboard):
    """Клавиатура выбора способа оплаты."""

    def __init__(
            self,
            amount: Decimal,
            plan: SubscriptionPlan,
            period: PaymentPeriod,
            saved_methods: Optional[List[Dict[str, Any]]] = None,
            available_providers: Optional[List[PaymentProvider]] = None
    ):
        """
        Инициализация клавиатуры оплаты.

        Args:
            amount: Сумма к оплате
            plan: Выбранный тариф
            period: Период оплаты
            saved_methods: Сохранённые способы оплаты
            available_providers: Доступные провайдеры
        """
        super().__init__()
        self.amount = amount
        self.plan = plan
        self.period = period
        self.saved_methods = saved_methods or []
        self.available_providers = available_providers or list(PaymentProvider)

        logger.debug(f"Создание клавиатуры оплаты: {amount} ₽")

    async def build(self, **kwargs) -> InlineKeyboardMarkup:
        """Построить клавиатуру оплаты."""
        # Заголовок с суммой
        self.add_button(
            text=f"💳 К оплате: {int(self.amount)} ₽",
            callback_data="noop"
        )

        # Сохранённые карты
        if self.saved_methods:
            self.add_button(
                text="— Сохранённые карты —",
                callback_data="noop"
            )

            for method in self.saved_methods[:3]:  # Максимум 3
                card_text = f"💳 •••• {method['last4']}"
                if method.get("is_default"):
                    card_text += " ✓"

                self.add_button(
                    text=card_text,
                    callback_data=PaymentCallbackData(
                        action="use_saved",
                        provider="saved",
                        value=method["id"]
                    )
                )

        # Новые способы оплаты
        self.add_button(
            text="— Способы оплаты —",
            callback_data="noop"
        )

        # Провайдеры
        provider_info = {
            PaymentProvider.YOOKASSA: {
                "name": "ЮKassa",
                "emoji": "💳",
                "description": "Банковские карты"
            },
            PaymentProvider.TINKOFF: {
                "name": "Тинькофф",
                "emoji": "🟡",
                "description": "Оплата через Тинькофф"
            },
            PaymentProvider.SBERBANK: {
                "name": "СберБанк",
                "emoji": "🟢",
                "description": "Оплата через Сбербанк"
            },
            PaymentProvider.CRYPTO: {
                "name": "Криптовалюта",
                "emoji": "₿",
                "description": "Bitcoin, USDT"
            },
            PaymentProvider.STARS: {
                "name": "Telegram Stars",
                "emoji": "⭐",
                "description": "Оплата звёздами"
            }
        }

        for provider in self.available_providers:
            info = provider_info[provider]

            self.add_button(
                text=f"{info['emoji']} {info['name']}",
                callback_data=PaymentCallbackData(
                    action="select_provider",
                    provider=provider.value,
                    amount=str(self.amount)
                )
            )

        # Настройка сетки
        saved_count = len(self.saved_methods) if self.saved_methods else 0
        self.builder.adjust(
            1,  # Заголовок
            1,  # Сохранённые карты (заголовок)
            *([1] * saved_count),  # Сохранённые карты
            1,  # Новые способы (заголовок)
            2, 2, 1  # Провайдеры
        )

        # Дополнительные опции
        self.add_button(
            text="🔐 Безопасность платежей",
            callback_data="payment:security_info"
        )

        self.add_button(
            text="❌ Отмена",
            callback_data=SubscriptionCallbackData(
                action="cancel_payment"
            )
        )

        self.builder.adjust(2)

        return await super().build(**kwargs)


class CurrentSubscriptionKeyboard(InlineKeyboard):
    """Клавиатура текущей подписки."""

    def __init__(
            self,
            subscription_data: Dict[str, Any],
            payment_methods: Optional[List[Dict[str, Any]]] = None
    ):
        """
        Инициализация клавиатуры текущей подписки.

        Args:
            subscription_data: Данные подписки
            payment_methods: Способы оплаты
        """
        super().__init__()
        self.subscription = subscription_data
        self.payment_methods = payment_methods or []

    async def build(self, **kwargs) -> InlineKeyboardMarkup:
        """Построить клавиатуру."""
        # Информация о подписке
        plan_info = SubscriptionPlansKeyboard.PLAN_INFO.get(
            SubscriptionPlan(self.subscription["plan"]),
            {}
        )

        # Статус подписки
        if self.subscription["is_active"]:
            status_text = "✅ Активна"
        elif self.subscription["is_trial"]:
            status_text = "🎁 Пробный период"
        else:
            status_text = "❌ Неактивна"

        self.add_button(
            text=f"{status_text} • {plan_info.get('name', 'Неизвестный')}",
            callback_data="noop"
        )

        # Срок действия
        if self.subscription["end_date"]:
            end_date = self.subscription["end_date"]
            days_left = (end_date - datetime.now()).days

            if days_left > 0:
                self.add_button(
                    text=f"📅 Действует до: {end_date.strftime('%d.%m.%Y')} ({days_left} дн.)",
                    callback_data="noop"
                )
            else:
                self.add_button(
                    text="⚠️ Подписка истекла",
                    callback_data="noop"
                )

        # Автопродление
        if self.subscription.get("auto_renewal"):
            renewal_text = "🔄 Автопродление: ВКЛ"
            renewal_action = "disable"
        else:
            renewal_text = "🔄 Автопродление: ВЫКЛ"
            renewal_action = "enable"

        self.add_button(
            text=renewal_text,
            callback_data=AutoRenewalCallbackData(
                action=renewal_action
            )
        )

        # Способ оплаты для автопродления
        if self.subscription.get("auto_renewal") and self.payment_methods:
            default_method = next(
                (m for m in self.payment_methods if m.get("is_default")),
                self.payment_methods[0]
            )

            self.add_button(
                text=f"💳 Карта: •••• {default_method['last4']}",
                callback_data=AutoRenewalCallbackData(
                    action="change_method"
                )
            )

        self.builder.adjust(1)

        # Действия
        if self.subscription["plan"] != "vip":
            self.add_button(
                text="⬆️ Улучшить тариф",
                callback_data=SubscriptionCallbackData(
                    action="upgrade"
                )
            )

        if self.subscription["is_active"]:
            self.add_button(
                text="🔄 Продлить",
                callback_data=SubscriptionCallbackData(
                    action="renew"
                )
            )
        else:
            self.add_button(
                text="💳 Активировать",
                callback_data=SubscriptionCallbackData(
                    action="activate"
                )
            )

        # История платежей
        self.add_button(
            text="📋 История платежей",
            callback_data=SubscriptionCallbackData(
                action="payment_history"
            )
        )

        # Отмена подписки
        if self.subscription["is_active"]:
            self.add_button(
                text="❌ Отменить подписку",
                callback_data=SubscriptionCallbackData(
                    action="cancel"
                )
            )

        # Настройка сетки
        buttons_count = 2 if self.subscription["is_active"] else 1
        self.builder.adjust(1, 1, 1, 1, buttons_count, 1, 1)

        self.add_back_button("subscription:menu")

        return await super().build(**kwargs)


class PromoCodeKeyboard(InlineKeyboard):
    """Клавиатура промокода."""

    def __init__(
            self,
            promo_info: Optional[Dict[str, Any]] = None,
            error_message: Optional[str] = None
    ):
        """
        Инициализация клавиатуры промокода.

        Args:
            promo_info: Информация о промокоде
            error_message: Сообщение об ошибке
        """
        super().__init__()
        self.promo_info = promo_info
        self.error_message = error_message

    async def build(self, **kwargs) -> InlineKeyboardMarkup:
        """Построить клавиатуру."""
        if self.error_message:
            # Ошибка промокода
            self.add_button(
                text=f"❌ {self.error_message}",
                callback_data="noop"
            )

            self.add_button(
                text="🔄 Попробовать другой",
                callback_data=PromoCallbackData(action="retry")
            )

        elif self.promo_info:
            # Успешная проверка промокода
            self.add_button(
                text=f"✅ Промокод принят!",
                callback_data="noop"
            )

            # Информация о скидке
            if self.promo_info["type"] == "percentage":
                discount_text = f"{self.promo_info['value']}% скидка"
            elif self.promo_info["type"] == "fixed":
                discount_text = f"{self.promo_info['value']} ₽ скидка"
            elif self.promo_info["type"] == "trial":
                discount_text = f"{self.promo_info['value']} дней бесплатно"

            self.add_button(
                text=f"🎁 {discount_text}",
                callback_data="noop"
            )

            # Применить
            self.add_button(
                text="✅ Применить",
                callback_data=PromoCallbackData(
                    action="apply",
                    code=self.promo_info["code"]
                )
            )

            self.add_button(
                text="❌ Отмена",
                callback_data=PromoCallbackData(action="cancel")
            )

            self.builder.adjust(1, 1, 2)

        else:
            # Ввод промокода
            self.add_button(
                text="💬 Введите промокод в чат",
                callback_data="noop"
            )

            # Популярные промокоды
            self.add_button(
                text="🎯 WELCOME10 (новым)",
                callback_data=PromoCallbackData(
                    action="check",
                    code="WELCOME10"
                )
            )

            self.add_button(
                text="🎯 TAROT2024",
                callback_data=PromoCallbackData(
                    action="check",
                    code="TAROT2024"
                )
            )

            self.add_button(
                text="❌ Отмена",
                callback_data=PromoCallbackData(action="cancel")
            )

            self.builder.adjust(1, 2, 1)

        return await super().build(**kwargs)


class PaymentHistoryKeyboard(PaginatedKeyboard):
    """Клавиатура истории платежей."""

    def __init__(
            self,
            payments: List[Dict[str, Any]],
            page: int = 1
    ):
        """
        Инициализация истории платежей.

        Args:
            payments: Список платежей
            page: Текущая страница
        """
        super().__init__(
            items=payments,
            page_size=5,
            current_page=page,
            menu_type="payment_history"
        )

    async def build(self, **kwargs) -> InlineKeyboardMarkup:
        """Построить клавиатуру."""
        # Платежи текущей страницы
        page_payments = self.get_page_items()

        if not page_payments:
            self.add_button(
                text="📭 История платежей пуста",
                callback_data="noop"
            )
        else:
            for payment in page_payments:
                # Статус платежа
                status_emoji = {
                    "succeeded": "✅",
                    "pending": "⏳",
                    "canceled": "❌",
                    "failed": "⚠️"
                }.get(payment["status"], "❓")

                # Формат даты
                date_str = payment["created_at"].strftime("%d.%m.%Y")

                # Текст кнопки
                button_text = (
                    f"{status_emoji} {date_str} - "
                    f"{int(payment['amount'])} ₽ "
                    f"({payment['description']})"
                )

                self.add_button(
                    text=button_text,
                    callback_data=PaymentCallbackData(
                        action="view",
                        payment_id=payment["id"]
                    )
                )

        # Настройка сетки
        self.builder.adjust(*([1] * len(page_payments)))

        # Пагинация
        if self.total_pages > 1:
            self.add_pagination_buttons()

        # Дополнительные действия
        self.add_button(
            text="📊 Статистика платежей",
            callback_data="payment:statistics"
        )

        self.add_button(
            text="💳 Способы оплаты",
            callback_data="payment:methods"
        )

        self.add_button(
            text="📄 Скачать чеки",
            callback_data="payment:download_receipts"
        )

        self.builder.adjust(1, 2)

        self.add_back_button("subscription:current")

        return await super().build(**kwargs)


class PaymentMethodsManagementKeyboard(InlineKeyboard):
    """Клавиатура управления способами оплаты."""

    def __init__(
            self,
            payment_methods: List[Dict[str, Any]]
    ):
        """
        Инициализация управления способами оплаты.

        Args:
            payment_methods: Список способов оплаты
        """
        super().__init__()
        self.payment_methods = payment_methods

    async def build(self, **kwargs) -> InlineKeyboardMarkup:
        """Построить клавиатуру."""
        if not self.payment_methods:
            self.add_button(
                text="💳 Нет сохранённых карт",
                callback_data="noop"
            )

            self.add_button(
                text="➕ Добавить карту",
                callback_data="payment:add_method"
            )
        else:
            # Список карт
            for method in self.payment_methods:
                # Информация о карте
                card_text = f"💳 •••• {method['last4']}"

                if method["card_type"]:
                    card_text += f" ({method['card_type']})"

                if method.get("is_default"):
                    card_text += " ✓ Основная"

                # Срок действия
                if method.get("expires_at"):
                    expires = method["expires_at"]
                    if expires < datetime.now():
                        card_text += " ⚠️ Истекла"

                self.add_button(
                    text=card_text,
                    callback_data=f"payment:method:{method['id']}"
                )

            # Добавить новую карту
            self.add_button(
                text="➕ Добавить карту",
                callback_data="payment:add_method"
            )

        # Настройка сетки
        self.builder.adjust(*([1] * (len(self.payment_methods) + 1)))

        # Информация о безопасности
        self.add_button(
            text="🔐 О безопасности",
            callback_data="payment:security_info"
        )

        self.add_back_button("subscription:current")

        return await super().build(**kwargs)


class SubscriptionCancellationKeyboard(InlineKeyboard):
    """Клавиатура отмены подписки."""

    def __init__(
            self,
            subscription_data: Dict[str, Any],
            show_reasons: bool = True
    ):
        """
        Инициализация клавиатуры отмены.

        Args:
            subscription_data: Данные подписки
            show_reasons: Показывать ли причины
        """
        super().__init__()
        self.subscription = subscription_data
        self.show_reasons = show_reasons

    async def build(self, **kwargs) -> InlineKeyboardMarkup:
        """Построить клавиатуру."""
        if self.show_reasons:
            # Причины отмены
            self.add_button(
                text="❓ Укажите причину отмены:",
                callback_data="noop"
            )

            reasons = [
                ("💰 Слишком дорого", "expensive"),
                ("🚫 Не использую", "not_using"),
                ("😕 Не подходит функционал", "features"),
                ("🐛 Технические проблемы", "technical"),
                ("🔄 Перехожу к конкуренту", "competitor"),
                ("🤷 Другая причина", "other")
            ]

            for text, reason in reasons:
                self.add_button(
                    text=text,
                    callback_data=f"cancel:reason:{reason}"
                )

            self.builder.adjust(1, 2, 2, 2)

        else:
            # Подтверждение отмены
            days_left = (self.subscription["end_date"] - datetime.now()).days

            self.add_button(
                text=f"⚠️ Подписка будет активна ещё {days_left} дней",
                callback_data="noop"
            )

            self.add_button(
                text="✅ Подтвердить отмену",
                callback_data="cancel:confirm"
            )

            # Альтернативы
            self.add_button(
                text="🔄 Сменить тариф",
                callback_data=SubscriptionCallbackData(
                    action="change_plan"
                )
            )

            self.add_button(
                text="⏸ Приостановить",
                callback_data=SubscriptionCallbackData(
                    action="pause"
                )
            )

            self.add_button(
                text="❌ Не отменять",
                callback_data=SubscriptionCallbackData(
                    action="keep"
                )
            )

            self.builder.adjust(1, 1, 2, 1)

        return await super().build(**kwargs)


# Вспомогательные функции
async def get_subscription_plans_keyboard(
        current_plan: str = "free",
        selected_period: str = "monthly",
        promo_code: Optional[str] = None,
        promo_discount: Optional[int] = None
) -> InlineKeyboardMarkup:
    """Получить клавиатуру тарифных планов."""
    keyboard = SubscriptionPlansKeyboard(
        current_plan=SubscriptionPlan(current_plan),
        selected_period=PaymentPeriod(selected_period),
        promo_code=promo_code,
        promo_discount=promo_discount
    )
    return await keyboard.build()


async def get_payment_method_keyboard(
        amount: Decimal,
        plan: str,
        period: str,
        saved_methods: Optional[List[Dict[str, Any]]] = None
) -> InlineKeyboardMarkup:
    """Получить клавиатуру способов оплаты."""
    keyboard = PaymentMethodKeyboard(
        amount=amount,
        plan=SubscriptionPlan(plan),
        period=PaymentPeriod(period),
        saved_methods=saved_methods
    )
    return await keyboard.build()


async def get_current_subscription_keyboard(
        subscription_data: Dict[str, Any],
        payment_methods: Optional[List[Dict[str, Any]]] = None
) -> InlineKeyboardMarkup:
    """Получить клавиатуру текущей подписки."""
    keyboard = CurrentSubscriptionKeyboard(
        subscription_data=subscription_data,
        payment_methods=payment_methods
    )
    return await keyboard.build()


async def get_promo_code_keyboard(
        promo_info: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None
) -> InlineKeyboardMarkup:
    """Получить клавиатуру промокода."""
    keyboard = PromoCodeKeyboard(
        promo_info=promo_info,
        error_message=error_message
    )
    return await keyboard.build()


logger.info("Модуль клавиатур подписки загружен")