"""
Инфраструктурный слой бота.

Этот модуль предоставляет всю инфраструктуру:
- База данных (модели, репозитории)
- Внешние API (OpenAI, платежи)
- Кэширование

Автор: AI Assistant
Дата создания: 2024-12-30
"""

import logging
from typing import Optional, Any

# База данных
from .database import (
    # Подключение - ИСПРАВЛЕНО: DatabaseConnection вместо DatabaseManager
    DatabaseConnection,
    db_connection,

    # Модели
    User,
    Subscription,
    Payment,
    TarotCard,
    TarotReading,
    NatalChart,

    # Репозитории
    UnitOfWork,
    get_unit_of_work,
    UserRepository,
    TarotRepository,
    SubscriptionRepository,

    # Функции
    setup_database,
    check_database_health
)

# Внешние API
from .external_apis import (
    # LLM
    OpenAIClient,
    AnthropicClient,
    LLMManager,
    llm_manager,

    # Функции
    interpret_tarot_cards,
    analyze_birth_chart,
    check_api_health
)

# Кэширование
from .cache import (
    cache_manager,
    cache_get,
    cache_set,
    cache_delete,
    cached
)

# Настройка логирования
logger = logging.getLogger(__name__)

# Версия инфраструктуры
__version__ = "1.0.0"


# Глобальные экземпляры (будут инициализированы при запуске)
_database_connection: Optional[DatabaseConnection] = None
_llm_manager: Optional[LLMManager] = None


async def init_infrastructure():
    """Инициализировать всю инфраструктуру."""
    global _database_connection, _llm_manager

    logger.info("Инициализация инфраструктуры...")

    try:
        # База данных
        logger.info("Настройка базы данных...")
        await setup_database()
        _database_connection = db_connection

        # LLM уже инициализирован как глобальный экземпляр
        _llm_manager = llm_manager

        # Кэш инициализируется автоматически при первом использовании
        await cache_manager.init()

        logger.info("Инфраструктура успешно инициализирована")

    except Exception as e:
        logger.error(f"Ошибка инициализации инфраструктуры: {e}")
        raise


async def shutdown_infrastructure():
    """Корректно завершить работу инфраструктуры."""
    logger.info("Завершение работы инфраструктуры...")

    try:
        # Закрываем соединения с БД
        if _database_connection:
            await _database_connection.close()

        # Закрываем кэш
        await cache_manager.close()

        logger.info("Инфраструктура корректно завершена")

    except Exception as e:
        logger.error(f"Ошибка при завершении инфраструктуры: {e}")


# Функции для получения глобальных экземпляров
def get_db_connection() -> DatabaseConnection:
    """Получить подключение к базе данных."""
    if not _database_connection:
        raise RuntimeError("База данных не инициализирована")
    return _database_connection


def get_llm() -> LLMManager:
    """Получить менеджер LLM."""
    if not _llm_manager:
        raise RuntimeError("LLM менеджер не инициализирован")
    return _llm_manager


def get_cache():
    """Получить менеджер кэша."""
    return cache_manager


# Основные экспорты
__all__ = [
    # Функции инициализации
    "init_infrastructure",
    "shutdown_infrastructure",

    # Получение менеджеров
    "get_db_connection",
    "get_llm",
    "get_cache",

    # База данных
    "User",
    "UnitOfWork",
    "get_unit_of_work",

    # API
    "interpret_tarot_cards",
    "analyze_birth_chart",

    # Кэш
    "cache_get",
    "cache_set",
    "cache_delete",
    "cached",

    # Версия
    "__version__"
]


logger.info(f"Инфраструктура v{__version__} загружена")