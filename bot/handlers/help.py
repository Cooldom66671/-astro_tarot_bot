"""
Обработчик команды /help и справочной информации.

Этот модуль отвечает за:
- Общую справку по боту
- Разделы помощи по функциям
- Часто задаваемые вопросы (FAQ)
- Контакты поддержки
- Обучающие материалы

Автор: AI Assistant
Дата создания: 2024-12-30
"""

import logging
from typing import Optional, Dict, List, Any
from enum import Enum

from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from bot.handlers.base import (
    BaseHandler,
    error_handler,
    log_action,
    answer_callback_query,
    edit_or_send_message
)
from config import settings, BotCommands

# НОВЫЕ ИМПОРТЫ ДЛЯ КЛАВИАТУР
from infrastructure.telegram.keyboards import (
    InlineKeyboard,
    DynamicMenu,
    PaginatedKeyboard,
    Keyboards,
    BaseCallbackData,
    parse_callback_data
)

# Настройка логирования
logger = logging.getLogger(__name__)


class HelpSection(Enum):
    """Разделы помощи."""
    GENERAL = ("general", "📋 Общая информация")
    COMMANDS = ("commands", "💬 Команды")
    TAROT = ("tarot", "🎴 Таро")
    ASTROLOGY = ("astrology", "🔮 Астрология")
    SUBSCRIPTION = ("subscription", "💎 Подписка")
    PROFILE = ("profile", "👤 Профиль")
    FAQ = ("faq", "❓ Частые вопросы")
    SUPPORT = ("support", "🆘 Поддержка")

    def __init__(self, code: str, title: str):
        self.code = code
        self.title = title


class FAQCategory(Enum):
    """Категории FAQ."""
    GENERAL = ("general", "Общие вопросы")
    TAROT = ("tarot", "Вопросы о Таро")
    ASTROLOGY = ("astrology", "Вопросы об Астрологии")
    PAYMENT = ("payment", "Оплата и подписка")
    TECHNICAL = ("technical", "Технические вопросы")

    def __init__(self, code: str, title: str):
        self.code = code
        self.title = title


# НОВЫЕ CALLBACK DATA КЛАССЫ
class HelpCallbackData(BaseCallbackData, prefix="help"):
    """Callback data для помощи."""
    section: Optional[str] = None


class FAQCallbackData(BaseCallbackData, prefix="faq"):
    """Callback data для FAQ."""
    category: Optional[str] = None
    question_id: Optional[int] = None


# НОВАЯ КЛАВИАТУРА ДЛЯ ПОМОЩИ
class HelpMenuKeyboard(DynamicMenu):
    """Клавиатура меню помощи."""

    def __init__(self):
        super().__init__(menu_id="help_main", level=0)

    async def build(self, **kwargs) -> types.InlineKeyboardMarkup:
        """Построить меню помощи."""
        # Основные разделы
        for section in HelpSection:
            if section == HelpSection.FAQ:
                # FAQ имеет подменю
                self.add_menu_item(
                    section.code,
                    section.title.split()[1],  # Убираем эмодзи
                    section.title.split()[0],   # Эмодзи отдельно
                    submenu=True
                )
            else:
                self.add_button(
                    text=section.title,
                    callback_data=HelpCallbackData(
                        action="section",
                        value=section.code
                    )
                )

        # Настройка сетки
        self.builder.adjust(1, 1, 1, 1, 2, 2)

        return await super().build(**kwargs)


# НОВАЯ КЛАВИАТУРА ДЛЯ FAQ
class FAQKeyboard(PaginatedKeyboard):
    """Клавиатура FAQ с пагинацией."""

    def __init__(self, category: FAQCategory, questions: List[Dict[str, str]], page: int = 1):
        self.category = category
        self.questions = questions
        super().__init__(
            items=questions,
            page_size=5,
            current_page=page,
            menu_type=f"faq_{category.code}"
        )

    async def build(self, **kwargs) -> types.InlineKeyboardMarkup:
        """Построить клавиатуру FAQ."""
        # Заголовок категории
        self.add_button(
            text=f"📂 {self.category.title}",
            callback_data="noop"
        )

        # Вопросы текущей страницы
        page_questions = self.get_page_items()

        for i, q in enumerate(page_questions):
            # Вычисляем глобальный индекс вопроса
            global_index = (self.current_page - 1) * self.page_size + i

            self.add_button(
                text=f"❓ {q['question'][:50]}{'...' if len(q['question']) > 50 else ''}",
                callback_data=FAQCallbackData(
                    action="show",
                    value=self.category.code,
                    page=global_index
                )
            )

        # Настройка сетки для вопросов
        self.builder.adjust(1, *([1] * len(page_questions)))

        # Пагинация
        if self.total_pages > 1:
            self.add_pagination_buttons()

        # Назад к категориям
        self.add_button(
            text="◀️ К категориям",
            callback_data=FAQCallbackData(action="menu")
        )

        return await super().build(**kwargs)


