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
from typing import Optional, Dict, List
from enum import Enum

from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from bot.handlers.base import BaseHandler, error_handler, log_action
from infrastructure.telegram import (
    MessageBuilder,
    MessageStyle,
    InlineKeyboard,
    DynamicMenu,
    get_info_message
)

# Настройка логирования
logger = logging.getLogger(__name__)


class HelpSection(Enum):
    """Разделы помощи."""
    GENERAL = ("general", "📋 Общая информация", "general")
    COMMANDS = ("commands", "💬 Команды", "commands")
    TAROT = ("tarot", "🎴 Таро", "tarot")
    ASTROLOGY = ("astrology", "🔮 Астрология", "astrology")
    SUBSCRIPTION = ("subscription", "💎 Подписка", "subscription")
    PROFILE = ("profile", "👤 Профиль", "profile")
    FAQ = ("faq", "❓ Частые вопросы", "faq")
    SUPPORT = ("support", "🆘 Поддержка", "support")

    def __init__(self, code: str, title: str, key: str):
        self.code = code
        self.title = title
        self.key = key


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


class HelpHandler(BaseHandler):
    """Обработчик справки и помощи."""

    # FAQ вопросы и ответы
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
                "question": "Как работают расклады?",
                "answer": (
                    "1. Выберите тип расклада\n"
                    "2. Сформулируйте вопрос\n"
                    "3. Бот перемешает колоду\n"
                    "4. Выберите карты\n"
                    "5. Получите интерпретацию"
                )
            },
            {
                "question": "Можно ли повторить расклад?",
                "answer": (
                    "Да, но рекомендуется:\n"
                    "• Не делать одинаковые расклады чаще раза в день\n"
                    "• Формулировать вопрос по-разному\n"
                    "• Доверять первому раскладу"
                )
            },
            {
                "question": "Что означают перевернутые карты?",
                "answer": (
                    "Перевернутые карты показывают:\n"
                    "• Внутренние процессы\n"
                    "• Блокировки энергии\n"
                    "• Теневые аспекты\n"
                    "• Задержки или препятствия"
                )
            }
        ],
        FAQCategory.ASTROLOGY: [
            {
                "question": "Зачем нужны данные рождения?",
                "answer": (
                    "Для точных расчетов необходимы:\n"
                    "• Дата - для знака зодиака\n"
                    "• Время - для асцендента и домов\n"
                    "• Место - для координат\n\n"
                    "Без этих данных невозможно построить натальную карту."
                )
            },
            {
                "question": "Что если не знаю время рождения?",
                "answer": (
                    "Можно указать примерное время или полдень.\n"
                    "Будут доступны:\n"
                    "• Положения планет в знаках\n"
                    "• Основные аспекты\n\n"
                    "Недоступны:\n"
                    "• Точный асцендент\n"
                    "• Дома гороскопа"
                )
            },
            {
                "question": "Как часто обновляются прогнозы?",
                "answer": (
                    "• Ежедневные - каждый день\n"
                    "• Недельные - по понедельникам\n"
                    "• Месячные - 1 числа\n"
                    "• Персональные - учитывают транзиты в реальном времени"
                )
            }
        ],
        FAQCategory.PAYMENT: [
            {
                "question": "Какие есть тарифы?",
                "answer": (
                    "🥉 Базовый - 299₽/мес\n"
                    "🥈 Премиум - 599₽/мес\n"
                    "🥇 VIP - 1499₽/мес\n\n"
                    "При оплате за год - скидка 17%"
                )
            },
            {
                "question": "Как оплатить подписку?",
                "answer": (
                    "1. Перейдите в раздел 💎 Подписка\n"
                    "2. Выберите тариф\n"
                    "3. Выберите способ оплаты\n"
                    "4. Следуйте инструкциям\n\n"
                    "Принимаем карты, ЮMoney, криптовалюту."
                )
            },
            {
                "question": "Как отменить подписку?",
                "answer": (
                    "1. Зайдите в 💎 Подписка\n"
                    "2. Нажмите 'Управление'\n"
                    "3. Выберите 'Отменить подписку'\n\n"
                    "Подписка будет активна до конца оплаченного периода."
                )
            }
        ],
        FAQCategory.TECHNICAL: [
            {
                "question": "Бот не отвечает, что делать?",
                "answer": (
                    "Попробуйте:\n"
                    "1. Перезапустить бота командой /start\n"
                    "2. Проверить интернет-соединение\n"
                    "3. Обновить Telegram\n\n"
                    "Если не помогло - напишите в поддержку."
                )
            },
            {
                "question": "Как удалить свои данные?",
                "answer": (
                    "1. Зайдите в ⚙️ Настройки\n"
                    "2. Выберите 'Конфиденциальность'\n"
                    "3. Нажмите 'Удалить все данные'\n\n"
                    "Внимание: это действие необратимо!"
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

    def register_handlers(self) -> None:
        """Регистрация обработчиков."""
        # Команда /help
        self.router.message.register(
            self.cmd_help,
            Command("help")
        )

        # Callback для разделов помощи
        self.router.callback_query.register(
            self.help_section_callback,
            F.data.startswith("help:")
        )

        # Callback для FAQ
        self.router.callback_query.register(
            self.faq_callback,
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
            state: FSMContext
    ) -> None:
        """
        Обработчик команды /help.

        Args:
            message: Сообщение пользователя
            state: Контекст FSM
        """
        # Основное меню помощи
        builder = MessageBuilder(MessageStyle.MARKDOWN_V2)

        builder.add_bold("📚 Справка и помощь").add_line()
        builder.add_separator().add_line()

        builder.add_line("Выберите раздел для получения подробной информации:")
        builder.add_line()

        # Создаем клавиатуру с разделами
        keyboard = await self._create_help_menu()

        await message.answer(
            builder.build(),
            reply_markup=keyboard,
            parse_mode="MarkdownV2"
        )

    @error_handler()
    @log_action("support_command")
    async def cmd_support(
            self,
            message: types.Message,
            state: FSMContext
    ) -> None:
        """Обработчик команды /support."""
        support_text = await get_info_message("support")

        # Кнопки быстрых действий
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
            callback_data="help:faq"
        )

        keyboard.builder.adjust(1, 1, 1)

        await message.answer(
            support_text,
            reply_markup=await keyboard.build(),
            parse_mode="MarkdownV2"
        )

    @error_handler()
    async def cmd_commands(
            self,
            message: types.Message,
            state: FSMContext
    ) -> None:
        """Обработчик команды /commands."""
        commands_text = await get_info_message("commands")

        await message.answer(
            commands_text,
            parse_mode="MarkdownV2"
        )

    @error_handler()
    async def help_section_callback(
            self,
            callback: types.CallbackQuery,
            state: FSMContext
    ) -> None:
        """Обработка выбора раздела помощи."""
        _, section_code = callback.data.split(":", 1)

        # Находим раздел
        section = None
        for s in HelpSection:
            if s.code == section_code:
                section = s
                break

        if not section:
            await callback.answer("Раздел не найден", show_alert=True)
            return

        # Показываем контент раздела
        if section == HelpSection.FAQ:
            await self._show_faq_menu(callback.message)
        else:
            content = await self._get_section_content(section)
            keyboard = await self._create_section_keyboard(section)

            await callback.message.edit_text(
                content,
                reply_markup=keyboard,
                parse_mode="MarkdownV2"
            )

        await callback.answer()

    @error_handler()
    async def faq_callback(
            self,
            callback: types.CallbackQuery,
            state: FSMContext
    ) -> None:
        """Обработка FAQ."""
        parts = callback.data.split(":")
        action = parts[1]

        if action == "category":
            # Показываем вопросы категории
            category_code = parts[2]
            await self._show_faq_category(callback.message, category_code)

        elif action == "question":
            # Показываем ответ на вопрос
            category_code = parts[2]
            question_index = int(parts[3])
            await self._show_faq_answer(callback.message, category_code, question_index)

        elif action == "menu":
            # Возврат к меню FAQ
            await self._show_faq_menu(callback.message)

        await callback.answer()

    async def _create_help_menu(self) -> types.InlineKeyboardMarkup:
        """Создать главное меню помощи."""
        menu = DynamicMenu("help_main")

        for section in HelpSection:
            menu.add_menu_item(
                item_id=section.code,
                text=section.title,
                emoji=section.title.split()[0]
            )

        return await menu.build()

    async def _get_section_content(self, section: HelpSection) -> str:
        """Получить контент раздела помощи."""
        builder = MessageBuilder(MessageStyle.MARKDOWN_V2)

        builder.add_bold(section.title).add_line()
        builder.add_separator().add_line()

        # Контент по разделам
        if section == HelpSection.GENERAL:
            builder.add_line("🤖 **Астро-Таро Ассистент** - ваш персональный помощник в мире эзотерики.")
            builder.add_empty_line()
            builder.add_bold("Основные возможности:").add_line()
            builder.add_list([
                "Гадания на картах Таро",
                "Персональные гороскопы",
                "Натальные карты",
                "Анализ совместимости",
                "Лунный календарь"
            ])

        elif section == HelpSection.COMMANDS:
            commands_text = await get_info_message("commands")
            return commands_text

        elif section == HelpSection.TAROT:
            builder.add_line("Раздел **Таро** позволяет:")
            builder.add_list([
                "Получать карту дня",
                "Делать различные расклады",
                "Изучать значения карт",
                "Сохранять важные расклады",
                "Вести историю гаданий"
            ])
            builder.add_empty_line()
            builder.add_italic("Совет: формулируйте вопросы четко и конкретно")

        elif section == HelpSection.ASTROLOGY:
            builder.add_line("Раздел **Астрология** включает:")
            builder.add_list([
                "Ежедневные гороскопы",
                "Натальную карту рождения",
                "Текущие транзиты планет",
                "Анализ совместимости пар",
                "Лунный календарь"
            ])
            builder.add_empty_line()
            builder.add_italic("Для точных расчетов нужны данные рождения")

        elif section == HelpSection.SUBSCRIPTION:
            builder.add_line("💎 **Подписка** открывает:")
            builder.add_empty_line()
            builder.add_bold("Базовый (299₽/мес):").add_line()
            builder.add_list([
                "Неограниченные карты дня",
                "10 раскладов в день",
                "Персональные гороскопы"
            ])
            builder.add_empty_line()
            builder.add_bold("Премиум (599₽/мес):").add_line()
            builder.add_list([
                "Все возможности Базового",
                "Неограниченные расклады",
                "Натальная карта",
                "Транзиты и прогрессии"
            ])

        elif section == HelpSection.PROFILE:
            builder.add_line("В разделе **Профиль** вы можете:")
            builder.add_list([
                "Просмотреть свои данные",
                "Изменить данные рождения",
                "Посмотреть статистику",
                "Управлять подпиской",
                "Настроить уведомления"
            ])

        elif section == HelpSection.SUPPORT:
            support_text = await get_info_message("support")
            return support_text

        return builder.build()

    async def _create_section_keyboard(
            self,
            section: HelpSection
    ) -> types.InlineKeyboardMarkup:
        """Создать клавиатуру для раздела."""
        keyboard = InlineKeyboard()

        # Дополнительные кнопки по разделам
        if section == HelpSection.TAROT:
            keyboard.add_button(
                text="🎴 Попробовать Таро",
                callback_data="main_menu:tarot"
            )
        elif section == HelpSection.ASTROLOGY:
            keyboard.add_button(
                text="🔮 Попробовать Астрологию",
                callback_data="main_menu:astrology"
            )
        elif section == HelpSection.SUBSCRIPTION:
            keyboard.add_button(
                text="💎 Оформить подписку",
                callback_data="main_menu:subscription"
            )

        # Кнопка назад
        keyboard.add_button(
            text="◀️ Назад к разделам",
            callback_data="help:menu"
        )

        return await keyboard.build()

    async def _show_faq_menu(self, message: types.Message) -> None:
        """Показать меню FAQ."""
        builder = MessageBuilder(MessageStyle.MARKDOWN_V2)

        builder.add_bold("❓ Часто задаваемые вопросы").add_line()
        builder.add_separator().add_line()
        builder.add_line("Выберите категорию:")

        keyboard = InlineKeyboard()

        for category in FAQCategory:
            keyboard.add_button(
                text=category.title,
                callback_data=f"faq:category:{category.code}"
            )

        keyboard.add_button(
            text="◀️ Назад",
            callback_data="help:menu"
        )

        keyboard.builder.adjust(1)

        await message.edit_text(
            builder.build(),
            reply_markup=await keyboard.build(),
            parse_mode="MarkdownV2"
        )

    async def _show_faq_category(
            self,
            message: types.Message,
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
            return

        builder = MessageBuilder(MessageStyle.MARKDOWN_V2)
        builder.add_bold(f"❓ {category.title}").add_line()
        builder.add_separator().add_line()

        keyboard = InlineKeyboard()

        # Список вопросов
        questions = self.FAQ_DATA[category]
        for i, faq in enumerate(questions):
            # Сокращаем вопрос для кнопки
            short_question = faq["question"]
            if len(short_question) > 30:
                short_question = short_question[:27] + "..."

            keyboard.add_button(
                text=f"❔ {short_question}",
                callback_data=f"faq:question:{category_code}:{i}"
            )

        keyboard.add_button(
            text="◀️ Назад к категориям",
            callback_data="faq:menu"
        )

        keyboard.builder.adjust(1)

        await message.edit_text(
            builder.build(),
            reply_markup=await keyboard.build(),
            parse_mode="MarkdownV2"
        )

    async def _show_faq_answer(
            self,
            message: types.Message,
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

        builder = MessageBuilder(MessageStyle.MARKDOWN_V2)
        builder.add_bold("❔ " + faq["question"]).add_line()
        builder.add_separator().add_line()
        builder.add_line(faq["answer"])

        keyboard = InlineKeyboard()

        # Навигация по вопросам
        if question_index > 0:
            keyboard.add_button(
                text="⬅️ Предыдущий",
                callback_data=f"faq:question:{category_code}:{question_index - 1}"
            )

        if question_index < len(questions) - 1:
            keyboard.add_button(
                text="➡️ Следующий",
                callback_data=f"faq:question:{category_code}:{question_index + 1}"
            )

        keyboard.add_button(
            text="📋 К вопросам",
            callback_data=f"faq:category:{category_code}"
        )

        keyboard.add_button(
            text="❓ Все категории",
            callback_data="faq:menu"
        )

        if len(questions) > 1:
            keyboard.builder.adjust(2, 1, 1)
        else:
            keyboard.builder.adjust(1, 1)

        await message.edit_text(
            builder.build(),
            reply_markup=await keyboard.build(),
            parse_mode="MarkdownV2"
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