"""
Пакет ядра (core) Астро-Таро Бота.

Этот модуль объединяет и экспортирует все основные компоненты
бизнес-логики приложения:
- Сущности (entities) - бизнес-объекты
- Исключения (exceptions) - кастомные ошибки
- Интерфейсы (interfaces) - контракты для инфраструктуры

Ядро приложения не зависит от внешних фреймворков и содержит
только чистую бизнес-логику.

Использование:
    # Импорт сущностей
    from core import User, Subscription, BirthChart

    # Импорт исключений
    from core import ValidationError, SubscriptionRequiredError

    # Импорт интерфейсов
    from core import IUserService, IRepository

    # Импорт всего
    from core import *
"""

# ===== ИМПОРТ ИЗ ПОДМОДУЛЕЙ =====

# Сущности (Entities)
from core.entities import (
    # Основные сущности
    User,
    Subscription,
    BirthChart,

    # Вспомогательные классы
    BirthData,
    UserSubscription,
    UserSettings,
    PlanFeatures,
    PLAN_FEATURES,
    PromoCode,
    PromoCodeType,
    Payment,
    PlanetPosition,
    Aspect,
    House,
    AspectType,
    HouseSystem,
    Element,
    Quality,
    SIGN_PROPERTIES,
    ASPECT_ORBS,
    ASPECT_ANGLES,

    # Функции-помощники
    create_user_from_telegram_data,
    get_plan_features,
    calculate_subscription_price,
)

# Исключения (Exceptions)
from core.exceptions import (
    # Базовые
    BaseAppException,
    ErrorCode,

    # Валидация
    ValidationError,
    MultipleValidationError,

    # Бизнес-логика
    BusinessLogicError,
    EntityNotFoundError,
    EntityAlreadyExistsError,
    InvalidStateTransitionError,

    # Доступ
    AuthenticationRequiredError,
    AccessDeniedError,
    SubscriptionRequiredError,
    SubscriptionExpiredError,

    # Лимиты
    RateLimitExceededError,
    DailyLimitReachedError,

    # Внешние сервисы
    ExternalServiceError,
    LLMAPIError,
    PaymentAPIError,
    GeocodingAPIError,

    # База данных
    DatabaseError,
    DatabaseConnectionError,
    TransactionError,

    # Функции
    handle_exception,
    is_client_error,
    is_server_error,
)

# Интерфейсы (Interfaces)
from core.interfaces import (
    # Репозитории
    IRepository,
    IUnitOfWork,
    IRepositoryFactory,
    IUserRepository,
    ISubscriptionRepository,
    IBirthChartRepository,
    ITarotReadingRepository,
    IPaymentRepository,

    # Сервисы
    IService,
    IServiceManager,
    ServiceResult,
    IUserService,
    ISubscriptionService,
    IAstrologyService,
    ITarotService,
    INotificationService,
    IContentService,

    # Вспомогательные классы
    QueryOptions,
    Pagination,
    Page,
    TelegramUserData,
    BirthDataInput,
    PaymentRequest,
)

# ===== ВЕРСИЯ И МЕТАДАННЫЕ =====

__version__ = "0.1.0"
__author__ = "Astro-Tarot Bot Team"
__description__ = "Core business logic for Astro-Tarot Bot"


# ===== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =====

def get_core_info() -> dict:
    """
    Получить информацию о пакете core.

    Returns:
        Dict с информацией о версии и компонентах
    """
    return {
        "version": __version__,
        "author": __author__,
        "description": __description__,
        "components": {
            "entities": ["User", "Subscription", "BirthChart"],
            "exceptions": len([name for name in dir() if name.endswith("Error")]),
            "interfaces": {
                "repositories": 5,
                "services": 6,
            }
        }
    }


def validate_business_rules() -> list:
    """
    Проверить бизнес-правила приложения.

    Returns:
        List с предупреждениями о нарушениях
    """
    warnings = []

    # Проверяем цены подписок
    from config import Prices
    if Prices.BASIC_MONTHLY >= Prices.PREMIUM_MONTHLY:
        warnings.append("Цена Basic должна быть меньше Premium")

    if Prices.PREMIUM_MONTHLY >= Prices.VIP_MONTHLY:
        warnings.append("Цена Premium должна быть меньше VIP")

    # Проверяем лимиты
    from config import Limits
    if Limits.MAX_PARTNERS_FREE >= Limits.MAX_PARTNERS_PREMIUM:
        warnings.append("Лимит партнеров для Free должен быть меньше Premium")

    return warnings


# ===== ФАБРИЧНЫЕ ФУНКЦИИ =====

def create_guest_user(telegram_id: int) -> User:
    """
    Создать гостевого пользователя.

    Args:
        telegram_id: ID в Telegram

    Returns:
        User с минимальными данными
    """
    from datetime import datetime

    return User(
        id=0,  # Временный ID
        telegram_id=telegram_id,
        created_at=datetime.now()
    )


