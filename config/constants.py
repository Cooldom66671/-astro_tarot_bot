"""
Модуль констант для Астро-Таро Бота.

Этот модуль содержит все неизменяемые значения приложения:
- Команды бота и их описания
- Тексты кнопок для клавиатур
- Статусы и состояния
- Лимиты и ограничения
- Типы услуг и раскладов
- Ценовые константы
- Regex паттерны для валидации

Использование:
    from config.constants import BotCommands, ButtonTexts, Limits

    # В handlers
    @router.message(Command(BotCommands.START))
    async def start_handler(message: Message):
        ...
"""

import re
from enum import Enum
from typing import Final, Dict, List, Tuple, Pattern
from datetime import timedelta
from decimal import Decimal


# ===== КОМАНДЫ БОТА =====

class BotCommands:
    """Команды бота и их описания для BotFather."""

    # Основные команды
    START: Final[str] = "start"
    HELP: Final[str] = "help"
    MENU: Final[str] = "menu"
    CANCEL: Final[str] = "cancel"

    # Профиль и настройки
    PROFILE: Final[str] = "profile"
    SETTINGS: Final[str] = "settings"

    # Астрология
    ASTROLOGY: Final[str] = "astrology"
    HOROSCOPE: Final[str] = "horoscope"
    NATAL_CHART: Final[str] = "natal"
    COMPATIBILITY: Final[str] = "compatibility"
    FORECAST: Final[str] = "forecast"

    # Таро
    TAROT: Final[str] = "tarot"
    DAILY_CARD: Final[str] = "card"
    TAROT_SPREAD: Final[str] = "spread"

    # Подписка
    SUBSCRIBE: Final[str] = "subscribe"
    SUBSCRIPTION: Final[str] = "subscription"

    # Поддержка
    SUPPORT: Final[str] = "support"
    FEEDBACK: Final[str] = "feedback"

    # Админские команды
    ADMIN: Final[str] = "admin"
    STATS: Final[str] = "stats"
    BROADCAST: Final[str] = "broadcast"
    USERS: Final[str] = "users"

    @classmethod
    def get_commands_description(cls) -> Dict[str, str]:
        """Получить описания команд для установки в BotFather."""
        return {
            cls.START: "🚀 Запустить бота",
            cls.HELP: "❓ Помощь и инструкции",
            cls.MENU: "📱 Главное меню",
            cls.CANCEL: "❌ Отменить текущее действие",
            cls.PROFILE: "👤 Мой профиль",
            cls.SETTINGS: "⚙️ Настройки",
            cls.ASTROLOGY: "🔮 Астрология",
            cls.HOROSCOPE: "📅 Гороскоп",
            cls.NATAL_CHART: "🌟 Натальная карта",
            cls.COMPATIBILITY: "💕 Совместимость",
            cls.FORECAST: "🔮 Прогноз",
            cls.TAROT: "🎴 Таро",
            cls.DAILY_CARD: "🎴 Карта дня",
            cls.TAROT_SPREAD: "🃏 Расклад Таро",
            cls.SUBSCRIBE: "💎 Оформить подписку",
            cls.SUBSCRIPTION: "💳 Моя подписка",
            cls.SUPPORT: "🆘 Поддержка",
            cls.FEEDBACK: "💬 Обратная связь",
        }

    @classmethod
    def get_admin_commands_description(cls) -> Dict[str, str]:
        """Получить описания админских команд."""
        return {
            cls.ADMIN: "🔧 Админ-панель",
            cls.STATS: "📊 Статистика",
            cls.BROADCAST: "📢 Рассылка",
            cls.USERS: "👥 Управление пользователями",
        }


# ===== ТЕКСТЫ КНОПОК =====

