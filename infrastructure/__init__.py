"""
Инфраструктурный слой бота.

Этот модуль предоставляет всю инфраструктуру:
- База данных (модели, репозитории)
- Внешние API (OpenAI, платежи)
- Telegram интерфейс (клавиатуры, сообщения)
- Кэширование

Автор: AI Assistant
Дата создания: 2024-12-30
"""

import logging
from typing import Optional, Any

# База данных
from .database import (
    # Подключение
    DatabaseManager,

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

# Telegram
from .telegram import (
    # Клавиатуры
    Keyboards,
    get_main_menu,

    # Сообщения
    MessageFactory,
    MessageManager,
    CommonMessages,

    # Функции
    get_welcome_message
)

# Настройка логирования
logger = logging.getLogger(__name__)

# Версия инфраструктуры
__version__ = "1.0.0"


# Глобальные экземпляры (будут инициализированы при запуске)
_database_manager: Optional[DatabaseManager] = None
_llm_manager: Optional[LLMManager] = None
_cache_manager: Optional[Any] = None  # CacheManager из cache.py
_message_manager: Optional[MessageManager] = None


async def init_infrastructure():
    """Инициализировать всю инфраструктуру."""
    global _database_manager, _llm_manager, _cache_manager, _message_manager

    logger.info("Инициализация инфраструктуры...")

    try:
        # База данных
        logger.info("Подключение к базе данных...")
        _database_manager = DatabaseManager()
        await _database_manager.connect()
        await setup_database()

        # Внешние API
        logger.info("Инициализация внешних API...")
        _llm_manager = LLMManager()

        # Кэш
        logger.info("Инициализация кэша...")
        _cache_manager = cache_manager  # Используем глобальный экземпляр из cache.py

        # Сообщения
        logger.info("Инициализация менеджера сообщений...")
        _message_manager = MessageManager()

        logger.info("Инфраструктура успешно инициализирована")

    except Exception as e:
        logger.error(f"Ошибка инициализации инфраструктуры: {e}")
        raise


async def shutdown_infrastructure():
    """Корректно завершить работу инфраструктуры."""
    logger.info("Завершение работы инфраструктуры...")

    try:
        # Закрываем соединения
        if _database_manager:
            await _database_manager.disconnect()

        logger.info("Инфраструктура корректно завершена")

    except Exception as e:
        logger.error(f"Ошибка при завершении инфраструктуры: {e}")


# Функции для получения глобальных экземпляров
def get_db_manager() -> DatabaseManager:
    """Получить менеджер базы данных."""
    if not _database_manager:
        raise RuntimeError("База данных не инициализирована")
    return _database_manager


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


def get_messages() -> MessageManager:
    """Получить менеджер сообщений."""
    if not _message_manager:
        raise RuntimeError("Менеджер сообщений не инициализирован")
    return _message_manager


# Основные экспорты
__all__ = [
    # Функции инициализации
    "init_infrastructure",
    "shutdown_infrastructure",

    # Получение менеджеров
    "get_db_manager",
    "get_llm",
    "get_cache",
    "get_messages",

    # База данных
    "User",
    "UnitOfWork",
    "get_unit_of_work",

    # API
    "interpret_tarot_cards",
    "analyze_birth_chart",

    # Telegram
    "Keyboards",
    "MessageFactory",
    "CommonMessages",

    # Версия
    "__version__"
]


logger.info(f"Инфраструктура v{__version__} загружена")