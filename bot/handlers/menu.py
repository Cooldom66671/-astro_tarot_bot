"""
Обработчик главного меню и навигации.

Этот модуль отвечает за:
- Отображение главного меню
- Навигацию по разделам бота
- Быстрые действия
- Адаптацию интерфейса под уровень подписки
- Переходы между разделами

Автор: AI Assistant
Дата создания: 2024-12-30
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest

from bot.handlers.base import BaseHandler, require_subscription
from infrastructure.telegram import (
    Keyboards,
    MessageFactory,
    MessageStyle,
    MessageEmoji as Emoji
)
from infrastructure import get_unit_of_work

logger = logging.getLogger(__name__)


class MenuHandler(BaseHandler):
    """Обработчик главного меню и навигации."""

    def register_handlers(self, router: Router) -> None:
        """Регистрация обработчиков меню."""
        # Команда /menu
        router.message.register(
            self.cmd_menu,
            Command("menu")
        )

        # Главное меню через callback
        router.callback_query.register(
            self.show_main_menu,
            F.data == "main_menu"
        )

        # Быстрые действия
        router.callback_query.register(
            self.show_quick_actions,
            F.data == "quick_actions"
        )

        # Разделы меню
        router.callback_query.register(
            self.show_tarot_section,
            F.data == "section_tarot"
        )

        router.callback_query.register(
            self.show_astrology_section,
            F.data == "section_astrology"
        )

        router.callback_query.register(
            self.show_subscription_section,
            F.data == "section_subscription"
        )

        router.callback_query.register(
            self.show_profile_section,
            F.data == "section_profile"
        )

        router.callback_query.register(
            self.show_settings_section,
            F.data == "section_settings"
        )

        # Админ панель
        router.callback_query.register(
            self.show_admin_panel,
            F.data == "admin_panel"
        )

        # Навигация "Назад"
        router.callback_query.register(
            self.go_back,
            F.data.startswith("back_to_")
        )

    async def cmd_menu(
            self,
            message: Message,
            state: FSMContext,
            **kwargs
    ) -> None:
        """Обработчик команды /menu."""
        await state.clear()  # Очищаем состояние

        async with get_unit_of_work() as uow:
            user = await self.get_or_create_user(
                uow,
                message.from_user
            )

            # Проверяем новые функции
            new_features = await self._check_new_features(user, uow)

            # Создаем главное меню
            keyboard = await Keyboards.main_menu(
                subscription_level=user.subscription_plan,
                is_admin=user.is_admin,
                has_new_features=new_features
            )

            # Формируем приветствие
            greeting = await self._get_personalized_greeting(user)

            await message.answer(
                greeting,
                reply_markup=keyboard,
                parse_mode="HTML"
            )

    async def show_main_menu(
            self,
            callback: CallbackQuery,
            state: FSMContext,
            **kwargs
    ) -> None:
        """Показать главное меню через callback."""
        await state.clear()

        async with get_unit_of_work() as uow:
            user = await self.get_or_create_user(
                uow,
                callback.from_user
            )

            new_features = await self._check_new_features(user, uow)

            keyboard = await Keyboards.main_menu(
                subscription_level=user.subscription_plan,
                is_admin=user.is_admin,
                has_new_features=new_features
            )

            greeting = await self._get_personalized_greeting(user)

            await self.edit_or_send_message(
                callback,
                greeting,
                reply_markup=keyboard,
                parse_mode="HTML"
            )

    async def show_quick_actions(
            self,
            callback: CallbackQuery,
            **kwargs
    ) -> None:
        """Показать меню быстрых действий."""
        async with get_unit_of_work() as uow:
            user = await uow.users.get_by_telegram_id(
                callback.from_user.id
            )

            keyboard = await Keyboards.quick_actions(
                subscription_level=user.subscription_plan
            )

            text = MessageFactory.create(
                "quick_actions",
                MessageStyle.MARKDOWN_V2,
                user_name=user.display_name
            )

            await self.edit_or_send_message(
                callback,
                text,
                reply_markup=keyboard
            )

    async def show_tarot_section(
            self,
            callback: CallbackQuery,
            **kwargs
    ) -> None:
        """Показать раздел Таро."""
        async with get_unit_of_work() as uow:
            user = await uow.users.get_by_telegram_id(
                callback.from_user.id
            )

            # Получаем статистику пользователя
            stats = await uow.tarot.get_user_statistics(user.id)

            keyboard = await Keyboards.tarot_menu(
                subscription_level=user.subscription_plan,
                has_saved_spreads=stats.get("total_spreads", 0) > 0
            )

            text = await self._format_tarot_menu(user, stats)

            await self.edit_or_send_message(
                callback,
                text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )

    async def show_astrology_section(
            self,
            callback: CallbackQuery,
            **kwargs
    ) -> None:
        """Показать раздел астрологии."""
        async with get_unit_of_work() as uow:
            user = await uow.users.get_by_telegram_id(
                callback.from_user.id
            )

            has_birth_data = bool(user.birth_data)

            keyboard = await Keyboards.astrology_menu(
                subscription_level=user.subscription_plan,
                has_birth_data=has_birth_data
            )

            text = await self._format_astrology_menu(
                user,
                has_birth_data
            )

            await self.edit_or_send_message(
                callback,
                text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )

    async def show_subscription_section(
            self,
            callback: CallbackQuery,
            **kwargs
    ) -> None:
        """Показать раздел подписки."""
        async with get_unit_of_work() as uow:
            user = await uow.users.get_by_telegram_id(
                callback.from_user.id
            )

            subscription = await uow.subscriptions.get_active(user.id)

            keyboard = await Keyboards.subscription_menu(
                current_plan=user.subscription_plan,
                subscription=subscription
            )

            text = await self._format_subscription_menu(
                user,
                subscription
            )

            await self.edit_or_send_message(
                callback,
                text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )

    async def show_profile_section(
            self,
            callback: CallbackQuery,
            **kwargs
    ) -> None:
        """Показать раздел профиля."""
        async with get_unit_of_work() as uow:
            user = await uow.users.get_by_telegram_id(
                callback.from_user.id
            )

            # Получаем общую статистику
            tarot_stats = await uow.tarot.get_user_statistics(user.id)
            astro_stats = await uow.astrology.get_user_statistics(user.id)

            keyboard = await Keyboards.profile_menu(
                has_birth_data=bool(user.birth_data),
                has_history=tarot_stats.get("total_spreads", 0) > 0
            )

            text = await self._format_profile_menu(
                user,
                tarot_stats,
                astro_stats
            )

            await self.edit_or_send_message(
                callback,
                text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )

    async def show_settings_section(
            self,
            callback: CallbackQuery,
            **kwargs
    ) -> None:
        """Показать раздел настроек."""
        async with get_unit_of_work() as uow:
            user = await uow.users.get_by_telegram_id(
                callback.from_user.id
            )

            keyboard = await Keyboards.settings_menu(
                notifications_enabled=user.notifications_enabled,
                language=user.language
            )

            text = await self._format_settings_menu(user)

            await self.edit_or_send_message(
                callback,
                text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )

    @require_subscription("vip")
    async def show_admin_panel(
            self,
            callback: CallbackQuery,
            **kwargs
    ) -> None:
        """Показать админ панель (только для администраторов)."""
        async with get_unit_of_work() as uow:
            user = await uow.users.get_by_telegram_id(
                callback.from_user.id
            )

            if not user.is_admin:
                await callback.answer(
                    "У вас нет доступа к админ панели",
                    show_alert=True
                )
                return

            # Получаем статистику системы
            stats = await self._get_system_stats(uow)

            keyboard = await Keyboards.admin_menu()

            text = await self._format_admin_menu(stats)

            await self.edit_or_send_message(
                callback,
                text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )

    async def go_back(
            self,
            callback: CallbackQuery,
            state: FSMContext,
            **kwargs
    ) -> None:
        """Обработчик кнопки 'Назад'."""
        destination = callback.data.replace("back_to_", "")

        # Мапинг destinations на обработчики
        handlers_map = {
            "main": self.show_main_menu,
            "tarot": self.show_tarot_section,
            "astrology": self.show_astrology_section,
            "subscription": self.show_subscription_section,
            "profile": self.show_profile_section,
            "settings": self.show_settings_section,
            "quick_actions": self.show_quick_actions
        }

        handler = handlers_map.get(destination, self.show_main_menu)
        await handler(callback, state, **kwargs)

    # Вспомогательные методы

    async def _get_personalized_greeting(
            self,
            user
    ) -> str:
        """Получить персонализированное приветствие."""
        hour = datetime.now().hour

        if 5 <= hour < 12:
            time_greeting = "Доброе утро"
        elif 12 <= hour < 17:
            time_greeting = "Добрый день"
        elif 17 <= hour < 23:
            time_greeting = "Добрый вечер"
        else:
            time_greeting = "Доброй ночи"

        name = user.display_name or "путешественник"

        # Добавляем информацию о подписке
        if user.subscription_plan == "vip":
            status = f"{Emoji.CROWN} VIP статус"
        elif user.subscription_plan == "premium":
            status = f"{Emoji.STAR} Premium подписка"
        elif user.subscription_plan == "basic":
            status = f"{Emoji.CHECK} Basic подписка"
        else:
            status = "Бесплатный аккаунт"

        return (
            f"<b>{time_greeting}, {name}!</b>\n\n"
            f"{status}\n\n"
            f"Выберите раздел или воспользуйтесь быстрыми действиями:"
        )

    async def _check_new_features(self, user, uow) -> bool:
        """Проверить наличие новых функций для пользователя."""
        # Здесь можно добавить логику проверки новых функций
        # Например, непрочитанные уведомления, новые расклады и т.д.
        last_login = user.last_active
        if last_login:
            days_since_login = (datetime.utcnow() - last_login).days
            return days_since_login > 7
        return False

    async def _format_tarot_menu(self, user, stats) -> str:
        """Форматировать меню раздела Таро."""
        total_spreads = stats.get("total_spreads", 0)
        favorite_spread = stats.get("favorite_spread", "Карта дня")

        text = (
            f"<b>{Emoji.CARDS} Раздел Таро</b>\n\n"
            f"Откройте тайны судьбы с помощью карт Таро.\n\n"
        )

        if total_spreads > 0:
            text += (
                f"📊 <b>Ваша статистика:</b>\n"
                f"• Раскладов выполнено: {total_spreads}\n"
                f"• Любимый расклад: {favorite_spread}\n\n"
            )

        text += "Выберите действие:"

        return text

    async def _format_astrology_menu(
            self,
            user,
            has_birth_data: bool
    ) -> str:
        """Форматировать меню раздела астрологии."""
        text = (
            f"<b>{Emoji.STARS} Раздел астрологии</b>\n\n"
            f"Узнайте, что говорят звезды о вашей судьбе.\n\n"
        )

        if has_birth_data:
            text += f"✅ Данные рождения сохранены\n\n"
        else:
            text += (
                f"⚠️ <i>Для персональных прогнозов добавьте "
                f"данные рождения в профиле</i>\n\n"
            )

        text += "Выберите действие:"

        return text

    async def _format_subscription_menu(
            self,
            user,
            subscription
    ) -> str:
        """Форматировать меню подписки."""
        plan_names = {
            "free": "Бесплатный",
            "basic": "Basic",
            "premium": "Premium",
            "vip": "VIP"
        }

        text = (
            f"<b>{Emoji.PAYMENT} Управление подпиской</b>\n\n"
            f"Текущий тариф: <b>{plan_names[user.subscription_plan]}</b>\n"
        )

        if subscription and subscription.is_active:
            days_left = (subscription.end_date - datetime.utcnow()).days
            text += (
                f"Действует до: {subscription.end_date.strftime('%d.%m.%Y')}\n"
                f"Осталось дней: {days_left}\n"
            )

            if subscription.auto_renew:
                text += f"✅ Автопродление включено\n"

        text += "\nВыберите действие:"

        return text

    async def _format_profile_menu(
            self,
            user,
            tarot_stats,
            astro_stats
    ) -> str:
        """Форматировать меню профиля."""
        text = (
            f"<b>{Emoji.USER} Ваш профиль</b>\n\n"
            f"<b>Имя:</b> {user.display_name or 'Не указано'}\n"
            f"<b>ID:</b> <code>{user.telegram_id}</code>\n"
            f"<b>Дата регистрации:</b> {user.created_at.strftime('%d.%m.%Y')}\n"
        )

        if user.birth_data:
            text += f"<b>Дата рождения:</b> {user.birth_data.get('date', 'Не указана')}\n"

        # Статистика использования
        total_actions = (
                tarot_stats.get("total_spreads", 0) +
                astro_stats.get("total_horoscopes", 0)
        )

        if total_actions > 0:
            text += (
                f"\n<b>📊 Статистика:</b>\n"
                f"• Раскладов Таро: {tarot_stats.get('total_spreads', 0)}\n"
                f"• Гороскопов: {astro_stats.get('total_horoscopes', 0)}\n"
            )

        text += "\nВыберите действие:"

        return text

    async def _format_settings_menu(self, user) -> str:
        """Форматировать меню настроек."""
        notifications = "Включены" if user.notifications_enabled else "Выключены"
        language = "Русский" if user.language == "ru" else "English"

        text = (
            f"<b>{Emoji.SETTINGS} Настройки</b>\n\n"
            f"<b>Уведомления:</b> {notifications}\n"
            f"<b>Язык:</b> {language}\n"
            f"<b>Часовой пояс:</b> {user.timezone or 'UTC'}\n\n"
            f"Выберите параметр для изменения:"
        )

        return text

    async def _get_system_stats(self, uow) -> dict:
        """Получить статистику системы для админ панели."""
        # Получаем статистику из БД
        total_users = await uow.users.count_total()
        active_users = await uow.users.count_active(days=7)

        subscriptions = await uow.subscriptions.count_by_plan()

        # Доходы за месяц
        monthly_revenue = await uow.payments.get_monthly_revenue()

        return {
            "total_users": total_users,
            "active_users": active_users,
            "subscriptions": subscriptions,
            "monthly_revenue": monthly_revenue
        }

    async def _format_admin_menu(self, stats) -> str:
        """Форматировать админ меню."""
        text = (
            f"<b>{Emoji.ADMIN} Панель администратора</b>\n\n"
            f"<b>📊 Статистика системы:</b>\n"
            f"• Всего пользователей: {stats['total_users']}\n"
            f"• Активных (7 дней): {stats['active_users']}\n\n"
            f"<b>💳 Подписки:</b>\n"
        )

        for plan, count in stats['subscriptions'].items():
            text += f"• {plan.upper()}: {count}\n"

        text += (
            f"\n<b>💰 Доход за месяц:</b> "
            f"{stats['monthly_revenue']:,.0f} ₽\n\n"
            f"Выберите действие:"
        )

        return text


def setup(router: Router) -> None:
    """Настройка обработчиков меню."""
    handler = MenuHandler()
    handler.register_handlers(router)