class ButtonTexts:
    """Тексты для inline и reply кнопок."""

    # Главное меню
    ASTROLOGY: Final[str] = "🔮 Астрология"
    TAROT: Final[str] = "🎴 Таро"
    PROFILE: Final[str] = "👤 Профиль"
    SETTINGS: Final[str] = "⚙️ Настройки"
    HELP: Final[str] = "❓ Помощь"
    SUBSCRIPTION: Final[str] = "💎 Подписка"

    # Меню астрологии
    HOROSCOPE: Final[str] = "📅 Гороскоп"
    NATAL_CHART: Final[str] = "🌟 Натальная карта"
    COMPATIBILITY: Final[str] = "💕 Совместимость"
    TRANSITS: Final[str] = "🌍 Транзиты"
    FORECAST: Final[str] = "🔮 Прогноз"
    MOON_CALENDAR: Final[str] = "🌙 Лунный календарь"

    # Типы гороскопов
    DAILY_HOROSCOPE: Final[str] = "📅 На сегодня"
    WEEKLY_HOROSCOPE: Final[str] = "📆 На неделю"
    MONTHLY_HOROSCOPE: Final[str] = "🗓 На месяц"
    YEARLY_HOROSCOPE: Final[str] = "📊 На год"

    # Меню таро
    DAILY_CARD: Final[str] = "🎴 Карта дня"
    THREE_CARDS: Final[str] = "3️⃣ Три карты"
    CELTIC_CROSS: Final[str] = "✨ Кельтский крест"
    RELATIONSHIP: Final[str] = "💑 Отношения"
    CAREER: Final[str] = "💼 Карьера и финансы"
    YES_NO: Final[str] = "✅ Да/Нет"
    WEEK_AHEAD: Final[str] = "📅 Неделя вперед"
    MONTH_AHEAD: Final[str] = "🗓 Месяц вперед"
    YEAR_AHEAD: Final[str] = "📊 Год вперед"
    CHAKRAS: Final[str] = "🌈 Чакры"

    # Навигация
    BACK: Final[str] = "◀️ Назад"
    MAIN_MENU: Final[str] = "🏠 Главное меню"
    NEXT: Final[str] = "Далее ▶️"
    PREVIOUS: Final[str] = "◀️ Предыдущий"
    SKIP: Final[str] = "Пропустить ⏩"
    CLOSE: Final[str] = "❌ Закрыть"

    # Действия
    CONFIRM: Final[str] = "✅ Подтвердить"
    CANCEL: Final[str] = "❌ Отменить"
    RETRY: Final[str] = "🔄 Попробовать снова"
    SAVE: Final[str] = "💾 Сохранить"
    DELETE: Final[str] = "🗑 Удалить"
    EDIT: Final[str] = "✏️ Изменить"
    SHARE: Final[str] = "📤 Поделиться"
    REFRESH: Final[str] = "🔄 Обновить"

    # Подписка
    SUBSCRIBE: Final[str] = "💎 Оформить подписку"
    EXTEND_SUBSCRIPTION: Final[str] = "🔄 Продлить подписку"
    CANCEL_SUBSCRIPTION: Final[str] = "❌ Отменить подписку"
    VIEW_PLANS: Final[str] = "📋 Тарифные планы"
    UPGRADE_PLAN: Final[str] = "⬆️ Улучшить план"

    # Генерация отчетов
    GENERATE_PDF: Final[str] = "📄 Скачать PDF"
    SEND_EMAIL: Final[str] = "📧 Отправить на email"

    # Интерактивный расклад
    DRAW_CARD: Final[str] = "🎴 Вытянуть карту"
    SHOW_INTERPRETATION: Final[str] = "📖 Показать толкование"
    ADD_TO_FAVORITES: Final[str] = "⭐ В избранное"
    REMOVE_FROM_FAVORITES: Final[str] = "⭐ Из избранного"

    # Да/Нет
    YES: Final[str] = "✅ Да"
    NO: Final[str] = "❌ Нет"


# ===== CALLBACK DATA ПРЕФИКСЫ =====

