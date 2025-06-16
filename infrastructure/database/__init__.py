"""
Главный модуль для работы с базой данных.

Этот модуль:
- Экспортирует все компоненты БД
- Предоставляет функции инициализации
- Содержит хелперы для управления БД
- Обеспечивает единую точку входа
"""

from typing import Dict, Any, Optional
import asyncio
from datetime import datetime

from config import logger, settings

# Экспорт подключения
from infrastructure.database.connection import (
    db_connection, Base, DatabaseConnection,
    get_db_session, init_database, shutdown_database
)

# Экспорт всех моделей
from infrastructure.database.models import (
    # Базовые классы
    BaseModel, BaseUserModel, BaseTransactionModel, BaseCachedModel,
    TimestampMixin, SoftDeleteMixin, UUIDMixin, AuditMixin,

    # Модели пользователей
    User, UserStatus, UserBirthData, UserSettings, UserConsent,

    # Модели подписок
    Subscription, Payment, PromoCode, SubscriptionPlan, PaymentMethod,
    PaymentStatus, PaymentProvider, PromoCodeType,

    # Модели Таро
    TarotDeck, TarotCard, TarotSpread, TarotReading, SavedReading,
    CardType, ReadingType,

    # Астрологические модели
    NatalChart, PlanetPosition, AspectData, HouseData,
    Transit, Synastry, AstroForecast,
    Planet, ZodiacSign, AspectType, HouseSystem, ForecastType,

    # Функции моделей
    create_all_tables, drop_all_tables, recreate_all_tables,
    check_database_schema, init_default_data, get_database_stats
)

# Экспорт репозиториев и UoW
from infrastructure.database.repositories import (
    BaseRepository, UserRepository, TarotRepository, SubscriptionRepository,
    UnitOfWork, get_unit_of_work, RepositoryFactory,
    get_user_by_telegram_id, create_or_update_user_from_telegram,
    create_tarot_reading
)

# Экспорт всех компонентов
__all__ = [
    # Подключение
    'db_connection', 'Base', 'DatabaseConnection',
    'get_db_session', 'init_database', 'shutdown_database',

    # Базовые классы моделей
    'BaseModel', 'BaseUserModel', 'BaseTransactionModel', 'BaseCachedModel',
    'TimestampMixin', 'SoftDeleteMixin', 'UUIDMixin', 'AuditMixin',

    # Модели
    'User', 'UserStatus', 'UserBirthData', 'UserSettings', 'UserConsent',
    'Subscription', 'Payment', 'PromoCode', 'SubscriptionPlan', 'PaymentMethod',
    'PaymentStatus', 'PaymentProvider', 'PromoCodeType',
    'TarotDeck', 'TarotCard', 'TarotSpread', 'TarotReading', 'SavedReading',
    'CardType', 'ReadingType',
    'NatalChart', 'PlanetPosition', 'AspectData', 'HouseData',
    'Transit', 'Synastry', 'AstroForecast',
    'Planet', 'ZodiacSign', 'AspectType', 'HouseSystem', 'ForecastType',

    # Репозитории
    'BaseRepository', 'UserRepository', 'TarotRepository', 'SubscriptionRepository',
    'UnitOfWork', 'get_unit_of_work', 'RepositoryFactory',

    # Главные функции
    'setup_database', 'reset_database', 'check_database_health',
    'run_migrations', 'backup_database', 'restore_database'
]


# Главные функции управления БД

