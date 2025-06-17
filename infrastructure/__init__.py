"""
Инфраструктурный слой бота.

Этот модуль предоставляет всю инфраструктуру:
- База данных (модели, репозитории)
- Внешние API (OpenAI, платежи)
- Кэширование
- Утилиты и хелперы

Автор: AI Assistant
Дата создания: 2024-12-30
"""

import logging
from typing import Optional, Any, Dict

# Настройка логирования
logger = logging.getLogger(__name__)

# Версия инфраструктуры
__version__ = "1.0.0"

# Импорт подмодулей с обработкой ошибок
try:
    # База данных
    from infrastructure.database import (
        # Подключение
        DatabaseConnection,
        db_connection,
        init_database,
        shutdown_database,

        # Модели
        User,
        UserStatus,
        UserBirthData,
        UserSettings,
        Subscription,
        Payment,
        PromoCode,
        TarotCard,
        TarotDeck,
        TarotSpread,
        TarotReading,
        SavedReading,
        NatalChart,
        PlanetPosition,
        AspectData,

        # Репозитории и UoW
        BaseRepository,
        UserRepository,
        TarotRepository,
        SubscriptionRepository,
        UnitOfWork,
        get_unit_of_work,

        # Утилиты БД
        get_user_by_telegram_id,
        create_or_update_user_from_telegram,
        create_tarot_reading,
        get_database_statistics
    )
    database_available = True
    logger.info("Модуль базы данных загружен")
except ImportError as e:
    logger.warning(f"Не удалось загрузить модуль базы данных: {e}")
    database_available = False

    # Создаем заглушки для критичных функций
    async def get_unit_of_work():
        raise RuntimeError("База данных не инициализирована")

try:
    # Внешние API
    from infrastructure.external_apis import (
        # Базовый клиент
        BaseAPIClient,
        RequestMethod,
        CircuitState,

        # LLM
        OpenAIClient,
        OpenAIModel,
        GenerationType,
        AnthropicClient,
        ClaudeModel,
        LLMManager,
        LLMProvider,
        LLMRequest,
        LLMResponse,
        TaskPriority,
        llm_manager,

        # Функции генерации
        generate_text,
        interpret_tarot_cards,
        analyze_birth_chart,
        generate_daily_horoscope,
        answer_question,

        # Утилиты API
        check_api_health,
        get_api_statistics,
        estimate_generation_cost
    )
    external_apis_available = True
    logger.info("Модуль внешних API загружен")
except ImportError as e:
    logger.warning(f"Не удалось загрузить модуль внешних API: {e}")
    external_apis_available = False

    # Создаем заглушки
    llm_manager = None

    async def interpret_tarot_cards(*args, **kwargs):
        return "Интерпретация недоступна в оффлайн режиме"

    async def analyze_birth_chart(*args, **kwargs):
        return "Анализ недоступен в оффлайн режиме"

try:
    # Кэширование
    from infrastructure.cache import (
        CacheManager,
        cache_manager,
        cache_get,
        cache_set,
        cache_delete,
        cache_clear,
        cached,
        invalidate_cache,
        get_cache_stats
    )
    cache_available = True
    logger.info("Модуль кэширования загружен")
except ImportError as e:
    logger.warning(f"Не удалось загрузить модуль кэширования: {e}")
    cache_available = False

    # Создаем заглушки
    cache_manager = None

    async def cache_get(key: str):
        return None

    async def cache_set(key: str, value: Any, ttl: int = 3600):
        pass

# Глобальные экземпляры
_initialized = False
_database_connection: Optional[DatabaseConnection] = None
_llm_manager: Optional[LLMManager] = None
_cache_manager: Optional[Any] = None


async def init_infrastructure(config: Optional[Dict[str, Any]] = None):
    """
    Инициализировать всю инфраструктуру.

    Args:
        config: Дополнительная конфигурация
    """
    global _initialized, _database_connection, _llm_manager, _cache_manager

    if _initialized:
        logger.warning("Инфраструктура уже инициализирована")
        return

    logger.info("Инициализация инфраструктуры...")

    errors = []

    try:
        # База данных
        if database_available:
            logger.info("Настройка базы данных...")
            await init_database()
            _database_connection = db_connection
            logger.info("База данных инициализирована")
        else:
            logger.warning("База данных недоступна")
    except Exception as e:
        logger.error(f"Ошибка инициализации БД: {e}")
        errors.append(f"БД: {e}")

    try:
        # Внешние API
        if external_apis_available and llm_manager:
            _llm_manager = llm_manager
            # Проверяем доступность хотя бы одного провайдера
            if not _llm_manager.providers:
                logger.warning("Нет доступных LLM провайдеров")
            else:
                logger.info(f"Доступно LLM провайдеров: {len(_llm_manager.providers)}")
        else:
            logger.warning("Внешние API недоступны")
    except Exception as e:
        logger.error(f"Ошибка инициализации API: {e}")
        errors.append(f"API: {e}")

    try:
        # Кэш
        if cache_available and cache_manager:
            await cache_manager.init()
            _cache_manager = cache_manager
            logger.info("Кэш инициализирован")
        else:
            logger.warning("Кэш недоступен")
    except Exception as e:
        logger.error(f"Ошибка инициализации кэша: {e}")
        errors.append(f"Кэш: {e}")

    if errors:
        logger.warning(f"Инфраструктура инициализирована с ошибками: {errors}")
    else:
        logger.info("Инфраструктура успешно инициализирована")

    _initialized = True