class HelpHandler(BaseHandler):
    """Обработчик справки и помощи."""

    # FAQ вопросы и ответы (оставляем без изменений)
    FAQ_DATA = {
        FAQCategory.GENERAL: [
            {
                "question": "Что умеет этот бот?",
                "answer": (
                    "Бот помогает с Таро и Астрологией:\n"
                    "• Гадания на картах Таро\n"
                    "• Персональные гороскопы\n"
                    "• Натальные карты\n"
                    "• Совместимость пар\n"
                    "• Лунный календарь"
                )
            },
            {
                "question": "Как начать пользоваться?",
                "answer": (
                    "1. Нажмите /start\n"
                    "2. Пройдите короткую регистрацию\n"
                    "3. Выберите интересующий раздел\n"
                    "4. Следуйте подсказкам бота"
                )
            },
            {
                "question": "Бот бесплатный?",
                "answer": (
                    "Да, базовые функции бесплатны:\n"
                    "• 1 карта дня\n"
                    "• 3 простых расклада в день\n"
                    "• Общие гороскопы\n\n"
                    "Расширенные функции доступны по подписке."
                )
            }
        ],
        FAQCategory.TAROT: [
            {
                "question": "Какие расклады доступны?",
                "answer": (
                    "Доступные расклады:\n"
                    "• Карта дня - бесплатно\n"
                    "• Три карты - прошлое/настоящее/будущее\n"
                    "• Кельтский крест - детальный анализ\n"
                    "• Расклад на отношения\n"
                    "• Расклад на работу и финансы"
                )
            },
            {
                "question": "Можно ли сохранять расклады?",
                "answer": (
                    "Да! Все ваши расклады сохраняются:\n"
                    "• История последних 30 раскладов\n"
                    "• Избранные расклады без ограничений\n"
                    "• Возможность поделиться раскладом"
                )
            }
        ],
        FAQCategory.ASTROLOGY: [
            {
                "question": "Нужно ли точное время рождения?",
                "answer": (
                    "Время рождения важно для:\n"
                    "• Точного расчета домов\n"
                    "• Положения Луны\n"
                    "• Восходящего знака\n\n"
                    "Без времени доступен упрощенный расчет."
                )
            },
            {
                "question": "Какие гороскопы доступны?",
                "answer": (
                    "Типы гороскопов:\n"
                    "• Дневной - бесплатно\n"
                    "• Недельный и месячный\n"
                    "• Персональный на основе натальной карты\n"
                    "• Любовный гороскоп\n"
                    "• Бизнес-гороскоп"
                )
            }
        ],
        FAQCategory.PAYMENT: [
            {
                "question": "Какие способы оплаты?",
                "answer": (
                    "Доступные способы оплаты:\n"
                    "• Банковские карты\n"
                    "• ЮMoney (Яндекс.Деньги)\n"
                    "• Telegram Stars\n"
                    "• Криптовалюта\n\n"
                    "Все платежи защищены."
                )
            },
            {
                "question": "Можно ли отменить подписку?",
                "answer": (
                    "Да, в любой момент:\n"
                    "1. Перейдите в /subscription\n"
                    "2. Нажмите 'Управление'\n"
                    "3. Выберите 'Отменить подписку'\n\n"
                    "Доступ сохранится до конца периода."
                )
            }
        ],
        FAQCategory.TECHNICAL: [
            {
                "question": "Безопасны ли мои данные?",
                "answer": (
                    "Ваши данные защищены:\n"
                    "• Шифрование всех данных\n"
                    "• Нет передачи третьим лицам\n"
                    "• Соответствие GDPR\n"
                    "• Возможность удалить все данные"
                )
            },
            {
                "question": "Можно ли пользоваться с компьютера?",
                "answer": (
                    "Да! Используйте:\n"
                    "• Telegram Desktop\n"
                    "• Telegram Web\n\n"
                    "Все функции будут работать одинаково."
                )
            }
        ]
    }

    # Содержание разделов помощи (оставляем без изменений)
    HELP_CONTENT = {
        HelpSection.GENERAL: (
            "📋 <b>Общая информация</b>\n\n"
            "Астро-Таро Бот - ваш персональный помощник в мире эзотерики.\n\n"
            "<b>Основные возможности:</b>\n"
            "• Гадания на картах Таро\n"
            "• Персональные гороскопы\n"
            "• Натальные карты\n"
            "• Анализ совместимости\n"
            "• Лунный календарь\n\n"
            "Начните с /menu или выберите интересующий раздел ниже."
        ),
        HelpSection.COMMANDS: (
            "💬 <b>Доступные команды</b>\n\n"
            "<b>Основные:</b>\n"
            "/start - Начать работу\n"
            "/menu - Главное меню\n"
            "/help - Эта справка\n"
            "/cancel - Отменить действие\n\n"
            "<b>Разделы:</b>\n"
            "/tarot - Расклады Таро\n"
            "/astrology - Астрология\n"
            "/profile - Ваш профиль\n"
            "/subscription - Подписка\n\n"
            "<b>Дополнительно:</b>\n"
            "/stats - Ваша статистика\n"
            "/settings - Настройки\n"
            "/support - Поддержка"
        ),
        HelpSection.TAROT: (
            "🎴 <b>Помощь по Таро</b>\n\n"
            "<b>Как сделать расклад:</b>\n"
            "1. Выберите /tarot или Таро в меню\n"
            "2. Выберите тип расклада\n"
            "3. Сформулируйте вопрос\n"
            "4. Выберите карты или доверьтесь случаю\n\n"
            "<b>Типы раскладов:</b>\n"
            "• <b>Карта дня</b> - общий совет на день\n"
            "• <b>Три карты</b> - прошлое/настоящее/будущее\n"
            "• <b>Кельтский крест</b> - детальный анализ ситуации\n"
            "• <b>Отношения</b> - анализ партнерства\n"
            "• <b>Да/Нет</b> - быстрый ответ"
        ),
        HelpSection.ASTROLOGY: (
            "🔮 <b>Помощь по Астрологии</b>\n\n"
            "<b>Для точных расчетов нужны:</b>\n"
            "• Дата рождения\n"
            "• Время рождения (желательно)\n"
            "• Место рождения\n\n"
            "<b>Доступные функции:</b>\n"
            "• <b>Натальная карта</b> - ваш астрологический портрет\n"
            "• <b>Гороскопы</b> - прогнозы на день/неделю/месяц\n"
            "• <b>Транзиты</b> - текущие влияния планет\n"
            "• <b>Синастрия</b> - совместимость с партнером\n"
            "• <b>Лунный календарь</b> - благоприятные дни"
        ),
        HelpSection.SUBSCRIPTION: (
            "💎 <b>Помощь по подписке</b>\n\n"
            "<b>Уровни подписки:</b>\n\n"
            "🆓 <b>Бесплатный</b>\n"
            "• 1 карта дня\n"
            "• 3 простых расклада в день\n"
            "• Общие гороскопы\n\n"
            "⭐ <b>Premium</b>\n"
            "• Безлимитные расклады\n"
            "• Персональные гороскопы\n"
            "• Сохранение истории\n"
            "• Приоритетная поддержка\n\n"
            "🌟 <b>VIP</b>\n"
            "• Все функции Premium\n"
            "• Эксклюзивные расклады\n"
            "• Личные консультации\n"
            "• Ранний доступ к новым функциям"
        ),
        HelpSection.PROFILE: (
            "👤 <b>Помощь по профилю</b>\n\n"
            "<b>В профиле вы можете:</b>\n"
            "• Просмотреть свои данные\n"
            "• Изменить данные рождения\n"
            "• Настроить уведомления\n"
            "• Выбрать язык интерфейса\n"
            "• Управлять подпиской\n\n"
            "<b>Статистика показывает:</b>\n"
            "• Количество раскладов\n"
            "• Любимые карты\n"
            "• Время использования\n"
            "• Достижения"
        )
    }

    def register_handlers(self) -> None:
        """Регистрация обработчиков."""
        # Команда /help
        self.router.message.register(
            self.cmd_help,
            Command("help")
        )

        # Callback для разделов помощи - НОВЫЙ ОБРАБОТЧИК
        self.router.callback_query.register(
            self.help_callback_handler,
            HelpCallbackData.filter()
        )

        # Callback для FAQ - НОВЫЙ ОБРАБОТЧИК
        self.router.callback_query.register(
            self.faq_callback_handler,
            FAQCallbackData.filter()
        )

        # Старые callback для обратной совместимости
        self.router.callback_query.register(
            self.legacy_help_callback,
            F.data.startswith("help:")
        )

        self.router.callback_query.register(
            self.legacy_faq_callback,
            F.data.startswith("faq:")
        )

        # Команда /support
        self.router.message.register(
            self.cmd_support,
            Command("support")
        )

        # Команда /commands
        self.router.message.register(
            self.cmd_commands,
            Command("commands")
        )

    @error_handler()
    @log_action("help_command")
    async def cmd_help(
            self,
            message: types.Message,
            state: FSMContext,
            **kwargs
    ) -> None:
        """
        Обработчик команды /help.

        Args:
            message: Сообщение пользователя
            state: Контекст FSM
        """
        text = (
            "📚 <b>Справка и помощь</b>\n\n"
            "Выберите раздел для получения подробной информации:"
        )

        # ИСПОЛЬЗУЕМ НОВУЮ КЛАВИАТУРУ
        keyboard = HelpMenuKeyboard()
        kb = await keyboard.build()

        await message.answer(
            text,
            reply_markup=kb,
            parse_mode="HTML"
        )

    @error_handler()
    @log_action("support_command")
    async def cmd_support(
            self,
            message: types.Message,
            state: FSMContext,
            **kwargs
    ) -> None:
        """Обработчик команды /support."""
        text = (
            "🆘 <b>Служба поддержки</b>\n\n"
            "Мы всегда готовы помочь!\n\n"
            "<b>Способы связи:</b>\n"
            "• Чат поддержки: @astrotaro_support\n"
            "• Email: support@astrotaro.bot\n"
            "• В боте: отправьте /feedback\n\n"
            "<b>Время работы:</b>\n"
            "Пн-Пт: 9:00 - 21:00 МСК\n"
            "Сб-Вс: 10:00 - 18:00 МСК\n\n"
            "Среднее время ответа: 30 минут"
        )

        # ИСПОЛЬЗУЕМ НОВУЮ КЛАВИАТУРУ
        keyboard = InlineKeyboard()
        keyboard.add_button(
            text="💬 Чат поддержки",
            url="https://t.me/astrotaro_support"
        )
        keyboard.add_button(
            text="📧 Написать email",
            url="mailto:support@astrotaro.bot"
        )
        keyboard.add_button(
            text="❓ Частые вопросы",
            callback_data=FAQCallbackData(action="menu")
        )
        keyboard.add_button(
            text="◀️ Назад к справке",
            callback_data=HelpCallbackData(action="menu")
        )

        keyboard.builder.adjust(1, 1, 1, 1)
        kb = await keyboard.build()

        await message.answer(
            text,
            reply_markup=kb,
            parse_mode="HTML"
        )

    @error_handler()
    async def cmd_commands(
            self,
            message: types.Message,
            state: FSMContext,
            **kwargs
    ) -> None:
        """Обработчик команды /commands."""
        # Используем контент из раздела COMMANDS
        text = self.HELP_CONTENT[HelpSection.COMMANDS]

        # ИСПОЛЬЗУЕМ НОВУЮ КНОПКУ НАЗАД
        keyboard = await Keyboards.back(
            HelpCallbackData(action="menu").pack()
        )

        await message.answer(
            text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )

    @error_handler()
    async def help_callback_handler(
            self,
            callback: types.CallbackQuery,
            callback_data: HelpCallbackData,
            state: FSMContext
    ) -> None:
        """Обработка выбора раздела помощи через новый callback."""
        action = callback_data.action

        if action == "menu":
            # Возврат к главному меню помощи
            text = (
                "📚 <b>Справка и помощь</b>\n\n"
                "Выберите раздел для получения подробной информации:"
            )
            keyboard = HelpMenuKeyboard()
            kb = await keyboard.build()
        elif action == "section":
            # Показываем раздел
            section_code = callback_data.value
            section = None

            for s in HelpSection:
                if s.code == section_code:
                    section = s
                    break

            if not section:
                await answer_callback_query(callback, "Раздел не найден", show_alert=True)
                return

            # Специальная обработка для FAQ
            if section == HelpSection.FAQ:
                await self._show_faq_menu(callback)
                return
            elif section == HelpSection.SUPPORT:
                # Для support показываем отдельное меню
                await self._show_support_menu(callback)
                return
            else:
                text = self.HELP_CONTENT.get(section, "Информация не найдена")
                kb = self._create_section_keyboard(section)
        else:
            await answer_callback_query(callback, "Неизвестное действие", show_alert=True)
            return

        await edit_or_send_message(
            callback.message,
            text,
            reply_markup=kb,
            parse_mode="HTML"
        )

        await answer_callback_query(callback)

    @error_handler()
    async def faq_callback_handler(
            self,
            callback: types.CallbackQuery,
            callback_data: FAQCallbackData,
            state: FSMContext
    ) -> None:
        """Обработка FAQ через новый callback."""
        action = callback_data.action

        if action == "menu":
            await self._show_faq_menu(callback)
        elif action == "category":
            category_code = callback_data.value
            await self._show_faq_category(callback, category_code)
        elif action == "show":
            category_code = callback_data.value
            question_index = callback_data.page
            await self._show_faq_question(callback, category_code, question_index)

        await answer_callback_query(callback)

    # Обработчики для обратной совместимости
    @error_handler()
    async def legacy_help_callback(
            self,
            callback: types.CallbackQuery,
            state: FSMContext
    ) -> None:
        """Старый обработчик для обратной совместимости."""
        _, action = callback.data.split(":", 1)

        # Преобразуем в новый формат
        if action == "menu":
            new_callback_data = HelpCallbackData(action="menu")
        else:
            new_callback_data = HelpCallbackData(action="section", value=action)

        await self.help_callback_handler(callback, new_callback_data, state)

    @error_handler()
    async def legacy_faq_callback(
            self,
            callback: types.CallbackQuery,
            state: FSMContext
    ) -> None:
        """Старый обработчик FAQ для обратной совместимости."""
        parts = callback.data.split(":")

        if len(parts) < 2:
            await answer_callback_query(callback, "Ошибка данных", show_alert=True)
            return

        action = parts[1]

        if action == "menu":
            new_callback_data = FAQCallbackData(action="menu")
        elif action == "category" and len(parts) >= 3:
            new_callback_data = FAQCallbackData(action="category", value=parts[2])
        elif action == "question" and len(parts) >= 4:
            new_callback_data = FAQCallbackData(
                action="show",
                value=parts[2],
                page=int(parts[3])
            )
        else:
            await answer_callback_query(callback, "Неизвестное действие", show_alert=True)
            return

        await self.faq_callback_handler(callback, new_callback_data, state)

    # Вспомогательные методы

    def _create_section_keyboard(self, section: HelpSection) -> types.InlineKeyboardMarkup:
        """Создать клавиатуру для раздела."""
        keyboard = InlineKeyboard()

        # Специальные кнопки для некоторых разделов
        if section == HelpSection.GENERAL:
            keyboard.add_button(
                text="🚀 Начать использование",
                callback_data="welcome:start"
            )
        elif section == HelpSection.TAROT:
            from infrastructure.telegram.keyboards import TarotCallbackData
            keyboard.add_button(
                text="🎴 Перейти к Таро",
                callback_data=TarotCallbackData(action="menu")
            )
        elif section == HelpSection.ASTROLOGY:
            from infrastructure.telegram.keyboards import AstrologyCallbackData
            keyboard.add_button(
                text="🔮 Перейти к Астрологии",
                callback_data=AstrologyCallbackData(action="menu")
            )
        elif section == HelpSection.SUBSCRIPTION:
            from infrastructure.telegram.keyboards import SubscriptionCallbackData
            keyboard.add_button(
                text="💎 Оформить подписку",
                callback_data=SubscriptionCallbackData(action="plans")
            )

        # Кнопка назад
        keyboard.add_button(
            text="◀️ Назад к справке",
            callback_data=HelpCallbackData(action="menu")
        )

        return keyboard.builder.as_markup()

    async def _show_faq_menu(self, callback: types.CallbackQuery) -> None:
        """Показать меню FAQ."""
        text = (
            "❓ <b>Часто задаваемые вопросы</b>\n\n"
            "Выберите категорию:"
        )

        keyboard = InlineKeyboard()

        for category in FAQCategory:
            keyboard.add_button(
                text=category.title,
                callback_data=FAQCallbackData(
                    action="category",
                    value=category.code
                )
            )

        keyboard.builder.adjust(1)

        keyboard.add_button(
            text="◀️ Назад к справке",
            callback_data=HelpCallbackData(action="menu")
        )

        kb = await keyboard.build()

        await edit_or_send_message(
            callback.message,
            text,
            reply_markup=kb,
            parse_mode="HTML"
        )

    async def _show_faq_category(
            self,
            callback: types.CallbackQuery,
            category_code: str
    ) -> None:
        """Показать вопросы категории."""
        # Находим категорию
        category = None
        for c in FAQCategory:
            if c.code == category_code:
                category = c
                break

        if not category or category not in self.FAQ_DATA:
            await answer_callback_query(
                callback,
                "Категория не найдена",
                show_alert=True
            )
            return

        questions = self.FAQ_DATA[category]

        # ИСПОЛЬЗУЕМ НОВУЮ ПАГИНИРОВАННУЮ КЛАВИАТУРУ
        keyboard = FAQKeyboard(category, questions)
        kb = await keyboard.build()

        text = f"❓ <b>{category.title}</b>\n\nВыберите вопрос:"

        await edit_or_send_message(
            callback.message,
            text,
            reply_markup=kb,
            parse_mode="HTML"
        )

    async def _show_faq_question(
            self,
            callback: types.CallbackQuery,
            category_code: str,
            question_index: int
    ) -> None:
        """Показать ответ на вопрос."""
        # Находим категорию
        category = None
        for c in FAQCategory:
            if c.code == category_code:
                category = c
                break

        if not category or category not in self.FAQ_DATA:
            return

        questions = self.FAQ_DATA[category]
        if question_index >= len(questions):
            return

        faq = questions[question_index]

        text = (
            f"❔ <b>{faq['question']}</b>\n\n"
            f"{faq['answer']}"
        )

        keyboard = InlineKeyboard()

        # Навигация по вопросам
        nav_row = []
        if question_index > 0:
            nav_row.append(types.InlineKeyboardButton(
                text="⬅️ Предыдущий",
                callback_data=FAQCallbackData(
                    action="show",
                    value=category_code,
                    page=question_index - 1
                ).pack()
            ))

        if question_index < len(questions) - 1:
            nav_row.append(types.InlineKeyboardButton(
                text="➡️ Следующий",
                callback_data=FAQCallbackData(
                    action="show",
                    value=category_code,
                    page=question_index + 1
                ).pack()
            ))

        if nav_row:
            keyboard.builder.row(*nav_row)

        keyboard.add_button(
            text="📋 К вопросам",
            callback_data=FAQCallbackData(
                action="category",
                value=category_code
            )
        )

        keyboard.add_button(
            text="❓ Все категории",
            callback_data=FAQCallbackData(action="menu")
        )

        kb = await keyboard.build()

        await edit_or_send_message(
            callback.message,
            text,
            reply_markup=kb,
            parse_mode="HTML"
        )

    async def _show_support_menu(self, callback: types.CallbackQuery) -> None:
        """Показать меню поддержки."""
        text = (
            "🆘 <b>Служба поддержки</b>\n\n"
            "Мы всегда готовы помочь!\n\n"
            "<b>Способы связи:</b>\n"
            "• Чат поддержки: @astrotaro_support\n"
            "• Email: support@astrotaro.bot\n\n"
            "<b>Время работы:</b>\n"
            "Пн-Пт: 9:00 - 21:00 МСК\n"
            "Сб-Вс: 10:00 - 18:00 МСК"
        )

        keyboard = InlineKeyboard()

        keyboard.add_button(
            text="💬 Чат поддержки",
            url="https://t.me/astrotaro_support"
        )
        keyboard.add_button(
            text="📧 Написать email",
            url="mailto:support@astrotaro.bot"
        )
        keyboard.add_button(
            text="❓ Частые вопросы",
            callback_data=FAQCallbackData(action="menu")
        )
        keyboard.add_button(
            text="◀️ Назад к справке",
            callback_data=HelpCallbackData(action="menu")
        )

        keyboard.builder.adjust(1, 1, 1, 1)
        kb = await keyboard.build()

        await edit_or_send_message(
            callback.message,
            text,
            reply_markup=kb,
            parse_mode="HTML"
        )


# Функция для регистрации обработчика
def register_help_handler(router: Router) -> None:
    """
    Регистрация обработчика помощи.

    Args:
        router: Роутер для регистрации
    """
    handler = HelpHandler(router)
    handler.register_handlers()
    logger.info("Help handler зарегистрирован")


logger.info("Модуль обработчика помощи загружен")