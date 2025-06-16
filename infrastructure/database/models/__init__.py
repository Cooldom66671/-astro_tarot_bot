"""
Экспорт всех моделей базы данных.

Этот модуль:
- Импортирует все модели для удобного использования
- Предоставляет функции для работы с БД
- Содержит утилиты для миграций и инициализации
- Проверяет целостность схемы БД
"""

from typing import List, Type, Dict, Any, Optional
import asyncio
from datetime import datetime

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.schema import CreateTable

from config import logger
from infrastructure.database.connection import Base, db_connection
from infrastructure.database.models.base import (
    BaseModel, BaseUserModel, BaseTransactionModel, BaseCachedModel,
    TimestampMixin, SoftDeleteMixin, UUIDMixin, AuditMixin,
    create_all_indexes, get_model_statistics
)

# Импорт моделей пользователей
from infrastructure.database.models.user import (
    User, UserStatus, UserBirthData, UserSettings, UserConsent
)

# Импорт моделей подписок и платежей
from infrastructure.database.models.subscription import (
    Subscription, Payment, PromoCode, SubscriptionPlan, PaymentMethod,
    PaymentStatus, PaymentProvider, PromoCodeType
)

# Импорт моделей Таро
from infrastructure.database.models.tarot import (
    TarotDeck, TarotCard, TarotSpread, TarotReading, SavedReading,
    CardType, ReadingType
)

# Импорт астрологических моделей
from infrastructure.database.models.astrology import (
    NatalChart, PlanetPosition, AspectData, HouseData,
    Transit, Synastry, AstroForecast,
    Planet, ZodiacSign, AspectType, HouseSystem, ForecastType
)

# Экспорт всех моделей
__all__ = [
    # Базовые классы
    'Base', 'BaseModel', 'BaseUserModel', 'BaseTransactionModel', 'BaseCachedModel',
    'TimestampMixin', 'SoftDeleteMixin', 'UUIDMixin', 'AuditMixin',

    # Модели пользователей
    'User', 'UserStatus', 'UserBirthData', 'UserSettings', 'UserConsent',

    # Модели подписок
    'Subscription', 'Payment', 'PromoCode', 'SubscriptionPlan', 'PaymentMethod',
    'PaymentStatus', 'PaymentProvider', 'PromoCodeType',

    # Модели Таро
    'TarotDeck', 'TarotCard', 'TarotSpread', 'TarotReading', 'SavedReading',
    'CardType', 'ReadingType',

    # Астрологические модели
    'NatalChart', 'PlanetPosition', 'AspectData', 'HouseData',
    'Transit', 'Synastry', 'AstroForecast',
    'Planet', 'ZodiacSign', 'AspectType', 'HouseSystem', 'ForecastType',

    # Функции
    'create_all_tables', 'drop_all_tables', 'recreate_all_tables',
    'get_all_models', 'check_database_schema', 'init_default_data'
]

# Список всех моделей в порядке создания (учитывая зависимости)
ALL_MODELS: List[Type[BaseModel]] = [
    # Независимые модели
    TarotDeck,
    SubscriptionPlan,

    # Пользователи
    User,
    UserBirthData,
    UserSettings,
    UserConsent,

    # Зависимые от пользователей
    PromoCode,
    PaymentMethod,
    Payment,
    Subscription,

    # Таро (зависит от User и TarotDeck)
    TarotCard,
    TarotSpread,
    TarotReading,
    SavedReading,

    # Астрология (зависит от User)
    NatalChart,
    PlanetPosition,
    AspectData,
    HouseData,
    Transit,
    Synastry,
    AstroForecast,
]


def get_all_models() -> List[Type[BaseModel]]:
    """
    Получение списка всех моделей.

    Returns:
        Список классов моделей
    """
    return ALL_MODELS.copy()


async def create_all_tables(engine: Optional[AsyncEngine] = None) -> None:
    """
    Создание всех таблиц в БД.

    Args:
        engine: Engine SQLAlchemy (если не указан, используется глобальный)
    """
    engine = engine or db_connection.engine
    if not engine:
        raise RuntimeError("Database engine не инициализирован")

    logger.info("Начало создания таблиц БД...")

    try:
        async with engine.begin() as conn:
            # Создание таблиц
            await conn.run_sync(Base.metadata.create_all)

            # Создание кастомных индексов
            await conn.run_sync(create_all_indexes)

        logger.info("✅ Все таблицы успешно созданы")

    except Exception as e:
        logger.error(f"Ошибка при создании таблиц: {e}")
        raise


