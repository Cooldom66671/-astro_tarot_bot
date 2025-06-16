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

from enum import Enum, IntEnum
from typing import Final, Dict, List, Tuple
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
    NATAL_CHART: Final[str] = "natal"
    COMPATIBILITY: Final[str] = "compatibility"
    FORECAST: Final[str] = "forecast"

    # Таро
    DAILY_CARD: Final[str] = "card"
    TAROT_SPREAD: Final[str] = "tarot"

    # Подписка
    SUBSCRIBE: Final[str] = "subscribe"
    SUBSCRIPTION: Final[str] = "subscription"

    # Админские команды
    ADMIN: Final[str] = "admin"
    STATS: Final[str] = "stats"
    BROADCAST: Final[str] = "broadcast"

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
            cls.NATAL_CHART: "🌟 Натальная карта",
            cls.COMPATIBILITY: "💕 Совместимость",
            cls.FORECAST: "🔮 Прогноз",
            cls.DAILY_CARD: "🎴 Карта дня",
            cls.TAROT_SPREAD: "🃏 Расклад Таро",
            cls.SUBSCRIBE: "💎 Оформить подписку",
            cls.SUBSCRIPTION: "💳 Моя подписка",
        }


# ===== ТЕКСТЫ КНОПОК =====

class ButtonTexts:
    """Тексты для inline и reply кнопок."""

    # Главное меню
    ASTROLOGY: Final[str] = "🌟 Астрология"
    TAROT: Final[str] = "🃏 Таро"
    PROFILE: Final[str] = "👤 Профиль"
    SETTINGS: Final[str] = "⚙️ Настройки"
    HELP: Final[str] = "❓ Помощь"

    # Меню астрологии
    NATAL_CHART: Final[str] = "📊 Натальная карта"
    COMPATIBILITY: Final[str] = "💕 Совместимость"
    FORECAST: Final[str] = "🔮 Прогноз"

    # Меню таро
    DAILY_CARD: Final[str] = "🎴 Карта дня"
    THREE_CARDS: Final[str] = "3️⃣ Три карты"
    CELTIC_CROSS: Final[str] = "✨ Кельтский крест"
    RELATIONSHIP: Final[str] = "💑 Расклад на отношения"
    CAREER: Final[str] = "💼 Карьера и финансы"
    YES_NO: Final[str] = "✅ Да/Нет"

    # Навигация
    BACK: Final[str] = "◀️ Назад"
    MAIN_MENU: Final[str] = "🏠 Главное меню"
    NEXT: Final[str] = "Далее ▶️"
    SKIP: Final[str] = "Пропустить ⏩"

    # Действия
    CONFIRM: Final[str] = "✅ Подтвердить"
    CANCEL: Final[str] = "❌ Отменить"
    RETRY: Final[str] = "🔄 Попробовать снова"
    SAVE: Final[str] = "💾 Сохранить"
    DELETE: Final[str] = "🗑 Удалить"
    EDIT: Final[str] = "✏️ Изменить"

    # Подписка
    SUBSCRIBE: Final[str] = "💎 Оформить подписку"
    EXTEND_SUBSCRIPTION: Final[str] = "🔄 Продлить подписку"
    CANCEL_SUBSCRIPTION: Final[str] = "❌ Отменить подписку"
    VIEW_PLANS: Final[str] = "📋 Тарифные планы"

    # Генерация отчетов
    GENERATE_PDF: Final[str] = "📄 Скачать PDF"
    SEND_EMAIL: Final[str] = "📧 Отправить на email"

    # Интерактивный расклад
    DRAW_CARD: Final[str] = "🎴 Вытянуть карту"
    SHOW_INTERPRETATION: Final[str] = "📖 Показать толкование"


# ===== CALLBACK DATA ПРЕФИКСЫ =====

class CallbackPrefixes:
    """Префиксы для callback_data в inline кнопках."""

    # Навигация
    MENU: Final[str] = "menu"
    BACK: Final[str] = "back"

    # Астрология
    ASTRO: Final[str] = "astro"
    NATAL: Final[str] = "natal"
    COMPAT: Final[str] = "compat"
    FORECAST: Final[str] = "forecast"

    # Таро
    TAROT: Final[str] = "tarot"
    SPREAD: Final[str] = "spread"
    CARD: Final[str] = "card"

    # Подписка
    SUB: Final[str] = "sub"
    PLAN: Final[str] = "plan"
    PAY: Final[str] = "pay"

    # Настройки
    SETTINGS: Final[str] = "set"
    TONE: Final[str] = "tone"

    # Действия
    CONFIRM: Final[str] = "confirm"
    CANCEL: Final[str] = "cancel"
    DELETE: Final[str] = "delete"


