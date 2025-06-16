"""
Модуль обработчиков команд и событий бота.

Этот модуль объединяет все обработчики:
- Базовые обработчики
- Обработчики команд
- Обработчики разделов (Таро, Астрология, Подписка)
- Middleware и фильтры

Автор: AI Assistant
Дата создания: 2024-12-30
"""

import logging
from typing import List, Optional

from aiogram import Router, Dispatcher
from aiogram.filters import ExceptionTypeFilter
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramAPIError,
    TelegramRetryAfter
)

# Базовые обработчики
from .base import BaseHandler
from .start import StartHandler
from .help import HelpHandler
from .menu import MenuHandler
from .common import CommonHandler

# Обработчики разделов
from .tarot import TarotHandlers
from .astrology import AstrologyHandlers
from .subscription import SubscriptionHandlers

logger = logging.getLogger(__name__)

__all__ = [
    'BaseHandler',
    'StartHandler',
    'HelpHandler',
    'MenuHandler',
    'CommonHandler',
    'TarotHandlers',
    'AstrologyHandlers',
    'SubscriptionHandlers',
    'setup_handlers',
    'create_dispatcher'
]


def setup_handlers(dp: Dispatcher) -> None:
    """
    Настройка всех обработчиков бота.

    Args:
        dp: Диспетчер aiogram
    """
    # Создаем основной роутер
    main_router = Router(name="main")

    # Создаем роутеры для разделов
    base_router = Router(name="base")
    tarot_router = Router(name="tarot")
    astrology_router = Router(name="astrology")
    subscription_router = Router(name="subscription")
    admin_router = Router(name="admin")

    # Регистрируем базовые обработчики
    logger.info("Registering base handlers...")

    # Важно: порядок регистрации имеет значение!
    # Сначала специфичные обработчики, потом общие

    # 1. Обработчик старта (самый приоритетный)
    start_handler = StartHandler()
    start_handler.register_handlers(base_router)

    # 2. Обработчик помощи
    help_handler = HelpHandler()
    help_handler.register_handlers(base_router)

    # 3. Обработчик меню
    menu_handler = MenuHandler()
    menu_handler.register_handlers(base_router)

    # 4. Обработчики разделов
    tarot_handlers = TarotHandlers()
    tarot_handlers.register_handlers(tarot_router)

    astrology_handlers = AstrologyHandlers()
    astrology_handlers.register_handlers(astrology_router)

    subscription_handlers = SubscriptionHandlers()
    subscription_handlers.register_handlers(subscription_router)

    # 5. Общие обработчики (самый низкий приоритет)
    common_handler = CommonHandler()
    common_handler.register_handlers(base_router)

    # Подключаем роутеры к главному
    main_router.include_router(base_router)
    main_router.include_router(tarot_router)
    main_router.include_router(astrology_router)
    main_router.include_router(subscription_router)
    main_router.include_router(admin_router)

    # Подключаем главный роутер к диспетчеру
    dp.include_router(main_router)

    # Настраиваем middleware
    setup_middleware(dp)

    # Настраиваем обработчики ошибок
    setup_error_handlers(dp)

    logger.info("All handlers registered successfully")


def setup_middleware(dp: Dispatcher) -> None:
    """
    Настройка middleware для обработки запросов.

    Args:
        dp: Диспетчер aiogram
    """
    # Импортируем функцию настройки middleware
    from bot.middleware import setup_middleware as middleware_setup

    logger.info("Setting up middleware...")

    # Используем централизованную настройку middleware
    middleware_instances = middleware_setup(dp)

    logger.info("Middleware setup complete")

    # Возвращаем экземпляры для возможного использования
    return middleware_instances