async def drop_all_tables(engine: Optional[AsyncEngine] = None) -> None:
    """
    Удаление всех таблиц из БД.

    ВНИМАНИЕ: Это удалит все данные!

    Args:
        engine: Engine SQLAlchemy
    """
    engine = engine or db_connection.engine
    if not engine:
        raise RuntimeError("Database engine не инициализирован")

    logger.warning("⚠️  Начало удаления всех таблиц БД...")

    try:
        async with engine.begin() as conn:
            # Удаление в обратном порядке из-за foreign keys
            await conn.run_sync(Base.metadata.drop_all)

        logger.warning("✅ Все таблицы удалены")

    except Exception as e:
        logger.error(f"Ошибка при удалении таблиц: {e}")
        raise


async def recreate_all_tables(engine: Optional[AsyncEngine] = None) -> None:
    """
    Пересоздание всех таблиц (удаление и создание).

    ВНИМАНИЕ: Это удалит все данные!

    Args:
        engine: Engine SQLAlchemy
    """
    engine = engine or db_connection.engine

    logger.warning("⚠️  Пересоздание всех таблиц БД...")
    await drop_all_tables(engine)
    await create_all_tables(engine)
    logger.info("✅ Таблицы пересозданы")


async def check_database_schema() -> Dict[str, Any]:
    """
    Проверка схемы базы данных.

    Returns:
        Словарь с информацией о таблицах и их состоянии
    """
    if not db_connection.engine:
        return {"error": "Database engine не инициализирован"}

    result = {
        "tables": {},
        "missing_tables": [],
        "total_tables": len(ALL_MODELS),
        "checked_at": datetime.utcnow().isoformat()
    }

    try:
        async with db_connection.engine.connect() as conn:
            # Получение списка существующих таблиц
            inspector = inspect(conn)
            existing_tables = await conn.run_sync(lambda sync_conn: inspector.get_table_names())

            # Проверка каждой модели
            for model in ALL_MODELS:
                table_name = model.__tablename__
                exists = table_name in existing_tables

                if exists:
                    # Получение информации о таблице
                    columns = await conn.run_sync(
                        lambda sync_conn: inspector.get_columns(table_name)
                    )
                    indexes = await conn.run_sync(
                        lambda sync_conn: inspector.get_indexes(table_name)
                    )

                    # Подсчет записей
                    count_result = await conn.execute(
                        text(f"SELECT COUNT(*) FROM {table_name}")
                    )
                    row_count = count_result.scalar()

                    result["tables"][table_name] = {
                        "exists": True,
                        "columns_count": len(columns),
                        "indexes_count": len(indexes),
                        "row_count": row_count
                    }
                else:
                    result["missing_tables"].append(table_name)
                    result["tables"][table_name] = {
                        "exists": False,
                        "columns_count": 0,
                        "indexes_count": 0,
                        "row_count": 0
                    }

        result["is_complete"] = len(result["missing_tables"]) == 0
        return result

    except Exception as e:
        logger.error(f"Ошибка при проверке схемы БД: {e}")
        return {"error": str(e)}


