"""
Модуль обработчиков раздела астрологии.

Этот модуль содержит все обработчики для работы с астрологией:
- Гороскопы (дневные, недельные, месячные, годовые)
- Натальные карты
- Транзиты и прогрессии
- Синастрия (совместимость)
- Лунный календарь
- Ввод данных рождения

Автор: AI Assistant
Дата создания: 2024-12-30
"""

import logging
from datetime import datetime, date, timedelta
from typing import Dict, Any, Optional, List
import asyncio
import re
import math

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
from bot.states import AstrologyStates
from infrastructure.telegram.keyboards import (
    Keyboards,
    InlineKeyboard,
    AstrologyCallbackData,
    BirthDataCallbackData,
    ChartCallbackData,
    TransitCallbackData,
    CalendarCallbackData,
    HoroscopeType
)
from infrastructure import get_unit_of_work
from services import get_astrology_service
from config import settings

logger = logging.getLogger(__name__)


class AstrologyHandlers(BaseHandler):
    """Обработчики для раздела астрологии."""

    # Константы
    ZODIAC_DATES = {
        "aries": (3, 21, 4, 19),
        "taurus": (4, 20, 5, 20),
        "gemini": (5, 21, 6, 20),
        "cancer": (6, 21, 7, 22),
        "leo": (7, 23, 8, 22),
        "virgo": (8, 23, 9, 22),
        "libra": (9, 23, 10, 22),
        "scorpio": (10, 23, 11, 21),
        "sagittarius": (11, 22, 12, 21),
        "capricorn": (12, 22, 1, 19),
        "aquarius": (1, 20, 2, 18),
        "pisces": (2, 19, 3, 20)
    }

    def register_handlers(self) -> None:
        """Регистрация обработчиков астрологии."""
        # Команда /astrology
        self.router.message.register(
            self.cmd_astrology,
            Command("astrology")
        )

        # Главное меню астрологии
        self.router.callback_query.register(
            self.show_astrology_menu,
            F.data == "astrology_menu"
        )

        # Гороскопы
        self.router.callback_query.register(
            self.show_horoscope_menu,
            F.data == "horoscope_menu"
        )

        self.router.callback_query.register(
            self.select_horoscope_type,
            F.data.startswith("horoscope_type:")
        )

        self.router.callback_query.register(
            self.select_zodiac_sign,
            F.data.startswith("zodiac_select:")
        )

        self.router.callback_query.register(
            self.horoscope_daily,
            F.data == "horoscope_daily"
        )

        # Натальная карта
        self.router.callback_query.register(
            self.show_natal_chart,
            F.data == "natal_chart"
        )

        self.router.callback_query.register(
            self.natal_chart_settings,
            F.data == "natal_settings"
        )

        # Транзиты
        self.router.callback_query.register(
            self.show_transits_menu,
            F.data == "transits_menu"
        )

        self.router.callback_query.register(
            self.select_transit_period,
            F.data.startswith("transit_period:")
        )

        # Синастрия
        self.router.callback_query.register(
            self.start_synastry,
            F.data == "synastry"
        )

        # Лунный календарь
        self.router.callback_query.register(
            self.show_lunar_calendar,
            F.data == "moon_calendar"
        )

        self.router.callback_query.register(
            self.lunar_day_details,
            F.data.startswith("lunar_day:")
        )

        # Данные рождения
        self.router.callback_query.register(
            self.start_birth_data_input,
            F.data == "input_birth_data"
        )

        self.router.callback_query.register(
            self.edit_birth_data,
            F.data == "edit_birth_data"
        )

        # Обработчики состояний для ввода данных
        self.router.message.register(
            self.process_birth_date,
            StateFilter(AstrologyStates.waiting_for_date)
        )

        self.router.message.register(
            self.process_birth_time,
            StateFilter(AstrologyStates.waiting_for_time)
        )

        self.router.message.register(
            self.process_birth_place,
            StateFilter(AstrologyStates.waiting_for_place)
        )

        # Обработчики для callback в состояниях
        self.router.callback_query.register(
            self.skip_birth_time,
            F.data == "skip_birth_time",
            StateFilter(AstrologyStates.waiting_for_time)
        )

        self.router.callback_query.register(
            self.confirm_birth_data,
            F.data == "confirm_birth_data",
            StateFilter(AstrologyStates.confirming_data)
        )

    @error_handler()
    @log_action("astrology_command")
    async def cmd_astrology(
            self,
            message: Message,
            state: FSMContext,
            **kwargs
    ) -> None:
        """Команда /astrology - вход в раздел астрологии."""
        await state.clear()

        async with get_unit_of_work() as uow:
            user = await get_or_create_user(message.from_user)
            user_db = await uow.users.get_by_telegram_id(message.from_user.id)

            # Проверяем наличие данных рождения
            has_birth_data = bool(user_db and hasattr(user_db, 'birth_date') and user_db.birth_date)

            # Получаем текущую фазу луны
            moon_phase = self._calculate_moon_phase()

            # Используем фабрику клавиатур
            keyboard = await Keyboards.astrology_menu(
                subscription_level=user_db.subscription_plan if user_db and hasattr(user_db, 'subscription_plan') else None,
                has_birth_data=has_birth_data,
                current_moon_phase=moon_phase["emoji"]
            )

            text = self._format_astrology_welcome(
                user_db,
                has_birth_data,
                moon_phase
            )

            await message.answer(
                text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )

    @error_handler()
    async def show_astrology_menu(
            self,
            callback: CallbackQuery,
            state: FSMContext,
            **kwargs
    ) -> None:
        """Показать главное меню астрологии."""
        await state.clear()

        async with get_unit_of_work() as uow:
            user = await uow.users.get_by_telegram_id(callback.from_user.id)

            if not user:
                await answer_callback_query(callback, "Необходимо начать с /start", show_alert=True)
                return

            has_birth_data = bool(hasattr(user, 'birth_date') and user.birth_date)
            moon_phase = self._calculate_moon_phase()

            # Используем фабрику клавиатур
            keyboard = await Keyboards.astrology_menu(
                subscription_level=user.subscription_plan if hasattr(user, 'subscription_plan') else None,
                has_birth_data=has_birth_data,
                current_moon_phase=moon_phase["emoji"]
            )

            text = self._format_astrology_welcome(
                user,
                has_birth_data,
                moon_phase
            )

            await edit_or_send_message(
                callback.message,
                text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )

        await answer_callback_query(callback)

    @error_handler()
    async def show_horoscope_menu(
            self,
            callback: CallbackQuery,
            state: FSMContext,
            **kwargs
    ) -> None:
        """Показать меню гороскопов."""
        async with get_unit_of_work() as uow:
            user = await uow.users.get_by_telegram_id(callback.from_user.id)
            subscription = user.subscription_plan if user and hasattr(user, 'subscription_plan') else "free"

            text = (
                "📅 <b>Гороскопы</b>\n\n"
                "Выберите тип гороскопа:"
            )

            # Используем фабрику клавиатур
            keyboard = await Keyboards.horoscope_menu(subscription_level=subscription)

            await edit_or_send_message(
                callback.message,
                text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )

        await answer_callback_query(callback)

    @error_handler()
    @log_action("daily_horoscope")
    async def horoscope_daily(
            self,
            callback: CallbackQuery,
            state: FSMContext,
            **kwargs
    ) -> None:
        """Быстрый доступ к дневному гороскопу."""
        async with get_unit_of_work() as uow:
            user = await uow.users.get_by_telegram_id(callback.from_user.id)

            if not user:
                await answer_callback_query(callback, "Необходимо начать с /start", show_alert=True)
                return

            # Если у пользователя есть данные рождения, сразу показываем гороскоп
            if hasattr(user, 'birth_date') and user.birth_date:
                zodiac_sign = self._get_zodiac_sign(user.birth_date)
                await self._show_horoscope(callback, "daily", zodiac_sign, user)
            else:
                # Иначе просим выбрать знак
                text = "🌟 Выберите ваш знак зодиака:"
                keyboard = await Keyboards.zodiac_selection("daily")

                await edit_or_send_message(
                    callback.message,
                    text,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )

        await answer_callback_query(callback)

    @error_handler()
    async def select_horoscope_type(
            self,
            callback: CallbackQuery,
            state: FSMContext,
            **kwargs
    ) -> None:
        """Выбор типа гороскопа."""
        horoscope_type = callback.data.split(":")[1]

        async with get_unit_of_work() as uow:
            user = await uow.users.get_by_telegram_id(callback.from_user.id)

            # Проверяем доступность
            if not self._is_horoscope_available(horoscope_type, user.subscription_plan if user else "free"):
                await answer_callback_query(
                    callback,
                    "⭐ Этот тип гороскопа доступен только по подписке",
                    show_alert=True
                )
                return

            # Сохраняем тип в состоянии
            await state.update_data(horoscope_type=horoscope_type)

            # Если есть данные рождения, показываем гороскоп
            if user and hasattr(user, 'birth_date') and user.birth_date:
                zodiac_sign = self._get_zodiac_sign(user.birth_date)
                await self._show_horoscope(callback, horoscope_type, zodiac_sign, user)
            else:
                # Показываем выбор знака
                text = "🌟 Выберите знак зодиака:"
                keyboard = await Keyboards.zodiac_selection(horoscope_type)

                await edit_or_send_message(
                    callback.message,
                    text,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )

        await answer_callback_query(callback)

    @error_handler()
    async def select_zodiac_sign(
            self,
            callback: CallbackQuery,
            state: FSMContext,
            **kwargs
    ) -> None:
        """Выбор знака зодиака."""
        parts = callback.data.split(":")
        horoscope_type = parts[1]
        zodiac_sign = parts[2]

        async with get_unit_of_work() as uow:
            user = await uow.users.get_by_telegram_id(callback.from_user.id)
            await self._show_horoscope(callback, horoscope_type, zodiac_sign, user)

        await answer_callback_query(callback)

    @error_handler()
    async def show_natal_chart(
            self,
            callback: CallbackQuery,
            state: FSMContext,
            **kwargs
    ) -> None:
        """Показать натальную карту."""
        async with get_unit_of_work() as uow:
            user = await uow.users.get_by_telegram_id(callback.from_user.id)

            if not user:
                await answer_callback_query(callback, "Необходимо начать с /start", show_alert=True)
                return

            # Проверяем наличие данных рождения
            if not hasattr(user, 'birth_date') or not user.birth_date:
                text = (
                    "🗺 <b>Натальная карта</b>\n\n"
                    "Для построения натальной карты необходимы:\n"
                    "• Дата рождения\n"
                    "• Время рождения (желательно)\n"
                    "• Место рождения\n\n"
                    "Пожалуйста, введите данные рождения:"
                )

                # Используем InlineKeyboard для создания кнопок
                keyboard = InlineKeyboard()
                keyboard.add_button(text="📝 Ввести данные", callback_data="input_birth_data")
                keyboard.add_button(text="◀️ Назад", callback_data="astrology_menu")
                keyboard.builder.adjust(1)

                keyboard_markup = await keyboard.build()
            else:
                # Строим натальную карту
                astrology_service = get_astrology_service()
                natal_chart = await astrology_service.calculate_natal_chart(
                    user.birth_date,
                    user.birth_time if hasattr(user, 'birth_time') else None,
                    user.birth_place if hasattr(user, 'birth_place') else None
                )

                text = self._format_natal_chart(natal_chart)

                # Используем фабрику клавиатур
                keyboard_markup = await Keyboards.natal_chart_menu()

            await edit_or_send_message(
                callback.message,
                text,
                reply_markup=keyboard_markup,
                parse_mode="HTML"
            )

        await answer_callback_query(callback)

    @error_handler()
    async def show_lunar_calendar(
            self,
            callback: CallbackQuery,
            state: FSMContext,
            **kwargs
    ) -> None:
        """Показать лунный календарь."""
        today = date.today()
        moon_phase = self._calculate_moon_phase()
        lunar_day = self._calculate_lunar_day()

        text = (
            f"🌙 <b>Лунный календарь</b>\n\n"
            f"<b>Сегодня:</b> {today.strftime('%d.%m.%Y')}\n"
            f"<b>Лунный день:</b> {lunar_day['day']}-й\n"
            f"<b>Фаза луны:</b> {moon_phase['emoji']} {moon_phase['name']}\n\n"
            f"<b>Характеристика дня:</b>\n"
            f"{lunar_day['description']}\n\n"
            f"<b>Благоприятно:</b>\n"
            f"✅ {lunar_day['good_for']}\n\n"
            f"<b>Неблагоприятно:</b>\n"
            f"❌ {lunar_day['bad_for']}"
        )

        # Используем фабрику клавиатур
        keyboard = await Keyboards.lunar_calendar_menu()

        await edit_or_send_message(
            callback.message,
            text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )

        await answer_callback_query(callback)

    @error_handler()
    async def start_birth_data_input(
            self,
            callback: CallbackQuery,
            state: FSMContext,
            **kwargs
    ) -> None:
        """Начать ввод данных рождения."""
        text = (
            "📝 <b>Ввод данных рождения</b>\n\n"
            "Шаг 1 из 3: Дата рождения\n\n"
            "Введите вашу дату рождения в формате:\n"
            "ДД.ММ.ГГГГ (например: 15.03.1990)"
        )

        # Используем кнопку отмены
        keyboard = await Keyboards.cancel()

        await edit_or_send_message(
            callback.message,
            text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )

        await state.set_state(AstrologyStates.waiting_for_date)
        await answer_callback_query(callback)

    # Обработчики состояний

    @error_handler()
    async def process_birth_date(
            self,
            message: Message,
            state: FSMContext
    ) -> None:
        """Обработка даты рождения."""
        date_text = message.text.strip()

        # Валидация формата
        date_pattern = r'^\d{2}\.\d{2}\.\d{4}$'
        if not re.match(date_pattern, date_text):
            await message.answer(
                "❌ Неверный формат даты.\n"
                "Используйте формат ДД.ММ.ГГГГ (например: 15.03.1990)"
            )
            return

        try:
            birth_date = datetime.strptime(date_text, "%d.%m.%Y").date()

            # Проверяем корректность
            age = (date.today() - birth_date).days / 365.25
            if age < 1 or age > 120:
                await message.answer("❌ Пожалуйста, введите корректную дату рождения")
                return

        except ValueError:
            await message.answer("❌ Некорректная дата. Попробуйте еще раз:")
            return

        # Сохраняем дату
        await state.update_data(birth_date=birth_date)

        # Переходим к времени
        text = (
            "📝 <b>Ввод данных рождения</b>\n\n"
            "Шаг 2 из 3: Время рождения\n\n"
            "Введите время рождения в формате:\n"
            "ЧЧ:ММ (например: 14:30)\n\n"
            "Точное время важно для расчета домов и асцендента."
        )

        # Создаем клавиатуру с кнопками
        keyboard = InlineKeyboard()
        keyboard.add_button(text="⏭ Не знаю точное время", callback_data="skip_birth_time")
        keyboard.add_button(text="❌ Отмена", callback_data="cancel:birth_data")
        keyboard.builder.adjust(1)

        await message.answer(
            text,
            reply_markup=await keyboard.build(),
            parse_mode="HTML"
        )

        await state.set_state(AstrologyStates.waiting_for_time)

    @error_handler()
    async def process_birth_time(
            self,
            message: Message,
            state: FSMContext
    ) -> None:
        """Обработка времени рождения."""
        time_text = message.text.strip()

        # Валидация формата
        time_pattern = r'^\d{1,2}:\d{2}$'
        if not re.match(time_pattern, time_text):
            await message.answer(
                "❌ Неверный формат времени.\n"
                "Используйте формат ЧЧ:ММ (например: 14:30)"
            )
            return

        try:
            birth_time = datetime.strptime(time_text, "%H:%M").time()
        except ValueError:
            await message.answer("❌ Некорректное время. Попробуйте еще раз:")
            return

        # Сохраняем время
        await state.update_data(birth_time=birth_time)

        # Переходим к месту
        text = (
            "📝 <b>Ввод данных рождения</b>\n\n"
            "Шаг 3 из 3: Место рождения\n\n"
            "Введите город или населенный пункт:"
        )

        await message.answer(text, parse_mode="HTML")
        await state.set_state(AstrologyStates.waiting_for_place)

    @error_handler()
    async def process_birth_place(
            self,
            message: Message,
            state: FSMContext
    ) -> None:
        """Обработка места рождения."""
        place = message.text.strip()

        if len(place) < 2:
            await message.answer("❌ Название слишком короткое. Попробуйте еще раз:")
            return

        # Сохраняем место
        await state.update_data(birth_place=place)

        # Получаем все данные
        data = await state.get_data()

        # Показываем подтверждение
        text = (
            "✅ <b>Проверьте данные:</b>\n\n"
            f"<b>Дата:</b> {data['birth_date'].strftime('%d.%m.%Y')}\n"
        )

        if 'birth_time' in data:
            text += f"<b>Время:</b> {data['birth_time'].strftime('%H:%M')}\n"
        else:
            text += "<b>Время:</b> не указано\n"

        text += f"<b>Место:</b> {data['birth_place']}\n\n"
        text += "Все верно?"

        # Используем клавиатуру подтверждения
        keyboard = await Keyboards.yes_no(
            yes_data="confirm_birth_data",
            no_data="edit_birth_data"
        )

        await message.answer(
            text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )

        await state.set_state(AstrologyStates.confirming_data)

    @error_handler()
    async def skip_birth_time(
            self,
            callback: CallbackQuery,
            state: FSMContext
    ) -> None:
        """Пропустить ввод времени рождения."""
        # Переходим к месту рождения
        text = (
            "📝 <b>Ввод данных рождения</b>\n\n"
            "Шаг 3 из 3: Место рождения\n\n"
            "Введите город или населенный пункт:"
        )

        await edit_or_send_message(
            callback.message,
            text,
            parse_mode="HTML"
        )

        await state.set_state(AstrologyStates.waiting_for_place)
        await answer_callback_query(callback)

    @error_handler()
    async def confirm_birth_data(
            self,
            callback: CallbackQuery,
            state: FSMContext
    ) -> None:
        """Подтвердить и сохранить данные рождения."""
        data = await state.get_data()

        async with get_unit_of_work() as uow:
            user = await uow.users.get_by_telegram_id(callback.from_user.id)

            if user:
                # Обновляем данные пользователя
                user.birth_date = data['birth_date']
                user.birth_time = data.get('birth_time')
                user.birth_place = data['birth_place']

                await uow.users.update(user)
                await uow.commit()

        # Очищаем состояние
        await state.clear()

        text = (
            "✅ <b>Данные рождения сохранены!</b>\n\n"
            "Теперь вам доступны:\n"
            "• Персональные гороскопы\n"
            "• Натальная карта\n"
            "• Транзиты планет\n"
            "• Анализ совместимости"
        )

        # Используем фабрику клавиатур
        keyboard = await Keyboards.birth_data_saved()

        await edit_or_send_message(
            callback.message,
            text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )

        await answer_callback_query(callback)

    # Вспомогательные методы

    def _format_astrology_welcome(
            self,
            user: Any,
            has_birth_data: bool,
            moon_phase: Dict[str, Any]
    ) -> str:
        """Форматировать приветствие раздела астрологии."""
        text = "🔮 <b>Астрология</b>\n\n"

        text += (
            "Откройте тайны звезд и планет. "
            "Узнайте, что говорит космос о вашей судьбе.\n\n"
        )

        # Информация о луне
        text += f"Сегодня: {moon_phase['emoji']} {moon_phase['name']}\n"

        if has_birth_data and user:
            text += "✅ Данные рождения сохранены\n"

            # Определяем знак зодиака
            if hasattr(user, 'birth_date') and user.birth_date:
                sign = self._get_zodiac_sign(user.birth_date)
                sign_name = self._get_sign_name(sign)
                text += f"Ваш знак: <b>{sign_name}</b>\n"
        else:
            text += "💡 <i>Добавьте данные рождения для персональных прогнозов</i>\n"

        text += "\nЧто бы вы хотели узнать?"

        return text

    async def _show_horoscope(
            self,
            callback: CallbackQuery,
            horoscope_type: str,
            zodiac_sign: str,
            user: Any
    ) -> None:
        """Показать гороскоп."""
        astrology_service = get_astrology_service()

        # Получаем гороскоп
        horoscope = await astrology_service.get_horoscope(
            zodiac_sign,
            horoscope_type,
            user.id if user else None
        )

        sign_name = self._get_sign_name(zodiac_sign)
        period = self._get_period_dates(horoscope_type)

        text = (
            f"{sign_name}\n"
            f"<b>{self._get_horoscope_name(horoscope_type).title()} гороскоп</b>\n"
            f"<i>{period}</i>\n\n"
            f"{horoscope['text']}\n\n"
        )

        if horoscope.get('lucky_numbers'):
            text += f"<b>Счастливые числа:</b> {', '.join(map(str, horoscope['lucky_numbers']))}\n"

        if horoscope.get('lucky_color'):
            text += f"<b>Цвет дня:</b> {horoscope['lucky_color']}\n"

        # Используем фабрику клавиатур для создания меню результата
        keyboard = await Keyboards.horoscope_result(
            horoscope_type=horoscope_type,
            zodiac_sign=zodiac_sign
        )

        await edit_or_send_message(
            callback.message,
            text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )

    def _format_natal_chart(self, natal_chart: Dict[str, Any]) -> str:
        """Форматировать натальную карту."""
        text = "🗺 <b>Ваша натальная карта</b>\n\n"

        # Основные показатели
        text += "<b>Планеты в знаках:</b>\n"
        for planet, sign in natal_chart['planets'].items():
            text += f"• {planet}: {sign}\n"

        text += "\n<b>Дома:</b>\n"
        for house, sign in natal_chart['houses'].items()[:4]:  # Показываем первые 4 дома
            text += f"• {house}: {sign}\n"

        text += f"\n<b>Асцендент:</b> {natal_chart['ascendant']}\n"
        text += f"<b>МС (Середина неба):</b> {natal_chart['midheaven']}\n"

        if natal_chart.get('aspects'):
            text += "\n<b>Основные аспекты:</b>\n"
            for aspect in natal_chart['aspects'][:3]:  # Показываем 3 главных аспекта
                text += f"• {aspect}\n"

        return text

    def _calculate_moon_phase(self) -> Dict[str, Any]:
        """Рассчитать текущую фазу луны."""
        # Упрощенный расчет фазы луны
        # В реальности нужен более точный алгоритм
        today = date.today()

        # Известная новолуние
        known_new_moon = date(2024, 1, 11)

        # Лунный цикл примерно 29.53 дня
        lunar_cycle = 29.53

        days_since = (today - known_new_moon).days
        phase_index = (days_since % lunar_cycle) / lunar_cycle

        if phase_index < 0.03 or phase_index > 0.97:
            return {"emoji": "🌑", "name": "Новолуние", "phase": 0}
        elif phase_index < 0.22:
            return {"emoji": "🌒", "name": "Растущий месяц", "phase": 1}
        elif phase_index < 0.28:
            return {"emoji": "🌓", "name": "Первая четверть", "phase": 2}
        elif phase_index < 0.47:
            return {"emoji": "🌔", "name": "Растущая луна", "phase": 3}
        elif phase_index < 0.53:
            return {"emoji": "🌕", "name": "Полнолуние", "phase": 4}
        elif phase_index < 0.72:
            return {"emoji": "🌖", "name": "Убывающая луна", "phase": 5}
        elif phase_index < 0.78:
            return {"emoji": "🌗", "name": "Последняя четверть", "phase": 6}
        else:
            return {"emoji": "🌘", "name": "Убывающий месяц", "phase": 7}

    def _calculate_lunar_day(self) -> Dict[str, Any]:
        """Рассчитать лунный день."""
        moon_phase = self._calculate_moon_phase()

        # Упрощенный расчет лунного дня
        today = date.today()
        known_new_moon = date(2024, 1, 11)
        days_since = (today - known_new_moon).days
        lunar_day = (days_since % 30) + 1

        # Характеристики лунных дней (упрощенно)
        lunar_days_info = {
            1: {
                "description": "День планирования и новых начинаний",
                "good_for": "Планирование, медитация, очищение",
                "bad_for": "Активные действия, споры"
            },
            15: {
                "description": "День искушений и соблазнов",
                "good_for": "Творчество, развлечения",
                "bad_for": "Важные решения, диета"
            },
            # Добавить остальные дни...
        }

        info = lunar_days_info.get(lunar_day, {
            "description": "Обычный лунный день",
            "good_for": "Повседневные дела",
            "bad_for": "Рискованные предприятия"
        })

        return {
            "day": lunar_day,
            "emoji": moon_phase["emoji"],
            **info
        }

    def _get_zodiac_sign(self, birth_date: date) -> str:
        """Определить знак зодиака по дате."""
        month = birth_date.month
        day = birth_date.day

        for sign, (start_month, start_day, end_month, end_day) in self.ZODIAC_DATES.items():
            if start_month == month and day >= start_day:
                return sign
            elif end_month == month and day <= end_day:
                return sign
            elif start_month > end_month:  # Козерог
                if month == start_month and day >= start_day:
                    return sign
                elif month == end_month and day <= end_day:
                    return sign

        return "aries"  # Fallback

    def _get_sign_name(self, sign: str) -> str:
        """Получить название знака на русском."""
        names = {
            "aries": "Овен ♈",
            "taurus": "Телец ♉",
            "gemini": "Близнецы ♊",
            "cancer": "Рак ♋",
            "leo": "Лев ♌",
            "virgo": "Дева ♍",
            "libra": "Весы ♎",
            "scorpio": "Скорпион ♏",
            "sagittarius": "Стрелец ♐",
            "capricorn": "Козерог ♑",
            "aquarius": "Водолей ♒",
            "pisces": "Рыбы ♓"
        }
        return names.get(sign, sign.title())

    def _get_horoscope_name(self, horoscope_type: str) -> str:
        """Получить название типа гороскопа."""
        names = {
            "daily": "дневной",
            "weekly": "недельный",
            "monthly": "месячный",
            "yearly": "годовой"
        }
        return names.get(horoscope_type, horoscope_type)

    def _get_period_dates(self, horoscope_type: str) -> str:
        """Получить даты периода для гороскопа."""
        today = date.today()

        if horoscope_type == "daily":
            return today.strftime("%d.%m.%Y")
        elif horoscope_type == "weekly":
            week_start = today - timedelta(days=today.weekday())
            week_end = week_start + timedelta(days=6)
            return f"{week_start.strftime('%d.%m')} - {week_end.strftime('%d.%m')}"
        elif horoscope_type == "monthly":
            return today.strftime("%B %Y")
        elif horoscope_type == "yearly":
            return str(today.year)

        return ""

    def _is_horoscope_available(
            self,
            horoscope_type: str,
            subscription: str
    ) -> bool:
        """Проверить доступность типа гороскопа."""
        if horoscope_type in ["daily", "weekly"]:
            return True  # Доступно всем
        elif horoscope_type == "monthly":
            return subscription in ["basic", "premium", "vip"]
        elif horoscope_type == "yearly":
            return subscription in ["premium", "vip"]

        return False


# Функция для регистрации обработчика
def register_astrology_handler(router: Router) -> None:
    """
    Регистрация обработчика астрологии.

    Args:
        router: Роутер для регистрации
    """
    handler = AstrologyHandlers(router)
    handler.register_handlers()
    logger.info("Astrology handler зарегистрирован")


logger.info("Модуль обработчика астрологии загружен")