class CallbackPrefixes:
    """Префиксы для callback_data в inline кнопках."""

    # Навигация
    MENU: Final[str] = "menu"
    BACK: Final[str] = "back"
    PAGE: Final[str] = "page"

    # Главное меню
    MAIN_MENU: Final[str] = "main_menu"

    # Астрология
    ASTRO: Final[str] = "astro"
    HOROSCOPE: Final[str] = "horoscope"
    NATAL: Final[str] = "natal"
    COMPAT: Final[str] = "compat"
    FORECAST: Final[str] = "forecast"
    TRANSIT: Final[str] = "transit"
    MOON: Final[str] = "moon"

    # Таро
    TAROT: Final[str] = "tarot"
    SPREAD: Final[str] = "spread"
    CARD: Final[str] = "card"
    HISTORY: Final[str] = "history"

    # Подписка
    SUB: Final[str] = "sub"
    PLAN: Final[str] = "plan"
    PAY: Final[str] = "pay"
    PAYMENT: Final[str] = "payment"

    # Профиль
    PROFILE: Final[str] = "profile"
    BIRTH: Final[str] = "birth"

    # Настройки
    SETTINGS: Final[str] = "set"
    TONE: Final[str] = "tone"
    NOTIF: Final[str] = "notif"
    LANG: Final[str] = "lang"

    # Действия
    CONFIRM: Final[str] = "confirm"
    CANCEL: Final[str] = "cancel"
    DELETE: Final[str] = "delete"
    EDIT: Final[str] = "edit"
    REFRESH: Final[str] = "refresh"

    # Знаки зодиака
    ZODIAC: Final[str] = "zodiac"


# ===== СТАТУСЫ И СОСТОЯНИЯ =====

class SubscriptionStatus(str, Enum):
    """Статусы подписки пользователя."""
    FREE = "free"
    ACTIVE = "active"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    SUSPENDED = "suspended"
    TRIAL = "trial"


class SubscriptionPlan(str, Enum):
    """Тарифные планы подписки."""
    FREE = "free"
    BASIC = "basic"
    PREMIUM = "premium"
    VIP = "vip"

    @property
    def display_name(self) -> str:
        """Отображаемое название плана."""
        names = {
            self.FREE: "Бесплатный",
            self.BASIC: "Базовый",
            self.PREMIUM: "Премиум",
            self.VIP: "VIP"
        }
        return names[self]


class ToneOfVoice(str, Enum):
    """Тональность общения бота."""
    FRIEND = "friend"  # Дружеский
    MENTOR = "mentor"  # Наставник
    EXPERT = "expert"  # Эксперт
    MYSTIC = "mystic"  # Мистический

    @property
    def display_name(self) -> str:
        """Отображаемое название тональности."""
        names = {
            self.FRIEND: "🤗 Дружеский",
            self.MENTOR: "🧑‍🏫 Наставник",
            self.EXPERT: "🎓 Эксперт",
            self.MYSTIC: "🔮 Мистический"
        }
        return names[self]


class PaymentStatus(str, Enum):
    """Статусы платежа."""
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


# ===== ТИПЫ РАСКЛАДОВ ТАРО =====

class TarotSpreadType(str, Enum):
    """Типы раскладов Таро."""
    DAILY_CARD = "daily_card"  # Карта дня
    THREE_CARDS = "three_cards"  # Три карты
    CELTIC_CROSS = "celtic_cross"  # Кельтский крест
    RELATIONSHIP = "relationship"  # На отношения
    CAREER = "career"  # Карьера
    YES_NO = "yes_no"  # Да/Нет
    WEEK_AHEAD = "week_ahead"  # Неделя вперед
    MONTH_AHEAD = "month_ahead"  # Месяц вперед
    YEAR_AHEAD = "year_ahead"  # Год вперед
    CHAKRAS = "chakras"  # Чакры

    @property
    def card_count(self) -> int:
        """Количество карт в раскладе."""
        counts = {
            self.DAILY_CARD: 1,
            self.THREE_CARDS: 3,
            self.CELTIC_CROSS: 10,
            self.RELATIONSHIP: 7,
            self.CAREER: 5,
            self.YES_NO: 1,
            self.WEEK_AHEAD: 7,
            self.MONTH_AHEAD: 4,
            self.YEAR_AHEAD: 12,
            self.CHAKRAS: 7
        }
        return counts[self]

    @property
    def required_subscription(self) -> str:
        """Минимальная подписка для расклада."""
        requirements = {
            self.DAILY_CARD: SubscriptionPlan.FREE,
            self.THREE_CARDS: SubscriptionPlan.FREE,
            self.CELTIC_CROSS: SubscriptionPlan.BASIC,
            self.RELATIONSHIP: SubscriptionPlan.PREMIUM,
            self.CAREER: SubscriptionPlan.BASIC,
            self.YES_NO: SubscriptionPlan.FREE,
            self.WEEK_AHEAD: SubscriptionPlan.BASIC,
            self.MONTH_AHEAD: SubscriptionPlan.PREMIUM,
            self.YEAR_AHEAD: SubscriptionPlan.PREMIUM,
            self.CHAKRAS: SubscriptionPlan.VIP
        }
        return requirements[self]


