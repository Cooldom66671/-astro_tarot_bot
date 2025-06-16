"""
Базовый модуль для всех обработчиков.

Этот модуль содержит:
- Базовые классы обработчиков
- Декораторы для обработки ошибок
- Общие функции проверки доступа
- Логирование действий
- Метрики использования

Автор: AI Assistant
Дата создания: 2024-12-30
"""

import asyncio
import logging
import functools
import time
from typing import Optional, Dict, Any, Callable, Union, List, Type
from datetime import datetime

from aiogram import Router, types
from aiogram.filters import CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest

# Импортируем cache_manager вместо get_cache
from infrastructure.cache import cache_manager
from infrastructure import get_unit_of_work
from core.exceptions import SubscriptionRequiredError

# Настройка логирования
logger = logging.getLogger(__name__)


class CommonMessages:
    """Общие сообщения для пользователей."""
    ERROR_GENERIC = "😔 Произошла ошибка. Попробуйте позже или обратитесь в поддержку."
    SUBSCRIPTION_REQUIRED = "⭐ Эта функция доступна только по подписке.\n\nОформите подписку для доступа ко всем возможностям бота!"
    RATE_LIMIT_EXCEEDED = "⏳ Слишком много запросов. Попробуйте через несколько секунд."
    MAINTENANCE = "🔧 Бот находится на техническом обслуживании. Попробуйте позже."