async def shutdown_infrastructure():
    """Корректно завершить работу инфраструктуры."""
    global _initialized, _database_connection, _llm_manager, _cache_manager

    if not _initialized:
        return

    logger.info("Завершение работы инфраструктуры...")

    errors = []

    # Закрываем соединения с БД
    if _database_connection:
        try:
            await shutdown_database()
            logger.info("База данных закрыта")
        except Exception as e:
            logger.error(f"Ошибка закрытия БД: {e}")
            errors.append(f"БД: {e}")

    # Закрываем кэш
    if _cache_manager:
        try:
            await _cache_manager.close()
            logger.info("Кэш закрыт")
        except Exception as e:
            logger.error(f"Ошибка закрытия кэша: {e}")
            errors.append(f"Кэш: {e}")

    if errors:
        logger.warning(f"Инфраструктура завершена с ошибками: {errors}")
    else:
        logger.info("Инфраструктура корректно завершена")

    _initialized = False
    _database_connection = None
    _llm_manager = None
    _cache_manager = None


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
    if not _cache_manager:
        raise RuntimeError("Кэш не инициализирован")
    return _cache_manager


async def check_infrastructure_health() -> Dict[str, Any]:
    """
    Проверка состояния всей инфраструктуры.

    Returns:
        Отчет о состоянии компонентов
    """
    health = {
        "initialized": _initialized,
        "components": {
            "database": {
                "available": database_available,
                "connected": _database_connection is not None,
                "status": "unknown"
            },
            "external_apis": {
                "available": external_apis_available,
                "connected": _llm_manager is not None,
                "providers": []
            },
            "cache": {
                "available": cache_available,
                "connected": _cache_manager is not None,
                "status": "unknown"
            }
        }
    }

    # Проверяем БД
    if _database_connection:
        try:
            db_health = await _database_connection.health_check()
            health["components"]["database"]["status"] = db_health.get("status", "unknown")
            health["components"]["database"]["details"] = db_health
        except Exception as e:
            health["components"]["database"]["status"] = "error"
            health["components"]["database"]["error"] = str(e)

    # Проверяем API
    if _llm_manager:
        try:
            health["components"]["external_apis"]["providers"] = list(_llm_manager.providers.keys())
            if external_apis_available:
                api_health = await check_api_health()
                health["components"]["external_apis"]["details"] = api_health
        except Exception as e:
            health["components"]["external_apis"]["error"] = str(e)

    # Проверяем кэш
    if _cache_manager:
        try:
            cache_stats = await _cache_manager.get_stats()
            health["components"]["cache"]["status"] = "healthy"
            health["components"]["cache"]["stats"] = cache_stats
        except Exception as e:
            health["components"]["cache"]["status"] = "error"
            health["components"]["cache"]["error"] = str(e)

    return health


# Основные экспорты
__all__ = [
    # Версия
    "__version__",

    # Функции инициализации
    "init_infrastructure",
    "shutdown_infrastructure",
    "check_infrastructure_health",

    # Получение менеджеров
    "get_db_connection",
    "get_llm",
    "get_cache",

    # База данных (если доступна)
    "User",
    "Subscription",
    "Payment",
    "TarotCard",
    "TarotReading",
    "NatalChart",
    "UnitOfWork",
    "get_unit_of_work",
    "UserRepository",
    "TarotRepository",
    "SubscriptionRepository",

    # API (если доступны)
    "llm_manager",
    "interpret_tarot_cards",
    "analyze_birth_chart",
    "generate_text",
    "check_api_health",

    # Кэш (если доступен)
    "cache_manager",
    "cache_get",
    "cache_set",
    "cache_delete",
    "cached",

    # Флаги доступности
    "database_available",
    "external_apis_available",
    "cache_available"
]

logger.info(f"Инфраструктура v{__version__} загружена")