async def setup_database(
        create_tables: bool = True,
        init_data: bool = True
) -> Dict[str, Any]:
    """
    Полная настройка базы данных.

    Args:
        create_tables: Создать таблицы
        init_data: Инициализировать начальные данные

    Returns:
        Словарь с информацией о настройке
    """
    logger.info("🚀 Начало настройки базы данных...")
    start_time = datetime.utcnow()
    result = {
        "status": "success",
        "steps": [],
        "duration_seconds": 0
    }

    try:
        # 1. Инициализация подключения
        logger.info("Шаг 1: Инициализация подключения")
        await init_database()
        result["steps"].append({
            "step": "connection",
            "status": "completed"
        })

        # 2. Проверка схемы
        logger.info("Шаг 2: Проверка схемы БД")
        schema_info = await check_database_schema()
        result["schema_check"] = schema_info

        # 3. Создание таблиц если нужно
        if create_tables and schema_info.get("missing_tables"):
            logger.info("Шаг 3: Создание недостающих таблиц")
            await create_all_tables()
            result["steps"].append({
                "step": "create_tables",
                "status": "completed",
                "tables_created": len(schema_info["missing_tables"])
            })

        # 4. Инициализация начальных данных
        if init_data:
            logger.info("Шаг 4: Инициализация начальных данных")
            await init_default_data()
            result["steps"].append({
                "step": "init_data",
                "status": "completed"
            })

        # 5. Финальная проверка
        logger.info("Шаг 5: Финальная проверка")
        health = await check_database_health()
        result["health_check"] = health

        # Расчет времени
        duration = (datetime.utcnow() - start_time).total_seconds()
        result["duration_seconds"] = duration

        logger.info(f"✅ База данных настроена за {duration:.2f} секунд")

    except Exception as e:
        logger.error(f"❌ Ошибка настройки БД: {e}")
        result["status"] = "error"
        result["error"] = str(e)

    return result


async def reset_database(
        confirm: bool = False
) -> Dict[str, Any]:
    """
    Полный сброс базы данных.

    ВНИМАНИЕ: Это удалит все данные!

    Args:
        confirm: Подтверждение операции

    Returns:
        Словарь с информацией о сбросе
    """
    if not confirm:
        return {
            "status": "cancelled",
            "message": "Требуется подтверждение для сброса БД"
        }

    logger.warning("⚠️  Начало полного сброса базы данных...")

    try:
        # 1. Удаление всех таблиц
        await drop_all_tables()

        # 2. Создание таблиц заново
        await create_all_tables()

        # 3. Инициализация данных
        await init_default_data()

        logger.info("✅ База данных успешно сброшена")

        return {
            "status": "success",
            "message": "База данных сброшена и инициализирована"
        }

    except Exception as e:
        logger.error(f"❌ Ошибка сброса БД: {e}")
        return {
            "status": "error",
            "error": str(e)
        }


async def check_database_health() -> Dict[str, Any]:
    """
    Комплексная проверка здоровья БД.

    Returns:
        Словарь с детальной информацией о состоянии
    """
    health_report = {
        "status": "unknown",
        "timestamp": datetime.utcnow().isoformat(),
        "checks": {},
        "warnings": [],
        "errors": []
    }

    try:
        # 1. Проверка подключения
        connection_health = await db_connection.health_check()
        health_report["checks"]["connection"] = connection_health

        if connection_health.get("status") != "healthy":
            health_report["errors"].append("Проблема с подключением к БД")

        # 2. Проверка схемы
        schema_info = await check_database_schema()
        health_report["checks"]["schema"] = {
            "complete": schema_info.get("is_complete", False),
            "missing_tables": schema_info.get("missing_tables", [])
        }

        if schema_info.get("missing_tables"):
            health_report["warnings"].append(
                f"Отсутствуют таблицы: {', '.join(schema_info['missing_tables'])}"
            )

        # 3. Проверка статистики
        stats = await get_database_stats()
        health_report["checks"]["statistics"] = stats

        # 4. Проверка производительности
        async with get_unit_of_work() as uow:
            start = datetime.utcnow()
            count = await uow.users.count()
            query_time = (datetime.utcnow() - start).total_seconds()

            health_report["checks"]["performance"] = {
                "sample_query_time": query_time,
                "is_slow": query_time > 1.0
            }

            if query_time > 1.0:
                health_report["warnings"].append(
                    f"Медленные запросы: {query_time:.2f}s"
                )

        # 5. Определение общего статуса
        if health_report["errors"]:
            health_report["status"] = "unhealthy"
        elif health_report["warnings"]:
            health_report["status"] = "degraded"
        else:
            health_report["status"] = "healthy"

    except Exception as e:
        health_report["status"] = "error"
        health_report["errors"].append(f"Ошибка проверки: {str(e)}")

    return health_report


