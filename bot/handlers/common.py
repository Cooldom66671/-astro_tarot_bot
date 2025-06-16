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

from aiogram import Router, F
from aiogram.filters import Command, CommandObject
from aiogram.types import Message, CallbackQuery, ErrorEvent
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest

from bot.handlers.base import BaseHandler
from infrastructure.telegram import (
    MessageFactory,
    MessageBuilder,
    MessageStyle,
    MessageEmoji as Emoji,
    MessageUtils
)
from infrastructure import get_unit_of_work

logger = logging.getLogger(__name__)


class CommonHandler(BaseHandler):
    """Обработчик общих команд и событий."""

    def register_handlers(self, router: Router) -> None:
        """Регистрация обработчиков."""
        # Команда отмены
        router.message.register(
            self.cmd_cancel,
            Command("cancel")
        )

        # Команда статистики
        router.message.register(
            self.cmd_stats,
            Command("stats")
        )

        # О боте
        router.message.register(
            self.cmd_about,
            Command("about")
        )

        # Команда обратной связи
        router.message.register(
            self.cmd_feedback,
            Command("feedback")
        )

        # Системная информация (для админов)
        router.message.register(
            self.cmd_system,
            Command("system")
        )

        # Обработка неизвестных команд
        router.message.register(
            self.unknown_command,
            Command()  # Любая команда
        )

        # Обработка обычных текстовых сообщений
        router.message.register(
            self.handle_text_message,
            F.text & ~F.text.startswith("/")
        )

        # Общие callback кнопки
        router.callback_query.register(
            self.close_message,
            F.data == "close"
        )

        router.callback_query.register(
            self.refresh_data,
            F.data.startswith("refresh:")
        )

        router.callback_query.register(
            self.confirm_action,
            F.data.startswith("confirm:")
        )

        router.callback_query.register(
            self.cancel_action,
            F.data.startswith("cancel:")
        )

        # Обработка ошибок
        router.error.register(
            self.handle_error,
            F.exception.as_("error")
        )

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
                f"{Emoji.INFO} Нет активных действий для отмены.\n"
                f"Используйте /menu для возврата в главное меню."
            )
            return

        # Очищаем состояние
        await state.clear()

        # Формируем сообщение об отмене
        state_descriptions = {
            "OnboardingStates": "процесс знакомства",
            "TarotStates": "выбор карт",
            "AstrologyStates": "ввод данных",
            "PaymentStates": "процесс оплаты",
            "FeedbackStates": "отправка отзыва"
        }

        # Определяем, что было отменено
        state_group = current_state.split(":")[0] if ":" in current_state else "действие"
        action_name = state_descriptions.get(state_group, "текущее действие")

        await message.answer(
            f"{Emoji.CANCEL} <b>Отменено:</b> {action_name}\n\n"
            f"Используйте /menu для возврата в главное меню.",
            parse_mode="HTML"
        )

    async def cmd_stats(
            self,
            message: Message,
            **kwargs
    ) -> None:
        """Показать статистику пользователя."""
        async with get_unit_of_work() as uow:
            user = await self.get_or_create_user(
                uow,
                message.from_user
            )

            # Получаем статистику
            tarot_stats = await uow.tarot.get_user_statistics(user.id)
            astro_stats = await uow.astrology.get_user_statistics(user.id)

            # Форматируем статистику
            builder = MessageBuilder(MessageStyle.HTML)

            builder.add_bold(f"{Emoji.CHART} Ваша статистика").add_line(2)

            # Общая информация
            days_with_bot = (datetime.utcnow() - user.created_at).days
            builder.add_text(f"<b>Дней с ботом:</b> {days_with_bot}").add_line()
            builder.add_text(f"<b>Уровень подписки:</b> {user.subscription_plan.upper()}").add_line(2)

            # Статистика Таро
            if tarot_stats["total_spreads"] > 0:
                builder.add_bold(f"{Emoji.CARDS} Таро:").add_line()
                builder.add_text(f"• Раскладов выполнено: {tarot_stats['total_spreads']}").add_line()
                builder.add_text(f"• Избранных раскладов: {tarot_stats['favorite_count']}").add_line()
                builder.add_text(f"• Любимый расклад: {tarot_stats['favorite_spread']}").add_line()

                # Топ карт
                if tarot_stats.get("top_cards"):
                    builder.add_line()
                    builder.add_text("<b>Частые карты:</b>").add_line()
                    for card, count in tarot_stats["top_cards"][:3]:
                        builder.add_text(f"• {card}: {count} раз").add_line()

                builder.add_line()

            # Статистика астрологии
            if astro_stats["total_horoscopes"] > 0:
                builder.add_bold(f"{Emoji.STARS} Астрология:").add_line()
                builder.add_text(f"• Гороскопов просмотрено: {astro_stats['total_horoscopes']}").add_line()
                builder.add_text(f"• Натальных карт: {astro_stats['natal_charts']}").add_line()
                builder.add_text(f"• Прогнозов транзитов: {astro_stats['transits']}").add_line(2)

            # Достижения
            achievements = await self._calculate_achievements(
                user,
                tarot_stats,
                astro_stats
            )

            if achievements:
                builder.add_bold(f"{Emoji.ACHIEVEMENT} Достижения:").add_line()
                for achievement in achievements:
                    builder.add_text(f"• {achievement}").add_line()
                builder.add_line()

            # Рекомендации
            builder.add_italic(
                self._get_stats_recommendation(
                    tarot_stats["total_spreads"],
                    astro_stats["total_horoscopes"]
                )
            )

            await message.answer(
                builder.build(),
                parse_mode="HTML"
            )

    async def cmd_about(
            self,
            message: Message,
            **kwargs
    ) -> None:
        """Информация о боте."""
        about_text = MessageFactory.create(
            "about_bot",
            MessageStyle.HTML,
            version="2.0",
            year=datetime.now().year
        )

        # Добавляем статистику бота
        async with get_unit_of_work() as uow:
            total_users = await uow.users.count_total()
            total_spreads = await uow.tarot.count_total_spreads()

            stats_text = (
                f"\n\n<b>{Emoji.CHART} Статистика бота:</b>\n"
                f"• Пользователей: {total_users:,}\n"
                f"• Раскладов выполнено: {total_spreads:,}\n"
                f"• Работает с: Январь 2024"
            )

        await message.answer(
            about_text + stats_text,
            parse_mode="HTML",
            disable_web_page_preview=True
        )

    async def cmd_feedback(
            self,
            message: Message,
            state: FSMContext,
            command: CommandObject,
            **kwargs
    ) -> None:
        """Отправка обратной связи."""
        # Если есть текст сразу после команды
        if command.args:
            await self._process_feedback(
                message,
                command.args,
                message.from_user
            )
        else:
            # Запускаем состояние для сбора отзыва
            from bot.states import FeedbackStates

            await state.set_state(FeedbackStates.waiting_for_text)

            await message.answer(
                f"{Emoji.FEEDBACK} <b>Обратная связь</b>\n\n"
                f"Напишите ваш отзыв, предложение или сообщение об ошибке.\n"
                f"Мы обязательно рассмотрим его!\n\n"
                f"<i>Отправьте /cancel для отмены</i>",
                parse_mode="HTML"
            )

    async def cmd_system(
            self,
            message: Message,
            **kwargs
    ) -> None:
        """Системная информация (только для админов)."""
        async with get_unit_of_work() as uow:
            user = await uow.users.get_by_telegram_id(
                message.from_user.id
            )

            if not user or not user.is_admin:
                await self.unknown_command(message)
                return

            # Собираем системную информацию
            system_info = await self._collect_system_info(uow)

            builder = MessageBuilder(MessageStyle.HTML)
            builder.add_bold(f"{Emoji.ADMIN} Системная информация").add_line(2)

            # Основные метрики
            builder.add_bold("Пользователи:").add_line()
            builder.add_text(f"• Всего: {system_info['users']['total']}").add_line()
            builder.add_text(f"• Активных (24ч): {system_info['users']['active_24h']}").add_line()
            builder.add_text(f"• Активных (7д): {system_info['users']['active_7d']}").add_line()
            builder.add_text(f"• Новых сегодня: {system_info['users']['new_today']}").add_line(2)

            # Подписки
            builder.add_bold("Подписки:").add_line()
            for plan, count in system_info['subscriptions'].items():
                percentage = (count / system_info['users']['total']) * 100
                builder.add_text(f"• {plan.upper()}: {count} ({percentage:.1f}%)").add_line()
            builder.add_line()

            # Активность
            builder.add_bold("Активность (сегодня):").add_line()
            builder.add_text(f"• Раскладов: {system_info['activity']['spreads_today']}").add_line()
            builder.add_text(f"• Гороскопов: {system_info['activity']['horoscopes_today']}").add_line()
            builder.add_text(f"• Платежей: {system_info['activity']['payments_today']}").add_line(2)

            # Система
            builder.add_bold("Система:").add_line()
            builder.add_text(f"• Версия: 2.0").add_line()
            builder.add_text(f"• Uptime: {system_info['system']['uptime']}").add_line()
            builder.add_text(f"• База данных: {system_info['system']['db_size']} MB").add_line()
            builder.add_text(f"• Кэш: {system_info['system']['cache_hits']}% hits").add_line()

            await message.answer(
                builder.build(),
                parse_mode="HTML"
            )

    async def unknown_command(
            self,
            message: Message,
            **kwargs
    ) -> None:
        """Обработка неизвестных команд."""
        # Список известных команд
        known_commands = [
            "/start", "/help", "/menu", "/cancel",
            "/stats", "/about", "/feedback", "/support",
            "/tarot", "/astrology", "/subscription"
        ]

        # Пытаемся найти похожую команду
        command = message.text.split()[0].lower()
        suggestions = self._find_similar_commands(command, known_commands)

        response = f"{Emoji.CONFUSED} Неизвестная команда: {command}\n\n"

        if suggestions:
            response += f"Возможно, вы имели в виду:\n"
            for suggestion in suggestions[:3]:
                response += f"• {suggestion}\n"
            response += "\n"

        response += (
            f"Используйте /help для просмотра доступных команд\n"
            f"или /menu для главного меню."
        )

        await message.answer(response)

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

        # Анализируем сообщение
        text_lower = message.text.lower()

        # Простые ответы на частые фразы
        responses = {
            "привет": self._greeting_response,
            "спасибо": self._thanks_response,
            "помощь": self._help_hint,
            "таро": self._tarot_hint,
            "гороскоп": self._horoscope_hint,
            "подписка": self._subscription_hint
        }

        for keyword, response_func in responses.items():
            if keyword in text_lower:
                await message.answer(
                    response_func(),
                    parse_mode="HTML"
                )
                return

        # Если ничего не подошло
        await message.answer(
            f"{Emoji.THINKING} Я не совсем понял ваш запрос.\n\n"
            f"Попробуйте:\n"
            f"• /menu - главное меню\n"
            f"• /help - справка по командам\n"
            f"• /tarot - расклады Таро\n"
            f"• /astrology - астрология"
        )

    async def close_message(
            self,
            callback: CallbackQuery,
            **kwargs
    ) -> None:
        """Закрыть/удалить сообщение."""
        await self.delete_message_safe(callback.message)
        await callback.answer("Закрыто")

    async def refresh_data(
            self,
            callback: CallbackQuery,
            **kwargs
    ) -> None:
        """Обновить данные в сообщении."""
        # Извлекаем тип данных для обновления
        data_type = callback.data.split(":")[1]

        # Здесь должна быть логика обновления в зависимости от типа
        # Пока просто показываем уведомление
        await callback.answer(
            f"{Emoji.REFRESH} Данные обновлены",
            show_alert=False
        )

    async def confirm_action(
            self,
            callback: CallbackQuery,
            state: FSMContext,
            **kwargs
    ) -> None:
        """Подтверждение действия."""
        # Извлекаем действие и параметры
        parts = callback.data.split(":")
        action = parts[1]
        params = parts[2] if len(parts) > 2 else None

        # Обрабатываем в зависимости от действия
        await callback.answer(
            f"{Emoji.CHECK} Подтверждено",
            show_alert=False
        )

        # Здесь должна быть логика выполнения подтвержденного действия

    async def cancel_action(
            self,
            callback: CallbackQuery,
            state: FSMContext,
            **kwargs
    ) -> None:
        """Отмена действия."""
        await state.clear()
        await self.delete_message_safe(callback.message)
        await callback.answer(
            f"{Emoji.CANCEL} Отменено",
            show_alert=False
        )

    async def handle_error(
            self,
            event: ErrorEvent,
            **kwargs
    ) -> None:
        """Обработка ошибок."""
        logger.error(
            f"Error in handler: {event.exception}",
            exc_info=event.exception
        )

        # Пытаемся отправить сообщение пользователю
        if hasattr(event.update, "message") and event.update.message:
            user_message = event.update.message
        elif hasattr(event.update, "callback_query") and event.update.callback_query:
            user_message = event.update.callback_query.message
        else:
            return

        try:
            error_text = MessageFactory.create(
                "error_occurred",
                MessageStyle.HTML
            )

            await user_message.answer(error_text, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Failed to send error message: {e}")

    # Вспомогательные методы

    async def _process_feedback(
            self,
            message: Message,
            feedback_text: str,
            user
    ) -> None:
        """Обработать отзыв."""
        async with get_unit_of_work() as uow:
            # Сохраняем отзыв в БД
            await uow.feedback.create(
                user_id=user.id,
                text=feedback_text,
                type="feedback"
            )
            await uow.commit()

        # Отправляем админам
        await self._notify_admins_about_feedback(
            user,
            feedback_text
        )

        await message.answer(
            f"{Emoji.CHECK} <b>Спасибо за отзыв!</b>\n\n"
            f"Мы обязательно рассмотрим ваше сообщение "
            f"и учтем его в развитии бота.",
            parse_mode="HTML"
        )

    async def _calculate_achievements(
            self,
            user,
            tarot_stats: Dict[str, Any],
            astro_stats: Dict[str, Any]
    ) -> list:
        """Рассчитать достижения пользователя."""
        achievements = []

        # Достижения по количеству раскладов
        spreads = tarot_stats["total_spreads"]
        if spreads >= 100:
            achievements.append(f"{Emoji.ACHIEVEMENT} Мастер Таро (100+ раскладов)")
        elif spreads >= 50:
            achievements.append(f"{Emoji.ACHIEVEMENT} Знаток карт (50+ раскладов)")
        elif spreads >= 10:
            achievements.append(f"{Emoji.ACHIEVEMENT} Искатель истины (10+ раскладов)")

        # Достижения по времени
        days_with_bot = (datetime.utcnow() - user.created_at).days
        if days_with_bot >= 365:
            achievements.append(f"{Emoji.ACHIEVEMENT} Годовщина (365+ дней)")
        elif days_with_bot >= 30:
            achievements.append(f"{Emoji.ACHIEVEMENT} Постоянный клиент (30+ дней)")

        # Достижения по подписке
        if user.subscription_plan == "vip":
            achievements.append(f"{Emoji.CROWN} VIP статус")
        elif user.subscription_plan == "premium":
            achievements.append(f"{Emoji.STAR} Premium подписчик")

        return achievements

    def _get_stats_recommendation(
            self,
            tarot_count: int,
            astro_count: int
    ) -> str:
        """Получить рекомендацию на основе статистики."""
        total = tarot_count + astro_count

        if total == 0:
            return (
                "Начните свое путешествие в мир Таро и астрологии! "
                "Попробуйте расклад 'Карта дня' или дневной гороскоп."
            )
        elif total < 10:
            return (
                "Вы делаете первые шаги в познании себя. "
                "Исследуйте различные расклады и не забывайте о натальной карте!"
            )
        elif tarot_count > astro_count * 2:
            return (
                "Вы истинный ценитель Таро! "
                "Попробуйте также изучить вашу натальную карту для полной картины."
            )
        elif astro_count > tarot_count * 2:
            return (
                "Звезды - ваши верные спутники! "
                "Дополните астрологические знания мудростью карт Таро."
            )
        else:
            return (
                "Отличный баланс между Таро и астрологией! "
                "Продолжайте исследовать оба направления для глубокого самопознания."
            )

    async def _collect_system_info(self, uow) -> Dict[str, Any]:
        """Собрать системную информацию."""
        now = datetime.utcnow()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        # Пользователи
        total_users = await uow.users.count_total()
        active_24h = await uow.users.count_active(days=1)
        active_7d = await uow.users.count_active(days=7)
        new_today = await uow.users.count_registered_after(today_start)

        # Подписки
        subscriptions = await uow.subscriptions.count_by_plan()

        # Активность
        spreads_today = await uow.tarot.count_spreads_after(today_start)
        horoscopes_today = await uow.astrology.count_horoscopes_after(today_start)
        payments_today = await uow.payments.count_after(today_start)

        # Система
        # Здесь должны быть реальные метрики
        uptime = "14d 7h 23m"
        db_size = 156.7
        cache_hits = 87.3

        return {
            "users": {
                "total": total_users,
                "active_24h": active_24h,
                "active_7d": active_7d,
                "new_today": new_today
            },
            "subscriptions": subscriptions,
            "activity": {
                "spreads_today": spreads_today,
                "horoscopes_today": horoscopes_today,
                "payments_today": payments_today
            },
            "system": {
                "uptime": uptime,
                "db_size": db_size,
                "cache_hits": cache_hits
            }
        }

    def _find_similar_commands(
            self,
            command: str,
            known_commands: list
    ) -> list:
        """Найти похожие команды."""
        # Простой алгоритм на основе начала строки
        suggestions = []

        for known in known_commands:
            if known.startswith(command[:3]):
                suggestions.append(known)
            elif command[1:] in known:
                suggestions.append(known)

        return suggestions

    async def _notify_admins_about_feedback(
            self,
            user,
            feedback_text: str
    ) -> None:
        """Уведомить админов о новом отзыве."""
        # Здесь должна быть отправка уведомлений админам
        # Например, через отдельный канал или личные сообщения
        pass

    # Функции для генерации ответов

    def _greeting_response(self) -> str:
        """Ответ на приветствие."""
        return (
            f"{Emoji.WAVE} Привет! Рад вас видеть!\n\n"
            f"Используйте /menu для главного меню "
            f"или /help если нужна помощь."
        )

    def _thanks_response(self) -> str:
        """Ответ на благодарность."""
        return (
            f"{Emoji.HEART} Всегда пожалуйста! "
            f"Рад быть полезным!"
        )

    def _help_hint(self) -> str:
        """Подсказка о помощи."""
        return (
            f"{Emoji.INFO} Нужна помощь?\n\n"
            f"• /help - полная справка\n"
            f"• /support - связь с поддержкой\n"
            f"• /menu - главное меню"
        )

    def _tarot_hint(self) -> str:
        """Подсказка о Таро."""
        return (
            f"{Emoji.CARDS} Интересуетесь Таро?\n\n"
            f"• /tarot - перейти к раскладам\n"
            f"• /menu → Таро - через главное меню\n\n"
            f"Попробуйте расклад 'Карта дня' для начала!"
        )

    def _horoscope_hint(self) -> str:
        """Подсказка о гороскопе."""
        return (
            f"{Emoji.STARS} Хотите узнать гороскоп?\n\n"
            f"• /astrology - раздел астрологии\n"
            f"• /menu → Астрология - через меню\n\n"
            f"Доступны дневные, недельные и личные гороскопы!"
        )

    def _subscription_hint(self) -> str:
        """Подсказка о подписке."""
        return (
            f"{Emoji.PAYMENT} Интересует подписка?\n\n"
            f"• /subscription - управление подпиской\n"
            f"• /menu → Подписка - через меню\n\n"
            f"Откройте больше возможностей с Premium!"
        )


def setup(router: Router) -> None:
    """Настройка обработчиков общих команд."""
    handler = CommonHandler()
    handler.register_handlers(router)