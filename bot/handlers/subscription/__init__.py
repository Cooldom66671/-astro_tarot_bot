"""
Модуль обработчиков управления подпиской.

Этот модуль содержит все обработчики для работы с подписками:
- Просмотр тарифных планов
- Процесс покупки подписки
- Управление автопродлением
- История платежей
- Применение промокодов
- Отмена подписки

Автор: AI Assistant
Дата создания: 2024-12-30
"""

import logging
from datetime import datetime, date, timedelta
from typing import Dict, Any, Optional, List
from decimal import Decimal
import asyncio
import uuid

from aiogram import Router, F, Bot
from aiogram.filters import Command, StateFilter
from aiogram.types import (
    Message,
    CallbackQuery,
    LabeledPrice,
    PreCheckoutQuery
)
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest

from bot.handlers.base import (
    BaseHandler,
    error_handler,
    log_action,
    get_or_create_user,
    answer_callback_query,
    edit_or_send_message
)
from bot.states import SubscriptionStates, FeedbackStates
from infrastructure.telegram.keyboards import (
    Keyboards,
    InlineKeyboard,
    SubscriptionCallbackData,
    PaymentCallbackData,
    PromoCallbackData
)
from infrastructure import get_unit_of_work
from services import get_payment_service
from config import settings

logger = logging.getLogger(__name__)