# ===== СТАТУСЫ И СОСТОЯНИЯ =====

class SubscriptionStatus(str, Enum):
    """Статусы подписки пользователя."""
    FREE = "free"
    ACTIVE = "active"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    SUSPENDED = "suspended"


class SubscriptionPlan(str, Enum):
    """Тарифные планы подписки."""
    FREE = "free"
    BASIC = "basic"
    PREMIUM = "premium"
    VIP = "vip"


class ToneOfVoice(str, Enum):
    """Тональность общения бота."""
    FRIEND = "friend"  # Дружеский
    MENTOR = "mentor"  # Наставник
    EXPERT = "expert"  # Эксперт
    MYSTIC = "mystic"  # Мистический


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
    MAX_SPREADS_PER_DAY_PREMIUM: Final[int] = 10

    # Прогнозы
    MAX_FORECAST_DAYS_FREE: Final[int] = 1
    MAX_FORECAST_DAYS_PREMIUM: Final[int] = 365

    # API запросы
    RATE_LIMIT_PER_MINUTE: Final[int] = 20
    RATE_LIMIT_PER_HOUR: Final[int] = 300

    # Генерация контента
    MAX_LLM_RETRIES: Final[int] = 3
    LLM_TIMEOUT_SECONDS: Final[int] = 30
    MAX_PDF_GENERATION_TIME: Final[int] = 60

    # Файлы
    MAX_PDF_SIZE_MB: Final[int] = 10
    MAX_IMAGE_SIZE_MB: Final[int] = 5

    # Кэширование
    CACHE_TTL_SECONDS: Final[int] = 3600  # 1 час
    FSM_STATE_TTL_SECONDS: Final[int] = 86400  # 24 часа


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

    # Минимальная сумма платежа (ограничение YooKassa)
    MIN_PAYMENT_AMOUNT: Final[Decimal] = Decimal("1.00")

    @classmethod
    def get_annual_price(cls, monthly_price: Decimal) -> Decimal:
        """Рассчитать годовую цену со скидкой."""
        yearly = monthly_price * 12
        discount = yearly * cls.ANNUAL_DISCOUNT
        return yearly - discount


# ===== REGEX ПАТТЕРНЫ =====

class Patterns:
    """Regex паттерны для валидации."""

    # Имя (кириллица, латиница, пробелы, дефисы)
    NAME: Final[str] = r"^[а-яА-ЯёЁa-zA-Z\s\-]{2,100}$"

    # Время в формате HH:MM
    TIME: Final[str] = r"^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$"

    # Дата в формате DD.MM.YYYY
    DATE: Final[str] = r"^(0[1-9]|[12][0-9]|3[01])\.(0[1-9]|1[012])\.(19|20)\d\d$"

    # Email
    EMAIL: Final[str] = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"

    # Промокод
    PROMO_CODE: Final[str] = r"^[A-Z0-9]{4,20}$"


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

    # Разделы
    STAR: Final[str] = "⭐"
    CARDS: Final[str] = "🎴"
    CRYSTAL_BALL: Final[str] = "🔮"
    HEART: Final[str] = "❤️"
    MONEY: Final[str] = "💰"
    CALENDAR: Final[str] = "📅"


# ===== СООБЩЕНИЯ ОБ ОШИБКАХ =====

class ErrorMessages:
    """Стандартные сообщения об ошибках."""

    # Общие
    UNKNOWN_ERROR: Final[str] = "Произошла неизвестная ошибка. Попробуйте позже."
    NOT_IMPLEMENTED: Final[str] = "Эта функция пока в разработке."
    ACCESS_DENIED: Final[str] = "У вас нет доступа к этой функции."

    # Валидация
    INVALID_NAME: Final[str] = "Имя должно содержать только буквы, пробелы и дефисы."
    INVALID_DATE: Final[str] = "Неверный формат даты. Используйте ДД.ММ.ГГГГ"
    INVALID_TIME: Final[str] = "Неверный формат времени. Используйте ЧЧ:ММ"
    INVALID_CITY: Final[str] = "Город не найден. Проверьте правильность написания."

    # Подписка
    SUBSCRIPTION_REQUIRED: Final[str] = "Эта функция доступна только по подписке."
    SUBSCRIPTION_EXPIRED: Final[str] = "Ваша подписка истекла."

    # Лимиты
    DAILY_LIMIT_REACHED: Final[str] = "Вы достигли дневного лимита."
    RATE_LIMIT_EXCEEDED: Final[str] = "Слишком много запросов. Подождите немного."

    # Платежи
    PAYMENT_FAILED: Final[str] = "Платеж не прошел. Попробуйте другой способ оплаты."
    PAYMENT_CANCELLED: Final[str] = "Платеж отменен."


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