"""
Пакет бизнес-сущностей Астро-Таро Бота.

Этот модуль экспортирует все основные бизнес-сущности приложения
для удобного импорта в других модулях. Сущности не зависят от
инфраструктуры и содержат только бизнес-логику.

Использование:
    # Импорт отдельных сущностей
    from core.entities import User, Subscription, BirthChart

    # Импорт вспомогательных классов
    from core.entities import BirthData, Payment, Aspect

    # Создание сущностей
    user = User(id=1, telegram_id=123456789, created_at=datetime.now())
    subscription = Subscription(id=1, user_id=user.id)
    chart = BirthChart(birth_date=datetime.now(), latitude=55.75, longitude=37.61, timezone="UTC")
"""

# Импорт из модуля user
from core.entities.user import (
    User,
    BirthData,
    UserSubscription,
    UserSettings,
)

# Импорт из модуля subscription
from core.entities.subscription import (
    Subscription,
    PlanFeatures,
    PLAN_FEATURES,
    PromoCode,
    PromoCodeType,
    Payment,
)

# Импорт из модуля birth_chart
from core.entities.birth_chart import (
    BirthChart,
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
)

# Дополнительные импорты для удобства
from typing import TYPE_CHECKING, List, Optional, Dict, Any
from datetime import datetime


# Вспомогательные функции для работы с сущностями

def create_user_from_telegram_data(
        telegram_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        language_code: Optional[str] = None,
        is_premium: bool = False
) -> User:
    """
    Создать пользователя из данных Telegram.

    Args:
        telegram_id: ID пользователя в Telegram
        username: Username в Telegram
        first_name: Имя
        last_name: Фамилия
        language_code: Код языка
        is_premium: Есть ли Telegram Premium

    Returns:
        User: Созданный пользователь
    """
    from datetime import datetime

    # В реальном приложении ID будет генерироваться БД
    user = User(
        id=0,  # Временный ID
        telegram_id=telegram_id,
        created_at=datetime.now(),
        username=username,
        first_name=first_name,
        last_name=last_name,
        language_code=language_code,
        is_premium=is_premium
    )

    return user


def get_plan_features(plan_name: str) -> Optional[PlanFeatures]:
    """
    Получить характеристики тарифного плана по имени.

    Args:
        plan_name: Название плана (free, basic, premium, vip)

    Returns:
        PlanFeatures или None если план не найден
    """
    from config import SubscriptionPlan

    try:
        plan = SubscriptionPlan(plan_name)
        return PLAN_FEATURES.get(plan)
    except ValueError:
        return None


def calculate_subscription_price(
        plan_name: str,
        months: int = 1,
        with_annual_discount: bool = False
) -> Optional[Dict[str, Any]]:
    """
    Рассчитать стоимость подписки.

    Args:
        plan_name: Название плана
        months: Количество месяцев
        with_annual_discount: Применить годовую скидку

    Returns:
        Dict с информацией о цене или None
    """
    features = get_plan_features(plan_name)
    if not features:
        return None

    from decimal import Decimal
    from config import Prices

    base_price = features.monthly_price * months

    # Годовая скидка
    if with_annual_discount and months >= 12:
        discount = base_price * Prices.ANNUAL_DISCOUNT
        final_price = base_price - discount
    else:
        discount = Decimal("0")
        final_price = base_price

    return {
        "plan": plan_name,
        "months": months,
        "base_price": float(base_price),
        "discount": float(discount),
        "final_price": float(final_price),
        "currency": "RUB"
    }


# Типы для аннотаций
if TYPE_CHECKING:
    # Эти импорты только для подсказок типов
    UserList = List[User]
    SubscriptionList = List[Subscription]
    BirthChartDict = Dict[int, BirthChart]  # user_id -> chart

# Константы для экспорта
SUPPORTED_HOUSE_SYSTEMS = [system.value for system in HouseSystem]
SUPPORTED_ASPECTS = [aspect.value for aspect in AspectType]
ZODIAC_ELEMENTS = [element.value for element in Element]
ZODIAC_QUALITIES = [quality.value for quality in Quality]

# Экспорт всех сущностей и вспомогательных элементов
__all__ = [
    # Основные сущности
    "User",
    "Subscription",
    "BirthChart",

    # Вспомогательные классы из user
    "BirthData",
    "UserSubscription",
    "UserSettings",

    # Вспомогательные классы из subscription
    "PlanFeatures",
    "PLAN_FEATURES",
    "PromoCode",
    "PromoCodeType",
    "Payment",

    # Вспомогательные классы из birth_chart
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

    # Функции-помощники
    "create_user_from_telegram_data",
    "get_plan_features",
    "calculate_subscription_price",

    # Константы
    "SUPPORTED_HOUSE_SYSTEMS",
    "SUPPORTED_ASPECTS",
    "ZODIAC_ELEMENTS",
    "ZODIAC_QUALITIES",
]