async def init_default_data() -> None:
    """
    Инициализация начальных данных в БД.

    Создает:
    - Тарифные планы
    - Колоду Таро по умолчанию
    - Типы раскладов
    """
    logger.info("Инициализация начальных данных...")

    async with db_connection.get_session() as session:
        try:
            # Проверка, есть ли уже данные
            existing_plans = await session.execute(
                text("SELECT COUNT(*) FROM subscription_plans")
            )
            if existing_plans.scalar() > 0:
                logger.info("Начальные данные уже существуют")
                return

            # Создание тарифных планов
            plans = [
                SubscriptionPlan(
                    tier="free",
                    name="Бесплатный",
                    description="Базовые возможности",
                    monthly_price=0,
                    daily_readings_limit=3,
                    features={
                        "tarot_daily": True,
                        "basic_natal_chart": True,
                        "limited_forecasts": True
                    }
                ),
                SubscriptionPlan(
                    tier="basic",
                    name="Базовый",
                    description="Расширенные возможности",
                    monthly_price=299,
                    yearly_price=2990,
                    daily_readings_limit=10,
                    features={
                        "tarot_all": True,
                        "full_natal_chart": True,
                        "synastry": True,
                        "monthly_forecast": True
                    }
                ),
                SubscriptionPlan(
                    tier="premium",
                    name="Премиум",
                    description="Полный доступ",
                    monthly_price=599,
                    yearly_price=5990,
                    daily_readings_limit=50,
                    features={
                        "all_features": True,
                        "pdf_reports": True,
                        "priority_support": True,
                        "custom_spreads": True
                    }
                ),
                SubscriptionPlan(
                    tier="vip",
                    name="VIP",
                    description="Безлимитный доступ",
                    monthly_price=1299,
                    yearly_price=12990,
                    daily_readings_limit=999999,
                    features={
                        "unlimited": True,
                        "personal_astrologer": True,
                        "api_access": True
                    }
                )
            ]

            for plan in plans:
                session.add(plan)

            # Создание колоды Таро по умолчанию
            default_deck = TarotDeck(
                code="rider_waite",
                name="Райдер-Уэйт",
                description="Классическая колода Таро",
                author="Артур Эдвард Уэйт",
                year_created=1909,
                is_default=True
            )
            session.add(default_deck)

            # Создание базовых типов раскладов
            spreads = [
                TarotSpread(
                    code="card_of_day",
                    name="Карта дня",
                    description="Одна карта на текущий день",
                    card_count=1,
                    positions=[{"position": 1, "meaning": "Энергия дня"}],
                    category="daily",
                    difficulty_level=1
                ),
                TarotSpread(
                    code="three_cards",
                    name="Три карты",
                    description="Прошлое, настоящее, будущее",
                    card_count=3,
                    positions=[
                        {"position": 1, "meaning": "Прошлое"},
                        {"position": 2, "meaning": "Настоящее"},
                        {"position": 3, "meaning": "Будущее"}
                    ],
                    category="general",
                    difficulty_level=2
                ),
                TarotSpread(
                    code="celtic_cross",
                    name="Кельтский крест",
                    description="Классический расклад на 10 карт",
                    card_count=10,
                    positions=[
                        {"position": 1, "meaning": "Текущая ситуация"},
                        {"position": 2, "meaning": "Вызов/Крест"},
                        {"position": 3, "meaning": "Далекое прошлое"},
                        {"position": 4, "meaning": "Недавнее прошлое"},
                        {"position": 5, "meaning": "Возможное будущее"},
                        {"position": 6, "meaning": "Ближайшее будущее"},
                        {"position": 7, "meaning": "Ваш подход"},
                        {"position": 8, "meaning": "Внешние влияния"},
                        {"position": 9, "meaning": "Надежды и страхи"},
                        {"position": 10, "meaning": "Итог"}
                    ],
                    category="detailed",
                    difficulty_level=4,
                    is_premium=True
                )
            ]

            for spread in spreads:
                session.add(spread)

            await session.commit()
            logger.info("✅ Начальные данные успешно созданы")

        except Exception as e:
            await session.rollback()
            logger.error(f"Ошибка при создании начальных данных: {e}")
            raise


async def get_database_stats() -> Dict[str, Any]:
    """
    Получение статистики по базе данных.

    Returns:
        Словарь со статистикой
    """
    stats = {
        "tables": {},
        "total_rows": 0,
        "database_size": None,
        "largest_tables": [],
        "collected_at": datetime.utcnow().isoformat()
    }

    try:
        async with db_connection.get_session() as session:
            # Размер БД
            size_result = await session.execute(
                text("SELECT pg_database_size(current_database())")
            )
            stats["database_size_mb"] = round(size_result.scalar() / 1024 / 1024, 2)

            # Статистика по таблицам
            for model in ALL_MODELS:
                table_name = model.__tablename__

                # Количество записей
                count_result = await session.execute(
                    text(f"SELECT COUNT(*) FROM {table_name}")
                )
                row_count = count_result.scalar() or 0

                # Размер таблицы
                size_result = await session.execute(
                    text(f"SELECT pg_total_relation_size('{table_name}'::regclass)")
                )
                table_size = size_result.scalar() or 0

                stats["tables"][table_name] = {
                    "row_count": row_count,
                    "size_mb": round(table_size / 1024 / 1024, 2)
                }
                stats["total_rows"] += row_count

            # Топ-5 самых больших таблиц
            stats["largest_tables"] = sorted(
                [(name, data["size_mb"]) for name, data in stats["tables"].items()],
                key=lambda x: x[1],
                reverse=True
            )[:5]

        return stats

    except Exception as e:
        logger.error(f"Ошибка при получении статистики БД: {e}")
        return {"error": str(e)}


# Проверка при импорте модуля
logger.info(f"Загружено {len(ALL_MODELS)} моделей базы данных")