# ===== ПЛАНЕТЫ И ЗНАКИ ЗОДИАКА =====

class Planet(str, Enum):
    """Планеты в астрологии."""
    SUN = "sun"  # Солнце
    MOON = "moon"  # Луна
    MERCURY = "mercury"  # Меркурий
    VENUS = "venus"  # Венера
    MARS = "mars"  # Марс
    JUPITER = "jupiter"  # Юпитер
    SATURN = "saturn"  # Сатурн
    URANUS = "uranus"  # Уран
    NEPTUNE = "neptune"  # Нептун
    PLUTO = "pluto"  # Плутон
    NORTH_NODE = "north_node"  # Северный узел
    LILITH = "lilith"  # Лилит
    CHIRON = "chiron"  # Хирон

    @property
    def symbol(self) -> str:
        """Астрологический символ планеты."""
        symbols = {
            self.SUN: "☉", self.MOON: "☽", self.MERCURY: "☿",
            self.VENUS: "♀", self.MARS: "♂", self.JUPITER: "♃",
            self.SATURN: "♄", self.URANUS: "♅", self.NEPTUNE: "♆",
            self.PLUTO: "♇", self.NORTH_NODE: "☊",
            self.LILITH: "⚸", self.CHIRON: "⚷"
        }
        return symbols.get(self, "")


class ZodiacSign(str, Enum):
    """Знаки зодиака."""
    ARIES = "aries"  # Овен
    TAURUS = "taurus"  # Телец
    GEMINI = "gemini"  # Близнецы
    CANCER = "cancer"  # Рак
    LEO = "leo"  # Лев
    VIRGO = "virgo"  # Дева
    LIBRA = "libra"  # Весы
    SCORPIO = "scorpio"  # Скорпион
    SAGITTARIUS = "sagittarius"  # Стрелец
    CAPRICORN = "capricorn"  # Козерог
    AQUARIUS = "aquarius"  # Водолей
    PISCES = "pisces"  # Рыбы

    @property
    def symbol(self) -> str:
        """Символ знака зодиака."""
        symbols = {
            self.ARIES: "♈", self.TAURUS: "♉", self.GEMINI: "♊",
            self.CANCER: "♋", self.LEO: "♌", self.VIRGO: "♍",
            self.LIBRA: "♎", self.SCORPIO: "♏", self.SAGITTARIUS: "♐",
            self.CAPRICORN: "♑", self.AQUARIUS: "♒", self.PISCES: "♓"
        }
        return symbols[self]

    @property
    def ru_name(self) -> str:
        """Русское название знака."""
        names = {
            self.ARIES: "Овен", self.TAURUS: "Телец", self.GEMINI: "Близнецы",
            self.CANCER: "Рак", self.LEO: "Лев", self.VIRGO: "Дева",
            self.LIBRA: "Весы", self.SCORPIO: "Скорпион", self.SAGITTARIUS: "Стрелец",
            self.CAPRICORN: "Козерог", self.AQUARIUS: "Водолей", self.PISCES: "Рыбы"
        }
        return names[self]


# ===== ЛИМИТЫ И ОГРАНИЧЕНИЯ =====

