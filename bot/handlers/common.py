"""
Обработчик общих команд и событий.

Этот модуль отвечает за:
- Команду отмены /cancel
- Команду статистики /stats
- Команду /about
- Обработку неизвестных команд
- Общие callback кнопки
- Системные уведомления

Автор: AI Assistant
Дата создания: 2024-12-30
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from bot.states import FeedbackStates
from aiogram import Router, F
from aiogram.filters import Command, CommandObject
from aiogram.types import Message, CallbackQuery, ErrorEvent
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
    InlineKeyboard,
    Keyboards,
    ConfirmationKeyboard,
    BaseCallbackData,
    ConfirmCallbackData,
    RefreshCallbackData,
    parse_callback_data
)

logger = logging.getLogger(__name__)


# НОВЫЕ CALLBACK DATA
class CommonCallbackData(BaseCallbackData, prefix="common"):
    """Callback data для общих действий."""
    target: Optional[str] = None  # Цель действия


class FeedbackCallbackData(BaseCallbackData, prefix="feedback"):
    """Callback data для обратной связи."""
    rating: Optional[int] = None
    category: Optional[str] = None


class CommonHandler(BaseHandler):
    """Обработчик общих команд и событий."""

    def register_handlers(self) -> None:
        """Регистрация обработчиков."""
        # Команда отмены
        self.router.message.register(
            self.cmd_cancel,
            Command("cancel")
        )

        # Команда статистики
        self.router.message.register(
            self.cmd_stats,
            Command("stats")
        )

        # О боте
        self.router.message.register(
            self.cmd_about,
            Command("about")
        )

        # Команда обратной связи
        self.router.message.register(
            self.cmd_feedback,
            Command("feedback")
        )

        # Системная информация (для админов)
        self.router.message.register(
            self.cmd_system,
            Command("system")
        )

        # Обработка неизвестных команд
        self.router.message.register(
            self.unknown_command,
            Command()  # Любая команда
        )

        # Обработка обычных текстовых сообщений
        self.router.message.register(
            self.handle_text_message,
            F.text & ~F.text.startswith("/")
        )

        # НОВЫЕ ОБРАБОТЧИКИ CALLBACK
        self.router.callback_query.register(
            self.close_message_handler,
            CommonCallbackData.filter(F.action == "close")
        )

        self.router.callback_query.register(
            self.refresh_data_handler,
            RefreshCallbackData.filter()
        )

        self.router.callback_query.register(
            self.confirm_action_handler,
            ConfirmCallbackData.filter()
        )

        self.router.callback_query.register(
            self.feedback_callback_handler,
            FeedbackCallbackData.filter()
        )

        # Старые callback для обратной совместимости
        self.router.callback_query.register(
            self.legacy_callback_handler,
            F.data.in_(["close", "refresh:stats", "refresh:system"])
        )

    @error_handler()
    @log_action("cancel_command")
    async def cmd_cancel(
            self,
            message: Message,
            state: FSMContext,
            **kwargs
    ) -> None:
        """Отмена текущего действия."""
        # Получаем текущее состояние
        current_state = await state.get_state()

        if current_state is None:
            await message.answer(
                "❌ Нечего отменять.\n"
                "Используйте /menu для главного меню."
            )
            return

        # Очищаем состояние
        await state.clear()

        # ИСПОЛЬЗУЕМ НОВУЮ КНОПКУ
        keyboard = await Keyboards.menu_button()

        await message.answer(
            "✅ Действие отменено.",
            reply_markup=keyboard
        )

        # Логируем отмену
        await self.log_action(
            message.from_user.id,
            "action_cancelled",
            {"previous_state": current_state}
        )

    @error_handler()
    @log_action("stats_command")
    async def cmd_stats(
            self,
            message: Message,
            state: FSMContext,
            **kwargs
    ) -> None:
        """Показать статистику пользователя."""
        user_id = message.from_user.id

        async with get_unit_of_work() as uow:
            user = await uow.users.get_by_telegram_id(user_id)

            if not user:
                await message.answer("❌ Пользователь не найден")
                return

            # Получаем статистику
            tarot_stats = await uow.tarot.get_user_statistics(user.id)
            astro_stats = await uow.astrology.get_user_statistics(user.id)

            # Форматируем статистику
            text = self._format_user_stats(user, tarot_stats, astro_stats)

            # ИСПОЛЬЗУЕМ НОВУЮ КЛАВИАТУРУ
            keyboard = InlineKeyboard()
            keyboard.add_button(
                text="🔄 Обновить",
                callback_data=RefreshCallbackData(
                    action="refresh",
                    target="stats"
                )
            )
            keyboard.add_button(
                text="📊 Подробная статистика",
                callback_data=CommonCallbackData(
                    action="detailed",
                    value="stats",
                    target=str(user.id)
                )
            )
            keyboard.add_button(
                text="❌ Закрыть",
                callback_data=CommonCallbackData(action="close")
            )

            keyboard.builder.adjust(2, 1)
            kb = await keyboard.build()

            await message.answer(
                text,
                reply_markup=kb,
                parse_mode="HTML"
            )

    @error_handler()
    @log_action("about_command")
    async def cmd_about(
            self,
            message: Message,
            state: FSMContext,
            **kwargs
    ) -> None:
        """Информация о боте."""
        text = (
            "🤖 <b>Астро-Таро Бот</b>\n\n"
            f"Версия: {settings.bot.version if hasattr(settings.bot, 'version') else '1.0.0'}\n"
            f"Разработчик: AI Assistant\n\n"
            "Ваш персональный помощник в мире эзотерики:\n"
            "• 🎴 Расклады Таро\n"
            "• 🔮 Натальные карты\n"
            "• ⭐ Персональные гороскопы\n"
            "• 🌙 Лунный календарь\n"
            "• 💑 Анализ совместимости\n\n"
            "Телеграм канал: @astrotaro_news\n"
            "Поддержка: @astrotaro_support\n\n"
            "С любовью к звездам и картам! ✨"
        )

        # ИСПОЛЬЗУЕМ НОВУЮ КЛАВИАТУРУ
        keyboard = InlineKeyboard()
        keyboard.add_url_button("📢 Канал новостей", "https://t.me/astrotaro_news")
        keyboard.add_url_button("💬 Поддержка", "https://t.me/astrotaro_support")
        keyboard.add_button(
            text="⭐ Оставить отзыв",
            callback_data=FeedbackCallbackData(action="start")
        )
        keyboard.add_button(
            text="❌ Закрыть",
            callback_data=CommonCallbackData(action="close")
        )

        keyboard.builder.adjust(1, 1, 1, 1)
        kb = await keyboard.build()

        await message.answer(
            text,
            reply_markup=kb,
            parse_mode="HTML"
        )

    @error_handler()
    async def cmd_feedback(
            self,
            message: Message,
            state: FSMContext,
            **kwargs
    ) -> None:
        """Команда обратной связи."""
        text = (
            "💬 <b>Обратная связь</b>\n\n"
            "Мы ценим ваше мнение! Что вы хотите нам сообщить?"
        )

        # ИСПОЛЬЗУЕМ НОВУЮ КЛАВИАТУРУ ДЛЯ ВЫБОРА ТИПА ОБРАТНОЙ СВЯЗИ
        keyboard = InlineKeyboard()

        # Категории обратной связи
        categories = [
            ("💡", "Предложение", "suggestion"),
            ("🐛", "Сообщить об ошибке", "bug"),
            ("⭐", "Отзыв о боте", "review"),
            ("❓", "Вопрос", "question"),
            ("🤝", "Сотрудничество", "partnership")
        ]

        for emoji, text, category in categories:
            keyboard.add_button(
                text=f"{emoji} {text}",
                callback_data=FeedbackCallbackData(
                    action="category",
                    category=category
                )
            )

        keyboard.add_button(
            text="❌ Отмена",
            callback_data=CommonCallbackData(action="close")
        )

        keyboard.builder.adjust(1, 1, 1, 1, 1, 1)
        kb = await keyboard.build()

        await message.answer(
            text,
            reply_markup=kb,
            parse_mode="HTML"
        )

    @error_handler()
    async def cmd_system(
            self,
            message: Message,
            state: FSMContext,
            **kwargs
    ) -> None:
        """Системная информация (только для админов)."""
        if message.from_user.id not in settings.bot.admin_ids:
            await self.unknown_command(message, state)
            return

        # Собираем системную информацию
        text = await self._get_system_info()

        # ИСПОЛЬЗУЕМ НОВУЮ КЛАВИАТУРУ
        keyboard = InlineKeyboard()
        keyboard.add_button(
            text="🔄 Обновить",
            callback_data=RefreshCallbackData(
                action="refresh",
                target="system"
            )
        )
        keyboard.add_button(
            text="📊 Детальная статистика",
            callback_data=CommonCallbackData(
                action="admin",
                value="detailed_stats"
            )
        )
        keyboard.add_button(
            text="🔧 Управление",
            callback_data=CommonCallbackData(
                action="admin",
                value="management"
            )
        )
        keyboard.add_button(
            text="❌ Закрыть",
            callback_data=CommonCallbackData(action="close")
        )

        keyboard.builder.adjust(1, 2, 1)
        kb = await keyboard.build()

        await message.answer(
            text,
            reply_markup=kb,
            parse_mode="HTML"
        )

    @error_handler()
    async def unknown_command(
            self,
            message: Message,
            state: FSMContext,
            **kwargs
    ) -> None:
        """Обработка неизвестных команд."""
        command = message.text.split()[0] if message.text else ""

        # Пытаемся найти похожие команды
        suggestions = self._find_similar_commands(command)

        text = f"❓ Неизвестная команда: {command}\n\n"

        if suggestions:
            text += "Возможно, вы имели в виду:\n"
            for cmd in suggestions[:3]:
                text += f"• {cmd}\n"
            text += "\n"

        text += "Используйте /help для списка доступных команд."

        # ИСПОЛЬЗУЕМ НОВЫЕ КНОПКИ
        keyboard = InlineKeyboard()
        keyboard.add_button(
            text="📚 Справка",
            callback_data="help:menu"
        )
        keyboard.add_button(
            text="📋 Главное меню",
            callback_data="main_menu"
        )

        keyboard.builder.adjust(2)
        kb = await keyboard.build()

        await message.answer(text, reply_markup=kb)

    @error_handler()
    async def handle_text_message(
            self,
            message: Message,
            state: FSMContext,
            **kwargs
    ) -> None:
        """Обработка обычных текстовых сообщений."""
        current_state = await state.get_state()

        # Если есть активное состояние, не обрабатываем
        if current_state:
            return

        # Анализируем текст сообщения
        text_lower = message.text.lower()

        # Простые ответы на частые фразы
        if any(word in text_lower for word in ["привет", "здравствуй", "добрый день", "hi", "hello"]):
            await message.answer(self._greeting_response())
        elif any(word in text_lower for word in ["спасибо", "благодарю", "thanks"]):
            await message.answer(self._thanks_response())
        elif any(word in text_lower for word in ["помощь", "помоги", "help"]):
            await self._send_help_hint(message)
        elif any(word in text_lower for word in ["таро", "карты", "расклад"]):
            await self._send_tarot_hint(message)
        elif any(word in text_lower for word in ["гороскоп", "астрология", "натальн"]):
            await self._send_horoscope_hint(message)
        elif any(word in text_lower for word in ["подписка", "premium", "премиум"]):
            await self._send_subscription_hint(message)
        else:
            # Общий ответ с кнопками
            await self._send_default_response(message)

    # НОВЫЕ ОБРАБОТЧИКИ CALLBACK

    @error_handler()
    async def close_message_handler(
            self,
            callback: CallbackQuery,
            callback_data: CommonCallbackData,
            state: FSMContext,
            **kwargs
    ) -> None:
        """Закрыть/удалить сообщение."""
        try:
            await callback.message.delete()
        except TelegramBadRequest:
            await answer_callback_query(
                callback,
                "Не удалось удалить сообщение",
                show_alert=True
            )
            return

        await answer_callback_query(callback, "Закрыто")

    @error_handler()
    async def refresh_data_handler(
            self,
            callback: CallbackQuery,
            callback_data: RefreshCallbackData,
            state: FSMContext,
            **kwargs
    ) -> None:
        """Обновить данные."""
        target = callback_data.target

        if target == "stats":
            # Обновляем статистику
            await self.cmd_stats(callback.message, state)
        elif target == "system":
            # Обновляем системную информацию
            await self.cmd_system(callback.message, state)

        await answer_callback_query(callback, "Данные обновлены")

    @error_handler()
    async def confirm_action_handler(
            self,
            callback: CallbackQuery,
            callback_data: ConfirmCallbackData,
            state: FSMContext,
            **kwargs
    ) -> None:
        """Обработка подтверждения действия."""
        if callback_data.confirmed:
            action = callback_data.action_id
            # Здесь обрабатываем различные подтверждения
            await answer_callback_query(
                callback,
                f"✅ Действие подтверждено",
                show_alert=True
            )
        else:
            await edit_or_send_message(
                callback.message,
                "❌ Действие отменено",
                reply_markup=None
            )
            await answer_callback_query(callback)

    @error_handler()
    async def feedback_callback_handler(
            self,
            callback: CallbackQuery,
            callback_data: FeedbackCallbackData,
            state: FSMContext,
            **kwargs
    ) -> None:
        """Обработчик callback для обратной связи."""
        action = callback_data.action

        if action == "start":
            # Показываем категории
            await self._show_feedback_categories(callback)
        elif action == "category":
            # Выбрана категория
            category = callback_data.category
            await self._start_feedback_collection(callback, category, state)
        elif action == "rating":
            # Оценка бота
            rating = callback_data.rating
            await self._save_rating(callback, rating)

        await answer_callback_query(callback)

    # Обработчик для старых callback (обратная совместимость)
    @error_handler()
    async def legacy_callback_handler(
            self,
            callback: CallbackQuery,
            state: FSMContext,
            **kwargs
    ) -> None:
        """Обработка старых callback для обратной совместимости."""
        data = callback.data

        if data == "close":
            await self.close_message_handler(
                callback,
                CommonCallbackData(action="close"),
                state,
                **kwargs
            )
        elif data.startswith("refresh:"):
            target = data.split(":")[1]
            await self.refresh_data_handler(
                callback,
                RefreshCallbackData(action="refresh", target=target),
                state,
                **kwargs
            )

    # Вспомогательные методы

    def _format_user_stats(
            self,
            user: Any,
            tarot_stats: Dict[str, Any],
            astro_stats: Dict[str, Any]
    ) -> str:
        """Форматировать статистику пользователя."""
        text = f"📊 <b>Ваша статистика</b>\n\n"

        # Общая информация
        text += f"<b>👤 Профиль:</b>\n"
        text += f"• Имя: {user.display_name or user.first_name or 'Не указано'}\n"
        text += f"• Дата регистрации: {user.created_at.strftime('%d.%m.%Y') if hasattr(user, 'created_at') else 'Неизвестно'}\n"

        # Подписка
        if hasattr(user, 'subscription_plan') and user.subscription_plan:
            text += f"• Подписка: {user.subscription_plan.upper()}\n"

        text += "\n"

        # Статистика Таро
        if tarot_stats:
            text += f"<b>🎴 Таро:</b>\n"
            text += f"• Раскладов выполнено: {tarot_stats.get('total_spreads', 0)}\n"
            text += f"• Карт вытянуто: {tarot_stats.get('total_cards', 0)}\n"

            if tarot_stats.get('favorite_card'):
                text += f"• Любимая карта: {tarot_stats['favorite_card']}\n"

            text += "\n"

        # Статистика Астрологии
        if astro_stats:
            text += f"<b>🔮 Астрология:</b>\n"
            text += f"• Гороскопов просмотрено: {astro_stats.get('total_horoscopes', 0)}\n"
            text += f"• Натальных карт: {astro_stats.get('natal_charts', 0)}\n"
            text += f"• Проверок совместимости: {astro_stats.get('synastry_checks', 0)}\n"
            text += "\n"

        # Достижения
        total_actions = (
            tarot_stats.get('total_spreads', 0) +
            astro_stats.get('total_horoscopes', 0)
        )

        if total_actions > 0:
            text += f"<b>🏆 Достижения:</b>\n"

            if total_actions >= 100:
                text += "• 💫 Мастер эзотерики (100+ действий)\n"
            elif total_actions >= 50:
                text += "• ⭐ Продвинутый искатель (50+ действий)\n"
            elif total_actions >= 10:
                text += "• 🌟 Начинающий мистик (10+ действий)\n"
            else:
                text += "• ✨ Новичок\n"

        return text

    async def _get_system_info(self) -> str:
        """Получить системную информацию."""
        async with get_unit_of_work() as uow:
            # Статистика пользователей
            total_users = await uow.users.count_total()
            active_today = await uow.users.count_active(days=1)
            active_week = await uow.users.count_active(days=7)

            # Статистика подписок
            subscriptions = await uow.subscriptions.count_by_plan()

            # Статистика использования
            tarot_today = await uow.tarot.count_spreads_today()
            horoscopes_today = await uow.astrology.count_horoscopes_today()

        text = (
            "🖥 <b>Системная информация</b>\n\n"
            f"<b>👥 Пользователи:</b>\n"
            f"• Всего: {total_users}\n"
            f"• Активных сегодня: {active_today}\n"
            f"• Активных за неделю: {active_week}\n\n"
            f"<b>💎 Подписки:</b>\n"
        )

        for plan, count in subscriptions.items():
            text += f"• {plan.upper()}: {count}\n"

        text += (
            f"\n<b>📊 Активность сегодня:</b>\n"
            f"• Раскладов Таро: {tarot_today}\n"
            f"• Гороскопов: {horoscopes_today}\n\n"
            f"<b>🔧 Система:</b>\n"
            f"• Версия бота: {settings.bot.version if hasattr(settings.bot, 'version') else '1.0.0'}\n"
            f"• Окружение: {settings.environment}\n"
            f"• Время работы: {self._get_uptime()}"
        )

        return text

    def _get_uptime(self) -> str:
        """Получить время работы бота."""
        # Здесь должна быть логика получения uptime
        # Пока возвращаем заглушку
        return "Неизвестно"

    def _find_similar_commands(self, command: str) -> list:
        """Найти похожие команды."""
        known_commands = [
            "/start", "/help", "/menu", "/tarot", "/astrology",
            "/subscription", "/profile", "/settings", "/stats",
            "/about", "/support", "/cancel"
        ]

        # Убираем слэш для сравнения
        command = command.lstrip("/")

        # Простой алгоритм на основе начала строки
        suggestions = []

        for known in known_commands:
            known_clean = known.lstrip("/")
            if known_clean.startswith(command[:3]):
                suggestions.append(known)
            elif command in known_clean:
                suggestions.append(known)

        return suggestions[:3]  # Максимум 3 предложения

    # Функции для генерации ответов

    def _greeting_response(self) -> str:
        """Ответ на приветствие."""
        return (
            "👋 Привет! Рад вас видеть!\n\n"
            "Используйте /menu для главного меню "
            "или /help если нужна помощь."
        )

    def _thanks_response(self) -> str:
        """Ответ на благодарность."""
        return (
            "💖 Всегда пожалуйста! "
            "Рад быть полезным!"
        )

    async def _send_help_hint(self, message: Message) -> None:
        """Подсказка о помощи с кнопками."""
        text = (
            "ℹ️ Нужна помощь?\n\n"
            "Выберите, что вас интересует:"
        )

        keyboard = InlineKeyboard()
        keyboard.add_button(text="📚 Полная справка", callback_data="help:menu")
        keyboard.add_button(text="💬 Связь с поддержкой", callback_data="help:support")
        keyboard.add_button(text="📋 Главное меню", callback_data="main_menu")

        keyboard.builder.adjust(1, 1, 1)
        kb = await keyboard.build()

        await message.answer(text, reply_markup=kb)

    async def _send_tarot_hint(self, message: Message) -> None:
        """Подсказка о Таро с кнопками."""
        text = (
            "🎴 Интересуетесь Таро?\n\n"
            "Попробуйте популярные расклады:"
        )

        from infrastructure.telegram.keyboards import TarotCallbackData

        keyboard = InlineKeyboard()
        keyboard.add_button(
            text="🎴 Карта дня",
            callback_data=TarotCallbackData(action="daily_card")
        )
        keyboard.add_button(
            text="🔮 Быстрый расклад",
            callback_data=TarotCallbackData(action="quick_spread")
        )
        keyboard.add_button(
            text="📋 Все расклады",
            callback_data=TarotCallbackData(action="menu")
        )

        keyboard.builder.adjust(1, 1, 1)
        kb = await keyboard.build()

        await message.answer(text, reply_markup=kb)

    async def _send_horoscope_hint(self, message: Message) -> None:
        """Подсказка о гороскопе с кнопками."""
        text = (
            "⭐ Хотите узнать гороскоп?\n\n"
            "Доступные варианты:"
        )

        from infrastructure.telegram.keyboards import AstrologyCallbackData

        keyboard = InlineKeyboard()
        keyboard.add_button(
            text="☀️ Гороскоп на сегодня",
            callback_data=AstrologyCallbackData(action="daily_horoscope")
        )
        keyboard.add_button(
            text="🗓 На неделю",
            callback_data=AstrologyCallbackData(action="weekly_horoscope")
        )
        keyboard.add_button(
            text="🔮 Все функции астрологии",
            callback_data=AstrologyCallbackData(action="menu")
        )

        keyboard.builder.adjust(1, 1, 1)
        kb = await keyboard.build()

        await message.answer(text, reply_markup=kb)

    async def _send_subscription_hint(self, message: Message) -> None:
        """Подсказка о подписке с кнопками."""
        text = (
            "💎 Интересует подписка?\n\n"
            "Откройте больше возможностей:"
        )

        from infrastructure.telegram.keyboards import SubscriptionCallbackData

        keyboard = InlineKeyboard()
        keyboard.add_button(
            text="📋 Тарифные планы",
            callback_data=SubscriptionCallbackData(action="plans")
        )
        keyboard.add_button(
            text="🎁 Промокод",
            callback_data=SubscriptionCallbackData(action="promo")
        )
        keyboard.add_button(
            text="💳 Оформить подписку",
            callback_data=SubscriptionCallbackData(action="subscribe")
        )

        keyboard.builder.adjust(1, 1, 1)
        kb = await keyboard.build()

        await message.answer(text, reply_markup=kb)

    async def _send_default_response(self, message: Message) -> None:
        """Стандартный ответ с кнопками навигации."""
        text = (
            "🤔 Не совсем понимаю, что вы имеете в виду.\n\n"
            "Выберите нужный раздел:"
        )

        keyboard = InlineKeyboard()
        keyboard.add_button(text="📋 Главное меню", callback_data="main_menu")
        keyboard.add_button(text="🎴 Таро", callback_data="menu:tarot")
        keyboard.add_button(text="🔮 Астрология", callback_data="menu:astrology")
        keyboard.add_button(text="📚 Справка", callback_data="help:menu")

        keyboard.builder.adjust(2, 2)
        kb = await keyboard.build()

        await message.answer(text, reply_markup=kb)

    async def _show_feedback_categories(self, callback: CallbackQuery) -> None:
        """Показать категории обратной связи."""
        text = (
            "💬 <b>Обратная связь</b>\n\n"
            "Выберите тип сообщения:"
        )

        keyboard = InlineKeyboard()

        categories = [
            ("💡", "Предложение", "suggestion"),
            ("🐛", "Сообщить об ошибке", "bug"),
            ("⭐", "Отзыв о боте", "review"),
            ("❓", "Вопрос", "question"),
            ("🤝", "Сотрудничество", "partnership")
        ]

        for emoji, text_btn, category in categories:
            keyboard.add_button(
                text=f"{emoji} {text_btn}",
                callback_data=FeedbackCallbackData(
                    action="category",
                    category=category
                )
            )

        keyboard.add_button(
            text="❌ Отмена",
            callback_data=CommonCallbackData(action="close")
        )

        keyboard.builder.adjust(1, 1, 1, 1, 1, 1)
        kb = await keyboard.build()

        await edit_or_send_message(
            callback.message,
            text,
            reply_markup=kb,
            parse_mode="HTML"
        )

    async def _start_feedback_collection(
            self,
            callback: CallbackQuery,
            category: str,
            state: FSMContext
    ) -> None:
        """Начать сбор обратной связи."""
        category_names = {
            "suggestion": "предложение",
            "bug": "сообщение об ошибке",
            "review": "отзыв",
            "question": "вопрос",
            "partnership": "предложение о сотрудничестве"
        }

        text = (
            f"✍️ Отлично! Напишите ваше {category_names.get(category, 'сообщение')}.\n\n"
            "Просто отправьте текст в ответ на это сообщение."
        )

        keyboard = await Keyboards.cancel()

        await edit_or_send_message(
            callback.message,
            text,
            reply_markup=keyboard
        )

        # Сохраняем категорию и устанавливаем состояние
        await state.update_data(feedback_category=category)
        await state.set_state(FeedbackStates.waiting_for_text)

    async def _save_rating(self, callback: CallbackQuery, rating: int) -> None:
        """Сохранить оценку бота."""
        # Здесь логика сохранения оценки
        text = (
            f"Спасибо за вашу оценку: {'⭐' * rating}\n\n"
            "Ваше мнение очень важно для нас!"
        )

        keyboard = await Keyboards.close()

        await edit_or_send_message(
            callback.message,
            text,
            reply_markup=keyboard
        )


# Функция для регистрации обработчика
def register_common_handler(router: Router) -> None:
    """
    Регистрация обработчика общих команд.

    Args:
        router: Роутер для регистрации
    """
    handler = CommonHandler(router)
    handler.register_handlers()
    logger.info("Common handler зарегистрирован")


logger.info("Модуль обработчика общих команд загружен")