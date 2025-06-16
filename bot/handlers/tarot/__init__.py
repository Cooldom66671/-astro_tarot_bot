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

from bot.handlers.base import BaseHandler, require_subscription, error_handler
from bot.states import TarotStates
from infrastructure.telegram import (
    Keyboards,
    MessageFactory,
    TarotCardMessage,
    TarotSpreadMessage,
    MessageBuilder,
    MessageStyle,
    MessageEmoji as Emoji
)
from infrastructure import get_unit_of_work
from infrastructure.external_apis import get_llm_manager

logger = logging.getLogger(__name__)


class TarotHandlers(BaseHandler):
    """Обработчики для раздела Таро."""

    # Константы
    TAROT_DECK_SIZE = 78
    MAJOR_ARCANA_SIZE = 22

    def register_handlers(self, router: Router) -> None:
        """Регистрация обработчиков Таро."""
        # Команда /tarot
        router.message.register(
            self.cmd_tarot,
            Command("tarot")
        )

        # Главное меню Таро
        router.callback_query.register(
            self.show_tarot_menu,
            F.data == "tarot_menu"
        )

        # Карта дня
        router.callback_query.register(
            self.daily_card,
            F.data == "tarot_daily_card"
        )

        # Выбор расклада
        router.callback_query.register(
            self.show_spreads_list,
            F.data == "tarot_spreads"
        )

        router.callback_query.register(
            self.select_spread,
            F.data.startswith("spread_select:")
        )

        # Процесс выбора карт
        router.callback_query.register(
            self.start_card_selection,
            F.data.startswith("spread_start:")
        )

        router.callback_query.register(
            self.select_card,
            F.data.startswith("card_select:"),
            StateFilter(TarotStates.selecting_cards)
        )

        router.callback_query.register(
            self.random_card_selection,
            F.data == "card_random",
            StateFilter(TarotStates.selecting_cards)
        )

        # Просмотр результата
        router.callback_query.register(
            self.show_card_detail,
            F.data.startswith("card_detail:")
        )

        router.callback_query.register(
            self.toggle_favorite,
            F.data.startswith("tarot_favorite:")
        )

        router.callback_query.register(
            self.share_reading,
            F.data.startswith("tarot_share:")
        )

        # История
        router.callback_query.register(
            self.show_history,
            F.data == "tarot_history"
        )

        router.callback_query.register(
            self.show_reading_from_history,
            F.data.startswith("history_reading:")
        )

        router.callback_query.register(
            self.delete_reading,
            F.data.startswith("reading_delete:")
        )

        # Обучение
        router.callback_query.register(
            self.show_learning_menu,
            F.data == "tarot_learning"
        )

        router.callback_query.register(
            self.show_lesson,
            F.data.startswith("tarot_lesson:")
        )

        # Статистика
        router.callback_query.register(
            self.show_statistics,
            F.data == "tarot_stats"
        )

        # Навигация
        router.callback_query.register(
            self.navigate_cards,
            F.data.startswith("card_nav:")
        )

    async def cmd_tarot(
            self,
            message: Message,
            state: FSMContext,
            **kwargs
    ) -> None:
        """Команда /tarot - вход в раздел Таро."""
        await state.clear()

        async with get_unit_of_work() as uow:
            user = await self.get_or_create_user(uow, message.from_user)

            # Получаем статистику
            stats = await uow.tarot.get_user_statistics(user.id)

            # Проверяем карту дня
            daily_card = await uow.tarot.get_daily_card(user.id, date.today())

            keyboard = await Keyboards.tarot_menu(
                subscription_level=user.subscription_plan,
                has_saved_spreads=stats.get("total_spreads", 0) > 0,
                has_daily_card=daily_card is not None
            )

            text = await self._format_tarot_welcome(user, stats, daily_card)

            await message.answer(
                text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )

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

            stats = await uow.tarot.get_user_statistics(user.id)
            daily_card = await uow.tarot.get_daily_card(user.id, date.today())

            keyboard = await Keyboards.tarot_menu(
                subscription_level=user.subscription_plan,
                has_saved_spreads=stats.get("total_spreads", 0) > 0,
                has_daily_card=daily_card is not None
            )

            text = await self._format_tarot_welcome(user, stats, daily_card)

            await self.edit_or_send_message(
                callback,
                text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )

    @error_handler
    async def daily_card(
            self,
            callback: CallbackQuery,
            **kwargs
    ) -> None:
        """Карта дня."""
        await callback.answer(f"{Emoji.LOADING} Вытягиваю карту...")

        async with get_unit_of_work() as uow:
            user = await uow.users.get_by_telegram_id(callback.from_user.id)

            # Проверяем, есть ли уже карта дня
            existing_card = await uow.tarot.get_daily_card(user.id, date.today())

            if existing_card:
                # Показываем существующую карту
                card_id = existing_card.cards[0]["id"]
                interpretation = existing_card.interpretation
            else:
                # Выбираем новую карту
                card_id = random.randint(1, self.TAROT_DECK_SIZE)
                is_reversed = random.choice([True, False])

                # Получаем интерпретацию от AI
                interpretation = await self._get_card_interpretation(
                    card_id,
                    is_reversed,
                    "daily",
                    user
                )

                # Сохраняем в БД
                reading = await uow.tarot.create_reading(
                    user_id=user.id,
                    spread_type="daily_card",
                    question=None,
                    cards=[{
                        "id": card_id,
                        "position": 1,
                        "is_reversed": is_reversed
                    }],
                    interpretation=interpretation
                )
                await uow.commit()

            # Форматируем сообщение
            card_info = self._get_card_info(card_id)

            message = TarotCardMessage(
                card_name=card_info["name"],
                is_reversed=existing_card.cards[0]["is_reversed"] if existing_card else is_reversed,
                meaning=interpretation,
                keywords=card_info.get("keywords", []),
                advice=card_info.get("advice", ""),
                context="daily"
            )

            text = await message.format()

            # Клавиатура
            keyboard = await Keyboards.daily_card_actions(
                can_draw_new=existing_card is None
            )

            await self.edit_or_send_message(
                callback,
                text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )

    async def show_spreads_list(
            self,
            callback: CallbackQuery,
            **kwargs
    ) -> None:
        """Показать список доступных раскладов."""
        async with get_unit_of_work() as uow:
            user = await uow.users.get_by_telegram_id(callback.from_user.id)

            keyboard = await Keyboards.spread_selection(
                subscription_level=user.subscription_plan
            )

            text = (
                f"<b>{Emoji.CARDS} Выберите расклад</b>\n\n"
                f"Каждый расклад раскрывает определенные аспекты "
                f"вашей ситуации.\n\n"
                f"💡 <i>Совет: начните с простых раскладов, "
                f"если вы новичок в Таро</i>"
            )

            await self.edit_or_send_message(
                callback,
                text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )

    async def select_spread(
            self,
            callback: CallbackQuery,
            state: FSMContext,
            **kwargs
    ) -> None:
        """Выбор конкретного расклада."""
        spread_type = callback.data.split(":")[1]

        # Проверяем доступность расклада
        async with get_unit_of_work() as uow:
            user = await uow.users.get_by_telegram_id(callback.from_user.id)

            if not self._is_spread_available(spread_type, user.subscription_plan):
                await callback.answer(
                    "Этот расклад доступен только для подписчиков Premium",
                    show_alert=True
                )
                return

        # Получаем информацию о раскладе
        spread_info = self._get_spread_info(spread_type)

        # Сохраняем в состояние
        await state.update_data(
            spread_type=spread_type,
            spread_info=spread_info
        )

        # Запрашиваем вопрос, если нужно
        if spread_info.get("requires_question", True):
            await state.set_state(TarotStates.waiting_for_question)

            text = (
                f"<b>{spread_info['name']}</b>\n\n"
                f"{spread_info['description']}\n\n"
                f"🔮 <b>Сформулируйте ваш вопрос:</b>\n"
                f"<i>Чем конкретнее вопрос, тем точнее будет ответ</i>"
            )

            keyboard = await Keyboards.cancel_only()

            await self.edit_or_send_message(
                callback,
                text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        else:
            # Сразу начинаем выбор карт
            await self.start_card_selection(callback, state)

    async def start_card_selection(
            self,
            callback: CallbackQuery,
            state: FSMContext,
            **kwargs
    ) -> None:
        """Начать процесс выбора карт."""
        data = await state.get_data()
        spread_info = data.get("spread_info") or self._get_spread_info(
            callback.data.split(":")[1]
        )

        # Инициализируем данные для выбора карт
        await state.update_data(
            spread_info=spread_info,
            selected_cards=[],
            current_position=1
        )
        await state.set_state(TarotStates.selecting_cards)

        # Показываем интерфейс выбора первой карты
        await self._show_card_selection_interface(
            callback,
            state,
            position=1,
            total=spread_info["card_count"]
        )

    async def select_card(
            self,
            callback: CallbackQuery,
            state: FSMContext,
            **kwargs
    ) -> None:
        """Выбор конкретной карты."""
        card_id = int(callback.data.split(":")[1])

        data = await state.get_data()
        selected_cards = data.get("selected_cards", [])
        current_position = data.get("current_position", 1)
        spread_info = data["spread_info"]

        # Проверяем, не выбрана ли карта уже
        if any(card["id"] == card_id for card in selected_cards):
            await callback.answer(
                "Эта карта уже выбрана! Выберите другую.",
                show_alert=True
            )
            return

        # Добавляем карту
        is_reversed = random.choice([True, False])
        selected_cards.append({
            "id": card_id,
            "position": current_position,
            "is_reversed": is_reversed,
            "position_name": spread_info["positions"][current_position - 1]
        })

        await state.update_data(
            selected_cards=selected_cards,
            current_position=current_position + 1
        )

        # Проверяем, все ли карты выбраны
        if len(selected_cards) == spread_info["card_count"]:
            # Завершаем выбор
            await self._complete_reading(callback, state)
        else:
            # Показываем выбор следующей карты
            await self._show_card_selection_interface(
                callback,
                state,
                position=current_position + 1,
                total=spread_info["card_count"]
            )

    async def random_card_selection(
            self,
            callback: CallbackQuery,
            state: FSMContext,
            **kwargs
    ) -> None:
        """Случайный выбор всех оставшихся карт."""
        data = await state.get_data()
        selected_cards = data.get("selected_cards", [])
        spread_info = data["spread_info"]

        # Получаем ID уже выбранных карт
        selected_ids = [card["id"] for card in selected_cards]

        # Выбираем оставшиеся карты
        available_cards = [
            i for i in range(1, self.TAROT_DECK_SIZE + 1)
            if i not in selected_ids
        ]

        remaining_count = spread_info["card_count"] - len(selected_cards)
        random_cards = random.sample(available_cards, remaining_count)

        # Добавляем карты
        for i, card_id in enumerate(random_cards):
            position = len(selected_cards) + i + 1
            selected_cards.append({
                "id": card_id,
                "position": position,
                "is_reversed": random.choice([True, False]),
                "position_name": spread_info["positions"][position - 1]
            })

        await state.update_data(selected_cards=selected_cards)

        # Завершаем расклад
        await self._complete_reading(callback, state)

    @require_subscription("basic")
    async def show_history(
            self,
            callback: CallbackQuery,
            **kwargs
    ) -> None:
        """Показать историю раскладов."""
        async with get_unit_of_work() as uow:
            user = await uow.users.get_by_telegram_id(callback.from_user.id)

            # Получаем историю
            readings = await uow.tarot.get_user_readings(
                user.id,
                limit=10,
                offset=0
            )

            if not readings:
                await callback.answer(
                    "У вас пока нет сохраненных раскладов",
                    show_alert=True
                )
                return

            keyboard = await Keyboards.tarot_history(
                readings=readings,
                page=1,
                total_pages=1  # Упрощенно
            )

            text = (
                f"<b>{Emoji.HISTORY} История ваших раскладов</b>\n\n"
                f"Всего раскладов: {len(readings)}\n\n"
                f"Выберите расклад для просмотра:"
            )

            await self.edit_or_send_message(
                callback,
                text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )

    async def show_learning_menu(
            self,
            callback: CallbackQuery,
            **kwargs
    ) -> None:
        """Показать меню обучения."""
        keyboard = await Keyboards.tarot_learning()

        text = (
            f"<b>{Emoji.EDUCATION} Обучение Таро</b>\n\n"
            f"Изучайте значения карт, символику и методы интерпретации.\n\n"
            f"Выберите раздел:"
        )

        await self.edit_or_send_message(
            callback,
            text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )

    async def show_statistics(
            self,
            callback: CallbackQuery,
            **kwargs
    ) -> None:
        """Показать статистику Таро."""
        async with get_unit_of_work() as uow:
            user = await uow.users.get_by_telegram_id(callback.from_user.id)
            stats = await uow.tarot.get_detailed_statistics(user.id)

            message = MessageFactory.create(
                "tarot_statistics",
                MessageStyle.HTML,
                stats=stats,
                user_name=user.display_name
            )

            keyboard = await Keyboards.back_button("tarot_menu")

            await self.edit_or_send_message(
                callback,
                message,
                reply_markup=keyboard,
                parse_mode="HTML"
            )

    # Вспомогательные методы

    async def _format_tarot_welcome(
            self,
            user,
            stats: Dict[str, Any],
            daily_card
    ) -> str:
        """Форматировать приветствие раздела Таро."""
        builder = MessageBuilder(MessageStyle.HTML)

        builder.add_bold(f"{Emoji.CARDS} Добро пожаловать в мир Таро").add_line(2)

        if daily_card:
            builder.add_text("✨ Ваша карта дня уже выбрана").add_line()
        else:
            builder.add_text("🌟 Вы можете получить карту дня").add_line()

        if stats["total_spreads"] > 0:
            builder.add_line()
            builder.add_text(f"📊 Ваших раскладов: {stats['total_spreads']}").add_line()

            if stats.get("favorite_spread"):
                builder.add_text(f"❤️ Любимый: {stats['favorite_spread']}").add_line()

        builder.add_line()
        builder.add_italic("Что бы вы хотели узнать сегодня?")

        return builder.build()

    async def _show_card_selection_interface(
            self,
            callback: CallbackQuery,
            state: FSMContext,
            position: int,
            total: int
    ) -> None:
        """Показать интерфейс выбора карты."""
        data = await state.get_data()
        spread_info = data["spread_info"]
        selected_cards = data.get("selected_cards", [])

        # Текст с прогрессом
        position_name = spread_info["positions"][position - 1]

        text = (
            f"<b>Выбор карт: {position} из {total}</b>\n\n"
            f"🎯 <b>Позиция:</b> {position_name}\n\n"
            f"Выберите карту интуитивно или нажмите "
            f"'Случайный выбор' для автоматического выбора"
        )

        # Клавиатура выбора карт
        keyboard = await Keyboards.card_selection(
            excluded_cards=[card["id"] for card in selected_cards],
            show_minor=True,
            current_page=1
        )

        await self.edit_or_send_message(
            callback,
            text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )

    async def _complete_reading(
            self,
            callback: CallbackQuery,
            state: FSMContext
    ) -> None:
        """Завершить расклад и показать результат."""
        await callback.answer(f"{Emoji.LOADING} Интерпретирую расклад...")

        data = await state.get_data()
        spread_info = data["spread_info"]
        selected_cards = data["selected_cards"]
        question = data.get("question")

        async with get_unit_of_work() as uow:
            user = await uow.users.get_by_telegram_id(callback.from_user.id)

            # Получаем интерпретацию от AI
            interpretation = await self._get_spread_interpretation(
                spread_info["type"],
                selected_cards,
                question,
                user
            )

            # Сохраняем в БД
            reading = await uow.tarot.create_reading(
                user_id=user.id,
                spread_type=spread_info["type"],
                question=question,
                cards=selected_cards,
                interpretation=interpretation
            )
            await uow.commit()

            # Форматируем результат
            message = TarotSpreadMessage(
                spread_name=spread_info["name"],
                question=question,
                cards=selected_cards,
                interpretation=interpretation,
                reading_id=reading.id
            )

            text = await message.format()

            # Клавиатура действий
            keyboard = await Keyboards.reading_result_actions(
                reading_id=reading.id,
                is_favorite=False
            )

            await self.edit_or_send_message(
                callback,
                text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )

        await state.clear()

    async def _get_card_interpretation(
            self,
            card_id: int,
            is_reversed: bool,
            context: str,
            user
    ) -> str:
        """Получить интерпретацию карты от AI."""
        card_info = self._get_card_info(card_id)

        prompt = f"""
        Дай интерпретацию карты Таро для контекста "{context}":

        Карта: {card_info['name']}
        Положение: {'Перевернутая' if is_reversed else 'Прямое'}
        Ключевые слова: {', '.join(card_info.get('keywords', []))}

        Дай краткую, но содержательную интерпретацию (3-4 предложения).
        Учитывай положение карты. Будь позитивным и конструктивным.
        """

        llm = await get_llm_manager()
        interpretation = await llm.generate_completion(
            prompt,
            temperature=0.7,
            max_tokens=200
        )

        return interpretation

    async def _get_spread_interpretation(
            self,
            spread_type: str,
            cards: List[Dict],
            question: Optional[str],
            user
    ) -> str:
        """Получить интерпретацию расклада от AI."""
        spread_info = self._get_spread_info(spread_type)

        # Формируем описание карт
        cards_description = []
        for card in cards:
            card_info = self._get_card_info(card["id"])
            cards_description.append(
                f"{card['position_name']}: {card_info['name']} "
                f"({'перевернутая' if card['is_reversed'] else 'прямая'})"
            )

        prompt = f"""
        Сделай интерпретацию расклада Таро "{spread_info['name']}".

        {"Вопрос: " + question if question else "Общий расклад"}

        Карты:
        {chr(10).join(cards_description)}

        Дай связную интерпретацию расклада, учитывая:
        1. Значение каждой позиции
        2. Взаимосвязь между картами
        3. Общее послание расклада

        Будь конкретным, позитивным и дай практические советы.
        Ответ должен быть 5-7 предложений.
        """

        llm = await get_llm_manager()
        interpretation = await llm.generate_completion(
            prompt,
            temperature=0.7,
            max_tokens=400
        )

        return interpretation

    def _get_card_info(self, card_id: int) -> Dict[str, Any]:
        """Получить информацию о карте."""
        # Здесь должна быть полная база данных карт
        # Упрощенная версия для примера

        major_arcana = {
            1: {"name": "Маг", "keywords": ["воля", "мастерство", "действие"]},
            2: {"name": "Верховная Жрица", "keywords": ["интуиция", "тайна", "мудрость"]},
            3: {"name": "Императрица", "keywords": ["плодородие", "забота", "изобилие"]},
            # ... остальные карты
        }

        if card_id <= self.MAJOR_ARCANA_SIZE:
            return major_arcana.get(card_id, {
                "name": f"Старший Аркан {card_id}",
                "keywords": ["тайна", "судьба", "путь"]
            })
        else:
            # Младшие арканы
            suits = ["Жезлы", "Кубки", "Мечи", "Пентакли"]
            suit_index = (card_id - self.MAJOR_ARCANA_SIZE - 1) // 14
            card_in_suit = (card_id - self.MAJOR_ARCANA_SIZE - 1) % 14 + 1

            if card_in_suit <= 10:
                name = f"{card_in_suit} {suits[suit_index]}"
            else:
                court = ["Паж", "Рыцарь", "Королева", "Король"]
                name = f"{court[card_in_suit - 11]} {suits[suit_index]}"

            return {
                "name": name,
                "keywords": ["энергия", "действие", "развитие"]
            }

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
        user_level = subscription_levels.get(user_subscription, 0)

        return user_level >= required_level


def setup(router: Router) -> None:
    """Настройка обработчиков Таро."""
    handler = TarotHandlers()
    handler.register_handlers(router)