def create_trial_subscription(user_id: int, days: int = 7) -> Subscription:
    """
    Создать пробную подписку.

    Args:
        user_id: ID пользователя
        days: Количество дней пробного периода

    Returns:
        Subscription с пробным периодом
    """
    from datetime import datetime, timedelta
    from config import SubscriptionPlan, SubscriptionStatus

    subscription = Subscription(
        id=0,  # Временный ID
        user_id=user_id,
        plan=SubscriptionPlan.PREMIUM,  # Пробный период с Premium функциями
        status=SubscriptionStatus.ACTIVE
    )

    subscription.activate(
        plan=SubscriptionPlan.PREMIUM,
        period_months=0  # Особый случай для триала
    )
    subscription.expires_at = datetime.now() + timedelta(days=days)

    return subscription


# ===== ТИПЫ ДЛЯ TYPE HINTS =====

from typing import Union, Type

# Union типы для удобства
AnyEntity = Union[User, Subscription, BirthChart]
AnyException = Type[BaseAppException]
AnyRepository = Union[
    IUserRepository,
    ISubscriptionRepository,
    IBirthChartRepository,
    ITarotReadingRepository,
    IPaymentRepository
]
AnyService = Union[
    IUserService,
    ISubscriptionService,
    IAstrologyService,
    ITarotService,
    INotificationService,
    IContentService
]

# ===== КОНСТАНТЫ =====

# Минимальные требования для работы
MIN_PYTHON_VERSION = (3, 11)
REQUIRED_FEATURES = [
    "natal_chart_calculation",
    "tarot_spreads",
    "subscription_management",
    "payment_processing"
]


# ===== ПРОВЕРКА ОКРУЖЕНИЯ =====

def check_environment() -> bool:
    """
    Проверить, что окружение подходит для работы core.

    Returns:
        bool: True если все в порядке
    """
    import sys

    # Проверка версии Python
    if sys.version_info < MIN_PYTHON_VERSION:
        raise RuntimeError(
            f"Python {MIN_PYTHON_VERSION[0]}.{MIN_PYTHON_VERSION[1]}+ требуется, "
            f"текущая версия: {sys.version_info.major}.{sys.version_info.minor}"
        )

    return True


# Проверяем окружение при импорте
try:
    check_environment()
except RuntimeError as e:
    import warnings

    warnings.warn(str(e), RuntimeWarning)

# ===== ЭКСПОРТ =====

__all__ = [
    # ===== Сущности =====
    "User",
    "Subscription",
    "BirthChart",
    "BirthData",
    "UserSubscription",
    "UserSettings",
    "PlanFeatures",
    "PLAN_FEATURES",
    "PromoCode",
    "PromoCodeType",
    "Payment",
    "PlanetPosition",
    "Aspect",
    "House",
    "AspectType",
    "HouseSystem",
    "Element",
    "Quality",
    "SIGN_PROPERTIES",
    "ASPECT_ORBS",
    "ASPECT_ANGLES",

    # ===== Исключения =====
    "BaseAppException",
    "ErrorCode",
    "ValidationError",
    "MultipleValidationError",
    "BusinessLogicError",
    "EntityNotFoundError",
    "EntityAlreadyExistsError",
    "InvalidStateTransitionError",
    "AuthenticationRequiredError",
    "AccessDeniedError",
    "SubscriptionRequiredError",
    "SubscriptionExpiredError",
    "RateLimitExceededError",
    "DailyLimitReachedError",
    "ExternalServiceError",
    "LLMAPIError",
    "PaymentAPIError",
    "GeocodingAPIError",
    "DatabaseError",
    "DatabaseConnectionError",
    "TransactionError",

    # ===== Интерфейсы =====
    "IRepository",
    "IUnitOfWork",
    "IRepositoryFactory",
    "IUserRepository",
    "ISubscriptionRepository",
    "IBirthChartRepository",
    "ITarotReadingRepository",
    "IPaymentRepository",
    "IService",
    "IServiceManager",
    "ServiceResult",
    "IUserService",
    "ISubscriptionService",
    "IAstrologyService",
    "ITarotService",
    "INotificationService",
    "IContentService",
    "QueryOptions",
    "Pagination",
    "Page",
    "TelegramUserData",
    "BirthDataInput",
    "PaymentRequest",

    # ===== Функции =====
    "create_user_from_telegram_data",
    "get_plan_features",
    "calculate_subscription_price",
    "handle_exception",
    "is_client_error",
    "is_server_error",
    "get_core_info",
    "validate_business_rules",
    "create_guest_user",
    "create_trial_subscription",
    "check_environment",

    # ===== Типы =====
    "AnyEntity",
    "AnyException",
    "AnyRepository",
    "AnyService",

    # ===== Метаданные =====
    "__version__",
    "__author__",
    "__description__",
]