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
from typing import List, Optional, Dict, Any, Union

from aiogram import Router, Dispatcher
from aiogram.filters import ExceptionTypeFilter
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramAPIError,
    TelegramRetryAfter
)

logger = logging.getLogger(__name__)

# Экспортируемые функции
__all__ = [
    'setup_handlers',
    'create_dispatcher',
    'setup_middleware',
    'setup_error_handlers',
    'HandlersConfig',
    'register_all_handlers'
]


def setup_handlers(dp: Dispatcher) -> None:
    """
    Настройка всех обработчиков бота.

    Args:
        dp: Диспетчер aiogram
    """
    # Импортируем обработчики здесь, чтобы избежать циклических импортов
    from .base import BaseHandler
    from .start import StartHandler
    from .help import HelpHandler
    from .menu import MenuHandler
    from .common import CommonHandler

    # Создаем основной роутер
    main_router = Router(name="main")

    # Создаем роутеры для разделов
    base_router = Router(name="base")
    tarot_router = Router(name="tarot")
    astrology_router = Router(name="astrology")
    subscription_router = Router(name="subscription")
    profile_router = Router(name="profile")
    settings_router = Router(name="settings")
    admin_router = Router(name="admin")

    # Регистрируем базовые обработчики
    logger.info("Registering base handlers...")

    # Важно: порядок регистрации имеет значение!
    # Сначала специфичные обработчики, потом общие

    # 1. Обработчик старта (самый приоритетный)
    start_handler = StartHandler(base_router)
    start_handler.register_handlers()

    # 2. Обработчик помощи
    help_handler = HelpHandler(base_router)
    help_handler.register_handlers()

    # 3. Обработчик меню
    menu_handler = MenuHandler(base_router)
    menu_handler.register_handlers()

    # 4. Обработчики разделов
    # Проверяем наличие модулей и импортируем только существующие

    # Таро
    try:
        from .tarot import TarotHandler
        tarot_handler = TarotHandler(tarot_router)
        tarot_handler.register_handlers()
        logger.info("Tarot handlers registered")
    except ImportError:
        logger.warning("Tarot handlers not found, creating stub...")
        # Создаем заглушку для Таро
        _create_stub_handler(tarot_router, "tarot", "🎴 Раздел Таро в разработке")

    # Астрология
    try:
        from .astrology import AstrologyHandler
        astrology_handler = AstrologyHandler(astrology_router)
        astrology_handler.register_handlers()
        logger.info("Astrology handlers registered")
    except ImportError:
        logger.warning("Astrology handlers not found, creating stub...")
        _create_stub_handler(astrology_router, "astrology", "🔮 Раздел Астрология в разработке")

    # Подписка
    try:
        from .subscription import SubscriptionHandler
        subscription_handler = SubscriptionHandler(subscription_router)
        subscription_handler.register_handlers()
        logger.info("Subscription handlers registered")
    except ImportError:
        logger.warning("Subscription handlers not found, creating stub...")
        _create_stub_handler(subscription_router, "subscription", "💎 Раздел Подписка в разработке")

    # Профиль
    try:
        from .profile import ProfileHandler
        profile_handler = ProfileHandler(profile_router)
        profile_handler.register_handlers()
        logger.info("Profile handlers registered")
    except ImportError:
        logger.warning("Profile handlers not found, creating stub...")
        _create_stub_handler(profile_router, "profile", "👤 Раздел Профиль в разработке")

    # Настройки
    try:
        from .settings import SettingsHandler
        settings_handler = SettingsHandler(settings_router)
        settings_handler.register_handlers()
        logger.info("Settings handlers registered")
    except ImportError:
        logger.warning("Settings handlers not found, creating stub...")
        _create_stub_handler(settings_router, "settings", "⚙️ Раздел Настройки в разработке")

    # 5. Общие обработчики (самый низкий приоритет)
    common_handler = CommonHandler(base_router)
    common_handler.register_handlers()

    # 6. Админские обработчики (если есть)
    try:
        from .admin import AdminHandler
        admin_handler = AdminHandler(admin_router)
        admin_handler.register_handlers()
        logger.info("Admin handlers registered")
    except ImportError:
        logger.info("Admin handlers not found, skipping...")

    # Подключаем роутеры к главному
    main_router.include_router(base_router)
    main_router.include_router(tarot_router)
    main_router.include_router(astrology_router)
    main_router.include_router(subscription_router)
    main_router.include_router(profile_router)
    main_router.include_router(settings_router)

    # Админский роутер подключаем только если он был зарегистрирован
    try:
        # В aiogram 3.x проверяем наличие обработчиков через observers
        has_handlers = bool(admin_router.message.observers) or bool(admin_router.callback_query.observers)
        if has_handlers:
            main_router.include_router(admin_router)
    except AttributeError:
        # Если структура изменилась, пытаемся подключить в любом случае
        main_router.include_router(admin_router)

    # Подключаем главный роутер к диспетчеру
    dp.include_router(main_router)

    # Настраиваем middleware
    setup_middleware(dp)

    # Настраиваем обработчики ошибок
    setup_error_handlers(dp)

    logger.info("All handlers registered successfully")


