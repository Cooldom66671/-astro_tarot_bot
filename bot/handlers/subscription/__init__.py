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

from aiogram import Router, F
from aiogram.filters import Command, StateFilter
from aiogram.types import Message, CallbackQuery, LabeledPrice, PreCheckoutQuery
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest

from bot.handlers.base import BaseHandler, error_handler
from bot.states import SubscriptionStates
from infrastructure.telegram import (
    Keyboards,
    MessageFactory,
    MessageBuilder,
    MessageStyle,
    MessageEmoji as Emoji
)
from infrastructure import get_unit_of_work

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

    def register_handlers(self, router: Router) -> None:
        """Регистрация обработчиков подписки."""
        # Команда /subscription
        router.message.register(
            self.cmd_subscription,
            Command("subscription")
        )

        # Главное меню подписки
        router.callback_query.register(
            self.show_subscription_menu,
            F.data == "subscription_menu"
        )

        # Просмотр планов
        router.callback_query.register(
            self.show_plans,
            F.data == "show_plans"
        )

        router.callback_query.register(
            self.show_plan_details,
            F.data.startswith("plan_details:")
        )

        router.callback_query.register(
            self.compare_plans,
            F.data == "compare_plans"
        )

        # Покупка подписки
        router.callback_query.register(
            self.select_plan_to_buy,
            F.data.startswith("buy_plan:")
        )

        router.callback_query.register(
            self.select_payment_period,
            F.data.startswith("payment_period:")
        )

        router.callback_query.register(
            self.select_payment_method,
            F.data.startswith("payment_method:")
        )

        router.callback_query.register(
            self.process_payment,
            F.data.startswith("process_payment:")
        )

        # Промокоды
        router.callback_query.register(
            self.enter_promo_code,
            F.data == "enter_promo"
        )

        router.message.register(
            self.validate_promo_code,
            StateFilter(SubscriptionStates.waiting_for_promo)
        )

        # Управление подпиской
        router.callback_query.register(
            self.show_current_subscription,
            F.data == "current_subscription"
        )

        router.callback_query.register(
            self.toggle_auto_renew,
            F.data == "toggle_auto_renew"
        )

        router.callback_query.register(
            self.extend_subscription,
            F.data == "extend_subscription"
        )

        router.callback_query.register(
            self.upgrade_subscription,
            F.data == "upgrade_subscription"
        )

        # История платежей
        router.callback_query.register(
            self.show_payment_history,
            F.data == "payment_history"
        )

        router.callback_query.register(
            self.show_payment_details,
            F.data.startswith("payment_details:")
        )

        # Отмена подписки
        router.callback_query.register(
            self.start_cancellation,
            F.data == "cancel_subscription"
        )

        router.callback_query.register(
            self.confirm_cancellation,
            F.data.startswith("confirm_cancel:")
        )

        # Обработчики платежей
        router.pre_checkout_query.register(
            self.pre_checkout_handler
        )

        router.message.register(
            self.successful_payment_handler,
            F.successful_payment
        )

    async def cmd_subscription(
            self,
            message: Message,
            state: FSMContext,
            **kwargs
    ) -> None:
        """Команда /subscription - управление подпиской."""
        await state.clear()

        async with get_unit_of_work() as uow:
            user = await self.get_or_create_user(uow, message.from_user)
            subscription = await uow.subscriptions.get_active(user.id)

            keyboard = await Keyboards.subscription_menu(
                current_plan=user.subscription_plan,
                subscription=subscription
            )

            text = await self._format_subscription_status(user, subscription)

            await message.answer(
                text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )

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
            subscription = await uow.subscriptions.get_active(user.id)

            keyboard = await Keyboards.subscription_menu(
                current_plan=user.subscription_plan,
                subscription=subscription
            )

            text = await self._format_subscription_status(user, subscription)

            await self.edit_or_send_message(
                callback,
                text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )

    async def show_plans(
            self,
            callback: CallbackQuery,
            **kwargs
    ) -> None:
        """Показать доступные планы подписки."""
        async with get_unit_of_work() as uow:
            user = await uow.users.get_by_telegram_id(callback.from_user.id)

            keyboard = await Keyboards.subscription_plans(
                current_plan=user.subscription_plan
            )

            text = await self._format_plans_overview()

            await self.edit_or_send_message(
                callback,
                text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )

    async def show_plan_details(
            self,
            callback: CallbackQuery,
            **kwargs
    ) -> None:
        """Показать детали конкретного плана."""
        plan_name = callback.data.split(":")[1]

        if plan_name not in self.SUBSCRIPTION_PLANS:
            await callback.answer("План не найден", show_alert=True)
            return

        plan = self.SUBSCRIPTION_PLANS[plan_name]

        async with get_unit_of_work() as uow:
            user = await uow.users.get_by_telegram_id(callback.from_user.id)

            keyboard = await Keyboards.plan_details(
                plan_name=plan_name,
                can_buy=user.subscription_plan != plan_name
            )

            text = await self._format_plan_details(plan_name, plan)

            await self.edit_or_send_message(
                callback,
                text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )

    async def compare_plans(
            self,
            callback: CallbackQuery,
            **kwargs
    ) -> None:
        """Показать сравнение планов."""
        text = await self._format_plans_comparison()

        keyboard = await Keyboards.back_button("show_plans")

        await self.edit_or_send_message(
            callback,
            text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )

    async def select_plan_to_buy(
            self,
            callback: CallbackQuery,
            state: FSMContext,
            **kwargs
    ) -> None:
        """Начать процесс покупки плана."""
        plan_name = callback.data.split(":")[1]

        async with get_unit_of_work() as uow:
            user = await uow.users.get_by_telegram_id(callback.from_user.id)

            # Проверяем, не активен ли уже этот план
            if user.subscription_plan == plan_name:
                await callback.answer(
                    "У вас уже активен этот план",
                    show_alert=True
                )
                return

            # Сохраняем выбранный план
            await state.update_data(
                selected_plan=plan_name,
                base_price=self.SUBSCRIPTION_PLANS[plan_name]["price"]
            )

            # Показываем выбор периода
            keyboard = await Keyboards.payment_period_selection(plan_name)

            text = (
                f"<b>Выберите период оплаты</b>\n\n"
                f"План: <b>{self.SUBSCRIPTION_PLANS[plan_name]['name']}</b>\n\n"
                f"💡 При оплате на длительный период действуют скидки:\n"
                f"• 3 месяца - скидка 10%\n"
                f"• 12 месяцев - скидка 20%"
            )

            await self.edit_or_send_message(
                callback,
                text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )

    async def select_payment_period(
            self,
            callback: CallbackQuery,
            state: FSMContext,
            **kwargs
    ) -> None:
        """Выбор периода оплаты."""
        period = callback.data.split(":")[1]  # 1m, 3m, 12m

        data = await state.get_data()
        plan_name = data["selected_plan"]
        base_price = data["base_price"]

        # Рассчитываем цену с учетом периода
        period_multipliers = {"1m": 1, "3m": 3, "12m": 12}
        period_discounts = {"1m": 0, "3m": 10, "12m": 20}

        multiplier = period_multipliers[period]
        discount = period_discounts[period]

        total_price = base_price * multiplier
        discount_amount = total_price * discount / 100
        final_price = total_price - discount_amount

        await state.update_data(
            payment_period=period,
            total_price=total_price,
            discount_amount=discount_amount,
            final_price=final_price,
            promo_code=None,
            promo_discount=0
        )

        # Показываем выбор способа оплаты
        keyboard = await Keyboards.payment_method_selection(
            amount=final_price,
            has_saved_cards=False  # TODO: проверить сохраненные карты
        )

        text = await self._format_payment_summary(
            plan_name,
            period,
            total_price,
            discount_amount,
            final_price
        )

        await self.edit_or_send_message(
            callback,
            text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )

    async def enter_promo_code(
            self,
            callback: CallbackQuery,
            state: FSMContext,
            **kwargs
    ) -> None:
        """Ввод промокода."""
        await state.set_state(SubscriptionStates.waiting_for_promo)

        text = (
            f"<b>{Emoji.GIFT} Введите промокод</b>\n\n"
            f"Отправьте промокод для получения скидки.\n"
            f"Промокод должен быть активным и подходить "
            f"для выбранного тарифа.\n\n"
            f"<i>Отправьте /cancel для отмены</i>"
        )

        keyboard = await Keyboards.cancel_only()

        await self.edit_or_send_message(
            callback,
            text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )

    async def validate_promo_code(
            self,
            message: Message,
            state: FSMContext,
            **kwargs
    ) -> None:
        """Проверка и применение промокода."""
        promo_code = message.text.strip().upper()

        data = await state.get_data()
        plan_name = data["selected_plan"]

        # Проверяем промокод
        if promo_code not in self.PROMO_CODES:
            await message.answer(
                f"{Emoji.ERROR} Промокод не найден или недействителен.\n"
                f"Попробуйте другой код или продолжите без промокода."
            )
            return

        promo_data = self.PROMO_CODES[promo_code]

        # Проверяем применимость к плану
        if "all" not in promo_data["plans"] and plan_name not in promo_data["plans"]:
            await message.answer(
                f"{Emoji.ERROR} Этот промокод не применим к плану "
                f"{self.SUBSCRIPTION_PLANS[plan_name]['name']}.\n"
                f"Попробуйте другой код."
            )
            return

        # Рассчитываем скидку
        final_price = data["final_price"]

        if promo_data["type"] == "percent":
            promo_discount = final_price * promo_data["discount"] / 100
        else:
            promo_discount = promo_data["discount"]

        new_final_price = max(1, final_price - promo_discount)  # Минимум 1 рубль

        await state.update_data(
            promo_code=promo_code,
            promo_discount=promo_discount,
            final_price=new_final_price
        )

        await state.set_state(None)

        # Обновляем сводку оплаты
        keyboard = await Keyboards.payment_method_selection(
            amount=new_final_price,
            has_saved_cards=False,
            promo_applied=True
        )

        text = await self._format_payment_summary(
            plan_name,
            data["payment_period"],
            data["total_price"],
            data["discount_amount"],
            new_final_price,
            promo_code,
            promo_discount
        )

        await message.answer(
            f"{Emoji.CHECK} Промокод применен! Скидка {promo_data['discount']}%"
        )

        await message.answer(
            text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )

    async def select_payment_method(
            self,
            callback: CallbackQuery,
            state: FSMContext,
            **kwargs
    ) -> None:
        """Выбор способа оплаты."""
        method = callback.data.split(":")[1]

        data = await state.get_data()
        await state.update_data(payment_method=method)

        # В зависимости от метода запускаем соответствующий процесс
        if method == "telegram_stars":
            await self._process_telegram_stars_payment(callback, state)
        elif method == "yookassa":
            await self._process_yookassa_payment(callback, state)
        elif method == "crypto":
            await self._process_crypto_payment(callback, state)
        else:
            await callback.answer(
                "Этот способ оплаты временно недоступен",
                show_alert=True
            )

    async def show_current_subscription(
            self,
            callback: CallbackQuery,
            **kwargs
    ) -> None:
        """Показать текущую подписку."""
        async with get_unit_of_work() as uow:
            user = await uow.users.get_by_telegram_id(callback.from_user.id)
            subscription = await uow.subscriptions.get_active(user.id)

            if not subscription:
                await callback.answer(
                    "У вас нет активной подписки",
                    show_alert=True
                )
                return

            # Получаем статистику использования
            usage_stats = await uow.subscriptions.get_usage_stats(
                user.id,
                subscription.id
            )

            keyboard = await Keyboards.current_subscription_management(
                subscription=subscription,
                can_upgrade=user.subscription_plan != "vip"
            )

            text = await self._format_current_subscription(
                subscription,
                usage_stats
            )

            await self.edit_or_send_message(
                callback,
                text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )

    async def toggle_auto_renew(
            self,
            callback: CallbackQuery,
            **kwargs
    ) -> None:
        """Переключить автопродление."""
        async with get_unit_of_work() as uow:
            user = await uow.users.get_by_telegram_id(callback.from_user.id)
            subscription = await uow.subscriptions.get_active(user.id)

            if not subscription:
                await callback.answer("Подписка не найдена", show_alert=True)
                return

            # Переключаем автопродление
            subscription.auto_renew = not subscription.auto_renew
            await uow.commit()

            status = "включено" if subscription.auto_renew else "выключено"
            await callback.answer(
                f"Автопродление {status}",
                show_alert=False
            )

            # Обновляем меню
            await self.show_current_subscription(callback)

    async def show_payment_history(
            self,
            callback: CallbackQuery,
            **kwargs
    ) -> None:
        """Показать историю платежей."""
        async with get_unit_of_work() as uow:
            user = await uow.users.get_by_telegram_id(callback.from_user.id)

            payments = await uow.payments.get_user_payments(
                user.id,
                limit=10
            )

            if not payments:
                await callback.answer(
                    "История платежей пуста",
                    show_alert=True
                )
                return

            keyboard = await Keyboards.payment_history(
                payments=payments,
                page=1
            )

            text = await self._format_payment_history(payments)

            await self.edit_or_send_message(
                callback,
                text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )

    async def start_cancellation(
            self,
            callback: CallbackQuery,
            **kwargs
    ) -> None:
        """Начать процесс отмены подписки."""
        async with get_unit_of_work() as uow:
            user = await uow.users.get_by_telegram_id(callback.from_user.id)
            subscription = await uow.subscriptions.get_active(user.id)

            if not subscription:
                await callback.answer(
                    "У вас нет активной подписки",
                    show_alert=True
                )
                return

            # Показываем причины и альтернативы
            keyboard = await Keyboards.cancellation_reasons()

            text = (
                f"<b>{Emoji.WARNING} Отмена подписки</b>\n\n"
                f"Вы действительно хотите отменить подписку?\n\n"
                f"<b>Что вы потеряете:</b>\n"
                f"• Доступ к расширенным раскладам\n"
                f"• Персональные прогнозы\n"
                f"• История и статистика\n\n"
                f"Подписка будет активна до: "
                f"{subscription.end_date.strftime('%d.%m.%Y')}\n\n"
                f"Выберите причину отмены:"
            )

            await self.edit_or_send_message(
                callback,
                text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )

    async def confirm_cancellation(
            self,
            callback: CallbackQuery,
            **kwargs
    ) -> None:
        """Подтвердить отмену подписки."""
        reason = callback.data.split(":")[1]

        async with get_unit_of_work() as uow:
            user = await uow.users.get_by_telegram_id(callback.from_user.id)
            subscription = await uow.subscriptions.get_active(user.id)

            if not subscription:
                await callback.answer("Подписка не найдена", show_alert=True)
                return

            # Отменяем автопродление
            subscription.auto_renew = False
            subscription.cancellation_reason = reason
            subscription.cancelled_at = datetime.utcnow()

            await uow.commit()

            # Отправляем подтверждение
            await callback.answer("Подписка отменена", show_alert=False)

            keyboard = await Keyboards.subscription_cancelled()

            text = (
                f"{Emoji.CHECK} <b>Подписка отменена</b>\n\n"
                f"Ваша подписка будет активна до "
                f"{subscription.end_date.strftime('%d.%m.%Y')}.\n\n"
                f"После этой даты доступ к платным функциям "
                f"будет ограничен.\n\n"
                f"Вы всегда можете возобновить подписку в любой момент!"
            )

            await self.edit_or_send_message(
                callback,
                text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )

    # Обработчики платежей

    async def pre_checkout_handler(
            self,
            pre_checkout_query: PreCheckoutQuery,
            **kwargs
    ) -> None:
        """Обработчик предварительной проверки платежа."""
        # Проверяем, что платеж корректный
        await pre_checkout_query.answer(ok=True)

    async def successful_payment_handler(
            self,
            message: Message,
            **kwargs
    ) -> None:
        """Обработчик успешного платежа."""
        payment = message.successful_payment

        async with get_unit_of_work() as uow:
            user = await self.get_or_create_user(uow, message.from_user)

            # Парсим payload для получения деталей
            payload_parts = payment.invoice_payload.split(":")
            plan_name = payload_parts[0]
            period = payload_parts[1]

            # Создаем запись о платеже
            payment_record = await uow.payments.create(
                user_id=user.id,
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
                user_id=user.id,
                plan_name=plan_name,
                duration_days=duration_days,
                payment_id=payment_record.id
            )

            # Обновляем план пользователя
            user.subscription_plan = plan_name

            await uow.commit()

            # Отправляем подтверждение
            keyboard = await Keyboards.payment_success()

            text = (
                f"{Emoji.CHECK} <b>Оплата прошла успешно!</b>\n\n"
                f"План: <b>{self.SUBSCRIPTION_PLANS[plan_name]['name']}</b>\n"
                f"Действует до: {subscription.end_date.strftime('%d.%m.%Y')}\n\n"
                f"Спасибо за доверие! Теперь вам доступны "
                f"все возможности выбранного плана.\n\n"
                f"Чек об оплате отправлен вам в личные сообщения."
            )

            await message.answer(
                text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )

    # Вспомогательные методы

    async def _format_subscription_status(
            self,
            user,
            subscription: Optional[Any]
    ) -> str:
        """Форматировать статус подписки."""
        builder = MessageBuilder(MessageStyle.HTML)

        builder.add_bold(f"{Emoji.PAYMENT} Управление подпиской").add_line(2)

        if subscription and subscription.is_active:
            plan_name = self.SUBSCRIPTION_PLANS[user.subscription_plan]["name"]
            days_left = (subscription.end_date - datetime.utcnow()).days

            builder.add_text(f"<b>Текущий план:</b> {plan_name}").add_line()
            builder.add_text(
                f"<b>Действует до:</b> "
                f"{subscription.end_date.strftime('%d.%m.%Y')}"
            ).add_line()
            builder.add_text(f"<b>Осталось дней:</b> {days_left}").add_line()

            if subscription.auto_renew:
                builder.add_text("✅ Автопродление включено").add_line()
            else:
                builder.add_text("❌ Автопродление выключено").add_line()
        else:
            builder.add_text(
                "У вас нет активной подписки.\n"
                "Выберите подходящий план и откройте все возможности!"
            ).add_line()

        builder.add_line()
        builder.add_italic("Выберите действие:")

        return builder.build()

    async def _format_plans_overview(self) -> str:
        """Форматировать обзор планов."""
        builder = MessageBuilder(MessageStyle.HTML)

        builder.add_bold("Доступные планы подписки").add_line(2)

        for plan_key, plan in self.SUBSCRIPTION_PLANS.items():
            if plan_key == "basic":
                emoji = "⭐"
            elif plan_key == "premium":
                emoji = "💎"
            else:
                emoji = "👑"

            builder.add_bold(f"{emoji} {plan['name']} - {plan['price']} ₽/мес").add_line()
            builder.add_list(plan["features"][:3])
            builder.add_line()

        builder.add_italic(
            "Выберите план для подробной информации или "
            "сравните все планы"
        )

        return builder.build()

    async def _format_plan_details(
            self,
            plan_name: str,
            plan: Dict[str, Any]
    ) -> str:
        """Форматировать детали плана."""
        builder = MessageBuilder(MessageStyle.HTML)

        emoji_map = {"basic": "⭐", "premium": "💎", "vip": "👑"}
        emoji = emoji_map.get(plan_name, "📦")

        builder.add_bold(f"{emoji} План {plan['name']}").add_line()
        builder.add_text(f"<b>{plan['price']} ₽</b> в месяц").add_line(2)

        builder.add_bold("Что входит:").add_line()
        builder.add_list(plan["features"])
        builder.add_line()

        # Лимиты
        builder.add_bold("Лимиты:").add_line()
        limits = plan["limits"]

        if limits["tarot_spreads"] == -1:
            builder.add_text("• Расклады Таро: безлимит").add_line()
        else:
            builder.add_text(f"• Расклады Таро: {limits['tarot_spreads']}/мес").add_line()

        if limits["horoscopes"] == "all":
            builder.add_text("• Гороскопы: все типы").add_line()
        else:
            builder.add_text("• Гороскопы: дневные и недельные").add_line()

        if limits.get("natal_chart"):
            builder.add_text("• Натальная карта: ✅").add_line()

        if limits.get("transits"):
            builder.add_text("• Транзиты планет: ✅").add_line()

        if limits.get("synastry"):
            builder.add_text("• Анализ совместимости: ✅").add_line()

        return builder.build()

    async def _format_plans_comparison(self) -> str:
        """Форматировать сравнение планов."""
        text = (
            "<b>Сравнение планов подписки</b>\n\n"
            "<b>Функция | Free | Basic | Premium | VIP</b>\n"
            "➖➖➖➖➖➖➖➖➖➖➖➖➖\n"
            "Карта дня | ✅ | ✅ | ✅ | ✅\n"
            "Расклады/мес | 3 | 30 | ∞ | ∞\n"
            "История | ❌ | ✅ | ✅ | ✅\n"
            "Дневной гороскоп | ✅ | ✅ | ✅ | ✅\n"
            "Недельный | ❌ | ✅ | ✅ | ✅\n"
            "Месячный | ❌ | ❌ | ✅ | ✅\n"
            "Годовой | ❌ | ❌ | ✅ | ✅\n"
            "Натальная карта | ❌ | ❌ | ✅ | ✅\n"
            "Транзиты | ❌ | ❌ | ✅ | ✅\n"
            "Совместимость | ❌ | ❌ | ❌ | ✅\n"
            "Личный астролог | ❌ | ❌ | ❌ | ✅\n"
            "Поддержка | База | База | VIP | 24/7\n"
            "➖➖➖➖➖➖➖➖➖➖➖➖➖\n"
            "<b>Цена | 0₽ | 299₽ | 599₽ | 999₽</b>"
        )

        return text

    async def _format_payment_summary(
            self,
            plan_name: str,
            period: str,
            total_price: float,
            discount_amount: float,
            final_price: float,
            promo_code: Optional[str] = None,
            promo_discount: float = 0
    ) -> str:
        """Форматировать сводку платежа."""
        plan = self.SUBSCRIPTION_PLANS[plan_name]
        period_names = {"1m": "1 месяц", "3m": "3 месяца", "12m": "12 месяцев"}

        builder = MessageBuilder(MessageStyle.HTML)

        builder.add_bold(f"{Emoji.CART} Оформление подписки").add_line(2)

        builder.add_text(f"<b>План:</b> {plan['name']}").add_line()
        builder.add_text(f"<b>Период:</b> {period_names[period]}").add_line(2)

        builder.add_text(f"Стоимость: {total_price:.0f} ₽").add_line()

        if discount_amount > 0:
            builder.add_text(f"Скидка за период: -{discount_amount:.0f} ₽").add_line()

        if promo_code:
            builder.add_text(
                f"Промокод {promo_code}: -{promo_discount:.0f} ₽"
            ).add_line()

        builder.add_line()
        builder.add_bold(f"Итого: {final_price:.0f} ₽").add_line(2)

        builder.add_italic("Выберите способ оплаты:")

        return builder.build()

    async def _format_current_subscription(
            self,
            subscription,
            usage_stats: Dict[str, Any]
    ) -> str:
        """Форматировать информацию о текущей подписке."""
        plan = self.SUBSCRIPTION_PLANS[subscription.plan_name]
        days_left = (subscription.end_date - datetime.utcnow()).days

        builder = MessageBuilder(MessageStyle.HTML)

        builder.add_bold(f"Ваша подписка {plan['name']}").add_line(2)

        # Статус
        builder.add_text(
            f"<b>Активна до:</b> {subscription.end_date.strftime('%d.%m.%Y')}"
        ).add_line()
        builder.add_text(f"<b>Осталось дней:</b> {days_left}").add_line()

        if subscription.auto_renew:
            builder.add_text("✅ Автопродление включено").add_line()
        else:
            builder.add_text("❌ Автопродление выключено").add_line()

        builder.add_line()

        # Использование
        builder.add_bold("Использование в этом месяце:").add_line()

        if plan["limits"]["tarot_spreads"] == -1:
            builder.add_text(
                f"• Расклады Таро: {usage_stats.get('tarot_spreads', 0)}"
            ).add_line()
        else:
            used = usage_stats.get('tarot_spreads', 0)
            limit = plan["limits"]["tarot_spreads"]
            builder.add_text(f"• Расклады Таро: {used}/{limit}").add_line()

        builder.add_text(
            f"• Гороскопы: {usage_stats.get('horoscopes', 0)}"
        ).add_line()

        if usage_stats.get('natal_charts'):
            builder.add_text(
                f"• Натальные карты: {usage_stats['natal_charts']}"
            ).add_line()

        return builder.build()

    async def _format_payment_history(
            self,
            payments: List[Any]
    ) -> str:
        """Форматировать историю платежей."""
        builder = MessageBuilder(MessageStyle.HTML)

        builder.add_bold(f"{Emoji.HISTORY} История платежей").add_line(2)

        total_amount = sum(p.amount for p in payments)

        builder.add_text(
            f"Всего платежей: {len(payments)} на сумму {total_amount:.0f} ₽"
        ).add_line(2)

        for payment in payments[:5]:  # Показываем последние 5
            status_emoji = "✅" if payment.status == "completed" else "⏳"

            builder.add_text(
                f"{status_emoji} {payment.created_at.strftime('%d.%m.%Y')} - "
                f"{payment.amount:.0f} ₽ ({payment.plan_name})"
            ).add_line()

        if len(payments) > 5:
            builder.add_line()
            builder.add_italic("Показаны последние 5 платежей")

        return builder.build()

    async def _process_telegram_stars_payment(
            self,
            callback: CallbackQuery,
            state: FSMContext
    ) -> None:
        """Обработать оплату через Telegram Stars."""
        data = await state.get_data()

        plan_name = data["selected_plan"]
        period = data["payment_period"]
        final_price = int(data["final_price"])

        # Создаем инвойс
        await callback.message.answer_invoice(
            title=f"Подписка {self.SUBSCRIPTION_PLANS[plan_name]['name']}",
            description=f"Оплата подписки на {period}",
            payload=f"{plan_name}:{period}",
            provider_token="",  # Для Stars не нужен
            currency="XTR",  # Telegram Stars
            prices=[
                LabeledPrice(
                    label=f"Подписка {self.SUBSCRIPTION_PLANS[plan_name]['name']}",
                    amount=final_price
                )
            ],
            start_parameter=f"subscribe_{plan_name}",
            photo_url="https://example.com/subscription.jpg",  # Заменить на реальное фото
            need_email=True,
            send_email_to_provider=False
        )

        await callback.answer("Создан счет на оплату")

    async def _process_yookassa_payment(
            self,
            callback: CallbackQuery,
            state: FSMContext
    ) -> None:
        """Обработать оплату через ЮKassa."""
        # Здесь должна быть интеграция с ЮKassa API
        # Создание платежа, получение ссылки и т.д.

        await callback.answer(
            "Оплата через ЮKassa временно недоступна",
            show_alert=True
        )

    async def _process_crypto_payment(
            self,
            callback: CallbackQuery,
            state: FSMContext
    ) -> None:
        """Обработать оплату криптовалютой."""
        # Здесь должна быть интеграция с крипто-процессингом

        await callback.answer(
            "Оплата криптовалютой временно недоступна",
            show_alert=True
        )


def setup(router: Router) -> None:
    """Настройка обработчиков подписки."""
    handler = SubscriptionHandlers()
    handler.register_handlers(router)