class Limits:
    """Лимиты и ограничения приложения."""

    # Сообщения
    MAX_MESSAGE_LENGTH: Final[int] = 4096
    MAX_CAPTION_LENGTH: Final[int] = 1024
    MAX_CALLBACK_DATA_LENGTH: Final[int] = 64

    # Пользовательские данные
    MAX_NAME_LENGTH: Final[int] = 100
    MIN_NAME_LENGTH: Final[int] = 2
    MAX_CITY_LENGTH: Final[int] = 100
    MAX_PARTNERS_FREE: Final[int] = 1
    MAX_PARTNERS_PREMIUM: Final[int] = 10

    # Расклады Таро
    DAILY_CARD_COOLDOWN: Final[timedelta] = timedelta(hours=24)
    MAX_SPREADS_PER_DAY_FREE: Final[int] = 1
    MAX_SPREADS_PER_DAY_BASIC: Final[int] = 5
    MAX_SPREADS_PER_DAY_PREMIUM: Final[int] = 20
    MAX_SPREADS_PER_DAY_VIP: Final[int] = -1  # Безлимит

    # Гороскопы
    MAX_HOROSCOPE_PER_DAY_FREE: Final[int] = 1
    MAX_HOROSCOPE_PER_DAY_BASIC: Final[int] = 3
    MAX_HOROSCOPE_PER_DAY_PREMIUM: Final[int] = -1  # Безлимит

    # Прогнозы
    MAX_FORECAST_DAYS_FREE: Final[int] = 1
    MAX_FORECAST_DAYS_BASIC: Final[int] = 7
    MAX_FORECAST_DAYS_PREMIUM: Final[int] = 30
    MAX_FORECAST_DAYS_VIP: Final[int] = 365

    # API запросы
    RATE_LIMIT_PER_MINUTE: Final[int] = 20
    RATE_LIMIT_PER_HOUR: Final[int] = 300
    RATE_LIMIT_PER_DAY: Final[int] = 1000

    # Генерация контента
    MAX_LLM_RETRIES: Final[int] = 3
    LLM_TIMEOUT_SECONDS: Final[int] = 30
    MAX_PDF_GENERATION_TIME: Final[int] = 60

    # Файлы
    MAX_PDF_SIZE_MB: Final[int] = 10
    MAX_IMAGE_SIZE_MB: Final[int] = 5

    # Кэширование
    CACHE_TTL_SECONDS: Final[int] = 3600  # 1 час
    CACHE_TTL_HOROSCOPE: Final[int] = 86400  # 24 часа
    CACHE_TTL_NATAL_CHART: Final[int] = 604800  # 7 дней
    FSM_STATE_TTL_SECONDS: Final[int] = 86400  # 24 часа

    # История
    MAX_HISTORY_ITEMS: Final[int] = 100
    HISTORY_ITEMS_PER_PAGE: Final[int] = 10


# ===== ЦЕНЫ И ПЛАТЕЖИ =====

class Prices:
    """Цены на подписки и услуги."""

    # Подписки (в рублях)
    BASIC_MONTHLY: Final[Decimal] = Decimal("299.00")
    PREMIUM_MONTHLY: Final[Decimal] = Decimal("599.00")
    VIP_MONTHLY: Final[Decimal] = Decimal("1299.00")

    # Скидки
    ANNUAL_DISCOUNT: Final[Decimal] = Decimal("0.20")  # 20% скидка
    PROMO_DISCOUNT: Final[Decimal] = Decimal("0.10")  # 10% по промокоду
    FIRST_TIME_DISCOUNT: Final[Decimal] = Decimal("0.30")  # 30% для новых

    # Минимальная сумма платежа (ограничение YooKassa)
    MIN_PAYMENT_AMOUNT: Final[Decimal] = Decimal("1.00")

    @classmethod
    def get_annual_price(cls, monthly_price: Decimal) -> Decimal:
        """Рассчитать годовую цену со скидкой."""
        yearly = monthly_price * 12
        discount = yearly * cls.ANNUAL_DISCOUNT
        return yearly - discount

    @classmethod
    def get_price_with_promo(cls, price: Decimal, promo_discount: Decimal) -> Decimal:
        """Рассчитать цену с промокодом."""
        discount = price * promo_discount
        return price - discount


# ===== REGEX ПАТТЕРНЫ =====

