"""
Обработчик команды /start.

Этот модуль отвечает за:
- Приветствие новых пользователей
- Регистрацию в системе
- Обработку реферальных ссылок
- Запуск onboarding процесса
- Возврат существующих пользователей

Автор: AI Assistant
Дата создания: 2024-12-30
"""

import logging
import re
from typing import Optional
from datetime import datetime, timedelta

from aiogram import Router, types, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from bot.handlers.base import BaseHandler, error_handler, log_action, get_or_create_user
from infrastructure import get_unit_of_work
from infrastructure.telegram import (
    Keyboards,
    get_welcome_message,
    get_onboarding_message,
    WelcomeMessageType,
    OnboardingStep,
    get_time_based_greeting
)

# Настройка логирования
logger = logging.getLogger(__name__)


class OnboardingStates(StatesGroup):
    """Состояния процесса онбординга."""
    waiting_name = State()
    waiting_birth_date = State()
    waiting_birth_time = State()
    waiting_birth_place = State()
    showing_features = State()
    selecting_interests = State()


class StartHandler(BaseHandler):
    """Обработчик команды /start и онбординга."""

    def register_handlers(self) -> None:
        """Регистрация обработчиков."""
        # Команда /start
        self.router.message.register(
            self.cmd_start,
            CommandStart()
        )

        # Обработка реферальных параметров
        self.router.message.register(
            self.cmd_start_with_ref,
            CommandStart(deep_link=True)
        )

        # Состояния онбординга
        self.router.message.register(
            self.process_name,
            OnboardingStates.waiting_name
        )

        self.router.message.register(
            self.process_birth_date,
            OnboardingStates.waiting_birth_date
        )

        self.router.message.register(
            self.process_birth_time,
            OnboardingStates.waiting_birth_time
        )

        self.router.message.register(
            self.process_birth_place,
            OnboardingStates.waiting_birth_place
        )

        # Callback кнопок онбординга
        self.router.callback_query.register(
            self.onboarding_callback,
            F.data.startswith("onboarding:")
        )

        # Callback приветственных кнопок
        self.router.callback_query.register(
            self.welcome_callback,
            F.data.startswith("welcome:")
        )

    @error_handler()
    @log_action("start_command")
    async def cmd_start(
            self,
            message: types.Message,
            state: FSMContext
    ) -> None:
        """
        Обработчик команды /start.

        Args:
            message: Сообщение пользователя
            state: Контекст FSM
        """
        user_telegram = message.from_user

        # Получаем или создаем пользователя
        async with get_unit_of_work() as uow:
            user = await uow.users.get_by_telegram_id(user_telegram.id)

            if user:
                # Существующий пользователь
                await self._handle_existing_user(message, user, state)
            else:
                # Новый пользователь
                await self._handle_new_user(message, state)

    @error_handler()
    @log_action("start_with_referral")
    async def cmd_start_with_ref(
            self,
            message: types.Message,
            state: FSMContext
    ) -> None:
        """
        Обработчик /start с реферальным кодом.

        Args:
            message: Сообщение пользователя
            state: Контекст FSM
        """
        # Извлекаем параметр
        args = message.text.split(maxsplit=1)
        if len(args) > 1:
            param = args[1]

            # Проверяем тип параметра
            if param.startswith("ref_"):
                await self._handle_referral(message, param[4:], state)
            elif param.startswith("promo_"):
                await self._handle_promo(message, param[6:], state)
            else:
                # Обычный старт
                await self.cmd_start(message, state)
        else:
            await self.cmd_start(message, state)

    async def _handle_existing_user(
            self,
            message: types.Message,
            user: Any,
            state: FSMContext
    ) -> None:
        """Обработка существующего пользователя."""
        # Очищаем состояние
        await state.clear()

        # Считаем дни отсутствия
        days_away = 0
        if user.last_activity:
            days_away = (datetime.now() - user.last_activity).days

        # Обновляем последнюю активность
        async with get_unit_of_work() as uow:
            await uow.users.update(
                user.id,
                last_activity=datetime.now()
            )

        # Выбираем тип приветствия
        if days_away > 30:
            message_type = WelcomeMessageType.AFTER_BLOCK
        else:
            message_type = WelcomeMessageType.RETURNING_USER

        # Формируем приветствие
        welcome_text = await get_welcome_message(
            message_type,
            {
                "first_name": user.first_name,
                "days_away": days_away,
                "last_action": user.last_action
            }
        )

        # Отправляем с главным меню
        keyboard = await Keyboards.main_menu(
            user_subscription=user.subscription_plan or "free",
            is_admin=user.is_admin,
            user_name=user.first_name
        )

        await message.answer(
            welcome_text,
            reply_markup=keyboard,
            parse_mode="MarkdownV2"
        )

        # Показываем быстрые действия
        quick_keyboard = await Keyboards.quick_actions(
            user_subscription=user.subscription_plan or "free"
        )

        greeting = get_time_based_greeting(user.first_name)
        await message.answer(
            f"{greeting}\nЧто будем делать сегодня?",
            reply_markup=quick_keyboard,
            parse_mode="MarkdownV2"
        )

    async def _handle_new_user(
            self,
            message: types.Message,
            state: FSMContext
    ) -> None:
        """Обработка нового пользователя."""
        user_telegram = message.from_user

        # Создаем пользователя
        async with get_unit_of_work() as uow:
            user = await uow.users.create_or_update_from_telegram(
                telegram_id=user_telegram.id,
                username=user_telegram.username,
                first_name=user_telegram.first_name,
                last_name=user_telegram.last_name,
                language_code=user_telegram.language_code
            )

        # Приветственное сообщение
        welcome_text = await get_welcome_message(
            WelcomeMessageType.FIRST_START,
            {"first_name": user_telegram.first_name}
        )

        # Приветственная клавиатура
        keyboard = await Keyboards.welcome(user_telegram.first_name)

        await message.answer(
            welcome_text,
            reply_markup=keyboard,
            parse_mode="MarkdownV2"
        )

        # Сохраняем данные в состояние
        await state.update_data(
            user_id=user.id,
            is_new_user=True,
            onboarding_step=OnboardingStep.WELCOME.value
        )

    async def _handle_referral(
            self,
            message: types.Message,
            referral_code: str,
            state: FSMContext
    ) -> None:
        """Обработка реферальной ссылки."""
        user_telegram = message.from_user

        async with get_unit_of_work() as uow:
            # Проверяем реферальный код
            referrer = await uow.users.get_by_referral_code(referral_code)

            if not referrer:
                # Неверный код - обычная регистрация
                await self.cmd_start(message, state)
                return

            # Создаем пользователя с реферером
            user = await uow.users.create_or_update_from_telegram(
                telegram_id=user_telegram.id,
                username=user_telegram.username,
                first_name=user_telegram.first_name,
                last_name=user_telegram.last_name,
                language_code=user_telegram.language_code,
                referred_by_id=referrer.id
            )

            # Начисляем бонусы (если есть)
            # TODO: Добавить начисление бонусов

        # Специальное приветствие
        welcome_text = await get_welcome_message(
            WelcomeMessageType.REFERRAL,
            {
                "first_name": user_telegram.first_name,
                "referrer_name": referrer.first_name
            }
        )

        keyboard = await Keyboards.welcome(user_telegram.first_name)

        await message.answer(
            welcome_text,
            reply_markup=keyboard,
            parse_mode="MarkdownV2"
        )

        # Сохраняем данные
        await state.update_data(
            user_id=user.id,
            is_new_user=True,
            referrer_id=referrer.id,
            onboarding_step=OnboardingStep.WELCOME.value
        )

    async def _handle_promo(
            self,
            message: types.Message,
            promo_code: str,
            state: FSMContext
    ) -> None:
        """Обработка промокода при старте."""
        # Создаем пользователя как обычно
        await self._handle_new_user(message, state)

        # Сохраняем промокод для применения позже
        await state.update_data(promo_code=promo_code)

    @error_handler()
    async def welcome_callback(
            self,
            callback: types.CallbackQuery,
            state: FSMContext
    ) -> None:
        """Обработка callback кнопок приветствия."""
        action = callback.data.split(":")[1]

        if action == "start":
            # Начинаем онбординг
            await self._start_onboarding(callback.message, state)

        elif action == "quick_start":
            # Быстрый старт - сразу главное меню
            await self._quick_start(callback.message, state)

        elif action == "about":
            # Информация о боте
            from infrastructure.telegram import get_info_message
            info_text = await get_info_message("about")

            await callback.message.answer(
                info_text,
                parse_mode="MarkdownV2"
            )

        elif action == "promo":
            # Ввод промокода
            await callback.message.answer(
                "🎁 Введите промокод:",
                parse_mode="MarkdownV2"
            )
            # TODO: Добавить состояние для ввода промокода

        await callback.answer()

    async def _start_onboarding(
            self,
            message: types.Message,
            state: FSMContext
    ) -> None:
        """Начать процесс онбординга."""
        # Первый шаг - знакомство
        onboarding_text = await get_onboarding_message(
            OnboardingStep.INTRODUCTION
        )

        await message.answer(
            onboarding_text,
            parse_mode="MarkdownV2"
        )

        # Просим представиться
        await message.answer(
            "Как мне к тебе обращаться? Напиши своё имя:",
            parse_mode="MarkdownV2"
        )

        await state.set_state(OnboardingStates.waiting_name)
        await state.update_data(
            onboarding_step=OnboardingStep.INTRODUCTION.value
        )

    async def _quick_start(
            self,
            message: types.Message,
            state: FSMContext
    ) -> None:
        """Быстрый старт без онбординга."""
        data = await state.get_data()
        user_id = data.get("user_id")

        if not user_id:
            return

        # Обновляем пользователя
        async with get_unit_of_work() as uow:
            user = await uow.users.get_by_id(user_id)
            if user:
                await uow.users.update(
                    user_id,
                    onboarding_completed=True
                )

        # Показываем главное меню
        keyboard = await Keyboards.main_menu()

        await message.answer(
            "Отлично! Вот главное меню:",
            reply_markup=keyboard,
            parse_mode="MarkdownV2"
        )

        # Показываем подсказку по командам
        from infrastructure.telegram import get_info_message
        commands_text = await get_info_message("commands")

        await message.answer(
            commands_text,
            parse_mode="MarkdownV2"
        )

        # Очищаем состояние
        await state.clear()

    @error_handler()
    async def process_name(
            self,
            message: types.Message,
            state: FSMContext
    ) -> None:
        """Обработка ввода имени."""
        name = message.text.strip()

        # Валидация имени
        if len(name) < 2 or len(name) > 50:
            await message.answer(
                "❌ Имя должно быть от 2 до 50 символов",
                parse_mode="MarkdownV2"
            )
            return

        # Сохраняем имя
        data = await state.get_data()
        user_id = data.get("user_id")

        async with get_unit_of_work() as uow:
            await uow.users.update(
                user_id,
                preferred_name=name
            )

        await state.update_data(user_name=name)

        # Следующий шаг - данные рождения
        onboarding_text = await get_onboarding_message(
            OnboardingStep.BIRTH_DATA,
            {"user_name": name}
        )

        # Клавиатура для ввода данных
        from infrastructure.telegram import get_birth_data_keyboard
        keyboard = await get_birth_data_keyboard()

        await message.answer(
            onboarding_text,
            reply_markup=keyboard,
            parse_mode="MarkdownV2"
        )

        await state.update_data(
            onboarding_step=OnboardingStep.BIRTH_DATA.value
        )

    @error_handler()
    async def onboarding_callback(
            self,
            callback: types.CallbackQuery,
            state: FSMContext
    ) -> None:
        """Обработка callback кнопок онбординга."""
        action = callback.data.split(":")[1]

        if action == "skip":
            # Пропуск текущего шага
            await self._skip_onboarding_step(callback.message, state)

        elif action == "complete":
            # Завершение онбординга
            await self._complete_onboarding(callback.message, state)

        await callback.answer()

    async def _skip_onboarding_step(
            self,
            message: types.Message,
            state: FSMContext
    ) -> None:
        """Пропустить текущий шаг онбординга."""
        data = await state.get_data()
        current_step = data.get("onboarding_step")

        # Определяем следующий шаг
        steps = list(OnboardingStep)
        current_index = next(
            (i for i, s in enumerate(steps) if s.value == current_step),
            0
        )

        if current_index < len(steps) - 1:
            next_step = steps[current_index + 1]

            # Показываем следующий шаг
            onboarding_text = await get_onboarding_message(next_step)

            await message.answer(
                onboarding_text,
                parse_mode="MarkdownV2"
            )

            await state.update_data(
                onboarding_step=next_step.value
            )
        else:
            # Завершаем онбординг
            await self._complete_onboarding(message, state)

    async def _complete_onboarding(
            self,
            message: types.Message,
            state: FSMContext
    ) -> None:
        """Завершить процесс онбординга."""
        data = await state.get_data()
        user_id = data.get("user_id")

        # Обновляем пользователя
        async with get_unit_of_work() as uow:
            await uow.users.update(
                user_id,
                onboarding_completed=True
            )

        # Поздравление
        complete_text = await get_onboarding_message(
            OnboardingStep.COMPLETE
        )

        await message.answer(
            complete_text,
            parse_mode="MarkdownV2"
        )

        # Показываем главное меню
        keyboard = await Keyboards.main_menu()

        await message.answer(
            "Теперь ты можешь использовать все возможности бота!",
            reply_markup=keyboard,
            parse_mode="MarkdownV2"
        )

        # Очищаем состояние
        await state.clear()

    # Заглушки для остальных состояний
    async def process_birth_date(
            self,
            message: types.Message,
            state: FSMContext
    ) -> None:
        """Обработка даты рождения."""
        # TODO: Реализовать обработку даты
        await message.answer("Обработка даты рождения...")

    async def process_birth_time(
            self,
            message: types.Message,
            state: FSMContext
    ) -> None:
        """Обработка времени рождения."""
        # TODO: Реализовать обработку времени
        await message.answer("Обработка времени рождения...")

    async def process_birth_place(
            self,
            message: types.Message,
            state: FSMContext
    ) -> None:
        """Обработка места рождения."""
        # TODO: Реализовать обработку места
        await message.answer("Обработка места рождения...")


# Функция для регистрации обработчика
def register_start_handler(router: Router) -> None:
    """
    Регистрация обработчика /start.

    Args:
        router: Роутер для регистрации
    """
    handler = StartHandler(router)
    handler.register_handlers()
    logger.info("Start handler зарегистрирован")


logger.info("Модуль обработчика /start загружен")