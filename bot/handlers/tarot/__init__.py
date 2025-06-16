"""
Модуль обработчиков раздела Таро.

Этот модуль содержит все обработчики для работы с Таро:
- Выбор и выполнение раскладов
- Интерактивный выбор карт
- История и избранное
- Обучающие материалы
- Карта дня

Автор: AI Assistant
Дата создания: 2024-12-30
"""

import logging
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional
import random
import asyncio

from aiogram import Router, F
from aiogram.filters import Command, StateFilter
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest

from bot.handlers.base import (
    BaseHandler,
    require_subscription,
    error_handler,
    log_action,
    get_or_create_user,
    answer_callback_query,
    edit_or_send_message
)
from bot.states import TarotStates
from infrastructure.telegram.keyboards import (
    Keyboards,
    InlineKeyboard,
    TarotCallbackData,
    SpreadCallbackData,
    CardCallbackData,
    HistoryCallbackData
)
from infrastructure import get_unit_of_work
from services import get_tarot_service
from config import settings

logger = logging.getLogger(__name__)


class TarotHandlers(BaseHandler):
    """Обработчики для раздела Таро."""

    # Константы
    TAROT_DECK_SIZE = 78
    MAJOR_ARCANA_SIZE = 22

    def register_handlers(self) -> None:
        """Регистрация обработчиков Таро."""
        # Команда /tarot
        self.router.message.register(
            self.cmd_tarot,
            Command("tarot")
        )

        # Главное меню Таро
        self.router.callback_query.register(
            self.show_tarot_menu,
            F.data == "tarot_menu"
        )

        # Карта дня
        self.router.callback_query.register(
            self.daily_card,
            F.data == "tarot_daily_card"
        )

        # Выбор расклада
        self.router.callback_query.register(
            self.show_spreads_list,
            F.data == "tarot_spreads"
        )

        self.router.callback_query.register(
            self.select_spread,
            F.data.startswith("spread_select:")
        )

        # Процесс выбора карт
        self.router.callback_query.register(
            self.start_card_selection,
            F.data.startswith("spread_start:")
        )

        self.router.callback_query.register(
            self.select_card,
            F.data.startswith("card_select:"),
            StateFilter(TarotStates.selecting_cards)
        )

        self.router.callback_query.register(
            self.random_card_selection,
            F.data == "card_random",
            StateFilter(TarotStates.selecting_cards)
        )

        # Просмотр результата
        self.router.callback_query.register(
            self.show_card_detail,
            F.data.startswith("card_detail:")
        )

        self.router.callback_query.register(
            self.toggle_favorite,
            F.data.startswith("tarot_favorite:")
        )

        self.router.callback_query.register(
            self.share_reading,
            F.data.startswith("tarot_share:")
        )

        # История
        self.router.callback_query.register(
            self.show_history,
            F.data == "tarot_history"
        )

        self.router.callback_query.register(
            self.show_reading_from_history,
            F.data.startswith("history_reading:")
        )

        self.router.callback_query.register(
            self.delete_reading,
            F.data.startswith("reading_delete:")
        )

        # Обучение
        self.router.callback_query.register(
            self.show_learning_menu,
            F.data == "tarot_learning"
        )

        self.router.callback_query.register(
            self.show_lesson,
            F.data.startswith("tarot_lesson:")
        )

        # Статистика
        self.router.callback_query.register(
            self.show_statistics,
            F.data == "tarot_stats"
        )

        # Навигация
        self.router.callback_query.register(
            self.navigate_cards,
            F.data.startswith("card_nav:")
        )

    @error_handler()
    @log_action("tarot_command")
    async def cmd_tarot(
            self,
            message: Message,
            state: FSMContext,
            **kwargs
    ) -> None:
        """Команда /tarot - вход в раздел Таро."""
        await state.clear()

        async with get_unit_of_work() as uow:
            user = await get_or_create_user(message.from_user)
            user_db = await uow.users.get_by_telegram_id(message.from_user.id)

            # Получаем статистику
            stats = await uow.tarot.get_user_statistics(user_db.id) if user_db else {}

            # Проверяем карту дня
            daily_card = await uow.tarot.get_daily_card(user_db.id, date.today()) if user_db else None

            # Используем фабрику клавиатур
            keyboard = await Keyboards.tarot_menu(
                subscription_level=user_db.subscription_plan if user_db and hasattr(user_db, 'subscription_plan') else None,
                has_saved_spreads=stats.get("total_spreads", 0) > 0,
                has_daily_card=daily_card is not None
            )

            text = self._format_tarot_welcome(user_db, stats, daily_card)

            await message.answer(
                text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )

    @error_handler()
    async def show_tarot_menu(
            self,
            callback: CallbackQuery,
            state: FSMContext,
            **kwargs
    ) -> None:
        """Показать главное меню Таро."""
        await state.clear()

        async with get_unit_of_work() as uow:
            user = await uow.users.get_by_telegram_id(callback.from_user.id)

            if not user:
                await answer_callback_query(callback, "Необходимо начать с /start", show_alert=True)
                return

            stats = await uow.tarot.get_user_statistics(user.id)
            daily_card = await uow.tarot.get_daily_card(user.id, date.today())

            # Используем фабрику клавиатур
            keyboard = await Keyboards.tarot_menu(
                subscription_level=user.subscription_plan if hasattr(user, 'subscription_plan') else None,
                has_saved_spreads=stats.get("total_spreads", 0) > 0,
                has_daily_card=daily_card is not None
            )

            text = self._format_tarot_welcome(user, stats, daily_card)

            await edit_or_send_message(
                callback.message,
                text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )

        await answer_callback_query(callback)

    @error_handler()
    @log_action("daily_card")
    async def daily_card(
            self,
            callback: CallbackQuery,
            state: FSMContext,
            **kwargs
    ) -> None:
        """Карта дня."""
        async with get_unit_of_work() as uow:
            user = await uow.users.get_by_telegram_id(callback.from_user.id)

            if not user:
                await answer_callback_query(callback, "Необходимо начать с /start", show_alert=True)
                return

            # Проверяем, была ли уже карта сегодня
            today_card = await uow.tarot.get_daily_card(user.id, date.today())

            if today_card:
                # Показываем существующую карту
                card_info = await self._get_card_info(today_card.card_id)
                text = self._format_daily_card_repeat(card_info, today_card)
            else:
                # Генерируем новую карту
                tarot_service = get_tarot_service()
                card_info = await tarot_service.generate_daily_card(user.id, date.today())

                # Сохраняем в БД
                await uow.tarot.save_daily_card(
                    user_id=user.id,
                    card_id=card_info['id'],
                    date=date.today()
                )
                await uow.commit()

                text = self._format_daily_card_new(card_info)

            # Используем фабрику клавиатур
            keyboard = await Keyboards.tarot_daily_card_result(card_id=card_info['id'])

            await edit_or_send_message(
                callback.message,
                text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )

        await answer_callback_query(callback)

    @error_handler()
    async def show_spreads_list(
            self,
            callback: CallbackQuery,
            state: FSMContext,
            **kwargs
    ) -> None:
        """Показать список доступных раскладов."""
        async with get_unit_of_work() as uow:
            user = await uow.users.get_by_telegram_id(callback.from_user.id)
            subscription = user.subscription_plan if user and hasattr(user, 'subscription_plan') else "free"

            text = (
                "🎴 <b>Выберите расклад</b>\n\n"
                "Доступные расклады для вашего уровня подписки:"
            )

            # Используем фабрику клавиатур
            spreads_list = self._get_spreads_list()
            keyboard = await Keyboards.tarot_spreads_menu(
                spreads=spreads_list,
                user_subscription=subscription
            )

            await edit_or_send_message(
                callback.message,
                text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )

        await answer_callback_query(callback)

    @error_handler()
    async def select_spread(
            self,
            callback: CallbackQuery,
            state: FSMContext,
            **kwargs
    ) -> None:
        """Выбор конкретного расклада."""
        spread_type = callback.data.split(":")[1]

        async with get_unit_of_work() as uow:
            user = await uow.users.get_by_telegram_id(callback.from_user.id)

            # Проверяем доступность расклада
            if not self._is_spread_available(spread_type, user.subscription_plan if user else "free"):
                await answer_callback_query(
                    callback,
                    "⭐ Этот расклад доступен только по подписке",
                    show_alert=True
                )
                return

            spread_info = self._get_spread_info(spread_type)

            # Сохраняем тип расклада в состоянии
            await state.update_data(
                spread_type=spread_type,
                spread_info=spread_info
            )

            if spread_info["requires_question"]:
                # Запрашиваем вопрос
                text = (
                    f"<b>{spread_info['name']}</b>\n\n"
                    f"{spread_info['description']}\n\n"
                    "Сформулируйте ваш вопрос:"
                )

                # Создаем клавиатуру с кнопками
                keyboard = InlineKeyboard()
                keyboard.add_button(
                    text="⏭ Без вопроса",
                    callback_data=f"spread_start:{spread_type}:no_question"
                )
                keyboard.add_button(
                    text="◀️ Назад",
                    callback_data="tarot_spreads"
                )
                keyboard.builder.adjust(1)

                await edit_or_send_message(
                    callback.message,
                    text,
                    reply_markup=await keyboard.build(),
                    parse_mode="HTML"
                )

                await state.set_state(TarotStates.waiting_for_question)
            else:
                # Сразу начинаем расклад
                await self.start_card_selection(callback, state)

        await answer_callback_query(callback)

    @error_handler()
    async def start_card_selection(
            self,
            callback: CallbackQuery,
            state: FSMContext,
            **kwargs
    ) -> None:
        """Начать процесс выбора карт."""
        data = await state.get_data()
        spread_info = data.get("spread_info")

        if not spread_info:
            await answer_callback_query(callback, "Ошибка: информация о раскладе потеряна", show_alert=True)
            return

        # Генерируем колоду
        deck = list(range(self.TAROT_DECK_SIZE))
        random.shuffle(deck)

        await state.update_data(
            deck=deck,
            selected_cards=[],
            current_position=0
        )

        text = (
            f"<b>Выбор карт для расклада \"{spread_info['name']}\"</b>\n\n"
            f"Позиция 1/{spread_info['card_count']}: {spread_info['positions'][0]}\n\n"
            "Выберите карту или доверьтесь случаю:"
        )

        # Используем фабрику клавиатур
        keyboard = await Keyboards.tarot_card_selection()

        await edit_or_send_message(
            callback.message,
            text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )

        await state.set_state(TarotStates.selecting_cards)
        await answer_callback_query(callback)

    @error_handler()
    async def show_history(
            self,
            callback: CallbackQuery,
            state: FSMContext,
            **kwargs
    ) -> None:
        """Показать историю раскладов."""
        async with get_unit_of_work() as uow:
            user = await uow.users.get_by_telegram_id(callback.from_user.id)

            if not user:
                await answer_callback_query(callback, "Необходимо начать с /start", show_alert=True)
                return

            # Получаем историю
            history = await uow.tarot.get_user_spreads(user.id, limit=10)

            if not history:
                text = "📚 <b>История раскладов</b>\n\nУ вас пока нет сохраненных раскладов."

                keyboard = InlineKeyboard()
                keyboard.add_button(text="🎴 Сделать расклад", callback_data="tarot_spreads")
                keyboard.add_button(text="◀️ Назад", callback_data="tarot_menu")
                keyboard.builder.adjust(1)

                keyboard_markup = await keyboard.build()
            else:
                text = "📚 <b>История раскладов</b>\n\nВаши последние расклады:"

                # Используем фабрику клавиатур
                history_items = []
                for reading in history[:5]:
                    spread_name = self._get_spread_info(reading.spread_type)["name"]
                    history_items.append({
                        'id': reading.id,
                        'date': reading.created_at,
                        'spread_type': reading.spread_type,
                        'spread_name': spread_name
                    })

                keyboard_markup = await Keyboards.tarot_history(history_items)

            await edit_or_send_message(
                callback.message,
                text,
                reply_markup=keyboard_markup,
                parse_mode="HTML"
            )

        await answer_callback_query(callback)

    @error_handler()
    async def show_learning_menu(
            self,
            callback: CallbackQuery,
            state: FSMContext,
            **kwargs
    ) -> None:
        """Показать меню обучения."""
        text = (
            "📖 <b>Обучение Таро</b>\n\n"
            "Изучите значения карт и основы гадания:\n\n"
            "Выберите раздел:"
        )

        # Используем фабрику клавиатур
        keyboard = await Keyboards.tarot_learning_menu()

        await edit_or_send_message(
            callback.message,
            text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )

        await answer_callback_query(callback)

    @error_handler()
    async def show_statistics(
            self,
            callback: CallbackQuery,
            state: FSMContext,
            **kwargs
    ) -> None:
        """Показать статистику пользователя."""
        async with get_unit_of_work() as uow:
            user = await uow.users.get_by_telegram_id(callback.from_user.id)

            if not user:
                await answer_callback_query(callback, "Необходимо начать с /start", show_alert=True)
                return

            stats = await uow.tarot.get_detailed_statistics(user.id)

            text = self._format_statistics(stats)

            # Создаем клавиатуру
            keyboard = InlineKeyboard()
            keyboard.add_button(text="🔄 Обновить", callback_data="refresh:tarot_stats")
            keyboard.add_button(text="◀️ Назад", callback_data="tarot_menu")
            keyboard.builder.adjust(1)

            await edit_or_send_message(
                callback.message,
                text,
                reply_markup=await keyboard.build(),
                parse_mode="HTML"
            )

        await answer_callback_query(callback)

    # Вспомогательные методы

    def _format_tarot_welcome(
            self,
            user: Any,
            stats: Dict[str, Any],
            daily_card: Any
    ) -> str:
        """Форматировать приветственное сообщение."""
        text = "🎴 <b>Таро</b>\n\n"

        if user and hasattr(user, 'display_name'):
            text += f"Добро пожаловать, {user.display_name}!\n\n"

        text += "Откройте тайны судьбы с помощью древней мудрости карт Таро.\n\n"

        if stats.get("total_spreads", 0) > 0:
            text += f"📊 Ваша статистика:\n"
            text += f"• Раскладов выполнено: {stats['total_spreads']}\n"

            if stats.get("favorite_card"):
                text += f"• Частая карта: {stats['favorite_card']}\n"

            text += "\n"

        if daily_card:
            text += "✅ Карта дня уже получена\n\n"
        else:
            text += "🎴 Не забудьте получить карту дня!\n\n"

        text += "Выберите действие:"

        return text

    def _format_daily_card_new(self, card_info: Dict[str, Any]) -> str:
        """Форматировать новую карту дня."""
        text = (
            f"🎴 <b>Ваша карта дня</b>\n\n"
            f"<b>{card_info['name']}</b>\n\n"
            f"<i>{card_info['description']}</i>\n\n"
            f"<b>Ключевые слова:</b> {', '.join(card_info['keywords'])}\n\n"
            f"<b>Совет на день:</b>\n{card_info['daily_advice']}"
        )

        return text

    def _format_daily_card_repeat(self, card_info: Dict[str, Any], saved_card: Any) -> str:
        """Форматировать повторный показ карты дня."""
        text = (
            f"🎴 <b>Ваша карта дня</b>\n"
            f"<i>(получена в {saved_card.created_at.strftime('%H:%M')})</i>\n\n"
            f"<b>{card_info['name']}</b>\n\n"
            f"<i>{card_info['description']}</i>\n\n"
            f"<b>Напоминание:</b>\n{card_info['daily_advice']}"
        )

        return text

    def _format_statistics(self, stats: Dict[str, Any]) -> str:
        """Форматировать статистику."""
        text = "📊 <b>Ваша статистика Таро</b>\n\n"

        # Общая статистика
        text += f"<b>Всего раскладов:</b> {stats.get('total_spreads', 0)}\n"
        text += f"<b>Карт дня получено:</b> {stats.get('daily_cards', 0)}\n"
        text += f"<b>Избранных раскладов:</b> {stats.get('favorites', 0)}\n\n"

        # Любимые расклады
        if stats.get('favorite_spreads'):
            text += "<b>Любимые расклады:</b>\n"
            for spread, count in stats['favorite_spreads'][:3]:
                text += f"• {spread}: {count} раз\n"
            text += "\n"

        # Частые карты
        if stats.get('frequent_cards'):
            text += "<b>Частые карты:</b>\n"
            for card, count in stats['frequent_cards'][:5]:
                text += f"• {card}: {count} раз\n"

        return text

    def _get_spreads_list(self) -> List[Dict[str, Any]]:
        """Получить список всех раскладов."""
        return [
            {
                "id": "three_cards",
                "name": "🔮 Три карты",
                "required_subscription": "free"
            },
            {
                "id": "celtic_cross",
                "name": "✨ Кельтский крест",
                "required_subscription": "basic"
            },
            {
                "id": "relationship",
                "name": "💑 Отношения",
                "required_subscription": "premium"
            },
            {
                "id": "year_ahead",
                "name": "📅 Год вперед",
                "required_subscription": "premium"
            },
            {
                "id": "decision",
                "name": "🤔 Принятие решения",
                "required_subscription": "basic"
            },
            {
                "id": "chakras",
                "name": "🌈 Чакры",
                "required_subscription": "vip"
            }
        ]

    def _get_spread_info(self, spread_type: str) -> Dict[str, Any]:
        """Получить информацию о раскладе."""
        spreads = {
            "three_cards": {
                "type": "three_cards",
                "name": "Три карты",
                "description": "Простой расклад для быстрого анализа ситуации",
                "card_count": 3,
                "positions": ["Прошлое", "Настоящее", "Будущее"],
                "requires_question": True,
                "subscription": "free"
            },
            "celtic_cross": {
                "type": "celtic_cross",
                "name": "Кельтский крест",
                "description": "Классический подробный расклад",
                "card_count": 10,
                "positions": [
                    "Ситуация", "Вызов", "Прошлое", "Будущее",
                    "Возможности", "Влияние", "Совет", "Внешние силы",
                    "Надежды и страхи", "Итог"
                ],
                "requires_question": True,
                "subscription": "basic"
            },
            "relationship": {
                "type": "relationship",
                "name": "Отношения",
                "description": "Анализ отношений между людьми",
                "card_count": 7,
                "positions": [
                    "Вы", "Партнер", "Основа отношений",
                    "Прошлое", "Настоящее", "Будущее", "Совет"
                ],
                "requires_question": False,
                "subscription": "premium"
            },
            "year_ahead": {
                "type": "year_ahead",
                "name": "Год вперед",
                "description": "Прогноз на 12 месяцев",
                "card_count": 12,
                "positions": [f"Месяц {i+1}" for i in range(12)],
                "requires_question": False,
                "subscription": "premium"
            },
            "decision": {
                "type": "decision",
                "name": "Принятие решения",
                "description": "Поможет сделать выбор",
                "card_count": 5,
                "positions": ["Ситуация", "Вариант 1", "Вариант 2", "Совет", "Результат"],
                "requires_question": True,
                "subscription": "basic"
            },
            "chakras": {
                "type": "chakras",
                "name": "Чакры",
                "description": "Анализ энергетических центров",
                "card_count": 7,
                "positions": [
                    "Муладхара", "Свадхистана", "Манипура",
                    "Анахата", "Вишудха", "Аджна", "Сахасрара"
                ],
                "requires_question": False,
                "subscription": "vip"
            }
        }

        return spreads.get(spread_type, spreads["three_cards"])

    def _is_spread_available(
            self,
            spread_type: str,
            user_subscription: str
    ) -> bool:
        """Проверить доступность расклада для подписки."""
        spread_info = self._get_spread_info(spread_type)

        subscription_levels = {
            "free": 0,
            "basic": 1,
            "premium": 2,
            "vip": 3
        }

        required_level = subscription_levels.get(
            spread_info.get("subscription", "free"),
            0
        )
        user_level = subscription_levels.get(user_subscription or "free", 0)

        return user_level >= required_level

    async def _get_card_info(self, card_id: int) -> Dict[str, Any]:
        """Получить информацию о карте."""
        tarot_service = get_tarot_service()
        return await tarot_service.get_card_info(card_id)


# Функция для регистрации обработчика
def register_tarot_handler(router: Router) -> None:
    """
    Регистрация обработчика Таро.

    Args:
        router: Роутер для регистрации
    """
    handler = TarotHandlers(router)
    handler.register_handlers()
    logger.info("Tarot handler зарегистрирован")


logger.info("Модуль обработчика Таро загружен")