async def run_migrations(
        migration_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Запуск миграций БД.

    Args:
        migration_name: Имя конкретной миграции

    Returns:
        Результат выполнения миграций
    """
    # В реальном проекте здесь будет интеграция с Alembic
    logger.info(f"Запуск миграций{f': {migration_name}' if migration_name else ''}")

    # Пока просто проверяем и создаем недостающие таблицы
    schema_info = await check_database_schema()

    if schema_info.get("missing_tables"):
        await create_all_tables()
        return {
            "status": "success",
            "migrations_applied": 1,
            "tables_created": len(schema_info["missing_tables"])
        }

    return {
        "status": "success",
        "migrations_applied": 0,
        "message": "Все миграции уже применены"
    }


async def backup_database(
        backup_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Создание резервной копии БД.

    Args:
        backup_path: Путь для сохранения

    Returns:
        Информация о резервной копии
    """
    if not backup_path:
        backup_path = f"backups/db_backup_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.sql"

    logger.info(f"Создание резервной копии: {backup_path}")

    # В реальном проекте здесь будет вызов pg_dump
    # Пока возвращаем заглушку
    return {
        "status": "success",
        "backup_path": backup_path,
        "size_mb": 0,
        "tables_backed_up": 0,
        "message": "Функция backup будет реализована с pg_dump"
    }


async def restore_database(
        backup_path: str,
        confirm: bool = False
) -> Dict[str, Any]:
    """
    Восстановление БД из резервной копии.

    Args:
        backup_path: Путь к файлу резервной копии
        confirm: Подтверждение операции

    Returns:
        Информация о восстановлении
    """
    if not confirm:
        return {
            "status": "cancelled",
            "message": "Требуется подтверждение для восстановления БД"
        }

    logger.warning(f"Восстановление БД из: {backup_path}")

    # В реальном проекте здесь будет вызов pg_restore
    return {
        "status": "success",
        "restored_from": backup_path,
        "message": "Функция restore будет реализована с pg_restore"
    }


# Вспомогательные функции

async def get_table_sizes() -> Dict[str, int]:
    """
    Получение размеров всех таблиц.

    Returns:
        Словарь {имя_таблицы: размер_в_МБ}
    """
    stats = await get_database_stats()

    sizes = {}
    for table_name, table_stats in stats.get("tables", {}).items():
        sizes[table_name] = table_stats.get("size_mb", 0)

    return sizes


async def vacuum_database() -> Dict[str, Any]:
    """
    Оптимизация БД (VACUUM).

    Returns:
        Результат оптимизации
    """
    logger.info("Запуск VACUUM для оптимизации БД")

    try:
        async with db_connection.get_session() as session:
            # VACUUM нельзя запустить в транзакции
            await session.execute("COMMIT")
            await session.execute("VACUUM ANALYZE")

        return {
            "status": "success",
            "message": "База данных оптимизирована"
        }

    except Exception as e:
        logger.error(f"Ошибка VACUUM: {e}")
        return {
            "status": "error",
            "error": str(e)
        }


# Проверка окружения при импорте
if settings.is_production():
    logger.info("🏭 База данных в PRODUCTION режиме")
elif settings.is_testing():
    logger.info("🧪 База данных в TESTING режиме")
else:
    logger.info("🔧 База данных в DEVELOPMENT режиме")


# Автоматическая инициализация в development режиме
async def auto_init_development():
    """Автоматическая инициализация для разработки."""
    if settings.is_development() and settings.database.auto_init:
        logger.info("🔄 Автоматическая инициализация БД для разработки")
        await setup_database()

# Можно вызвать при необходимости
# asyncio.create_task(auto_init_development())