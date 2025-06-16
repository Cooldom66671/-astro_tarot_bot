"""
Модуль приветственных сообщений.

Этот модуль содержит:
- Сообщения для новых пользователей
- Onboarding последовательность
- Персонализированные приветствия
- Обучающие сообщения
- Информацию о возможностях бота

Автор: AI Assistant
Дата создания: 2024-12-30
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum
import random

from .base import (
    BaseMessage, TemplateMessage, MessageBuilder,
    MessageStyle, MessageEmoji, MessageFormatter
)

# Настройка логирования
logger = logging.getLogger(__name__)


class WelcomeMessageType(Enum):
    """Типы приветственных сообщений."""
    FIRST_START = "first_start"
    RETURNING_USER = "returning_user"
    AFTER_BLOCK = "after_block"
    REFERRAL = "referral"
    WITH_PROMO = "with_promo"
    QUICK_START = "quick_start"


class OnboardingStep(Enum):
    """Шаги онбординга."""
    WELCOME = "welcome"
    INTRODUCTION = "introduction"
    BIRTH_DATA = "birth_data"
    FEATURES = "features"
    FIRST_READING = "first_reading"
    SUBSCRIPTION = "subscription"
    COMPLETE = "complete"


class WelcomeMessage(BaseMessage):
    """Класс для создания приветственных сообщений."""

    def __init__(
            self,
            message_type: WelcomeMessageType,
            user_data: Optional[Dict[str, Any]] = None,
            style: MessageStyle = MessageStyle.MARKDOWN_V2
    ):
        """
        Инициализация приветственного сообщения.

        Args:
            message_type: Тип сообщения
            user_data: Данные пользователя
            style: Стиль форматирования
        """
        super().__init__(style)
        self.message_type = message_type
        self.user_data = user_data or {}

        logger.debug(f"Создание приветственного сообщения типа {message_type.value}")

    async def format(self, **kwargs) -> str:
        """Форматировать приветственное сообщение."""
        builder = MessageBuilder(self.style)

        # Выбираем метод форматирования по типу
        if self.message_type == WelcomeMessageType.FIRST_START:
            return self._format_first_start(builder)
        elif self.message_type == WelcomeMessageType.RETURNING_USER:
            return self._format_returning_user(builder)
        elif self.message_type == WelcomeMessageType.AFTER_BLOCK:
            return self._format_after_block(builder)
        elif self.message_type == WelcomeMessageType.REFERRAL:
            return self._format_referral(builder)
        elif self.message_type == WelcomeMessageType.WITH_PROMO:
            return self._format_with_promo(builder)
        elif self.message_type == WelcomeMessageType.QUICK_START:
            return self._format_quick_start(builder)

        return builder.build()

    def _format_first_start(self, builder: MessageBuilder) -> str:
        """Форматировать сообщение первого запуска."""
        name = self.user_data.get("first_name", "друг")

        # Приветствие
        greetings = [
            f"Добро пожаловать в мир тайн и откровений, {name}! ✨",
            f"Приветствую тебя, {name}! 🌟 Рад видеть тебя здесь!",
            f"Здравствуй, {name}! 🔮 Вселенная привела тебя сюда не случайно..."
        ]

        builder.add_line(random.choice(greetings))
        builder.add_empty_line()

        # Представление бота
        builder.add_line("Я — твой персональный помощник в мире Таро и Астрологии.")
        builder.add_line("Помогу тебе:")
        builder.add_list([
            "Получить ответы на волнующие вопросы 🎴",
            "Узнать, что готовят звёзды ⭐",
            "Раскрыть тайны натальной карты 🗺",
            "Найти гармонию и понимание себя 🧘"
        ])

        builder.add_empty_line()

        # Первые шаги
        builder.add_bold("Что ты можешь сделать прямо сейчас:").add_line()
        builder.add_text("• Получить ").add_bold("Карту дня").add_text(" — совет на сегодня").add_line()
        builder.add_text("• Сделать ").add_bold("Расклад Таро").add_text(" на любой вопрос").add_line()
        builder.add_text("• Прочитать ").add_bold("Персональный гороскоп").add_line()

        builder.add_empty_line()
        builder.add_italic("Выбери, с чего начнём твоё путешествие! 👇")

        return builder.build()

    def _format_returning_user(self, builder: MessageBuilder) -> str:
        """Форматировать сообщение для возвращающегося пользователя."""
        name = self.user_data.get("first_name", "друг")
        days_away = self.user_data.get("days_away", 0)

        # Персонализированное приветствие
        if days_away == 0:
            builder.add_line(f"С возвращением, {name}! 🌟")
        elif days_away == 1:
            builder.add_line(f"Рад снова видеть тебя, {name}! ✨")
        elif days_away < 7:
            builder.add_line(f"Давно не виделись, {name}! 🌙")
            builder.add_line(f"Прошло {days_away} {MessageFormatter.pluralize(days_away, 'день', 'дня', 'дней')}...")
        else:
            builder.add_line(f"Какая радость видеть тебя снова, {name}! 🎉")
            builder.add_line("Столько всего произошло за это время!")

        builder.add_empty_line()

        # Что нового
        if days_away > 7:
            builder.add_bold("Пока тебя не было:").add_line()
            builder.add_list([
                "Добавлены новые расклады Таро 🎴",
                "Улучшены астрологические прогнозы ⭐",
                "Появился лунный календарь 🌙"
            ])
            builder.add_empty_line()

        # Напоминание о возможностях
        last_action = self.user_data.get("last_action")
        if last_action == "tarot_reading":
            builder.add_line("Хочешь продолжить изучение Таро? У меня есть новые расклады для тебя!")
        elif last_action == "horoscope":
            builder.add_line("Твой персональный гороскоп уже готов! Узнай, что ждёт тебя сегодня.")
        else:
            builder.add_line("Готов продолжить наше путешествие? Выбирай, что тебя интересует!")

        return builder.build()

    def _format_after_block(self, builder: MessageBuilder) -> str:
        """Форматировать сообщение после блокировки."""
        name = self.user_data.get("first_name", "друг")

        builder.add_line(f"Привет, {name}! Рад, что ты вернулся! 🤗")
        builder.add_empty_line()

        builder.add_line("Я всегда здесь, чтобы помочь тебе найти ответы.")
        builder.add_line("Все твои данные сохранены, можем продолжить с того места, где остановились.")

        builder.add_empty_line()
        builder.add_italic("Что тебя интересует сегодня?")

        return builder.build()

    def _format_referral(self, builder: MessageBuilder) -> str:
        """Форматировать сообщение для реферального пользователя."""
        name = self.user_data.get("first_name", "друг")
        referrer_name = self.user_data.get("referrer_name", "твой друг")

        builder.add_line(f"Привет, {name}! 🌟")
        builder.add_line(f"Тебя пригласил(а) {referrer_name} — отличный выбор!")

        builder.add_empty_line()

        builder.add_bold("🎁 Специально для тебя:").add_line()
        builder.add_list([
            "3 дня премиум-подписки в подарок",
            "Эксклюзивный расклад «Путь к себе»",
            "Персональный астрологический прогноз"
        ])

        builder.add_empty_line()
        builder.add_line("Давай начнём твоё путешествие в мир самопознания!")

        return builder.build()

    def _format_with_promo(self, builder: MessageBuilder) -> str:
        """Форматировать сообщение с промокодом."""
        name = self.user_data.get("first_name", "друг")
        promo_code = self.user_data.get("promo_code", "WELCOME")
        discount = self.user_data.get("discount", 10)

        builder.add_line(f"Добро пожаловать, {name}! ✨")
        builder.add_empty_line()

        builder.add_line(f"🎁 Твой промокод {self._format_code(promo_code)} активирован!")
        builder.add_line(f"Ты получаешь скидку {discount}% на первую подписку!")

        builder.add_empty_line()

        builder.add_line("Это отличное начало для знакомства со всеми возможностями:")
        builder.add_list([
            "Неограниченные расклады Таро",
            "Персональные астрологические прогнозы",
            "Анализ натальной карты",
            "Эксклюзивные материалы"
        ])

        builder.add_empty_line()
        builder.add_italic("Начни прямо сейчас и получи максимум! 🚀")

        return builder.build()

    def _format_quick_start(self, builder: MessageBuilder) -> str:
        """Форматировать сообщение быстрого старта."""
        builder.add_bold("Быстрый старт 🚀").add_line()
        builder.add_empty_line()

        builder.add_line("Хочешь сразу к делу? Отлично!")
        builder.add_line("Вот что я могу сделать для тебя прямо сейчас:")

        builder.add_empty_line()

        builder.add_text("🎴 ").add_bold("/card").add_text(" — карта дня").add_line()
        builder.add_text("🔮 ").add_bold("/spread").add_text(" — расклад Таро").add_line()
        builder.add_text("⭐ ").add_bold("/horoscope").add_text(" — гороскоп").add_line()
        builder.add_text("🌙 ").add_bold("/moon").add_text(" — фаза луны").add_line()

        builder.add_empty_line()
        builder.add_italic("Просто выбери команду или используй меню внизу 👇")

        return builder.build()


class OnboardingMessage(BaseMessage):
    """Класс для создания сообщений онбординга."""

    # Шаблоны сообщений для каждого шага
    STEP_TEMPLATES = {
        OnboardingStep.WELCOME: {
            "title": "Добро пожаловать в путешествие! 🌟",
            "content": [
                "Я проведу тебя через несколько простых шагов,",
                "чтобы настроить всё идеально под твои потребности."
            ],
            "footer": "Это займёт всего 2-3 минуты ⏱"
        },
        OnboardingStep.INTRODUCTION: {
            "title": "Давай познакомимся поближе 🤝",
            "content": [
                "Меня зовут Астро-Таро Ассистент.",
                "Я помогу тебе:",
                "• Находить ответы через карты Таро",
                "• Понимать влияние планет на твою жизнь",
                "• Раскрывать потенциал через натальную карту",
                "• Планировать важные события"
            ],
            "footer": "А как мне к тебе обращаться?"
        },
        OnboardingStep.BIRTH_DATA: {
            "title": "Данные рождения 🎂",
            "content": [
                "Для персональных прогнозов и натальной карты",
                "мне понадобится информация о твоём рождении.",
                "",
                "Это поможет сделать все расчёты максимально точными",
                "и персонализированными именно для тебя."
            ],
            "footer": "Не волнуйся, все данные надёжно защищены 🔒"
        },
        OnboardingStep.FEATURES: {
            "title": "Что я умею 🎯",
            "content": [
                "🎴 **Таро** — от простой карты дня до сложных раскладов",
                "🔮 **Астрология** — гороскопы, натальная карта, транзиты",
                "💑 **Синастрия** — анализ совместимости",
                "🌙 **Лунный календарь** — благоприятные дни",
                "📚 **Обучение** — статьи и уроки"
            ],
            "footer": "И это только начало! 🚀"
        },
        OnboardingStep.FIRST_READING: {
            "title": "Твой первый расклад 🎴",
            "content": [
                "Предлагаю начать с простого расклада «Карта дня».",
                "Это поможет тебе:",
                "• Настроиться на день",
                "• Получить совет от Вселенной",
                "• Познакомиться с картами Таро"
            ],
            "footer": "Готов узнать, что тебя ждёт сегодня?"
        },
        OnboardingStep.SUBSCRIPTION: {
            "title": "Расширь свои возможности 💎",
            "content": [
                "С бесплатной версией ты получаешь:",
                "• 1 карту дня",
                "• 3 простых расклада в день",
                "• Базовые гороскопы",
                "",
                "Премиум-подписка открывает:",
                "• Неограниченные расклады",
                "• Персональные прогнозы",
                "• Натальную карту",
                "• Эксклюзивные функции"
            ],
            "footer": "Попробуй 3 дня бесплатно! 🎁"
        },
        OnboardingStep.COMPLETE: {
            "title": "Всё готово! 🎉",
            "content": [
                "Поздравляю! Теперь ты полностью готов",
                "к путешествию в мир самопознания.",
                "",
                "Помни: я всегда здесь, чтобы помочь тебе",
                "найти ответы и раскрыть свой потенциал."
            ],
            "footer": "Удачи на твоём пути! ✨"
        }
    }

    def __init__(
            self,
            step: OnboardingStep,
            user_data: Optional[Dict[str, Any]] = None,
            style: MessageStyle = MessageStyle.MARKDOWN_V2
    ):
        """
        Инициализация сообщения онбординга.

        Args:
            step: Шаг онбординга
            user_data: Данные пользователя
            style: Стиль форматирования
        """
        super().__init__(style)
        self.step = step
        self.user_data = user_data or {}

        logger.debug(f"Создание сообщения онбординга для шага {step.value}")

    async def format(self, **kwargs) -> str:
        """Форматировать сообщение онбординга."""
        template = self.STEP_TEMPLATES.get(self.step, {})
        builder = MessageBuilder(self.style)

        # Прогресс
        progress = self._get_progress()
        if progress:
            builder.add_line(progress).add_empty_line()

        # Заголовок
        if "title" in template:
            builder.add_bold(template["title"]).add_line()
            builder.add_empty_line()

        # Содержимое
        if "content" in template:
            for line in template["content"]:
                if line.startswith("•"):
                    # Элемент списка
                    builder.add_text("  ").add_line(line)
                elif "**" in line:
                    # Строка с выделением
                    parts = line.split("**")
                    for i, part in enumerate(parts):
                        if i % 2 == 0:
                            builder.add_text(part)
                        else:
                            builder.add_bold(part)
                    builder.add_line()
                else:
                    builder.add_line(line)

        # Подвал
        if "footer" in template:
            builder.add_empty_line()
            builder.add_italic(template["footer"])

        return builder.build()

    def _get_progress(self) -> str:
        """Получить индикатор прогресса."""
        steps = list(OnboardingStep)
        current_index = steps.index(self.step)
        total_steps = len(steps) - 1  # Исключаем COMPLETE

        if self.step == OnboardingStep.COMPLETE:
            return ""

        # Прогресс бар
        filled = "▓" * (current_index + 1)
        empty = "░" * (total_steps - current_index - 1)

        return f"Шаг {current_index + 1}/{total_steps} {filled}{empty}"


class WelcomeInfoMessage(BaseMessage):
    """Класс для информационных сообщений о боте."""

    def __init__(
            self,
            info_type: str,
            style: MessageStyle = MessageStyle.MARKDOWN_V2
    ):
        """
        Инициализация информационного сообщения.

        Args:
            info_type: Тип информации (about, features, privacy, etc.)
            style: Стиль форматирования
        """
        super().__init__(style)
        self.info_type = info_type

    async def format(self, **kwargs) -> str:
        """Форматировать информационное сообщение."""
        builder = MessageBuilder(self.style)

        if self.info_type == "about":
            return self._format_about(builder)
        elif self.info_type == "features":
            return self._format_features(builder)
        elif self.info_type == "privacy":
            return self._format_privacy(builder)
        elif self.info_type == "commands":
            return self._format_commands(builder)
        elif self.info_type == "support":
            return self._format_support(builder)

        return builder.build()

    def _format_about(self, builder: MessageBuilder) -> str:
        """Форматировать информацию о боте."""
        builder.add_bold("🤖 О боте").add_line()
        builder.add_separator().add_line()

        builder.add_line("Астро-Таро Ассистент — это современный помощник")
        builder.add_line("для тех, кто ищет ответы и стремится к самопознанию.")

        builder.add_empty_line()

        builder.add_bold("Наша миссия:").add_line()
        builder.add_line("Сделать мудрость Таро и Астрологии доступной каждому,")
        builder.add_line("помогая людям лучше понимать себя и свой путь.")

        builder.add_empty_line()

        builder.add_bold("Что делает нас особенными:").add_line()
        builder.add_list([
            "Персонализированный подход",
            "Профессиональные интерпретации",
            "Удобный интерфейс",
            "Конфиденциальность данных",
            "Постоянное развитие"
        ])

        builder.add_empty_line()

        builder.add_italic("Версия: 2.0.0 | Обновлено: декабрь 2024")

        return builder.build()

    def _format_features(self, builder: MessageBuilder) -> str:
        """Форматировать список возможностей."""
        builder.add_bold("✨ Возможности бота").add_line()
        builder.add_separator().add_line()

        # Таро
        builder.add_bold("🎴 Таро:").add_line()
        builder.add_list([
            "Карта дня с персональной интерпретацией",
            "15+ видов раскладов",
            "Детальный анализ каждой карты",
            "История всех раскладов",
            "Обучающие материалы"
        ])

        builder.add_empty_line()

        # Астрология
        builder.add_bold("🔮 Астрология:").add_line()
        builder.add_list([
            "Персональный гороскоп",
            "Натальная карта",
            "Транзиты и прогрессии",
            "Синастрия (совместимость)",
            "Лунный календарь"
        ])

        builder.add_empty_line()

        # Дополнительно
        builder.add_bold("🌟 Дополнительно:").add_line()
        builder.add_list([
            "Уведомления о важных событиях",
            "Персональные рекомендации",
            "Сохранение избранного",
            "Экспорт результатов",
            "Поддержка 24/7"
        ])

        return builder.build()

    def _format_privacy(self, builder: MessageBuilder) -> str:
        """Форматировать информацию о конфиденциальности."""
        builder.add_bold("🔒 Конфиденциальность").add_line()
        builder.add_separator().add_line()

        builder.add_line("Мы серьёзно относимся к защите твоих данных.")

        builder.add_empty_line()

        builder.add_bold("Что мы храним:").add_line()
        builder.add_list([
            "Имя и ID Telegram (для идентификации)",
            "Данные рождения (для расчётов)",
            "История раскладов (по желанию)",
            "Настройки и предпочтения"
        ])

        builder.add_empty_line()

        builder.add_bold("Мы НЕ:").add_line()
        builder.add_list([
            "Не передаём данные третьим лицам",
            "Не используем для рекламы",
            "Не храним платёжные данные",
            "Не читаем личные сообщения"
        ])

        builder.add_empty_line()

        builder.add_line("Ты можешь в любой момент:")
        builder.add_list([
            "Удалить все свои данные",
            "Экспортировать информацию",
            "Изменить настройки приватности"
        ])

        builder.add_empty_line()
        builder.add_italic("Подробнее: /privacy_policy")

        return builder.build()

    def _format_commands(self, builder: MessageBuilder) -> str:
        """Форматировать список команд."""
        builder.add_bold("📋 Команды бота").add_line()
        builder.add_separator().add_line()

        commands = [
            ("/start", "Начать работу с ботом"),
            ("/menu", "Главное меню"),
            ("/card", "Карта дня"),
            ("/spread", "Сделать расклад"),
            ("/horoscope", "Гороскоп"),
            ("/natal", "Натальная карта"),
            ("/moon", "Фаза луны"),
            ("/history", "История раскладов"),
            ("/profile", "Мой профиль"),
            ("/subscription", "Подписка"),
            ("/settings", "Настройки"),
            ("/help", "Помощь"),
            ("/support", "Поддержка")
        ]

        for cmd, description in commands:
            builder.add_text(self._format_code(cmd))
            builder.add_text(" — ")
            builder.add_text(description)
            builder.add_line()

        builder.add_empty_line()
        builder.add_italic("Совет: используй меню внизу для быстрого доступа 👇")

        return builder.build()

    def _format_support(self, builder: MessageBuilder) -> str:
        """Форматировать информацию о поддержке."""
        builder.add_bold("🆘 Поддержка").add_line()
        builder.add_separator().add_line()

        builder.add_line("Нужна помощь? Мы всегда на связи!")

        builder.add_empty_line()

        builder.add_bold("Способы связи:").add_line()
        builder.add_text("💬 Чат поддержки: ")
        builder.add_link("@astrotaro_support", "https://t.me/astrotaro_support")
        builder.add_line()

        builder.add_text("📧 Email: ")
        builder.add_code("support@astrotaro.bot")
        builder.add_line()

        builder.add_empty_line()

        builder.add_bold("Часто задаваемые вопросы:").add_line()
        builder.add_list([
            "Как изменить данные рождения? → /settings",
            "Как отменить подписку? → /subscription",
            "Не работает оплата? → напишите в поддержку",
            "Как удалить аккаунт? → /settings → Удалить данные"
        ])

        builder.add_empty_line()

        builder.add_bold("Время ответа:").add_line()
        builder.add_text("Обычно отвечаем в течение 2-4 часов")
        builder.add_line()
        builder.add_text("VIP-подписчики — приоритетная поддержка")

        return builder.build()


# Функции для быстрого создания сообщений
async def get_welcome_message(
        message_type: WelcomeMessageType,
        user_data: Optional[Dict[str, Any]] = None
) -> str:
    """
    Получить приветственное сообщение.

    Args:
        message_type: Тип сообщения
        user_data: Данные пользователя

    Returns:
        Отформатированное сообщение
    """
    message = WelcomeMessage(message_type, user_data)
    return await message.format()


async def get_onboarding_message(
        step: OnboardingStep,
        user_data: Optional[Dict[str, Any]] = None
) -> str:
    """
    Получить сообщение онбординга.

    Args:
        step: Шаг онбординга
        user_data: Данные пользователя

    Returns:
        Отформатированное сообщение
    """
    message = OnboardingMessage(step, user_data)
    return await message.format()


async def get_info_message(info_type: str) -> str:
    """
    Получить информационное сообщение.

    Args:
        info_type: Тип информации

    Returns:
        Отформатированное сообщение
    """
    message = WelcomeInfoMessage(info_type)
    return await message.format()


# Персонализированные приветствия по времени суток
def get_time_based_greeting(name: Optional[str] = None) -> str:
    """
    Получить приветствие в зависимости от времени суток.

    Args:
        name: Имя пользователя

    Returns:
        Приветствие
    """
    hour = datetime.now().hour

    if 5 <= hour < 12:
        greetings = [
            "Доброе утро{name}! ☀️",
            "Прекрасное утро{name}! 🌅",
            "Чудесного утра{name}! ⛅"
        ]
    elif 12 <= hour < 17:
        greetings = [
            "Добрый день{name}! 🌞",
            "Хорошего дня{name}! ☀️",
            "Прекрасный день{name}! 🌤"
        ]
    elif 17 <= hour < 22:
        greetings = [
            "Добрый вечер{name}! 🌆",
            "Чудесного вечера{name}! 🌇",
            "Приятного вечера{name}! 🌃"
        ]
    else:
        greetings = [
            "Доброй ночи{name}! 🌙",
            "Волшебной ночи{name}! ✨",
            "Спокойной ночи{name}! 🌟"
        ]

    greeting = random.choice(greetings)
    name_part = f", {name}" if name else ""

    return greeting.format(name=name_part)


# Мотивационные цитаты для приветствий
WELCOME_QUOTES = [
    "«Звёзды склоняют, но не обязывают» — Клавдий Птолемей",
    "«В картах Таро отражается не судьба, а путь к ней»",
    "«Познай себя» — Дельфийский оракул",
    "«Как вверху, так и внизу» — Гермес Трисмегист",
    "«Будущее принадлежит тем, кто верит в красоту своей мечты» — Элеонора Рузвельт",
    "«Каждая карта — это дверь к пониманию себя»",
    "«Астрология — это язык, на котором говорит Вселенная»",
    "«Мудрость начинается с удивления» — Сократ"
]


def get_random_welcome_quote() -> str:
    """Получить случайную мотивационную цитату."""
    return random.choice(WELCOME_QUOTES)


logger.info("Модуль приветственных сообщений загружен")