def setup_error_handlers(dp: Dispatcher) -> None:
    """
    Настройка глобальных обработчиков ошибок.

    Args:
        dp: Диспетчер aiogram
    """
    logger.info("Setting up error handlers...")

    @dp.error(ExceptionTypeFilter(TelegramRetryAfter))
    async def handle_retry_after(event, exception: TelegramRetryAfter):
        """Обработка ошибки превышения лимита запросов."""
        logger.warning(
            f"Rate limit exceeded. Retry after {exception.retry_after} seconds"
        )
        # Здесь можно добавить логику ожидания и повторной отправки

    @dp.error(ExceptionTypeFilter(TelegramBadRequest))
    async def handle_bad_request(event, exception: TelegramBadRequest):
        """Обработка ошибок некорректных запросов."""
        logger.error(f"Bad request: {exception}")
        # Обработка специфичных ошибок
        if "message is not modified" in str(exception):
            # Игнорируем ошибку, если сообщение не изменилось
            return True
        elif "message to delete not found" in str(exception):
            # Игнорируем, если сообщение уже удалено
            return True

    @dp.error(ExceptionTypeFilter(TelegramAPIError))
    async def handle_api_error(event, exception: TelegramAPIError):
        """Обработка общих ошибок Telegram API."""
        logger.error(f"Telegram API error: {exception}")

    @dp.error()
    async def handle_all_errors(event, exception: Exception):
        """Обработка всех остальных ошибок."""
        logger.error(
            f"Unhandled error in {event.router.name}: {exception}",
            exc_info=exception
        )

        # Пытаемся уведомить пользователя
        if hasattr(event.update, 'message') and event.update.message:
            try:
                await event.update.message.answer(
                    "😔 Произошла ошибка при обработке вашего запроса.\n"
                    "Пожалуйста, попробуйте позже или обратитесь в /support"
                )
            except:
                pass
        elif hasattr(event.update, 'callback_query') and event.update.callback_query:
            try:
                await event.update.callback_query.answer(
                    "Произошла ошибка. Попробуйте позже.",
                    show_alert=True
                )
            except:
                pass

    logger.info("Error handlers setup complete")


def create_dispatcher(
    storage: Optional[MemoryStorage | RedisStorage] = None
) -> Dispatcher:
    """
    Создание и настройка диспетчера.

    Args:
        storage: Хранилище FSM состояний

    Returns:
        Настроенный диспетчер
    """
    # Используем память по умолчанию, если storage не передан
    if storage is None:
        storage = MemoryStorage()
        logger.info("Using MemoryStorage for FSM")

    # Создаем диспетчер
    dp = Dispatcher(storage=storage)

    # Настраиваем обработчики
    setup_handlers(dp)

    return dp


class HandlersConfig:
    """Конфигурация обработчиков."""

    # Приоритеты роутеров
    ROUTER_PRIORITIES = {
        "admin": 100,      # Максимальный приоритет
        "base": 90,        # Базовые команды
        "tarot": 50,       # Разделы
        "astrology": 50,
        "subscription": 50,
        "common": 10       # Минимальный приоритет
    }

    # Настройки throttling
    THROTTLE_RATES = {
        "default": (5, 60),      # 5 запросов в минуту
        "tarot": (3, 60),        # 3 расклада в минуту
        "payment": (10, 3600),   # 10 попыток оплаты в час
        "feedback": (3, 3600),   # 3 отзыва в час
        "admin": (100, 60)       # 100 запросов в минуту для админов
    }

    # Таймауты
    TIMEOUTS = {
        "callback_answer": 3,    # Секунды для ответа на callback
        "typing_action": 5,      # Секунды для "печатает..."
        "payment_wait": 300,     # 5 минут на оплату
        "onboarding": 600        # 10 минут на онбординг
    }


# Функции-помощники для быстрой настройки

async def register_all_handlers(dp: Dispatcher) -> None:
    """
    Асинхронная регистрация всех обработчиков.
    Используется для случаев, когда нужна асинхронная инициализация.
    """
    setup_handlers(dp)

    # Здесь можно добавить асинхронную инициализацию
    # например, загрузку данных из БД
    logger.info("Async handlers initialization complete")


def get_router_by_name(dp: Dispatcher, name: str) -> Optional[Router]:
    """
    Получить роутер по имени.

    Args:
        dp: Диспетчер
        name: Имя роутера

    Returns:
        Router или None
    """
    for router in dp._routers:
        if router.name == name:
            return router
    return None


def list_registered_handlers(dp: Dispatcher) -> List[str]:
    """
    Получить список зарегистрированных обработчиков.

    Args:
        dp: Диспетчер

    Returns:
        Список имен роутеров
    """
    return [router.name for router in dp._routers]