class Patterns:
    """Regex паттерны для валидации."""

    # Компилированные паттерны для производительности
    # Имя (кириллица, латиница, пробелы, дефисы)
    NAME: Final[Pattern[str]] = re.compile(r"^[а-яА-ЯёЁa-zA-Z\s\-]{2,100}$")

    # Время в формате HH:MM
    TIME: Final[Pattern[str]] = re.compile(r"^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$")

    # Дата в формате DD.MM.YYYY
    DATE: Final[Pattern[str]] = re.compile(
        r"^(0[1-9]|[12][0-9]|3[01])\.(0[1-9]|1[012])\.(19|20)\d\d$"
    )

    # Email
    EMAIL: Final[Pattern[str]] = re.compile(
        r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    )

    # Промокод
    PROMO_CODE: Final[Pattern[str]] = re.compile(r"^[A-Z0-9]{4,20}$")

    # Город (кириллица, латиница, пробелы, дефисы)
    CITY: Final[Pattern[str]] = re.compile(r"^[а-яА-ЯёЁa-zA-Z\s\-]{2,100}$")

    # Телефон (международный формат)
    PHONE: Final[Pattern[str]] = re.compile(r"^\+?[1-9]\d{1,14}$")


# ===== КАРТЫ ТАРО =====

class TarotCards:
    """Константы для карт Таро."""

    # Количество карт
    MAJOR_ARCANA_COUNT: Final[int] = 22
    MINOR_ARCANA_COUNT: Final[int] = 56
    TOTAL_CARDS: Final[int] = 78

    # Масти младших арканов
    SUITS: Final[List[str]] = ["Жезлы", "Кубки", "Мечи", "Пентакли"]

    # Придворные карты
    COURT_CARDS: Final[List[str]] = ["Паж", "Рыцарь", "Королева", "Король"]

    # Числовые карты
    NUMBER_CARDS: Final[List[str]] = ["Туз", "Двойка", "Тройка", "Четверка",
                                      "Пятерка", "Шестерка", "Семерка",
                                      "Восьмерка", "Девятка", "Десятка"]


# ===== ЭМОДЗИ =====

class Emoji:
    """Эмодзи для красивого оформления."""

    # Знаки зодиака
    ZODIAC_SIGNS: Final[Dict[str, str]] = {
        "aries": "♈", "taurus": "♉", "gemini": "♊", "cancer": "♋",
        "leo": "♌", "virgo": "♍", "libra": "♎", "scorpio": "♏",
        "sagittarius": "♐", "capricorn": "♑", "aquarius": "♒", "pisces": "♓"
    }

    # Планеты
    PLANETS: Final[Dict[str, str]] = {
        "sun": "☉", "moon": "☽", "mercury": "☿", "venus": "♀",
        "mars": "♂", "jupiter": "♃", "saturn": "♄", "uranus": "♅",
        "neptune": "♆", "pluto": "♇"
    }

    # Статусы
    SUCCESS: Final[str] = "✅"
    ERROR: Final[str] = "❌"
    WARNING: Final[str] = "⚠️"
    INFO: Final[str] = "ℹ️"
    LOADING: Final[str] = "⏳"
    DONE: Final[str] = "✨"
    CHECK: Final[str] = "✔️"

    # Разделы
    STAR: Final[str] = "⭐"
    SPARKLES: Final[str] = "✨"
    CRYSTAL_BALL: Final[str] = "🔮"
    CARDS: Final[str] = "🎴"
    HEART: Final[str] = "❤️"
    MONEY: Final[str] = "💰"
    CALENDAR: Final[str] = "📅"
    MOON: Final[str] = "🌙"
    SUN: Final[str] = "☀️"
    EARTH: Final[str] = "🌍"

    # Действия
    BACK: Final[str] = "◀️"
    FORWARD: Final[str] = "▶️"
    UP: Final[str] = "⬆️"
    DOWN: Final[str] = "⬇️"
    REFRESH: Final[str] = "🔄"

    # Подписка
    CROWN: Final[str] = "👑"
    DIAMOND: Final[str] = "💎"
    STAR_STRUCK: Final[str] = "🤩"


# ===== СООБЩЕНИЯ ОБ ОШИБКАХ =====