class SubscriptionHandlers(BaseHandler):
    """Обработчики для управления подписками."""

    # Константы
    SUBSCRIPTION_PLANS = {
        "basic": {
            "name": "Basic",
            "price": 299,
            "duration": 30,
            "features": [
                "30 раскладов Таро в месяц",
                "Дневные и недельные гороскопы",
                "История раскладов",
                "Базовая поддержка"
            ],
            "limits": {
                "tarot_spreads": 30,
                "horoscopes": "daily_weekly",
                "natal_chart": False,
                "transits": False
            }
        },
        "premium": {
            "name": "Premium",
            "price": 599,
            "duration": 30,
            "features": [
                "Безлимитные расклады Таро",
                "Все типы гороскопов",
                "Натальная карта",
                "Транзиты планет",
                "Приоритетная поддержка"
            ],
            "limits": {
                "tarot_spreads": -1,  # Безлимит
                "horoscopes": "all",
                "natal_chart": True,
                "transits": True
            }
        },
        "vip": {
            "name": "VIP",
            "price": 999,
            "duration": 30,
            "features": [
                "Все возможности Premium",
                "Анализ совместимости",
                "Персональный астролог",
                "Эксклюзивные расклады",
                "VIP поддержка 24/7"
            ],
            "limits": {
                "tarot_spreads": -1,
                "horoscopes": "all",
                "natal_chart": True,
                "transits": True,
                "synastry": True,
                "personal_astrologer": True
            }
        }
    }

    PROMO_CODES = {
        "WELCOME20": {"discount": 20, "type": "percent", "plans": ["all"]},
        "PREMIUM50": {"discount": 50, "type": "percent", "plans": ["premium"]},
        "VIP100": {"discount": 100, "type": "fixed", "plans": ["vip"]},
        "FRIEND": {"discount": 30, "type": "percent", "plans": ["all"]}
    }

    def register_handlers(self) -> None:
        """Регистрация обработчиков подписки."""
        # Команда /subscription
        self.router.message.register(
            self.cmd_subscription,
            Command("subscription")
        )

        # Главное меню подписки
        self.router.callback_query.register(
            self.show_subscription_menu,
            F.data == "subscription_menu"
        )

        # Просмотр планов
        self.router.callback_query.register(
            self.show_plans,
            F.data == "show_plans"
        )

        self.router.callback_query.register(
            self.show_plan_details,
            F.data.startswith("plan_details:")
        )

        self.router.callback_query.register(
            self.compare_plans,
            F.data == "compare_plans"
        )

        # Покупка подписки
        self.router.callback_query.register(
            self.select_plan_to_buy,
            F.data.startswith("buy_plan:")
        )

        self.router.callback_query.register(
            self.select_payment_period,
            F.data.startswith("payment_period:")
        )

        self.router.callback_query.register(
            self.select_payment_method,
            F.data.startswith("payment_method:")
        )

        self.router.callback_query.register(
            self.process_payment,
            F.data.startswith("process_payment:")
        )

        # Промокоды
        self.router.callback_query.register(
            self.enter_promo_code,
            F.data == "enter_promo"
        )

        self.router.message.register(
            self.validate_promo_code,
            StateFilter(SubscriptionStates.waiting_for_promo)
        )

        # Управление подпиской
        self.router.callback_query.register(
            self.show_current_subscription,
            F.data == "current_subscription"
        )

        self.router.callback_query.register(
            self.toggle_auto_renew,
            F.data == "toggle_auto_renew"
        )

        self.router.callback_query.register(
            self.extend_subscription,
            F.data == "extend_subscription"
        )

        self.router.callback_query.register(
            self.upgrade_subscription,
            F.data == "upgrade_subscription"
        )

        # История платежей
        self.router.callback_query.register(
            self.show_payment_history,
            F.data == "payment_history"
        )

        self.router.callback_query.register(
            self.show_payment_details,
            F.data.startswith("payment_details:")
        )

        # Отмена подписки
        self.router.callback_query.register(
            self.start_cancellation,
            F.data == "cancel_subscription"
        )

        self.router.callback_query.register(
            self.confirm_cancellation,
            F.data.startswith("confirm_cancel:")
        )

        # Обработчики платежей
        self.router.pre_checkout_query.register(
            self.pre_checkout_handler
        )

        self.router.message.register(
            self.successful_payment_handler,
            F.successful_payment
        )

    @error_handler()
    @log_action("subscription_command")
    async def cmd_subscription(
            self,
            message: Message,
            state: FSMContext,
            **kwargs
    ) -> None:
        """Команда /subscription - управление подпиской."""
        await state.clear()

        async with get_unit_of_work() as uow:
            user = await get_or_create_user(message.from_user)
            user_db = await uow.users.get_by_telegram_id(message.from_user.id)

            if user_db:
                subscription = await uow.subscriptions.get_active_by_user_id(user_db.id)
            else:
                subscription = None

            # Используем фабрику клавиатур
            keyboard = await Keyboards.subscription_menu(
                current_plan=user_db.subscription_plan if user_db and hasattr(user_db, 'subscription_plan') else None,
                has_subscription=bool(subscription and subscription.is_active)
            )

            text = self._format_subscription_status(user_db, subscription)

            await message.answer(
                text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )

    @error_handler()
    async def show_subscription_menu(
            self,
            callback: CallbackQuery,
            state: FSMContext,
            **kwargs
    ) -> None:
        """Показать меню управления подпиской."""
        await state.clear()

        async with get_unit_of_work() as uow:
            user = await uow.users.get_by_telegram_id(callback.from_user.id)

            if not user:
                await answer_callback_query(callback, "Необходимо начать с /start", show_alert=True)
                return

            subscription = await uow.subscriptions.get_active_by_user_id(user.id)

            # Используем фабрику клавиатур
            keyboard = await Keyboards.subscription_menu(
                current_plan=user.subscription_plan if hasattr(user, 'subscription_plan') else None,
                has_subscription=bool(subscription and subscription.is_active)
            )

            text = self._format_subscription_status(user, subscription)

            await edit_or_send_message(
                callback.message,
                text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )

        await answer_callback_query(callback)

    @error_handler()
    async def show_plans(
            self,
            callback: CallbackQuery,
            state: FSMContext,
            **kwargs
    ) -> None:
        """Показать доступные планы подписки."""
        text = (
            "💎 <b>Тарифные планы</b>\n\n"
            "Выберите подходящий план:"
        )

        # Используем фабрику клавиатур
        keyboard = await Keyboards.subscription_plans(
            plans=self.SUBSCRIPTION_PLANS,
            current_plan=None
        )

        await edit_or_send_message(
            callback.message,
            text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )

        await answer_callback_query(callback)

    @error_handler()
    async def show_plan_details(
            self,
            callback: CallbackQuery,
            state: FSMContext,
            **kwargs
    ) -> None:
        """Показать детали плана."""
        plan_name = callback.data.split(":")[1]

        if plan_name not in self.SUBSCRIPTION_PLANS:
            await answer_callback_query(callback, "План не найден", show_alert=True)
            return

        plan = self.SUBSCRIPTION_PLANS[plan_name]

        text = self._format_plan_details(plan_name, plan)

        # Используем фабрику клавиатур
        keyboard = await Keyboards.plan_details(
            plan_name=plan_name,
            plan_info=plan
        )

        await edit_or_send_message(
            callback.message,
            text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )

        await answer_callback_query(callback)

    @error_handler()
    async def compare_plans(
            self,
            callback: CallbackQuery,
            state: FSMContext,
            **kwargs
    ) -> None:
        """Сравнить все планы."""
        text = self._format_plans_comparison()

        # Используем фабрику клавиатур
        keyboard = await Keyboards.compare_plans_menu()

        await edit_or_send_message(
            callback.message,
            text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )

        await answer_callback_query(callback)

    @error_handler()
    async def select_plan_to_buy(
            self,
            callback: CallbackQuery,
            state: FSMContext,
            **kwargs
    ) -> None:
        """Выбор плана для покупки."""
        plan_name = callback.data.split(":")[1]

        if plan_name not in self.SUBSCRIPTION_PLANS:
            await answer_callback_query(callback, "План не найден", show_alert=True)
            return

        # Сохраняем выбранный план
        await state.update_data(selected_plan=plan_name)

        text = (
            "📅 <b>Выберите период подписки</b>\n\n"
            "Чем дольше период, тем выгоднее!"
        )

        # Используем фабрику клавиатур
        keyboard = await Keyboards.payment_period_selection(
            plan_name=plan_name,
            base_price=self.SUBSCRIPTION_PLANS[plan_name]["price"]
        )

        await edit_or_send_message(
            callback.message,
            text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )

        await answer_callback_query(callback)

    @error_handler()
    async def select_payment_period(
            self,
            callback: CallbackQuery,
            state: FSMContext,
            **kwargs
    ) -> None:
        """Выбор периода оплаты."""
        parts = callback.data.split(":")
        plan_name = parts[1]
        period = parts[2]

        # Сохраняем период
        await state.update_data(payment_period=period)

        # Рассчитываем стоимость
        base_price = self.SUBSCRIPTION_PLANS[plan_name]["price"]
        total_price = self._calculate_price(base_price, period)

        text = (
            "💳 <b>Выберите способ оплаты</b>\n\n"
            f"К оплате: <b>{total_price} ₽</b>"
        )

        # Используем фабрику клавиатур
        keyboard = await Keyboards.payment_method_selection(
            plan_name=plan_name,
            period=period,
            amount=total_price
        )

        await edit_or_send_message(
            callback.message,
            text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )

        await answer_callback_query(callback)

    @error_handler()
    async def process_payment(
            self,
            callback: CallbackQuery,
            state: FSMContext,
            **kwargs
    ) -> None:
        """Обработка платежа."""
        parts = callback.data.split(":")
        plan_name = parts[1]
        period = parts[2]
        method = parts[3]

        plan = self.SUBSCRIPTION_PLANS[plan_name]
        price = self._calculate_price(plan["price"], period)

        if method == "telegram":
            # Создаем счет для оплаты через Telegram
            bot = Bot.get_current()

            await bot.send_invoice(
                chat_id=callback.from_user.id,
                title=f"Подписка {plan['name']}",
                description=f"Подписка на {self._get_period_name(period)}",
                payload=f"{plan_name}:{period}",
                provider_token=settings.payment.provider_token,
                currency="RUB",
                prices=[LabeledPrice(label=f"Подписка {plan['name']}", amount=price * 100)]
            )

            await answer_callback_query(callback, "Счет отправлен")

        elif method == "yoomoney":
            # Генерируем ссылку на оплату через ЮMoney
            payment_service = get_payment_service()
            payment_url = await payment_service.create_yoomoney_payment(
                amount=price,
                description=f"Подписка {plan['name']} на {self._get_period_name(period)}",
                user_id=callback.from_user.id,
                plan_name=plan_name,
                period=period
            )

            # Создаем клавиатуру с URL кнопкой
            keyboard = InlineKeyboard()
            keyboard.add_url_button(text="💳 Оплатить", url=payment_url)
            keyboard.add_button(
                text="◀️ Назад",
                callback_data=f"payment_period:{plan_name}:{period}"
            )
            keyboard.builder.adjust(1)

            text = (
                "💳 <b>Оплата через ЮMoney</b>\n\n"
                f"Сумма к оплате: <b>{price} ₽</b>\n\n"
                "Нажмите кнопку ниже для перехода к оплате:"
            )

            await edit_or_send_message(
                callback.message,
                text,
                reply_markup=await keyboard.build(),
                parse_mode="HTML"
            )

            await answer_callback_query(callback)

    @error_handler()
    async def enter_promo_code(
            self,
            callback: CallbackQuery,
            state: FSMContext,
            **kwargs
    ) -> None:
        """Ввод промокода."""
        text = (
            "🎟 <b>Введите промокод</b>\n\n"
            "Отправьте промокод в чат:"
        )

        # Используем кнопку отмены
        keyboard = await Keyboards.cancel("subscription_menu")

        await edit_or_send_message(
            callback.message,
            text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )

        await state.set_state(SubscriptionStates.waiting_for_promo)
        await answer_callback_query(callback)

    @error_handler()
    async def validate_promo_code(
            self,
            message: Message,
            state: FSMContext
    ) -> None:
        """Проверка промокода."""
        promo_code = message.text.strip().upper()

        if promo_code in self.PROMO_CODES:
            promo = self.PROMO_CODES[promo_code]

            text = (
                "✅ <b>Промокод активирован!</b>\n\n"
                f"Скидка: {promo['discount']}{'%' if promo['type'] == 'percent' else ' ₽'}\n"
            )

            # Сохраняем промокод в состоянии
            await state.update_data(promo_code=promo_code)
        else:
            text = "❌ Промокод не найден или недействителен"

        await state.clear()

        # Используем фабрику клавиатур
        keyboard = await Keyboards.promo_result(success=promo_code in self.PROMO_CODES)

        await message.answer(
            text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )

    @error_handler()
    async def show_current_subscription(
            self,
            callback: CallbackQuery,
            state: FSMContext,
            **kwargs
    ) -> None:
        """Показать текущую подписку."""
        async with get_unit_of_work() as uow:
            user = await uow.users.get_by_telegram_id(callback.from_user.id)

            if not user:
                await answer_callback_query(callback, "Пользователь не найден", show_alert=True)
                return

            subscription = await uow.subscriptions.get_active_by_user_id(user.id)

            if not subscription:
                await answer_callback_query(callback, "У вас нет активной подписки", show_alert=True)
                return

            text = self._format_current_subscription(subscription)

            # Используем фабрику клавиатур
            keyboard = await Keyboards.subscription_management(
                subscription=subscription,
                auto_renew=subscription.auto_renew
            )

            await edit_or_send_message(
                callback.message,
                text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )

        await answer_callback_query(callback)

    @error_handler()
    async def toggle_auto_renew(
            self,
            callback: CallbackQuery,
            state: FSMContext,
            **kwargs
    ) -> None:
        """Переключить автопродление."""
        async with get_unit_of_work() as uow:
            user = await uow.users.get_by_telegram_id(callback.from_user.id)

            if not user:
                await answer_callback_query(callback, "Пользователь не найден", show_alert=True)
                return

            subscription = await uow.subscriptions.get_active_by_user_id(user.id)

            if not subscription:
                await answer_callback_query(callback, "Подписка не найдена", show_alert=True)
                return

            # Переключаем автопродление
            subscription.auto_renew = not subscription.auto_renew
            await uow.subscriptions.update(subscription)
            await uow.commit()

            status = "включено" if subscription.auto_renew else "выключено"
            await answer_callback_query(
                callback,
                f"Автопродление {status}",
                show_alert=False
            )

            # Обновляем меню
            await self.show_current_subscription(callback, state)

    @error_handler()
    async def show_payment_history(
            self,
            callback: CallbackQuery,
            state: FSMContext,
            **kwargs
    ) -> None:
        """Показать историю платежей."""
        async with get_unit_of_work() as uow:
            user = await uow.users.get_by_telegram_id(callback.from_user.id)

            if not user:
                await answer_callback_query(callback, "Пользователь не найден", show_alert=True)
                return

            payments = await uow.payments.get_user_payments(user.id, limit=10)

            if not payments:
                text = "📋 <b>История платежей</b>\n\nУ вас пока нет платежей."
                keyboard = await Keyboards.back("subscription_menu")
            else:
                text = self._format_payment_history(payments)
                # Используем фабрику клавиатур
                keyboard = await Keyboards.payment_history(payments=payments[:5])

            await edit_or_send_message(
                callback.message,
                text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )

        await answer_callback_query(callback)

    @error_handler()
    async def start_cancellation(
            self,
            callback: CallbackQuery,
            state: FSMContext,
            **kwargs
    ) -> None:
        """Начать процесс отмены подписки."""
        async with get_unit_of_work() as uow:
            user = await uow.users.get_by_telegram_id(callback.from_user.id)

            if not user:
                await answer_callback_query(callback, "Пользователь не найден", show_alert=True)
                return

            subscription = await uow.subscriptions.get_active_by_user_id(user.id)

            if not subscription:
                await answer_callback_query(callback, "У вас нет активной подписки", show_alert=True)
                return

            # Показываем причины и альтернативы
            text = (
                "⚠️ <b>Отмена подписки</b>\n\n"
                "Вы действительно хотите отменить подписку?\n\n"
                "<b>Что вы потеряете:</b>\n"
                "• Доступ к расширенным раскладам\n"
                "• Персональные прогнозы\n"
                "• История и статистика\n\n"
                f"Подписка будет активна до: "
                f"{subscription.expires_at.strftime('%d.%m.%Y')}\n\n"
                "Выберите причину отмены:"
            )

            # Используем фабрику клавиатур
            keyboard = await Keyboards.cancellation_reasons()

            await edit_or_send_message(
                callback.message,
                text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )

        await answer_callback_query(callback)

    @error_handler()
    async def confirm_cancellation(
            self,
            callback: CallbackQuery,
            state: FSMContext,
            **kwargs
    ) -> None:
        """Подтвердить отмену подписки."""
        reason = callback.data.split(":")[1]

        async with get_unit_of_work() as uow:
            user = await uow.users.get_by_telegram_id(callback.from_user.id)

            if not user:
                await answer_callback_query(callback, "Пользователь не найден", show_alert=True)
                return

            subscription = await uow.subscriptions.get_active_by_user_id(user.id)

            if not subscription:
                await answer_callback_query(callback, "Подписка не найдена", show_alert=True)
                return

            # Отменяем автопродление
            subscription.auto_renew = False
            subscription.cancellation_reason = reason
            subscription.cancelled_at = datetime.utcnow()

            await uow.subscriptions.update(subscription)
            await uow.commit()

            # Отправляем подтверждение
            text = (
                "✅ <b>Подписка отменена</b>\n\n"
                f"Ваша подписка будет активна до "
                f"{subscription.expires_at.strftime('%d.%m.%Y')}.\n\n"
                "После этой даты доступ к платным функциям "
                "будет ограничен.\n\n"
                "Вы всегда можете возобновить подписку в любой момент!"
            )

            # Используем фабрику клавиатур
            keyboard = await Keyboards.subscription_cancelled()

            await edit_or_send_message(
                callback.message,
                text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )

            # Сохраняем причину отмены для аналитики
            await state.update_data(cancellation_reason=reason)
            await state.set_state(FeedbackStates.waiting_for_text)

        await answer_callback_query(callback, "Подписка отменена")

    # Обработчики платежей

    @error_handler()
    async def pre_checkout_handler(
            self,
            pre_checkout_query: PreCheckoutQuery,
            **kwargs
    ) -> None:
        """Обработчик предварительной проверки платежа."""
        # Проверяем, что платеж корректный
        await pre_checkout_query.answer(ok=True)

    @error_handler()
    async def successful_payment_handler(
            self,
            message: Message,
            **kwargs
    ) -> None:
        """Обработчик успешного платежа."""
        payment = message.successful_payment

        async with get_unit_of_work() as uow:
            user = await get_or_create_user(message.from_user)
            user_db = await uow.users.get_by_telegram_id(message.from_user.id)

            # Парсим payload для получения деталей
            payload_parts = payment.invoice_payload.split(":")
            plan_name = payload_parts[0]
            period = payload_parts[1]

            # Создаем запись о платеже
            payment_record = await uow.payments.create(
                user_id=user_db.id,
                amount=payment.total_amount / 100,  # Копейки в рубли
                currency=payment.currency,
                provider=payment.provider_payment_charge_id,
                status="completed",
                plan_name=plan_name,
                period=period
            )

            # Активируем/продлеваем подписку
            duration_map = {"1m": 30, "3m": 90, "12m": 365}
            duration_days = duration_map.get(period, 30)

            subscription = await uow.subscriptions.activate_or_extend(
                user_id=user_db.id,
                plan_name=plan_name,
                duration_days=duration_days,
                payment_id=payment_record.id
            )

            # Обновляем план пользователя
            user_db.subscription_plan = plan_name
            await uow.users.update(user_db)

            await uow.commit()

            # Отправляем подтверждение
            text = (
                f"✅ <b>Оплата прошла успешно!</b>\n\n"
                f"План: <b>{self.SUBSCRIPTION_PLANS[plan_name]['name']}</b>\n"
                f"Действует до: {subscription.expires_at.strftime('%d.%m.%Y')}\n\n"
                f"Спасибо за доверие! Теперь вам доступны "
                f"все возможности выбранного плана.\n\n"
                f"Чек об оплате отправлен вам в личные сообщения."
            )

            # Используем фабрику клавиатур
            keyboard = await Keyboards.payment_success()

            await message.answer(
                text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )

    # Вспомогательные методы

    def _format_subscription_status(
            self,
            user: Any,
            subscription: Optional[Any]
    ) -> str:
        """Форматировать статус подписки."""
        text = "💎 <b>Управление подпиской</b>\n\n"

        if subscription and subscription.is_active:
            plan = self.SUBSCRIPTION_PLANS.get(subscription.plan_name, {})

            text += (
                f"<b>Текущий план:</b> {plan.get('name', subscription.plan_name)}\n"
                f"<b>Действует до:</b> {subscription.expires_at.strftime('%d.%m.%Y')}\n"
                f"<b>Автопродление:</b> {'Включено' if subscription.auto_renew else 'Выключено'}\n\n"
            )

            # Показываем оставшиеся дни
            days_left = (subscription.expires_at - datetime.now()).days
            if days_left <= 7:
                text += f"⚠️ Осталось дней: {days_left}\n\n"
        else:
            text += (
                "У вас нет активной подписки.\n\n"
                "Оформите подписку для доступа к:\n"
                "• Безлимитным раскладам Таро\n"
                "• Персональным гороскопам\n"
                "• Натальным картам\n"
                "• Анализу совместимости\n"
                "• И многому другому!\n\n"
            )

        return text

    def _format_plan_details(self, plan_name: str, plan: Dict[str, Any]) -> str:
        """Форматировать детали плана."""
        text = f"💎 <b>План {plan['name']}</b>\n\n"
        text += f"<b>Стоимость:</b> {plan['price']} ₽/месяц\n\n"

        text += "<b>Возможности:</b>\n"
        for feature in plan['features']:
            text += f"• {feature}\n"

        text += "\n<b>Лимиты:</b>\n"
        limits = plan['limits']

        if limits['tarot_spreads'] == -1:
            text += "• Расклады Таро: Безлимит\n"
        else:
            text += f"• Расклады Таро: {limits['tarot_spreads']}/месяц\n"

        if limits.get('natal_chart'):
            text += "• Натальная карта: ✅\n"

        if limits.get('transits'):
            text += "• Транзиты планет: ✅\n"

        if limits.get('synastry'):
            text += "• Анализ совместимости: ✅\n"

        return text

    def _format_plans_comparison(self) -> str:
        """Форматировать сравнение планов."""
        text = "📊 <b>Сравнение тарифных планов</b>\n\n"

        for plan_name, plan in self.SUBSCRIPTION_PLANS.items():
            text += f"<b>{plan['name']} - {plan['price']} ₽/мес</b>\n"

            # Основные функции
            if plan['limits']['tarot_spreads'] == -1:
                text += "✅ Безлимитные расклады\n"
            else:
                text += f"📊 {plan['limits']['tarot_spreads']} раскладов/мес\n"

            if plan['limits'].get('natal_chart'):
                text += "✅ Натальная карта\n"

            if plan['limits'].get('transits'):
                text += "✅ Транзиты планет\n"

            if plan['limits'].get('synastry'):
                text += "✅ Совместимость\n"

            text += "\n"

        return text

    def _format_current_subscription(self, subscription: Any) -> str:
        """Форматировать текущую подписку."""
        plan = self.SUBSCRIPTION_PLANS.get(subscription.plan_name, {})

        text = (
            f"📋 <b>Ваша подписка</b>\n\n"
            f"<b>План:</b> {plan.get('name', subscription.plan_name)}\n"
            f"<b>Активна с:</b> {subscription.started_at.strftime('%d.%m.%Y')}\n"
            f"<b>Действует до:</b> {subscription.expires_at.strftime('%d.%m.%Y')}\n"
            f"<b>Автопродление:</b> {'✅ Включено' if subscription.auto_renew else '❌ Выключено'}\n\n"
        )

        # Дни до окончания
        days_left = (subscription.expires_at - datetime.now()).days

        if days_left <= 0:
            text += "⚠️ <b>Подписка истекла!</b>\n"
        elif days_left <= 7:
            text += f"⚠️ <b>Осталось дней:</b> {days_left}\n"
        else:
            text += f"<b>Осталось дней:</b> {days_left}\n"

        return text

    def _format_payment_history(self, payments: List[Any]) -> str:
        """Форматировать историю платежей."""
        text = "📜 <b>История платежей</b>\n\n"

        for payment in payments[:10]:
            text += (
                f"📅 {payment.created_at.strftime('%d.%m.%Y %H:%M')}\n"
                f"💰 {payment.amount} {payment.currency}\n"
                f"📋 {payment.description}\n"
                f"✅ {payment.status}\n\n"
            )

        return text

    def _calculate_price(self, base_price: int, period: str) -> int:
        """Рассчитать цену с учетом периода."""
        if period == "1m":
            return base_price
        elif period == "3m":
            return int(base_price * 3 * 0.9)  # Скидка 10%
        elif period == "12m":
            return int(base_price * 12 * 0.75)  # Скидка 25%

        return base_price

    def _get_period_name(self, period: str) -> str:
        """Получить название периода."""
        period_names = {
            "1m": "1 месяц",
            "3m": "3 месяца",
            "12m": "12 месяцев"
        }
        return period_names.get(period, period)


# Функция для регистрации обработчика
def register_subscription_handler(router: Router) -> None:
    """
    Регистрация обработчика подписки.

    Args:
        router: Роутер для регистрации
    """
    handler = SubscriptionHandlers(router)
    handler.register_handlers()
    logger.info("Subscription handler зарегистрирован")


logger.info("Модуль обработчика подписки загружен")