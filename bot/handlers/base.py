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

import logging
import functools
import time
from typing import Optional, Dict, Any, Callable, Union
from datetime import datetime

from aiogram import Router, types
from aiogram.filters import CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest

from infrastructure import get_unit_of_work, get_cache, CommonMessages
from infrastructure.telegram import MessageBuilder

# Настройка логирования
logger = logging.getLogger(__name__)


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
        await get_cache().set(cache_key, log_data, ttl=86400)  # 24 часа

    async def check_subscription(
            self,
            user_id: int,
            required_level: str = "basic"
    ) -> bool:
        """
        Проверить уровень подписки пользователя.

        Args:
            user_id: ID пользователя
            required_level: Требуемый уровень подписки

        Returns:
            True если подписка подходит
        """
        async with get_unit_of_work() as uow:
            user = await uow.users.get_by_telegram_id(user_id)
            if not user:
                return False

            subscription = await uow.users.get_active_subscription(user.id)
            if not subscription:
                return required_level == "free"

            # Проверка уровня подписки
            levels = ["free", "basic", "premium", "vip"]
            user_level_index = levels.index(subscription.plan)
            required_level_index = levels.index(required_level)

            return user_level_index >= required_level_index

    async def increment_usage(
            self,
            user_id: int,
            feature: str
    ) -> bool:
        """
        Увеличить счетчик использования функции.

        Args:
            user_id: ID пользователя
            feature: Название функции

        Returns:
            True если лимит не превышен
        """
        async with get_unit_of_work() as uow:
            user = await uow.users.get_by_telegram_id(user_id)
            if not user:
                return False

            # Проверяем и увеличиваем счетчик
            can_use = await uow.users.increment_reading_count(
                user.id,
                feature
            )

            return can_use


# Декораторы для обработчиков
def error_handler(send_message: bool = True):
    """
    Декоратор для обработки ошибок в хендлерах.

    Args:
        send_message: Отправлять ли сообщение об ошибке пользователю
    """

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(self, *args, **kwargs):
            # Находим объект message или callback_query
            message = None
            callback_query = None

            for arg in args:
                if isinstance(arg, types.Message):
                    message = arg
                    break
                elif isinstance(arg, types.CallbackQuery):
                    callback_query = arg
                    message = arg.message
                    break

            try:
                return await func(self, *args, **kwargs)

            except TelegramBadRequest as e:
                logger.error(f"Telegram API ошибка в {func.__name__}: {e}")

                if send_message and message:
                    error_text = "❌ Произошла ошибка при отправке сообщения"
                    if callback_query:
                        await callback_query.answer(error_text, show_alert=True)
                    else:
                        await message.answer(error_text)

            except Exception as e:
                logger.error(f"Ошибка в {func.__name__}: {e}", exc_info=True)

                if send_message and message:
                    error_text = CommonMessages.ERROR_GENERIC
                    if callback_query:
                        await callback_query.answer(
                            "❌ Произошла ошибка",
                            show_alert=True
                        )
                    else:
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
                if user_id:
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
                if user_id:
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
            current_count = await get_cache().get(cache_key) or 0

            if current_count >= max_calls:
                if message:
                    await message.answer(
                        f"⏳ Слишком много запросов. Попробуйте через {period} секунд."
                    )
                return

            # Увеличиваем счетчик
            await get_cache().set(
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
            user = await uow.users.create_or_update_from_telegram(
                telegram_user.id,
                telegram_user.username,
                telegram_user.first_name,
                telegram_user.last_name,
                telegram_user.language_code
            )

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
    except TelegramBadRequest:
        # Callback query уже устарел
        pass


async def edit_or_send_message(
        message: types.Message,
        text: str,
        reply_markup: Optional[Any] = None,
        **kwargs
) -> types.Message:
    """
    Редактировать сообщение или отправить новое.

    Args:
        message: Сообщение
        text: Новый текст
        reply_markup: Клавиатура
        **kwargs: Дополнительные параметры

    Returns:
        Отправленное/отредактированное сообщение
    """
    try:
        # Пробуем отредактировать
        return await message.edit_text(
            text,
            reply_markup=reply_markup,
            **kwargs
        )
    except TelegramBadRequest:
        # Не можем редактировать - отправляем новое
        return await message.answer(
            text,
            reply_markup=reply_markup,
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

    def add_handler(self, handler_class: type) -> None:
        """Добавить обработчик в группу."""
        handler = handler_class(self.router)
        handler.register_handlers()
        self.handlers.append(handler)

        logger.info(f"Зарегистрирован обработчик {handler.name} в группе {self.prefix}")

    def get_stats(self) -> Dict[str, int]:
        """Получить статистику группы."""
        return {
            "total_handlers": len(self.handlers),
            "handlers": [h.name for h in self.handlers]
        }


logger.info("Модуль базовых обработчиков загружен")