def _create_stub_handler(router: Router, section: str, message: str) -> None:
    """
    Создать заглушку для отсутствующего обработчика.

    Args:
        router: Роутер для регистрации
        section: Название раздела
        message: Сообщение для пользователя
    """
    from aiogram import F
    from aiogram.types import CallbackQuery
    from infrastructure.telegram.keyboards import Keyboards

    @router.callback_query(F.data.startswith(f"{section}:"))
    async def stub_handler(callback: CallbackQuery):
        """Заглушка для несуществующего раздела."""
        keyboard = await Keyboards.back("main_menu")

        await callback.message.answer(
            f"{message}\n\nИспользуйте /menu для возврата в главное меню.",
            reply_markup=keyboard
        )
        await callback.answer()


def setup_middleware(dp: Dispatcher) -> Dict[str, Any]:
    """
    Настройка middleware для обработки запросов.

    Args:
        dp: Диспетчер aiogram

    Returns:
        Словарь с экземплярами middleware
    """
    middleware_instances = {}

    try:
        # Импортируем middleware модули
        from bot.middleware.throttling import ThrottlingMiddleware
        from bot.middleware.database import DatabaseMiddleware
        from bot.middleware.logging import LoggingMiddleware
        from bot.middleware.user import UserMiddleware

        logger.info("Setting up middleware...")

        # В aiogram 3.x middleware регистрируется по-другому
        # 1. Logging middleware (первый в цепочке)
        logging_middleware = LoggingMiddleware()
        dp.update.middleware(logging_middleware)
        middleware_instances['logging'] = logging_middleware

        # 2. Database middleware
        db_middleware = DatabaseMiddleware()
        dp.update.middleware(db_middleware)
        middleware_instances['database'] = db_middleware

        # 3. User middleware
        user_middleware = UserMiddleware()
        dp.update.middleware(user_middleware)
        middleware_instances['user'] = user_middleware

        # 4. Throttling middleware (последний)
        throttling_middleware = ThrottlingMiddleware()
        dp.message.middleware(throttling_middleware)
        dp.callback_query.middleware(throttling_middleware)
        middleware_instances['throttling'] = throttling_middleware

        logger.info("Middleware setup complete")

    except ImportError as e:
        logger.warning(f"Some middleware modules not found: {e}")
        # Создаем минимальный middleware для работы бота
        try:
            from bot.middleware import BasicMiddleware
            basic_middleware = BasicMiddleware()
            dp.update.middleware(basic_middleware)
            middleware_instances['basic'] = basic_middleware
        except ImportError:
            logger.warning("No middleware configured, bot will work without middleware")

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
        import asyncio
        await asyncio.sleep(exception.retry_after)
        return True

    @dp.error(ExceptionTypeFilter(TelegramBadRequest))
    async def handle_bad_request(event, exception: TelegramBadRequest):
        """Обработка ошибок некорректных запросов."""
        logger.error(f"Bad request: {exception}")

        # Обработка специфичных ошибок
        error_text = str(exception).lower()

        # Игнорируемые ошибки
        ignored_errors = [
            "message is not modified",
            "message to delete not found",
            "query is too old",
            "message can't be deleted for everyone",
            "message to edit not found",
            "callback query id is invalid",
            "message identifier not specified",
            "message to react not found"
        ]

        for ignored in ignored_errors:
            if ignored in error_text:
                logger.debug(f"Ignoring error: {ignored}")
                return True

        return False

    @dp.error(ExceptionTypeFilter(TelegramAPIError))
    async def handle_api_error(event, exception: TelegramAPIError):
        """Обработка общих ошибок Telegram API."""
        logger.error(f"Telegram API error: {exception}")

        # Уведомляем администраторов о критичных ошибках
        if "chat not found" in str(exception).lower():
            logger.warning("User blocked the bot")
            return True

        # Обработка других известных ошибок
        if "bot was blocked by the user" in str(exception).lower():
            logger.warning("Bot was blocked by user")
            return True

        return False

    @dp.error()
    async def handle_all_errors(event, exception: Exception):
        """Обработка всех остальных ошибок."""
        logger.error(
            f"Unhandled error: {type(exception).__name__}: {exception}",
            exc_info=exception
        )

        # Получаем update для детальной информации
        update = event.update

        # Логируем детали update для отладки
        if update.message:
            logger.debug(f"Error in message from user {update.message.from_user.id}")
        elif update.callback_query:
            logger.debug(f"Error in callback from user {update.callback_query.from_user.id}")

        # Пытаемся уведомить пользователя
        try:
            error_message = (
                "😔 Произошла непредвиденная ошибка.\n"
                "Пожалуйста, попробуйте позже или обратитесь в поддержку."
            )

            if hasattr(event.update, 'message') and event.update.message:
                await event.update.message.answer(error_message)
            elif hasattr(event.update, 'callback_query') and event.update.callback_query:
                await event.update.callback_query.answer(
                    "Произошла ошибка. Попробуйте позже.",
                    show_alert=True
                )
        except Exception as e:
            logger.error(f"Failed to notify user about error: {e}")

        # В development режиме пробрасываем ошибку дальше
        try:
            from config import settings
            if hasattr(settings, 'environment') and settings.environment == "development":
                return False
        except ImportError:
            pass

        # В production логируем и продолжаем работу
        return True

    logger.info("Error handlers setup complete")


