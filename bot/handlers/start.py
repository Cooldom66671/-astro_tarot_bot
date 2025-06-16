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
from typing import Optional, Any
from datetime import datetime, timedelta

from aiogram import Router, types, F
from aiogram.filters import CommandStart, Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

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
    Keyboards,
    get_main_menu,
    get_welcome_keyboard,
    TimeBasedGreetingKeyboard,
    BirthDataKeyboard,
    get_birth_data_keyboard,
    MainMenuCallbackData,
    BirthDataCallbackData,
    parse_callback_data
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
        # Команда /start без параметров
        self.router.message.register(
            self.cmd_start,
            CommandStart()
        )

        # Команда /start с параметрами (deep link)
        self.router.message.register(
            self.cmd_start_with_args,
            Command("start"),
            lambda message: len(message.text.split()) > 1
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

        # НОВЫЕ CALLBACK ДЛЯ ДАННЫХ РОЖДЕНИЯ
        self.router.callback_query.register(
            self.birth_data_callback,
            BirthDataCallbackData.filter()
        )

    @error_handler()
    @log_action("start_command")
    async def cmd_start(
            self,
            message: types.Message,
            state: FSMContext,
            **kwargs
    ) -> None:
        """
        Обработчик команды /start.

        Args:
            message: Сообщение пользователя
            state: Контекст FSM
        """
        # Очищаем состояние
        await state.clear()

        user_telegram = message.from_user

        # Получаем или создаем пользователя
        user = await get_or_create_user(user_telegram)

        # Проверяем, новый ли это пользователь
        async with get_unit_of_work() as uow:
            # Проверяем, есть ли у пользователя заполненные данные
            user_db = await uow.users.get_by_telegram_id(user_telegram.id)

            if user_db and user_db.birth_date:
                # Существующий пользователь с данными
                await self._handle_existing_user(message, user_db, state)
            else:
                # Новый пользователь или без данных
                await self._handle_new_user(message, state)

    @error_handler()
    @log_action("start_with_args")
    async def cmd_start_with_args(
            self,
            message: types.Message,
            state: FSMContext,
            command: CommandObject = None,
            **kwargs
    ) -> None:
        """
        Обработчик /start с параметрами.

        Args:
            message: Сообщение пользователя
            state: Контекст FSM
            command: Объект команды
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
            elif param.startswith("reading_"):
                await self._handle_shared_reading(message, param[8:], state)
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
        # Получаем приветственное сообщение на основе времени
        greeting = self._get_time_based_greeting()
        user_name = user.first_name or "друг"

        text = (
            f"{greeting}, {user_name}! 👋\n\n"
            f"Рад видеть вас снова!\n"
            f"Чем могу помочь сегодня?"
        )

        # ИСПОЛЬЗУЕМ НОВУЮ ФУНКЦИЮ ДЛЯ ГЛАВНОГО МЕНЮ
        keyboard = await get_main_menu(
            user_subscription=user.subscription_plan if hasattr(user, 'subscription_plan') else 'free',
            is_admin=user.telegram_id in settings.bot.admin_ids,
            user_name=user_name
        )

        await message.answer(text, reply_markup=keyboard)

        # ОПЦИОНАЛЬНО: Показываем быстрые действия по времени суток
        time_keyboard = TimeBasedGreetingKeyboard(user_name)
        inline_kb = await time_keyboard.build()

        await message.answer(
            "Вот что я рекомендую сейчас:",
            reply_markup=inline_kb
        )

        # Логируем возвращение
        await self.log_action(
            user.telegram_id,
            "user_returned",
            {"days_since_last_visit": self._calculate_days_since_last_visit(user)}
        )

    async def _handle_new_user(
            self,
            message: types.Message,
            state: FSMContext
    ) -> None:
        """Обработка нового пользователя."""
        user_name = message.from_user.first_name or "друг"

        text = (
            f"🌟 Добро пожаловать, {user_name}!\n\n"
            f"Я - Астро-Таро Бот, ваш персональный помощник в мире "
            f"астрологии и таро.\n\n"
            f"Что я умею:\n"
            f"🎴 Делать расклады Таро\n"
            f"⭐ Строить натальные карты\n"
            f"🌙 Рассчитывать совместимость\n"
            f"📅 Давать персональные прогнозы\n\n"
            f"Давайте начнем с короткого знакомства?"
        )

        # ИСПОЛЬЗУЕМ НОВУЮ WELCOME КЛАВИАТУРУ
        keyboard = await get_welcome_keyboard(user_name)

        await message.answer(text, reply_markup=keyboard)

        # Логируем нового пользователя
        await self.log_action(
            message.from_user.id,
            "new_user_start",
            {"source": "direct"}
        )

    async def _handle_referral(
            self,
            message: types.Message,
            referral_code: str,
            state: FSMContext
    ) -> None:
        """Обработка реферальной ссылки."""
        # Сохраняем реферальный код
        await state.update_data(referral_code=referral_code)

        # Находим реферера
        async with get_unit_of_work() as uow:
            referrer = await uow.users.get_by_referral_code(referral_code)

            if referrer:
                # Сохраняем связь
                user = await get_or_create_user(message.from_user)
                user.referred_by = referrer.id
                await uow.users.update(user)
                await uow.commit()

                # Уведомляем реферера
                try:
                    await message.bot.send_message(
                        referrer.telegram_id,
                        f"🎉 По вашей реферальной ссылке зарегистрировался новый пользователь!"
                    )
                except Exception as e:
                    logger.error(f"Не удалось уведомить реферера: {e}")

        # Продолжаем обычный старт
        await self.cmd_start(message, state)

    async def _handle_promo(
            self,
            message: types.Message,
            promo_code: str,
            state: FSMContext
    ) -> None:
        """Обработка промокода."""
        # Сохраняем промокод
        await state.update_data(promo_code=promo_code)

        # Проверяем промокод
        async with get_unit_of_work() as uow:
            promo = await uow.promo_codes.get_by_code(promo_code)

            if promo and promo.is_active:
                text = f"🎁 Промокод {promo_code} активирован! {promo.description}"
                await message.answer(text)

        # Продолжаем обычный старт
        await self.cmd_start(message, state)

    async def _handle_shared_reading(
            self,
            message: types.Message,
            reading_id: str,
            state: FSMContext
    ) -> None:
        """Обработка просмотра shared расклада."""
        # TODO: Реализовать просмотр расклада
        await message.answer("Просмотр расклада будет доступен после регистрации!")
        await self.cmd_start(message, state)

    # Обработчики callback кнопок

    async def welcome_callback(
            self,
            callback: types.CallbackQuery,
            state: FSMContext
    ) -> None:
        """Обработчик callback кнопок приветствия."""
        action = callback.data.split(":")[-1]

        if action == "start":
            await self._start_onboarding(callback, state)
        elif action == "quick_start":
            await self._quick_start(callback, state)
        elif action == "about":
            await self._show_about(callback, state)
        elif action == "promo":
            await self._enter_promo(callback, state)

        await answer_callback_query(callback)

    # НОВЫЙ ОБРАБОТЧИК ДЛЯ ДАННЫХ РОЖДЕНИЯ
    async def birth_data_callback(
            self,
            callback: types.CallbackQuery,
            callback_data: BirthDataCallbackData,
            state: FSMContext
    ) -> None:
        """Обработчик callback для данных рождения."""
        action = callback_data.action

        if action == "edit":
            # Редактирование поля
            field = callback_data.field
            current_data = await state.get_data()

            keyboard = await get_birth_data_keyboard(
                current_data=current_data,
                editing_field=field
            )

            await callback.message.edit_reply_markup(reply_markup=keyboard)

        elif action == "set_date":
            # Установка даты
            date_str = callback_data.value
            date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
            await state.update_data(birth_date=date_obj)

            # Возвращаемся к общему виду
            current_data = await state.get_data()
            keyboard = await get_birth_data_keyboard(current_data=current_data)

            await callback.message.edit_reply_markup(reply_markup=keyboard)

        elif action == "set_time":
            # Установка времени
            time_str = callback_data.value
            time_obj = datetime.strptime(time_str, "%H:%M").time()
            await state.update_data(birth_time=time_obj)

            # Возвращаемся к общему виду
            current_data = await state.get_data()
            keyboard = await get_birth_data_keyboard(current_data=current_data)

            await callback.message.edit_reply_markup(reply_markup=keyboard)

        elif action == "set_place":
            # Установка места
            place_data = callback_data.value.split("|")
            await state.update_data(
                birth_place={
                    "name": place_data[0],
                    "lat": float(place_data[1]),
                    "lon": float(place_data[2])
                }
            )

            # Возвращаемся к общему виду
            current_data = await state.get_data()
            keyboard = await get_birth_data_keyboard(current_data=current_data)

            await callback.message.edit_reply_markup(reply_markup=keyboard)

        elif action == "confirm":
            # Сохранение данных
            await self._save_birth_data(callback.message, state)

        await answer_callback_query(callback)

    async def onboarding_callback(
            self,
            callback: types.CallbackQuery,
            state: FSMContext
    ) -> None:
        """Обработчик callback кнопок онбординга."""
        action = callback.data.split(":")[-1]

        if action == "start":
            await self._start_onboarding(callback, state)
        elif action == "skip":
            await self._skip_onboarding(callback, state)
        elif action == "back":
            await self._onboarding_back(callback, state)
        elif action.startswith("interest_"):
            await self._handle_interest_selection(callback, action[9:], state)

        await answer_callback_query(callback)

    # Методы онбординга

    async def _start_onboarding(
            self,
            callback: types.CallbackQuery,
            state: FSMContext
    ) -> None:
        """Начало процесса онбординга."""
        text = (
            "Отлично! Для персональных прогнозов мне понадобятся "
            "ваши данные рождения.\n\n"
            "Это займет всего пару минут."
        )

        # ИСПОЛЬЗУЕМ НОВУЮ КЛАВИАТУРУ ДЛЯ ДАННЫХ РОЖДЕНИЯ
        keyboard = await get_birth_data_keyboard()

        await edit_or_send_message(
            callback.message,
            text,
            reply_markup=keyboard
        )

        # Устанавливаем состояние
        await state.set_state(OnboardingStates.waiting_birth_date)

    async def _quick_start(
            self,
            callback: types.CallbackQuery,
            state: FSMContext
    ) -> None:
        """Быстрый старт без заполнения данных."""
        # Очищаем состояние
        await state.clear()

        # Показываем главное меню
        keyboard = await get_main_menu(user_subscription="free")

        await callback.message.answer(
            "⚡ Отлично! Вы можете начать использовать бот прямо сейчас.\n"
            "Данные для персональных прогнозов можно добавить позже в профиле.",
            reply_markup=keyboard
        )

        await callback.message.delete()

    async def _show_about(
            self,
            callback: types.CallbackQuery,
            state: FSMContext
    ) -> None:
        """Показать информацию о боте."""
        about_text = (
            "🔮 <b>Астро-Таро Бот</b>\n\n"
            "Версия 1.0.0\n\n"
            "<b>Возможности:</b>\n"
            "🎴 Расклады Таро - от простых до сложных\n"
            "⭐ Персональные гороскопы\n"
            "🗺 Натальная карта с подробным анализом\n"
            "🌙 Лунный календарь\n"
            "💑 Синастрия - совместимость пар\n"
            "📚 Обучающие материалы\n\n"
            "<b>Тарифы:</b>\n"
            "• Бесплатный - базовые функции\n"
            "• Базовый - расширенные возможности\n"
            "• Премиум - полный доступ\n"
            "• VIP - персональный астролог\n\n"
            "💬 Поддержка: @astrotarot_support\n"
            "📢 Новости: @astrotarot_news"
        )

        # Кнопка назад
        keyboard = await Keyboards.back("welcome:menu")

        await callback.message.edit_text(
            about_text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )

    async def _enter_promo(
            self,
            callback: types.CallbackQuery,
            state: FSMContext
    ) -> None:
        """Переход к вводу промокода."""
        from infrastructure.telegram.keyboards import get_promo_code_keyboard

        keyboard = await get_promo_code_keyboard()

        await callback.message.edit_text(
            "🎁 Введите промокод или выберите из популярных:",
            reply_markup=keyboard
        )

    async def _skip_onboarding(
            self,
            callback: types.CallbackQuery,
            state: FSMContext
    ) -> None:
        """Пропуск онбординга."""
        # Очищаем состояние
        await state.clear()

        text = (
            "Хорошо! Вы всегда можете заполнить данные позже "
            "в настройках профиля.\n\n"
            "Чем могу помочь?"
        )

        # Показываем главное меню
        keyboard = await get_main_menu()

        await edit_or_send_message(
            callback.message,
            text,
            reply_markup=keyboard
        )

    async def _save_birth_data(
            self,
            message: types.Message,
            state: FSMContext
    ) -> None:
        """Сохранение данных рождения."""
        data = await state.get_data()

        # Сохраняем в БД
        async with get_unit_of_work() as uow:
            user = await uow.users.get_by_telegram_id(message.chat.id)

            if user:
                # Обновляем данные
                if 'birth_date' in data:
                    user.birth_date = data['birth_date']
                if 'birth_time' in data:
                    user.birth_time = data['birth_time']
                if 'birth_place' in data:
                    user.birth_place = data['birth_place']['name']
                    user.birth_lat = data['birth_place']['lat']
                    user.birth_lon = data['birth_place']['lon']

                await uow.users.update(user)
                await uow.commit()

        # Очищаем состояние
        await state.clear()

        # Показываем главное меню
        keyboard = await get_main_menu(user_subscription="free")

        await message.answer(
            "✅ Отлично! Данные сохранены.\n\n"
            "Теперь вы можете получать персональные прогнозы!",
            reply_markup=keyboard
        )

    # Обработчики состояний (оставляем для совместимости)

    async def process_name(
            self,
            message: types.Message,
            state: FSMContext
    ) -> None:
        """Обработка имени пользователя."""
        name = message.text.strip()

        # Валидация имени
        if len(name) < 2:
            await message.answer("Имя слишком короткое. Попробуйте еще раз:")
            return

        if len(name) > 50:
            await message.answer("Имя слишком длинное. Попробуйте еще раз:")
            return

        # Сохраняем имя
        await state.update_data(user_name=name)

        # Показываем клавиатуру данных рождения
        current_data = await state.get_data()
        keyboard = await get_birth_data_keyboard(current_data=current_data)

        await message.answer(
            f"Приятно познакомиться, {name}! 😊\n\n"
            f"Теперь давайте заполним данные для астрологических расчетов:",
            reply_markup=keyboard
        )

    async def process_birth_date(
            self,
            message: types.Message,
            state: FSMContext
    ) -> None:
        """Обработка даты рождения (текстовый ввод)."""
        date_text = message.text.strip()

        # Валидация даты
        date_pattern = r'^\d{2}\.\d{2}\.\d{4}$'
        if not re.match(date_pattern, date_text):
            await message.answer(
                "Неверный формат даты. Используйте ДД.ММ.ГГГГ\n"
                "Например: 15.03.1990"
            )
            return

        try:
            birth_date = datetime.strptime(date_text, "%d.%m.%Y").date()

            # Проверяем корректность даты
            age = (datetime.now().date() - birth_date).days / 365.25
            if age < 1 or age > 120:
                await message.answer("Пожалуйста, введите корректную дату рождения")
                return

        except ValueError:
            await message.answer("Некорректная дата. Попробуйте еще раз:")
            return

        # Сохраняем дату
        await state.update_data(birth_date=birth_date)

        # Обновляем клавиатуру
        current_data = await state.get_data()
        keyboard = await get_birth_data_keyboard(current_data=current_data)

        await message.answer(
            "✅ Дата сохранена!",
            reply_markup=keyboard
        )

    async def process_birth_time(
            self,
            message: types.Message,
            state: FSMContext
    ) -> None:
        """Обработка времени рождения (текстовый ввод)."""
        time_text = message.text.strip()

        # Валидация времени
        time_pattern = r'^\d{1,2}:\d{2}$'
        if not re.match(time_pattern, time_text):
            await message.answer(
                "Неверный формат времени. Используйте ЧЧ:ММ\n"
                "Например: 14:30"
            )
            return

        try:
            birth_time = datetime.strptime(time_text, "%H:%M").time()
        except ValueError:
            await message.answer("Некорректное время. Попробуйте еще раз:")
            return

        # Сохраняем время
        await state.update_data(birth_time=birth_time)

        # Обновляем клавиатуру
        current_data = await state.get_data()
        keyboard = await get_birth_data_keyboard(current_data=current_data)

        await message.answer(
            "✅ Время сохранено!",
            reply_markup=keyboard
        )

    async def process_birth_place(
            self,
            message: types.Message,
            state: FSMContext
    ) -> None:
        """Обработка места рождения (текстовый ввод)."""
        place = message.text.strip()

        if len(place) < 2:
            await message.answer("Название слишком короткое. Попробуйте еще раз:")
            return

        # TODO: Здесь должен быть геокодинг для получения координат
        # Пока сохраняем только название
        await state.update_data(
            birth_place={
                "name": place,
                "lat": 0.0,  # TODO: получить из API
                "lon": 0.0   # TODO: получить из API
            }
        )

        # Обновляем клавиатуру
        current_data = await state.get_data()
        keyboard = await get_birth_data_keyboard(current_data=current_data)

        await message.answer(
            "✅ Место сохранено!",
            reply_markup=keyboard
        )

    async def _complete_onboarding(
            self,
            message: types.Message,
            state: FSMContext
    ) -> None:
        """Завершение онбординга."""
        # Получаем все данные
        data = await state.get_data()

        # Сохраняем в БД
        async with get_unit_of_work() as uow:
            user = await uow.users.get_by_telegram_id(message.from_user.id)

            if user:
                # Обновляем данные пользователя
                if 'user_name' in data:
                    user.display_name = data['user_name']
                if 'birth_date' in data:
                    user.birth_date = data['birth_date']
                if 'birth_time' in data:
                    user.birth_time = data['birth_time']
                if 'birth_place' in data:
                    user.birth_place = data['birth_place']['name']
                    user.birth_lat = data['birth_place'].get('lat', 0.0)
                    user.birth_lon = data['birth_place'].get('lon', 0.0)

                await uow.users.update(user)
                await uow.commit()

        # Очищаем состояние
        await state.clear()

        # Поздравляем с завершением
        text = (
            "🎉 Отлично! Регистрация завершена!\n\n"
            "Теперь вам доступны все возможности бота:\n"
            "• Персональные гороскопы\n"
            "• Натальная карта\n"
            "• Расклады Таро\n"
            "• И многое другое!\n\n"
            "С чего начнем?"
        )

        # Показываем главное меню
        keyboard = await get_main_menu(
            user_subscription=user.subscription_plan if hasattr(user, 'subscription_plan') else 'free',
            user_name=user.display_name if hasattr(user, 'display_name') else message.from_user.first_name
        )

        await message.answer(text, reply_markup=keyboard)

        # Логируем завершение онбординга
        await self.log_action(
            message.from_user.id,
            "onboarding_completed",
            data
        )

    # Вспомогательные методы

    def _get_time_based_greeting(self) -> str:
        """Получить приветствие на основе времени суток."""
        hour = datetime.now().hour

        if 5 <= hour < 12:
            return "Доброе утро"
        elif 12 <= hour < 17:
            return "Добрый день"
        elif 17 <= hour < 22:
            return "Добрый вечер"
        else:
            return "Доброй ночи"

    def _calculate_days_since_last_visit(self, user: Any) -> int:
        """Рассчитать дни с последнего визита."""
        if hasattr(user, 'last_active_at') and user.last_active_at:
            return (datetime.now() - user.last_active_at).days
        return 0

    async def _onboarding_back(
            self,
            callback: types.CallbackQuery,
            state: FSMContext
    ) -> None:
        """Возврат на предыдущий шаг онбординга."""
        # TODO: Реализовать логику возврата
        await callback.answer("Функция в разработке")

    async def _handle_interest_selection(
            self,
            callback: types.CallbackQuery,
            interest: str,
            state: FSMContext
    ) -> None:
        """Обработка выбора интересов."""
        # TODO: Реализовать выбор интересов
        await callback.answer(f"Выбран интерес: {interest}")


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