class ErrorMessages:
    """Стандартные сообщения об ошибках."""

    # Общие
    UNKNOWN_ERROR: Final[str] = "Произошла неизвестная ошибка. Попробуйте позже."
    NOT_IMPLEMENTED: Final[str] = "Эта функция пока в разработке."
    ACCESS_DENIED: Final[str] = "У вас нет доступа к этой функции."
    MAINTENANCE: Final[str] = "Бот на техническом обслуживании. Попробуйте позже."

    # Валидация
    INVALID_NAME: Final[str] = "Имя должно содержать только буквы, пробелы и дефисы (2-100 символов)."
    INVALID_DATE: Final[str] = "Неверный формат даты. Используйте ДД.ММ.ГГГГ"
    INVALID_TIME: Final[str] = "Неверный формат времени. Используйте ЧЧ:ММ"
    INVALID_CITY: Final[str] = "Город не найден. Проверьте правильность написания."
    INVALID_EMAIL: Final[str] = "Неверный формат email адреса."
    INVALID_PHONE: Final[str] = "Неверный формат телефона."

    # Подписка
    SUBSCRIPTION_REQUIRED: Final[str] = "Эта функция доступна только по подписке."
    SUBSCRIPTION_EXPIRED: Final[str] = "Ваша подписка истекла. Пожалуйста, продлите её."
    SUBSCRIPTION_LIMIT: Final[str] = "Вы достигли лимита для вашего тарифного плана."

    # Лимиты
    DAILY_LIMIT_REACHED: Final[str] = "Вы достигли дневного лимита. Попробуйте завтра."
    RATE_LIMIT_EXCEEDED: Final[str] = "Слишком много запросов. Подождите немного."
    SPREAD_LIMIT_REACHED: Final[str] = "Вы достигли лимита раскладов на сегодня."

    # Платежи
    PAYMENT_FAILED: Final[str] = "Платеж не прошел. Попробуйте другой способ оплаты."
    PAYMENT_CANCELLED: Final[str] = "Платеж отменен."
    PAYMENT_TIMEOUT: Final[str] = "Время ожидания платежа истекло."

    # Данные
    NO_BIRTH_DATA: Final[str] = "Для этой функции необходимо указать данные рождения."
    NO_PARTNER_DATA: Final[str] = "Необходимо добавить данные партнера."
    DATA_NOT_FOUND: Final[str] = "Данные не найдены."

    # Генерация
    GENERATION_FAILED: Final[str] = "Не удалось сгенерировать контент. Попробуйте позже."
    PDF_GENERATION_FAILED: Final[str] = "Не удалось создать PDF. Попробуйте позже."


# ===== ПРОМО-ТЕКСТЫ =====

class PromoTexts:
    """Промо-тексты для привлечения к подписке."""

    SUBSCRIPTION_BENEFITS: Final[str] = """
🌟 <b>Преимущества подписки:</b>

✅ Полный анализ натальной карты
✅ Неограниченные расклады Таро
✅ Прогнозы на любой период
✅ Совместимость с партнерами
✅ PDF-отчеты для скачивания
✅ Приоритетная поддержка

💎 Оформите подписку и раскройте все тайны судьбы!
"""

    TRIAL_ENDED: Final[str] = """
Ваш пробный период закончился. 

Оформите подписку, чтобы продолжить пользоваться всеми функциями бота!
"""

    LIMITED_ACCESS: Final[str] = """
⚠️ Ограниченный доступ

Эта функция доступна только для подписчиков плана {plan} и выше.

Обновите подписку для полного доступа!
"""

    UPGRADE_SUGGESTION: Final[str] = """
💡 Хотите больше возможностей?

Обновите подписку и получите:
• Больше раскладов в день
• Расширенные прогнозы
• Эксклюзивные функции

Нажмите /subscription для просмотра планов.
"""


# Экспорт всех констант
__all__ = [
    "BotCommands",
    "ButtonTexts",
    "CallbackPrefixes",
    "SubscriptionStatus",
    "SubscriptionPlan",
    "ToneOfVoice",
    "PaymentStatus",
    "TarotSpreadType",
    "Planet",
    "ZodiacSign",
    "Limits",
    "Prices",
    "Patterns",
    "TarotCards",
    "Emoji",
    "ErrorMessages",
    "PromoTexts",
]