def create_dispatcher(
    storage: Optional[Union[MemoryStorage, RedisStorage]] = None
) -> Dispatcher:
    """
    Создание и настройка диспетчера.

    Args:
        storage: Хранилище FSM состояний

    Returns:
        Настроенный диспетчер
    """
    # Проверяем настройки для выбора хранилища
    if storage is None:
        try:
            from config import settings

            # Пытаемся использовать Redis если настроен
            if hasattr(settings, 'redis') and hasattr(settings.redis, 'url') and settings.redis.url:
                try:
                    storage = RedisStorage.from_url(settings.redis.url)
                    logger.info("Using RedisStorage for FSM")
                except Exception as e:
                    logger.warning(f"Failed to connect to Redis: {e}")
                    storage = MemoryStorage()
                    logger.info("Falling back to MemoryStorage for FSM")
            else:
                storage = MemoryStorage()
                logger.info("Using MemoryStorage for FSM")
        except ImportError:
            storage = MemoryStorage()
            logger.info("Using MemoryStorage for FSM (no config found)")

    # Создаем диспетчер
    dp = Dispatcher(storage=storage)

    logger.info("Dispatcher created")
    return dp


class HandlersConfig:
    """Конфигурация обработчиков."""

    # Приоритеты роутеров
    ROUTER_PRIORITIES = {
        "admin": 100,        # Максимальный приоритет
        "base": 90,          # Базовые команды
        "tarot": 50,         # Разделы
        "astrology": 50,
        "subscription": 50,
        "profile": 50,
        "settings": 50,
        "common": 10         # Минимальный приоритет
    }

    # Настройки throttling (запросов, секунд)
    THROTTLE_RATES = {
        "default": (5, 60),         # 5 запросов в минуту
        "tarot": (3, 60),           # 3 расклада в минуту
        "astrology": (5, 60),       # 5 запросов астрологии в минуту
        "payment": (10, 3600),      # 10 попыток оплаты в час
        "feedback": (3, 3600),      # 3 отзыва в час
        "profile": (10, 60),        # 10 запросов к профилю в минуту
        "admin": (100, 60)          # 100 запросов в минуту для админов
    }

    # Таймауты в секундах
    TIMEOUTS = {
        "callback_answer": 3,       # Секунды для ответа на callback
        "typing_action": 5,         # Секунды для "печатает..."
        "payment_wait": 300,        # 5 минут на оплату
        "onboarding": 600,          # 10 минут на онбординг
        "spread_selection": 180,    # 3 минуты на выбор расклада
        "birth_data_input": 300     # 5 минут на ввод данных рождения
    }

    # Лимиты
    LIMITS = {
        "free_spreads_daily": 3,           # Бесплатных раскладов в день
        "free_horoscopes_daily": 1,        # Бесплатных гороскопов в день
        "message_length": 4000,            # Максимальная длина сообщения
        "callback_data_length": 64,        # Максимальная длина callback_data
        "saved_spreads_free": 5,           # Сохраненных раскладов для free
        "saved_spreads_premium": 50,       # Сохраненных раскладов для premium
        "history_items_per_page": 10,      # Элементов истории на странице
        "max_file_size": 20 * 1024 * 1024  # Максимальный размер файла (20MB)
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
    # Рекурсивный поиск роутера
    def find_router(router: Router, target_name: str) -> Optional[Router]:
        if hasattr(router, 'name') and router.name == target_name:
            return router

        # В aiogram 3.x роутеры хранятся в _sub_routers
        if hasattr(router, '_sub_routers'):
            for sub_router in router._sub_routers:
                found = find_router(sub_router, target_name)
                if found:
                    return found

        return None

    # Получаем главный роутер диспетчера
    if hasattr(dp, '_router'):
        return find_router(dp._router, name)

    return None


def list_registered_handlers(dp: Dispatcher) -> List[str]:
    """
    Получить список зарегистрированных обработчиков.

    Args:
        dp: Диспетчер

    Returns:
        Список имен роутеров
    """
    routers = []

    def collect_routers(router: Router, prefix: str = ""):
        name = getattr(router, 'name', 'unnamed')
        full_name = f"{prefix}/{name}" if prefix else name
        routers.append(full_name)

        # Собираем вложенные роутеры
        if hasattr(router, '_sub_routers'):
            for sub_router in router._sub_routers:
                collect_routers(sub_router, full_name)

    # Собираем все роутеры
    if hasattr(dp, '_router'):
        collect_routers(dp._router)

    return routers


# Декоратор для регистрации обработчиков
def handler_registry(router_name: str = "main"):
    """
    Декоратор для автоматической регистрации обработчиков.

    Args:
        router_name: Имя роутера для регистрации

    Example:
        @handler_registry("tarot")
        class TarotHandler(BaseHandler):
            pass
    """
    def decorator(handler_class):
        # Регистрируем класс в реестре
        if not hasattr(handler_registry, '_registry'):
            handler_registry._registry = {}

        if router_name not in handler_registry._registry:
            handler_registry._registry[router_name] = []

        handler_registry._registry[router_name].append(handler_class)

        # Добавляем метаданные к классу
        handler_class._router_name = router_name
        handler_class._auto_register = True

        return handler_class

    return decorator


# Инициализация реестра обработчиков
handler_registry._registry = {}


logger.info("Handlers module initialized")