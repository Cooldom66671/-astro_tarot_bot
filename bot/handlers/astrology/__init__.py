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
from zoneinfo import ZoneInfo

from aiogram import Router, F
from aiogram.filters import Command, StateFilter
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest

from bot.handlers.base import BaseHandler, require_subscription, error_handler
from bot.states import AstrologyStates
from infrastructure.telegram import (
    Keyboards,
    MessageFactory,
    HoroscopeMessage,
    NatalChartMessage,
    TransitMessage,
    MoonPhaseMessage,
    SynastryMessage,
    MessageBuilder,
    MessageStyle,
    MessageEmoji as Emoji,
    ZodiacSign,
    HoroscopeType
)
from infrastructure import get_unit_of_work
from infrastructure.external_apis import get_llm_manager

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

    def register_handlers(self, router: Router) -> None:
        """Регистрация обработчиков астрологии."""
        # Команда /astrology
        router.message.register(
            self.cmd_astrology,
            Command("astrology")
        )

        # Главное меню астрологии
        router.callback_query.register(
            self.show_astrology_menu,
            F.data == "astrology_menu"
        )

        # Гороскопы
        router.callback_query.register(
            self.show_horoscope_menu,
            F.data == "horoscope_menu"
        )

        router.callback_query.register(
            self.select_horoscope_type,
            F.data.startswith("horoscope_type:")
        )

        router.callback_query.register(
            self.select_zodiac_sign,
            F.data.startswith("zodiac_select:")
        )

        # Натальная карта
        router.callback_query.register(
            self.show_natal_chart,
            F.data == "natal_chart"
        )

        router.callback_query.register(
            self.natal_chart_settings,
            F.data == "natal_settings"
        )

        # Транзиты
        router.callback_query.register(
            self.show_transits_menu,
            F.data == "transits_menu"
        )

        router.callback_query.register(
            self.select_transit_period,
            F.data.startswith("transit_period:")
        )

        # Синастрия
        router.callback_query.register(
            self.start_synastry,
            F.data == "synastry_start"
        )

        router.callback_query.register(
            self.synastry_result,
            F.data.startswith("synastry_result:")
        )

        # Лунный календарь
        router.callback_query.register(
            self.show_lunar_calendar,
            F.data == "lunar_calendar"
        )

        router.callback_query.register(
            self.lunar_day_details,
            F.data.startswith("lunar_day:")
        )

        # Данные рождения
        router.callback_query.register(
            self.start_birth_data_input,
            F.data == "input_birth_data"
        )

        router.callback_query.register(
            self.edit_birth_data,
            F.data == "edit_birth_data"
        )

        # Обработчики состояний для ввода данных
        router.message.register(
            self.process_birth_date,
            StateFilter(AstrologyStates.waiting_for_date)
        )

        router.callback_query.register(
            self.process_birth_time_range,
            F.data.startswith("time_range:"),
            StateFilter(AstrologyStates.waiting_for_time)
        )

        router.callback_query.register(
            self.process_birth_city,
            F.data.startswith("city_select:"),
            StateFilter(AstrologyStates.waiting_for_place)
        )

        router.message.register(
            self.process_city_search,
            StateFilter(AstrologyStates.waiting_for_place)
        )

        # Навигация
        router.callback_query.register(
            self.calendar_navigation,
            F.data.startswith("calendar_nav:")
        )

    async def cmd_astrology(
            self,
            message: Message,
            state: FSMContext,
            **kwargs
    ) -> None:
        """Команда /astrology - вход в раздел астрологии."""
        await state.clear()

        async with get_unit_of_work() as uow:
            user = await self.get_or_create_user(uow, message.from_user)

            # Проверяем наличие данных рождения
            has_birth_data = bool(user.birth_data)

            # Получаем текущую фазу луны
            moon_phase = self._calculate_moon_phase()

            keyboard = await Keyboards.astrology_menu(
                subscription_level=user.subscription_plan,
                has_birth_data=has_birth_data,
                current_moon_phase=moon_phase["emoji"]
            )

            text = await self._format_astrology_welcome(
                user,
                has_birth_data,
                moon_phase
            )

            await message.answer(
                text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )

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

            has_birth_data = bool(user.birth_data)
            moon_phase = self._calculate_moon_phase()

            keyboard = await Keyboards.astrology_menu(
                subscription_level=user.subscription_plan,
                has_birth_data=has_birth_data,
                current_moon_phase=moon_phase["emoji"]
            )

            text = await self._format_astrology_welcome(
                user,
                has_birth_data,
                moon_phase
            )

            await self.edit_or_send_message(
                callback,
                text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )

    async def show_horoscope_menu(
            self,
            callback: CallbackQuery,
            **kwargs
    ) -> None:
        """Показать меню гороскопов."""
        async with get_unit_of_work() as uow:
            user = await uow.users.get_by_telegram_id(callback.from_user.id)

            # Определяем знак зодиака если есть данные
            user_sign = None
            if user.birth_data and user.birth_data.get("date"):
                birth_date = datetime.fromisoformat(user.birth_data["date"])
                user_sign = self._get_zodiac_sign(birth_date)

            keyboard = await Keyboards.horoscope_menu(
                subscription_level=user.subscription_plan,
                user_zodiac_sign=user_sign
            )

            text = (
                f"<b>{Emoji.STARS} Гороскопы</b>\n\n"
                f"Выберите тип гороскопа:\n\n"
            )

            if user_sign:
                text += f"Ваш знак: <b>{self._get_sign_name(user_sign)}</b>\n\n"
            else:
                text += (
                    f"💡 <i>Добавьте данные рождения в профиле "
                    f"для персональных гороскопов</i>\n\n"
                )

            await self.edit_or_send_message(
                callback,
                text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )

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

            # Проверяем доступность для подписки
            if not self._is_horoscope_available(horoscope_type, user.subscription_plan):
                await callback.answer(
                    "Этот тип гороскопа доступен только для Premium подписчиков",
                    show_alert=True
                )
                return

            # Если есть данные рождения, сразу показываем гороскоп
            if user.birth_data and user.birth_data.get("date"):
                birth_date = datetime.fromisoformat(user.birth_data["date"])
                user_sign = self._get_zodiac_sign(birth_date)

                await self._show_horoscope(
                    callback,
                    horoscope_type,
                    user_sign,
                    user
                )
            else:
                # Показываем выбор знака
                await state.update_data(horoscope_type=horoscope_type)

                keyboard = await Keyboards.zodiac_selection()

                text = (
                    f"<b>Выберите знак зодиака</b>\n\n"
                    f"Для какого знака показать {self._get_horoscope_name(horoscope_type)}?"
                )

                await self.edit_or_send_message(
                    callback,
                    text,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )

    async def select_zodiac_sign(
            self,
            callback: CallbackQuery,
            state: FSMContext,
            **kwargs
    ) -> None:
        """Выбор знака зодиака."""
        sign = callback.data.split(":")[1]
        data = await state.get_data()
        horoscope_type = data.get("horoscope_type", "daily")

        async with get_unit_of_work() as uow:
            user = await uow.users.get_by_telegram_id(callback.from_user.id)

            await self._show_horoscope(
                callback,
                horoscope_type,
                sign,
                user
            )

        await state.clear()

    @require_subscription("basic")
    async def show_natal_chart(
            self,
            callback: CallbackQuery,
            **kwargs
    ) -> None:
        """Показать натальную карту."""
        async with get_unit_of_work() as uow:
            user = await uow.users.get_by_telegram_id(callback.from_user.id)

            if not user.birth_data or not all(
                    key in user.birth_data for key in ["date", "time", "place"]
            ):
                await callback.answer(
                    "Сначала добавьте полные данные рождения",
                    show_alert=True
                )

                # Предлагаем ввести данные
                keyboard = await Keyboards.birth_data_request()

                text = (
                    f"<b>{Emoji.WARNING} Данные рождения не найдены</b>\n\n"
                    f"Для построения натальной карты необходимы:\n"
                    f"• Дата рождения\n"
                    f"• Точное время рождения\n"
                    f"• Место рождения\n\n"
                    f"Хотите добавить эти данные?"
                )

                await self.edit_or_send_message(
                    callback,
                    text,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
                return

            # Генерируем натальную карту
            await callback.answer(f"{Emoji.LOADING} Рассчитываю натальную карту...")

            natal_data = await self._calculate_natal_chart(user.birth_data)
            interpretation = await self._get_natal_interpretation(natal_data, user)

            # Сохраняем в БД
            await uow.astrology.save_natal_chart(
                user_id=user.id,
                chart_data=natal_data,
                interpretation=interpretation
            )
            await uow.commit()

            # Форматируем сообщение
            message = NatalChartMessage(
                birth_data=user.birth_data,
                planets=natal_data["planets"],
                houses=natal_data["houses"],
                aspects=natal_data["aspects"],
                interpretation=interpretation
            )

            text = await message.format()

            keyboard = await Keyboards.natal_chart_actions()

            await self.edit_or_send_message(
                callback,
                text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )

    @require_subscription("premium")
    async def show_transits_menu(
            self,
            callback: CallbackQuery,
            **kwargs
    ) -> None:
        """Показать меню транзитов."""
        async with get_unit_of_work() as uow:
            user = await uow.users.get_by_telegram_id(callback.from_user.id)

            if not user.birth_data:
                await callback.answer(
                    "Для транзитов нужны данные рождения",
                    show_alert=True
                )
                return

            keyboard = await Keyboards.transits_menu()

            text = (
                f"<b>{Emoji.TRANSIT} Транзиты планет</b>\n\n"
                f"Транзиты показывают, как текущее положение планет "
                f"влияет на вашу натальную карту.\n\n"
                f"Выберите период для анализа:"
            )

            await self.edit_or_send_message(
                callback,
                text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )

    async def select_transit_period(
            self,
            callback: CallbackQuery,
            **kwargs
    ) -> None:
        """Выбор периода транзитов."""
        period = callback.data.split(":")[1]

        await callback.answer(f"{Emoji.LOADING} Рассчитываю транзиты...")

        async with get_unit_of_work() as uow:
            user = await uow.users.get_by_telegram_id(callback.from_user.id)

            # Рассчитываем транзиты
            transits = await self._calculate_transits(
                user.birth_data,
                period
            )

            # Получаем интерпретацию
            interpretation = await self._get_transit_interpretation(
                transits,
                period,
                user
            )

            # Форматируем сообщение
            message = TransitMessage(
                period=period,
                transits=transits,
                interpretation=interpretation
            )

            text = await message.format()

            keyboard = await Keyboards.transit_actions(period)

            await self.edit_or_send_message(
                callback,
                text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )

    @require_subscription("premium")
    async def start_synastry(
            self,
            callback: CallbackQuery,
            state: FSMContext,
            **kwargs
    ) -> None:
        """Начать анализ синастрии."""
        async with get_unit_of_work() as uow:
            user = await uow.users.get_by_telegram_id(callback.from_user.id)

            if not user.birth_data:
                await callback.answer(
                    "Сначала добавьте свои данные рождения",
                    show_alert=True
                )
                return

            # Запускаем процесс ввода данных партнера
            await state.set_state(AstrologyStates.synastry_partner_data)

            text = (
                f"<b>{Emoji.HEART} Анализ совместимости</b>\n\n"
                f"Для анализа совместимости нужны данные партнера.\n\n"
                f"Введите дату рождения партнера в формате ДД.ММ.ГГГГ\n"
                f"Например: 15.03.1990"
            )

            keyboard = await Keyboards.cancel_only()

            await self.edit_or_send_message(
                callback,
                text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )

    async def show_lunar_calendar(
            self,
            callback: CallbackQuery,
            **kwargs
    ) -> None:
        """Показать лунный календарь."""
        # Рассчитываем данные на текущий месяц
        today = date.today()
        lunar_days = await self._calculate_lunar_month(today)

        # Форматируем календарь
        keyboard = await Keyboards.lunar_calendar(
            year=today.year,
            month=today.month,
            lunar_days=lunar_days,
            selected_day=today.day
        )

        # Текущая фаза луны
        current_phase = self._calculate_moon_phase()

        text = (
            f"<b>{Emoji.MOON} Лунный календарь</b>\n\n"
            f"<b>Сегодня:</b> {current_phase['emoji']} {current_phase['name']}\n"
            f"<b>Лунный день:</b> {current_phase['day']}\n"
            f"<b>Освещенность:</b> {current_phase['illumination']}%\n\n"
            f"Выберите день для подробной информации:"
        )

        await self.edit_or_send_message(
            callback,
            text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )

    async def start_birth_data_input(
            self,
            callback: CallbackQuery,
            state: FSMContext,
            **kwargs
    ) -> None:
        """Начать ввод данных рождения."""
        await state.set_state(AstrologyStates.waiting_for_date)

        text = (
            f"<b>{Emoji.CALENDAR} Ввод данных рождения</b>\n\n"
            f"<b>Шаг 1 из 3: Дата рождения</b>\n\n"
            f"Введите дату рождения в формате ДД.ММ.ГГГГ\n"
            f"Например: 25.12.1990"
        )

        keyboard = await Keyboards.cancel_only()

        await self.edit_or_send_message(
            callback,
            text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )

    async def process_birth_date(
            self,
            message: Message,
            state: FSMContext,
            **kwargs
    ) -> None:
        """Обработка даты рождения."""
        try:
            # Парсим дату
            date_parts = message.text.strip().split(".")
            if len(date_parts) != 3:
                raise ValueError("Неверный формат")

            day, month, year = map(int, date_parts)
            birth_date = datetime(year, month, day)

            # Проверяем корректность
            if birth_date > datetime.now():
                raise ValueError("Дата в будущем")

            if birth_date < datetime(1900, 1, 1):
                raise ValueError("Слишком старая дата")

            # Сохраняем и переходим к времени
            await state.update_data(
                birth_date=birth_date.isoformat()
            )
            await state.set_state(AstrologyStates.waiting_for_time)

            # Показываем выбор времени
            keyboard = await Keyboards.birth_time_selection()

            text = (
                f"<b>Шаг 2 из 3: Время рождения</b>\n\n"
                f"Выберите диапазон времени рождения или точное время.\n"
                f"Чем точнее время, тем точнее будут расчеты."
            )

            await message.answer(
                text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )

        except Exception as e:
            await message.answer(
                f"{Emoji.ERROR} Неверный формат даты. "
                f"Используйте формат ДД.ММ.ГГГГ\n"
                f"Например: 25.12.1990"
            )

    async def process_birth_time_range(
            self,
            callback: CallbackQuery,
            state: FSMContext,
            **kwargs
    ) -> None:
        """Обработка выбора времени рождения."""
        time_range = callback.data.split(":")[1]

        # Определяем примерное время
        time_map = {
            "morning": "09:00",
            "afternoon": "15:00",
            "evening": "20:00",
            "night": "02:00",
            "unknown": "12:00"
        }

        birth_time = time_map.get(time_range, "12:00")

        await state.update_data(birth_time=birth_time)
        await state.set_state(AstrologyStates.waiting_for_place)

        # Показываем выбор места
        keyboard = await Keyboards.birth_place_selection()

        text = (
            f"<b>Шаг 3 из 3: Место рождения</b>\n\n"
            f"Выберите город из списка популярных или введите название:"
        )

        await self.edit_or_send_message(
            callback,
            text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )

    async def process_birth_city(
            self,
            callback: CallbackQuery,
            state: FSMContext,
            **kwargs
    ) -> None:
        """Обработка выбора города рождения."""
        city = callback.data.split(":")[1]

        # Мапинг городов на координаты и часовые пояса
        city_data = self._get_city_data(city)

        data = await state.get_data()

        # Сохраняем все данные
        birth_data = {
            "date": data["birth_date"],
            "time": data["birth_time"],
            "place": city_data["name"],
            "lat": city_data["lat"],
            "lon": city_data["lon"],
            "timezone": city_data["timezone"]
        }

        async with get_unit_of_work() as uow:
            user = await uow.users.get_by_telegram_id(callback.from_user.id)
            user.birth_data = birth_data
            await uow.commit()

        await state.clear()

        # Показываем подтверждение
        await callback.answer(f"{Emoji.CHECK} Данные сохранены!")

        keyboard = await Keyboards.birth_data_saved()

        text = (
            f"<b>{Emoji.CHECK} Данные рождения сохранены!</b>\n\n"
            f"<b>Дата:</b> {datetime.fromisoformat(birth_data['date']).strftime('%d.%m.%Y')}\n"
            f"<b>Время:</b> {birth_data['time']}\n"
            f"<b>Место:</b> {birth_data['place']}\n\n"
            f"Теперь вам доступны:\n"
            f"• Персональные гороскопы\n"
            f"• Натальная карта\n"
            f"• Транзиты планет\n"
            f"• Анализ совместимости"
        )

        await self.edit_or_send_message(
            callback,
            text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )

    # Вспомогательные методы

    async def _format_astrology_welcome(
            self,
            user,
            has_birth_data: bool,
            moon_phase: Dict[str, Any]
    ) -> str:
        """Форматировать приветствие раздела астрологии."""
        builder = MessageBuilder(MessageStyle.HTML)

        builder.add_bold(f"{Emoji.STARS} Астрология").add_line(2)

        builder.add_text(
            "Откройте тайны звезд и планет. "
            "Узнайте, что говорит космос о вашей судьбе."
        ).add_line(2)

        # Информация о луне
        builder.add_text(
            f"Сегодня: {moon_phase['emoji']} {moon_phase['name']}"
        ).add_line()

        if has_birth_data:
            builder.add_text(f"✅ Данные рождения сохранены").add_line()

            # Определяем знак зодиака
            birth_date = datetime.fromisoformat(user.birth_data["date"])
            sign = self._get_zodiac_sign(birth_date)
            sign_name = self._get_sign_name(sign)

            builder.add_text(f"Ваш знак: <b>{sign_name}</b>").add_line()
        else:
            builder.add_text(
                f"💡 <i>Добавьте данные рождения для персональных прогнозов</i>"
            ).add_line()

        builder.add_line()
        builder.add_italic("Что бы вы хотели узнать?")

        return builder.build()

    async def _show_horoscope(
            self,
            callback: CallbackQuery,
            horoscope_type: str,
            zodiac_sign: str,
            user
    ) -> None:
        """Показать гороскоп."""
        await callback.answer(f"{Emoji.LOADING} Составляю гороскоп...")

        # Проверяем кэш
        async with get_unit_of_work() as uow:
            cached = await uow.astrology.get_cached_horoscope(
                zodiac_sign,
                horoscope_type,
                date.today()
            )

            if cached:
                horoscope_data = cached
            else:
                # Генерируем новый гороскоп
                horoscope_data = await self._generate_horoscope(
                    zodiac_sign,
                    horoscope_type,
                    user
                )

                # Сохраняем в кэш
                await uow.astrology.cache_horoscope(
                    zodiac_sign,
                    horoscope_type,
                    date.today(),
                    horoscope_data
                )
                await uow.commit()

        # Форматируем сообщение
        message = HoroscopeMessage(
            zodiac_sign=zodiac_sign,
            period_type=horoscope_type,
            period_dates=self._get_period_dates(horoscope_type),
            general_prediction=horoscope_data["general"],
            love_prediction=horoscope_data.get("love"),
            career_prediction=horoscope_data.get("career"),
            health_prediction=horoscope_data.get("health"),
            lucky_numbers=horoscope_data.get("lucky_numbers"),
            lucky_color=horoscope_data.get("lucky_color")
        )

        text = await message.format()

        keyboard = await Keyboards.horoscope_actions(
            zodiac_sign,
            horoscope_type,
            can_save=user.subscription_plan != "free"
        )

        await self.edit_or_send_message(
            callback,
            text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )

    async def _generate_horoscope(
            self,
            zodiac_sign: str,
            horoscope_type: str,
            user
    ) -> Dict[str, Any]:
        """Генерировать гороскоп с помощью AI."""
        sign_name = self._get_sign_name(zodiac_sign)
        period_name = self._get_horoscope_name(horoscope_type)

        prompt = f"""
        Составь {period_name} гороскоп для знака {sign_name}.

        Структура ответа:
        1. Общий прогноз (3-4 предложения)
        2. Любовь и отношения (2-3 предложения)
        3. Карьера и финансы (2-3 предложения)
        4. Здоровье (1-2 предложения)

        Стиль: позитивный, конструктивный, с конкретными советами.
        Избегай общих фраз, давай практические рекомендации.
        """

        llm = await get_llm_manager()
        response = await llm.generate_completion(
            prompt,
            temperature=0.8,
            max_tokens=500
        )

        # Парсим ответ
        # В реальной реализации нужен более сложный парсинг
        sections = response.split("\n\n")

        horoscope_data = {
            "general": sections[0] if len(sections) > 0 else "Общий прогноз",
            "love": sections[1] if len(sections) > 1 else None,
            "career": sections[2] if len(sections) > 2 else None,
            "health": sections[3] if len(sections) > 3 else None,
            "lucky_numbers": [7, 14, 23],  # Можно генерировать
            "lucky_color": "синий"  # Можно выбирать по знаку
        }

        return horoscope_data

    async def _calculate_natal_chart(
            self,
            birth_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Рассчитать натальную карту."""
        # Здесь должны быть астрологические расчеты
        # Упрощенная версия для примера

        return {
            "planets": {
                "sun": {"sign": "aries", "degree": 15.5, "house": 1},
                "moon": {"sign": "cancer", "degree": 22.3, "house": 4},
                "mercury": {"sign": "aries", "degree": 20.1, "house": 1},
                "venus": {"sign": "pisces", "degree": 10.7, "house": 12},
                "mars": {"sign": "leo", "degree": 5.2, "house": 5},
                "jupiter": {"sign": "sagittarius", "degree": 18.9, "house": 9},
                "saturn": {"sign": "capricorn", "degree": 25.4, "house": 10},
                "uranus": {"sign": "aquarius", "degree": 12.6, "house": 11},
                "neptune": {"sign": "pisces", "degree": 8.3, "house": 12},
                "pluto": {"sign": "scorpio", "degree": 14.7, "house": 8}
            },
            "houses": {
                1: {"sign": "aries", "degree": 0},
                2: {"sign": "taurus", "degree": 30},
                3: {"sign": "gemini", "degree": 60},
                4: {"sign": "cancer", "degree": 90},
                5: {"sign": "leo", "degree": 120},
                6: {"sign": "virgo", "degree": 150},
                7: {"sign": "libra", "degree": 180},
                8: {"sign": "scorpio", "degree": 210},
                9: {"sign": "sagittarius", "degree": 240},
                10: {"sign": "capricorn", "degree": 270},
                11: {"sign": "aquarius", "degree": 300},
                12: {"sign": "pisces", "degree": 330}
            },
            "aspects": [
                {"planet1": "sun", "planet2": "moon", "type": "square", "orb": 2.5},
                {"planet1": "venus", "planet2": "jupiter", "type": "trine", "orb": 1.2},
                {"planet1": "mars", "planet2": "saturn", "type": "opposition", "orb": 0.8}
            ]
        }

    async def _get_natal_interpretation(
            self,
            natal_data: Dict[str, Any],
            user
    ) -> str:
        """Получить интерпретацию натальной карты от AI."""
        # Формируем описание для AI
        planets_desc = []
        for planet, data in natal_data["planets"].items():
            planets_desc.append(
                f"{planet} в {data['sign']} в {data['house']} доме"
            )

        prompt = f"""
        Дай краткую интерпретацию натальной карты.

        Основные позиции:
        {chr(10).join(planets_desc[:5])}  # Только основные планеты

        Дай общую характеристику личности (3-4 предложения),
        основные таланты и вызовы.
        Будь конкретным и позитивным.
        """

        llm = await get_llm_manager()
        interpretation = await llm.generate_completion(
            prompt,
            temperature=0.7,
            max_tokens=300
        )

        return interpretation

    async def _calculate_transits(
            self,
            birth_data: Dict[str, Any],
            period: str
    ) -> List[Dict[str, Any]]:
        """Рассчитать транзиты на период."""
        # Упрощенный пример транзитов
        transits = [
            {
                "planet": "jupiter",
                "aspect": "trine",
                "natal_planet": "sun",
                "exact_date": date.today() + timedelta(days=5),
                "orb": 1.2,
                "importance": "high",
                "sphere": "career"
            },
            {
                "planet": "saturn",
                "aspect": "square",
                "natal_planet": "moon",
                "exact_date": date.today() + timedelta(days=15),
                "orb": 2.5,
                "importance": "medium",
                "sphere": "emotions"
            }
        ]

        return transits

    async def _get_transit_interpretation(
            self,
            transits: List[Dict[str, Any]],
            period: str,
            user
    ) -> str:
        """Получить интерпретацию транзитов от AI."""
        # Формируем описание транзитов
        transit_desc = []
        for t in transits[:3]:  # Берем топ-3
            transit_desc.append(
                f"{t['planet']} {t['aspect']} к натальному {t['natal_planet']}"
            )

        prompt = f"""
        Дай интерпретацию транзитов на {self._get_period_name(period)}.

        Основные транзиты:
        {chr(10).join(transit_desc)}

        Опиши общую атмосферу периода и дай 2-3 конкретных совета.
        Будь позитивным и практичным.
        """

        llm = await get_llm_manager()
        interpretation = await llm.generate_completion(
            prompt,
            temperature=0.7,
            max_tokens=250
        )

        return interpretation

    async def _calculate_lunar_month(
            self,
            target_date: date
    ) -> Dict[int, Dict[str, Any]]:
        """Рассчитать лунные дни на месяц."""
        lunar_days = {}

        # Упрощенный расчет для примера
        for day in range(1, 32):
            try:
                current_date = date(target_date.year, target_date.month, day)
                lunar_day = ((current_date.day + target_date.month * 2) % 30) + 1

                lunar_days[day] = {
                    "lunar_day": lunar_day,
                    "phase": self._get_moon_phase_for_day(lunar_day)
                }
            except ValueError:
                # Дня нет в этом месяце
                pass

        return lunar_days

    def _calculate_moon_phase(self) -> Dict[str, Any]:
        """Рассчитать текущую фазу луны."""
        # Упрощенный расчет для примера
        today = date.today()

        # Известное новолуние для расчета
        known_new_moon = date(2024, 1, 11)
        days_since = (today - known_new_moon).days

        # Лунный месяц ~29.53 дня
        lunar_month = 29.53
        phase_days = days_since % lunar_month

        # Определяем фазу
        if phase_days < 1.84:
            phase = {"name": "Новолуние", "emoji": "🌑", "percent": 0}
        elif phase_days < 5.53:
            phase = {"name": "Растущий серп", "emoji": "🌒", "percent": 25}
        elif phase_days < 9.22:
            phase = {"name": "Первая четверть", "emoji": "🌓", "percent": 50}
        elif phase_days < 12.91:
            phase = {"name": "Растущая луна", "emoji": "🌔", "percent": 75}
        elif phase_days < 16.61:
            phase = {"name": "Полнолуние", "emoji": "🌕", "percent": 100}
        elif phase_days < 20.30:
            phase = {"name": "Убывающая луна", "emoji": "🌖", "percent": 75}
        elif phase_days < 23.99:
            phase = {"name": "Последняя четверть", "emoji": "🌗", "percent": 50}
        else:
            phase = {"name": "Убывающий серп", "emoji": "🌘", "percent": 25}

        phase["day"] = int(phase_days) + 1
        phase["illumination"] = abs(phase["percent"])

        return phase

    def _get_moon_phase_for_day(self, lunar_day: int) -> str:
        """Получить эмодзи фазы луны для дня."""
        if lunar_day <= 2:
            return "🌑"
        elif lunar_day <= 6:
            return "🌒"
        elif lunar_day <= 9:
            return "🌓"
        elif lunar_day <= 13:
            return "🌔"
        elif lunar_day <= 17:
            return "🌕"
        elif lunar_day <= 21:
            return "🌖"
        elif lunar_day <= 24:
            return "🌗"
        else:
            return "🌘"

    def _get_zodiac_sign(self, birth_date: datetime) -> str:
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

    def _get_period_name(self, period: str) -> str:
        """Получить название периода."""
        names = {
            "today": "сегодня",
            "week": "неделю",
            "month": "месяц",
            "year": "год"
        }
        return names.get(period, period)

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

    def _get_city_data(self, city_code: str) -> Dict[str, Any]:
        """Получить данные города."""
        cities = {
            "moscow": {
                "name": "Москва",
                "lat": 55.7558,
                "lon": 37.6173,
                "timezone": "Europe/Moscow"
            },
            "spb": {
                "name": "Санкт-Петербург",
                "lat": 59.9311,
                "lon": 30.3609,
                "timezone": "Europe/Moscow"
            },
            "almaty": {
                "name": "Алматы",
                "lat": 43.2220,
                "lon": 76.8512,
                "timezone": "Asia/Almaty"
            },
            # Добавить больше городов
        }

        return cities.get(city_code, cities["moscow"])


def setup(router: Router) -> None:
    """Настройка обработчиков астрологии."""
    handler = AstrologyHandlers()
    handler.register_handlers(router)