class BaseHandler:
    """Базовый класс для всех обработчиков."""

    def __init__(self, router: Router):
        """
        Инициализация базового обработчика.

        Args:
            router: Роутер для регистрации обработчиков
        """
        self.router = router
        self.name = self.__class__.__name__

        logger.debug(f"Инициализирован обработчик {self.name}")

    def register_handlers(self) -> None:
        """Регистрация обработчиков. Должен быть переопределен в наследниках."""
        raise NotImplementedError("Метод register_handlers должен быть реализован")

    async def log_action(
            self,
            user_id: int,
            action: str,
            details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Логировать действие пользователя.

        Args:
            user_id: ID пользователя
            action: Название действия
            details: Дополнительные детали
        """
        log_data = {
            "user_id": user_id,
            "action": action,
            "handler": self.name,
            "timestamp": datetime.now().isoformat(),
            "details": details or {}
        }

        logger.info(f"Действие пользователя: {log_data}")

        # Сохраняем в кэш для аналитики
        cache_key = f"user_action:{user_id}:{int(time.time())}"
        await cache_manager.set(cache_key, log_data, ttl=86400)  # 24 часа

    async def check_subscription(
            self,
            user_id: int,
            required_level: str = "basic"
    ) -> bool:
        """
        Проверить уровень подписки пользователя.

        Args:
            user_id: ID пользователя Telegram
            required_level: Требуемый уровень подписки

        Returns:
            True если у пользователя есть нужный уровень подписки
        """
        try:
            async with get_unit_of_work() as uow:
                # Получаем пользователя
                user = await uow.users.get_by_telegram_id(user_id)
                if not user:
                    return False

                # Получаем активную подписку
                subscription = await uow.subscriptions.get_active_by_user_id(user.id)
                if not subscription:
                    return False

                # Проверяем уровень
                return subscription.check_access_level(required_level)

        except Exception as e:
            logger.error(f"Ошибка проверки подписки: {e}")
            return False

    async def send_typing_action(
            self,
            chat_id: Union[int, str]
    ) -> None:
        """
        Отправить действие "печатает".

        Args:
            chat_id: ID чата
        """
        try:
            from aiogram import Bot
            bot = Bot.get_current()
            await bot.send_chat_action(chat_id, action="typing")
        except Exception as e:
            logger.debug(f"Не удалось отправить typing action: {e}")

    async def get_user_language(self, user_id: int) -> str:
        """
        Получить язык пользователя.

        Args:
            user_id: ID пользователя

        Returns:
            Код языка (ru, en и т.д.)
        """
        try:
            # Сначала проверяем кэш
            cache_key = f"user_lang:{user_id}"
            cached_lang = await cache_manager.get(cache_key)
            if cached_lang:
                return cached_lang

            # Если нет в кэше, получаем из БД
            async with get_unit_of_work() as uow:
                user = await uow.users.get_by_telegram_id(user_id)
                if user and user.language_code:
                    # Сохраняем в кэш
                    await cache_manager.set(cache_key, user.language_code, ttl=3600)
                    return user.language_code

            return "ru"  # По умолчанию русский

        except Exception as e:
            logger.error(f"Ошибка получения языка пользователя: {e}")
            return "ru"


# Декораторы

def error_handler(send_message: bool = True):
    """
    Декоратор для обработки ошибок в обработчиках.

    Args:
        send_message: Отправлять ли сообщение об ошибке пользователю
    """

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Находим объект message или callback_query
            message = None
            callback_query = None

            # self может быть первым аргументом если это метод класса
            start_index = 1 if args and hasattr(args[0], '__class__') else 0

            for arg in args[start_index:]:
                if isinstance(arg, types.Message):
                    message = arg
                    break
                elif isinstance(arg, types.CallbackQuery):
                    callback_query = arg
                    message = arg.message
                    break

            try:
                return await func(*args, **kwargs)

            except TelegramBadRequest as e:
                logger.error(f"Telegram API ошибка в {func.__name__}: {e}")

                if send_message and message:
                    error_text = "❌ Произошла ошибка при отправке сообщения"
                    if callback_query:
                        await callback_query.answer(error_text, show_alert=True)
                    elif message:
                        await message.answer(error_text)

            except SubscriptionRequiredError:
                if send_message and message:
                    if callback_query:
                        await callback_query.answer(
                            "⭐ Требуется подписка",
                            show_alert=True
                        )
                    else:
                        await message.answer(CommonMessages.SUBSCRIPTION_REQUIRED)

            except Exception as e:
                logger.error(f"Ошибка в {func.__name__}: {e}", exc_info=True)

                if send_message and message:
                    error_text = CommonMessages.ERROR_GENERIC
                    if callback_query:
                        await callback_query.answer(
                            "❌ Произошла ошибка",
                            show_alert=True
                        )
                    elif message:
                        await message.answer(error_text)

        return wrapper

    return decorator


def require_subscription(level: str = "basic"):
    """
    Декоратор для проверки подписки.

    Args:
        level: Требуемый уровень подписки
    """

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(self, message: types.Message, *args, **kwargs):
            user_id = message.from_user.id

            # Проверяем подписку
            has_access = await self.check_subscription(user_id, level)

            if not has_access:
                await message.answer(CommonMessages.SUBSCRIPTION_REQUIRED)
                # Можно также предложить оформить подписку
                from infrastructure.telegram.keyboards import Keyboards
                keyboard = Keyboards.subscription_offer()
                await message.answer(
                    "Выберите подходящий тарифный план:",
                    reply_markup=keyboard
                )
                return

            return await func(self, message, *args, **kwargs)

        return wrapper

    return decorator


def log_action(action_name: str):
    """
    Декоратор для логирования действий.

    Args:
        action_name: Название действия для логов
    """

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(self, *args, **kwargs):
            # Находим user_id
            user_id = None

            for arg in args:
                if isinstance(arg, types.Message):
                    user_id = arg.from_user.id
                    break
                elif isinstance(arg, types.CallbackQuery):
                    user_id = arg.from_user.id
                    break

            # Логируем начало
            start_time = time.time()

            try:
                result = await func(self, *args, **kwargs)

                # Логируем успешное выполнение
                if user_id and hasattr(self, 'log_action'):
                    await self.log_action(
                        user_id,
                        action_name,
                        {
                            "status": "success",
                            "duration": time.time() - start_time
                        }
                    )

                return result

            except Exception as e:
                # Логируем ошибку
                if user_id and hasattr(self, 'log_action'):
                    await self.log_action(
                        user_id,
                        action_name,
                        {
                            "status": "error",
                            "error": str(e),
                            "duration": time.time() - start_time
                        }
                    )
                raise

        return wrapper

    return decorator


def check_rate_limit(max_calls: int = 10, period: int = 60):
    """
    Декоратор для проверки rate limit.

    Args:
        max_calls: Максимум вызовов
        period: Период в секундах
    """

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(self, *args, **kwargs):
            # Находим user_id
            user_id = None
            message = None

            for arg in args:
                if isinstance(arg, types.Message):
                    user_id = arg.from_user.id
                    message = arg
                    break
                elif isinstance(arg, types.CallbackQuery):
                    user_id = arg.from_user.id
                    message = arg.message
                    break

            if not user_id:
                return await func(self, *args, **kwargs)

            # Проверяем rate limit
            cache_key = f"rate_limit:{func.__name__}:{user_id}"
            current_count = await cache_manager.get(cache_key) or 0

            if current_count >= max_calls:
                if message:
                    await message.answer(CommonMessages.RATE_LIMIT_EXCEEDED)
                return

            # Увеличиваем счетчик
            await cache_manager.set(
                cache_key,
                current_count + 1,
                ttl=period
            )

            return await func(self, *args, **kwargs)

        return wrapper

    return decorator


# Общие функции для обработчиков

async def get_or_create_user(telegram_user: types.User) -> Any:
    """
    Получить или создать пользователя в БД.

    Args:
        telegram_user: Объект пользователя Telegram

    Returns:
        Объект пользователя из БД
    """
    async with get_unit_of_work() as uow:
        # Пробуем найти пользователя
        user = await uow.users.get_by_telegram_id(telegram_user.id)

        if not user:
            # Создаем нового пользователя
            from core.entities import User
            from datetime import datetime

            user = User(
                telegram_id=telegram_user.id,
                username=telegram_user.username,
                first_name=telegram_user.first_name,
                last_name=telegram_user.last_name,
                language_code=telegram_user.language_code or "ru",
                created_at=datetime.now(),
                is_active=True
            )

            user = await uow.users.create(user)
            await uow.commit()

        return user


async def answer_callback_query(
        callback_query: types.CallbackQuery,
        text: Optional[str] = None,
        show_alert: bool = False
) -> None:
    """
    Ответить на callback query с обработкой ошибок.

    Args:
        callback_query: Callback query
        text: Текст ответа
        show_alert: Показывать как alert
    """
    try:
        await callback_query.answer(text, show_alert=show_alert)
    except TelegramBadRequest as e:
        # Callback query уже устарел
        logger.debug(f"Callback query устарел: {e}")


async def edit_or_send_message(
        message: types.Message,
        text: str,
        reply_markup: Optional[Any] = None,
        parse_mode: Optional[str] = None,
        **kwargs
) -> types.Message:
    """
    Редактировать сообщение или отправить новое.

    Args:
        message: Сообщение
        text: Новый текст
        reply_markup: Клавиатура
        parse_mode: Режим парсинга
        **kwargs: Дополнительные параметры

    Returns:
        Отправленное/отредактированное сообщение
    """
    try:
        # Пробуем отредактировать
        return await message.edit_text(
            text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
            **kwargs
        )
    except TelegramBadRequest:
        # Не можем редактировать - отправляем новое
        return await message.answer(
            text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
            **kwargs
        )


async def delete_message_safe(message: types.Message) -> bool:
    """
    Безопасно удалить сообщение.

    Args:
        message: Сообщение для удаления

    Returns:
        True если удалено успешно
    """
    try:
        await message.delete()
        return True
    except TelegramBadRequest:
        return False


async def send_long_message(
        message: types.Message,
        text: str,
        parse_mode: Optional[str] = None,
        chunk_size: int = 4000
) -> List[types.Message]:
    """
    Отправить длинное сообщение, разбив на части.

    Args:
        message: Исходное сообщение
        text: Текст для отправки
        parse_mode: Режим парсинга
        chunk_size: Размер одного куска

    Returns:
        Список отправленных сообщений
    """
    messages = []

    # Разбиваем текст на части
    for i in range(0, len(text), chunk_size):
        chunk = text[i:i + chunk_size]

        # Убеждаемся, что не обрезаем посреди слова
        if i + chunk_size < len(text) and not text[i + chunk_size].isspace():
            last_space = chunk.rfind(' ')
            if last_space > 0:
                chunk = chunk[:last_space]
                i -= (chunk_size - last_space)

        sent_message = await message.answer(chunk, parse_mode=parse_mode)
        messages.append(sent_message)

        # Небольшая задержка между сообщениями
        if i + chunk_size < len(text):
            await asyncio.sleep(0.1)

    return messages


# Класс для группировки обработчиков
class HandlerGroup:
    """Группа связанных обработчиков."""

    def __init__(self, router: Router, prefix: str):
        """
        Инициализация группы.

        Args:
            router: Роутер
            prefix: Префикс для логов
        """
        self.router = router
        self.prefix = prefix
        self.handlers: List[BaseHandler] = []

    def add_handler(self, handler_class: Type[BaseHandler]) -> None:
        """Добавить обработчик в группу."""
        handler = handler_class(self.router)
        handler.register_handlers()
        self.handlers.append(handler)

        logger.info(f"Зарегистрирован обработчик {handler.name} в группе {self.prefix}")

    def get_stats(self) -> Dict[str, Any]:
        """Получить статистику группы."""
        return {
            "total_handlers": len(self.handlers),
            "handlers": [h.name for h in self.handlers],
            "prefix": self.prefix
        }


# Дополнительные утилиты
async def is_user_admin(user_id: int) -> bool:
    """
    Проверить, является ли пользователь администратором.

    Args:
        user_id: ID пользователя

    Returns:
        True если пользователь администратор
    """
    from config import settings
    return user_id in settings.bot.admin_ids


async def is_user_blocked_bot(user_id: int) -> bool:
    """
    Проверить, заблокировал ли пользователь бота.

    Args:
        user_id: ID пользователя

    Returns:
        True если пользователь заблокировал бота
    """
    try:
        from aiogram import Bot
        bot = Bot.get_current()
        await bot.send_chat_action(user_id, action="typing")
        return False
    except TelegramBadRequest as e:
        if "chat not found" in str(e).lower():
            return True
        return False


logger.info("Модуль базовых обработчиков загружен")