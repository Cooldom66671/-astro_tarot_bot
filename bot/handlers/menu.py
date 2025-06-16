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
from typing import Optional, Dict, Any

from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
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
from infrastructure import get_unit_of_work
from config import settings

# НОВЫЕ ИМПОРТЫ ДЛЯ КЛАВИАТУР
from infrastructure.telegram.keyboards import (
    get_main_menu,
    get_section_menu,
    MainMenuSection,
    QuickActionsKeyboard,
    SectionMenuKeyboard,
    MainMenuCallbackData,
    QuickActionCallbackData,
    Keyboards
)

logger = logging.getLogger(__name__)


class MenuHandler(BaseHandler):
    """Обработчик главного меню и навигации."""

    def register_handlers(self) -> None:
        """Регистрация обработчиков меню."""
        # Команда /menu
        self.router.message.register(
            self.cmd_menu,
            Command("menu")
        )

        # Главное меню через callback
        self.router.callback_query.register(
            self.show_main_menu,
            F.data == "main_menu"
        )

        # Быстрые действия через новый callback data
        self.router.callback_query.register(
            self.quick_action_handler,
            QuickActionCallbackData.filter()
        )

        # Разделы меню через новый callback data
        self.router.callback_query.register(
            self.section_handler,
            MainMenuCallbackData.filter()
        )

        # Обратная совместимость со старыми callback
        self.router.callback_query.register(
            self.show_quick_actions,
            F.data == "quick_actions"
        )

        # Старые callback для разделов (для обратной совместимости)
        for section in ["tarot", "astrology", "subscription", "profile", "settings"]:
            self.router.callback_query.register(
                self.legacy_section_handler,
                F.data == f"section_{section}"
            )

        # Админ панель
        self.router.callback_query.register(
            self.show_admin_panel,
            F.data == "admin_panel"
        )

        # Навигация "Назад"
        self.router.callback_query.register(
            self.go_back,
            F.data.startswith("back_to_")
        )

    @error_handler()
    @log_action("menu_command")
    async def cmd_menu(
            self,
            message: Message,
            state: FSMContext,
            **kwargs
    ) -> None:
        """Обработчик команды /menu."""
        await state.clear()  # Очищаем состояние

        # Получаем пользователя
        user = await get_or_create_user(message.from_user)

        async with get_unit_of_work() as uow:
            user_db = await uow.users.get_by_telegram_id(message.from_user.id)

            # ИСПОЛЬЗУЕМ НОВУЮ ФУНКЦИЮ ДЛЯ ГЛАВНОГО МЕНЮ
            keyboard = await get_main_menu(
                user_subscription=user_db.subscription_plan if hasattr(user_db, 'subscription_plan') else 'free',
                is_admin=message.from_user.id in settings.bot.admin_ids,
                user_name=message.from_user.first_name
            )

            # Формируем приветствие
            greeting = self._get_personalized_greeting(user_db)

            await message.answer(
                greeting,
                reply_markup=keyboard,
                parse_mode="HTML"
            )

    @error_handler()
    async def show_main_menu(
            self,
            callback: CallbackQuery,
            state: FSMContext,
            **kwargs
    ) -> None:
        """Показать главное меню через callback."""
        await state.clear()

        async with get_unit_of_work() as uow:
            user = await uow.users.get_by_telegram_id(callback.from_user.id)

            if not user:
                user = await get_or_create_user(callback.from_user)

            # ИСПОЛЬЗУЕМ НОВУЮ ФУНКЦИЮ
            keyboard = await get_main_menu(
                user_subscription=user.subscription_plan if hasattr(user, 'subscription_plan') else 'free',
                is_admin=callback.from_user.id in settings.bot.admin_ids,
                user_name=callback.from_user.first_name
            )

            greeting = self._get_personalized_greeting(user)

            await edit_or_send_message(
                callback.message,
                greeting,
                reply_markup=keyboard,
                parse_mode="HTML"
            )

        await answer_callback_query(callback)

    @error_handler()
    async def quick_action_handler(
            self,
            callback: CallbackQuery,
            callback_data: QuickActionCallbackData,
            state: FSMContext,
            **kwargs
    ) -> None:
        """Обработчик быстрых действий через новый callback data."""
        action = callback_data.action_type

        if action == "daily_card":
            await callback.answer("🎴 Переход к карте дня...")
            # TODO: вызвать обработчик таро

        elif action == "daily_horoscope":
            await callback.answer("⭐ Переход к гороскопу...")
            # TODO: вызвать обработчик астрологии

        elif action == "quick_spread":
            await callback.answer("🔮 Переход к быстрому раскладу...")
            # TODO: вызвать обработчик быстрого расклада

        elif action == "moon_phase":
            await callback.answer("🌙 Загрузка лунного календаря...")
            # TODO: показать фазу луны

    @error_handler()
    async def section_handler(
            self,
            callback: CallbackQuery,
            callback_data: MainMenuCallbackData,
            state: FSMContext,
            **kwargs
    ) -> None:
        """Обработчик выбора раздела через новый callback data."""
        section = callback_data.section

        # Конвертируем в enum
        try:
            section_enum = MainMenuSection(section)
        except ValueError:
            await answer_callback_query(callback, "Неизвестный раздел", show_alert=True)
            return

        # ИСПОЛЬЗУЕМ НОВУЮ ФУНКЦИЮ ДЛЯ МЕНЮ РАЗДЕЛА
        async with get_unit_of_work() as uow:
            user = await uow.users.get_by_telegram_id(callback.from_user.id)

            keyboard = await get_section_menu(
                section_enum,
                user_subscription=user.subscription_plan if user and hasattr(user, 'subscription_plan') else 'free'
            )

            # Получаем текст для раздела
            text = self._get_section_text(section_enum, user)

            await edit_or_send_message(
                callback.message,
                text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )

        await answer_callback_query(callback)

    @error_handler()
    async def legacy_section_handler(
            self,
            callback: CallbackQuery,
            state: FSMContext,
            **kwargs
    ) -> None:
        """Обработчик старых callback для обратной совместимости."""
        section_name = callback.data.replace("section_", "")

        # Создаем новый callback data
        try:
            section_enum = MainMenuSection(section_name.upper())
            new_callback_data = MainMenuCallbackData(
                action="select",
                section=section_enum.value
            )

            # Вызываем новый обработчик
            await self.section_handler(callback, new_callback_data, state, **kwargs)
        except ValueError:
            await self.show_legacy_section(callback, state, **kwargs)

    @error_handler()
    async def show_quick_actions(
            self,
            callback: CallbackQuery,
            state: FSMContext,
            **kwargs
    ) -> None:
        """Показать меню быстрых действий."""
        async with get_unit_of_work() as uow:
            user = await uow.users.get_by_telegram_id(callback.from_user.id)

            # ИСПОЛЬЗУЕМ НОВУЮ КЛАВИАТУРУ
            keyboard = QuickActionsKeyboard(
                user_subscription=user.subscription_plan if user and hasattr(user, 'subscription_plan') else 'free'
            )

            kb = await keyboard.build()

            text = (
                "⚡ <b>Быстрые действия</b>\n\n"
                "Выберите, что вы хотите сделать прямо сейчас:"
            )

            await edit_or_send_message(
                callback.message,
                text,
                reply_markup=kb,
                parse_mode="HTML"
            )

        await answer_callback_query(callback)

    # Оставляем старые методы для обратной совместимости
    async def show_legacy_section(
            self,
            callback: CallbackQuery,
            state: FSMContext,
            **kwargs
    ) -> None:
        """Показать раздел (старый метод)."""
        section = callback.data.replace("section_", "")

        if section == "tarot":
            await self.show_tarot_section(callback, state, **kwargs)
        elif section == "astrology":
            await self.show_astrology_section(callback, state, **kwargs)
        elif section == "subscription":
            await self.show_subscription_section(callback, state, **kwargs)
        elif section == "profile":
            await self.show_profile_section(callback, state, **kwargs)
        elif section == "settings":
            await self.show_settings_section(callback, state, **kwargs)

    @error_handler()
    async def show_tarot_section(
            self,
            callback: CallbackQuery,
            state: FSMContext,
            **kwargs
    ) -> None:
        """Показать раздел Таро."""
        async with get_unit_of_work() as uow:
            user = await uow.users.get_by_telegram_id(callback.from_user.id)

            # Получаем статистику
            stats = await uow.tarot.get_user_statistics(user.id) if user else {}

            # ИСПОЛЬЗУЕМ НОВЫЕ КЛАВИАТУРЫ
            from infrastructure.telegram.keyboards import TarotSection
            keyboard = await get_section_menu(
                MainMenuSection.TAROT,
                user_subscription=user.subscription_plan if user and hasattr(user, 'subscription_plan') else 'free'
            )

            text = self._format_tarot_menu(user, stats)

            await edit_or_send_message(
                callback.message,
                text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )

        await answer_callback_query(callback)

    @error_handler()
    async def show_astrology_section(
            self,
            callback: CallbackQuery,
            state: FSMContext,
            **kwargs
    ) -> None:
        """Показать раздел Астрология."""
        async with get_unit_of_work() as uow:
            user = await uow.users.get_by_telegram_id(callback.from_user.id)

            # Получаем статистику
            stats = await uow.astrology.get_user_statistics(user.id) if user else {}

            # ИСПОЛЬЗУЕМ НОВЫЕ КЛАВИАТУРЫ
            keyboard = await get_section_menu(
                MainMenuSection.ASTROLOGY,
                user_subscription=user.subscription_plan if user and hasattr(user, 'subscription_plan') else 'free'
            )

            text = self._format_astrology_menu(user, stats)

            await edit_or_send_message(
                callback.message,
                text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )

        await answer_callback_query(callback)

    @error_handler()
    async def show_subscription_section(
            self,
            callback: CallbackQuery,
            state: FSMContext,
            **kwargs
    ) -> None:
        """Показать раздел Подписка."""
        async with get_unit_of_work() as uow:
            user = await uow.users.get_by_telegram_id(callback.from_user.id)

            # Получаем текущую подписку
            subscription = await uow.subscriptions.get_active_by_user_id(user.id) if user else None

            # ИСПОЛЬЗУЕМ НОВЫЕ КЛАВИАТУРЫ
            keyboard = await get_section_menu(
                MainMenuSection.SUBSCRIPTION,
                user_subscription=user.subscription_plan if user and hasattr(user, 'subscription_plan') else 'free'
            )

            text = self._format_subscription_menu(user, subscription)

            await edit_or_send_message(
                callback.message,
                text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )

        await answer_callback_query(callback)

    @error_handler()
    async def show_profile_section(
            self,
            callback: CallbackQuery,
            state: FSMContext,
            **kwargs
    ) -> None:
        """Показать раздел Профиль."""
        async with get_unit_of_work() as uow:
            user = await uow.users.get_by_telegram_id(callback.from_user.id)

            if not user:
                await answer_callback_query(callback, "Профиль не найден", show_alert=True)
                return

            # Получаем статистику
            tarot_stats = await uow.tarot.get_user_statistics(user.id)
            astro_stats = await uow.astrology.get_user_statistics(user.id)

            # ИСПОЛЬЗУЕМ НОВЫЕ КЛАВИАТУРЫ
            keyboard = await get_section_menu(
                MainMenuSection.PROFILE,
                user_subscription=user.subscription_plan if hasattr(user, 'subscription_plan') else 'free'
            )

            text = self._format_profile_menu(user, tarot_stats, astro_stats)

            await edit_or_send_message(
                callback.message,
                text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )

        await answer_callback_query(callback)

    @error_handler()
    async def show_settings_section(
            self,
            callback: CallbackQuery,
            state: FSMContext,
            **kwargs
    ) -> None:
        """Показать раздел Настройки."""
        async with get_unit_of_work() as uow:
            user = await uow.users.get_by_telegram_id(callback.from_user.id)

            # ИСПОЛЬЗУЕМ НОВЫЕ КЛАВИАТУРЫ
            keyboard = await get_section_menu(
                MainMenuSection.SETTINGS,
                user_subscription=user.subscription_plan if user and hasattr(user, 'subscription_plan') else 'free'
            )

            text = self._format_settings_menu(user)

            await edit_or_send_message(
                callback.message,
                text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )

        await answer_callback_query(callback)

    @error_handler()
    async def show_admin_panel(
            self,
            callback: CallbackQuery,
            state: FSMContext,
            **kwargs
    ) -> None:
        """Показать админ панель."""
        # Проверяем права администратора
        if callback.from_user.id not in settings.bot.admin_ids:
            await answer_callback_query(callback, "Доступ запрещен", show_alert=True)
            return

        async with get_unit_of_work() as uow:
            stats = await self._get_system_stats(uow)

            # ИСПОЛЬЗУЕМ НОВЫЕ КЛАВИАТУРЫ
            keyboard = await get_section_menu(
                MainMenuSection.ADMIN,
                user_subscription='vip'  # Админ = VIP
            )

            text = self._format_admin_menu(stats)

            await edit_or_send_message(
                callback.message,
                text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )

        await answer_callback_query(callback)

    async def go_back(
            self,
            callback: CallbackQuery,
            state: FSMContext,
            **kwargs
    ) -> None:
        """Обработка навигации назад."""
        destination = callback.data.replace("back_to_", "")

        # Мапинг destinations на обработчики
        handlers_map = {
            "main": self.show_main_menu,
            "tarot": lambda cb, st, **kw: self.show_legacy_section(cb, st, **kw),
            "astrology": lambda cb, st, **kw: self.show_legacy_section(cb, st, **kw),
            "subscription": lambda cb, st, **kw: self.show_legacy_section(cb, st, **kw),
            "profile": lambda cb, st, **kw: self.show_legacy_section(cb, st, **kw),
            "settings": lambda cb, st, **kw: self.show_legacy_section(cb, st, **kw),
            "quick_actions": self.show_quick_actions
        }

        # Модифицируем callback.data для корректной работы
        if destination in ["tarot", "astrology", "subscription", "profile", "settings"]:
            callback.data = f"section_{destination}"

        handler = handlers_map.get(destination, self.show_main_menu)
        await handler(callback, state, **kwargs)

    # Вспомогательные методы

    def _get_personalized_greeting(self, user: Any) -> str:
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

        name = user.display_name if hasattr(user, 'display_name') and user.display_name else "путешественник"

        # Добавляем информацию о подписке
        if hasattr(user, 'subscription_plan'):
            if user.subscription_plan == "vip":
                status = "👑 VIP статус"
            elif user.subscription_plan == "premium":
                status = "⭐ Premium подписка"
            elif user.subscription_plan == "basic":
                status = "✅ Basic подписка"
            else:
                status = "Бесплатный аккаунт"
        else:
            status = "Бесплатный аккаунт"

        return (
            f"<b>{time_greeting}, {name}!</b>\n\n"
            f"{status}\n\n"
            f"Выберите раздел или воспользуйтесь быстрыми действиями:"
        )

    def _get_section_text(self, section: MainMenuSection, user: Any) -> str:
        """Получить текст для раздела."""
        if section == MainMenuSection.TAROT:
            return self._format_tarot_menu(user, {})
        elif section == MainMenuSection.ASTROLOGY:
            return self._format_astrology_menu(user, {})
        elif section == MainMenuSection.SUBSCRIPTION:
            return self._format_subscription_menu(user, None)
        elif section == MainMenuSection.PROFILE:
            return self._format_profile_menu(user, {}, {})
        elif section == MainMenuSection.SETTINGS:
            return self._format_settings_menu(user)
        elif section == MainMenuSection.ADMIN:
            return "🛠 <b>Панель администратора</b>\n\nВыберите действие:"
        else:
            return "Выберите действие:"

    # Методы форматирования (оставляем без изменений)

    def _format_tarot_menu(self, user: Any, stats: Dict[str, Any]) -> str:
        """Форматировать меню раздела Таро."""
        total_spreads = stats.get("total_spreads", 0)
        favorite_card = stats.get("favorite_card", "Не определена")

        text = (
            "🎴 <b>Таро</b>\n\n"
            "Откройте тайны судьбы с помощью карт Таро.\n\n"
        )

        if total_spreads > 0:
            text += (
                f"📊 <b>Ваша статистика:</b>\n"
                f"• Раскладов выполнено: {total_spreads}\n"
                f"• Любимая карта: {favorite_card}\n\n"
            )

        text += "Выберите действие:"

        return text

    def _format_astrology_menu(self, user: Any, stats: Dict[str, Any]) -> str:
        """Форматировать меню раздела Астрология."""
        text = (
            "🔮 <b>Астрология</b>\n\n"
            "Познайте влияние звезд на вашу судьбу.\n\n"
        )

        if user and hasattr(user, 'birth_date') and user.birth_date:
            text += "✅ Данные рождения заполнены\n\n"
        else:
            text += "⚠️ Заполните данные рождения для точных расчетов\n\n"

        text += "Выберите действие:"

        return text

    def _format_subscription_menu(self, user: Any, subscription: Any) -> str:
        """Форматировать меню подписки."""
        text = "💎 <b>Управление подпиской</b>\n\n"

        if subscription and subscription.is_active:
            text += (
                f"<b>Текущий план:</b> {subscription.plan_name}\n"
                f"<b>Действует до:</b> {subscription.expires_at.strftime('%d.%m.%Y')}\n"
                f"<b>Автопродление:</b> {'Включено' if subscription.auto_renew else 'Выключено'}\n\n"
            )
        else:
            text += (
                "У вас нет активной подписки.\n"
                "Оформите подписку для доступа ко всем функциям!\n\n"
            )

        return text

    def _format_profile_menu(self, user: Any, tarot_stats: Dict[str, Any], astro_stats: Dict[str, Any]) -> str:
        """Форматировать меню профиля."""
        text = (
            f"<b>👤 Ваш профиль</b>\n\n"
            f"<b>Имя:</b> {user.display_name or 'Не указано'}\n"
            f"<b>ID:</b> <code>{user.telegram_id}</code>\n"
            f"<b>Дата регистрации:</b> {user.created_at.strftime('%d.%m.%Y') if hasattr(user, 'created_at') else 'Неизвестно'}\n"
        )

        if hasattr(user, 'birth_date') and user.birth_date:
            text += f"<b>Дата рождения:</b> {user.birth_date.strftime('%d.%m.%Y')}\n"

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

    def _format_settings_menu(self, user: Any) -> str:
        """Форматировать меню настроек."""
        notifications = "Включены" if getattr(user, 'notifications_enabled', True) else "Выключены"
        language = "Русский" if getattr(user, 'language_code', 'ru') == "ru" else "English"

        text = (
            f"<b>⚙️ Настройки</b>\n\n"
            f"<b>Уведомления:</b> {notifications}\n"
            f"<b>Язык:</b> {language}\n"
            f"<b>Часовой пояс:</b> {getattr(user, 'timezone', 'UTC')}\n\n"
            f"Выберите параметр для изменения:"
        )

        return text

    async def _get_system_stats(self, uow: Any) -> Dict[str, Any]:
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

    def _format_admin_menu(self, stats: Dict[str, Any]) -> str:
        """Форматировать админ меню."""
        text = (
            f"<b>🔧 Панель администратора</b>\n\n"
            f"<b>📊 Статистика системы:</b>\n"
            f"• Всего пользователей: {stats['total_users']}\n"
            f"• Активных (7 дней): {stats['active_users']}\n\n"
            f"<b>💳 Подписки:</b>\n"
        )

        for plan, count in stats.get('subscriptions', {}).items():
            text += f"• {plan.upper()}: {count}\n"

        text += (
            f"\n<b>💰 Доход за месяц:</b> "
            f"{stats.get('monthly_revenue', 0):,.0f} ₽\n\n"
            f"Выберите действие:"
        )

        return text


# Функция для регистрации обработчика
def register_menu_handler(router: Router) -> None:
    """
    Регистрация обработчика меню.

    Args:
        router: Роутер для регистрации
    """
    handler = MenuHandler(router)
    handler.register_handlers()
    logger.info("Menu handler зарегистрирован")


logger.info("Модуль обработчика меню загружен")