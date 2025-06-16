"""
Middleware компоненты для обработки запросов.

Этот модуль содержит промежуточные обработчики для:
- Логирования всех запросов
- Проверки подписки и прав доступа
- Ограничения частоты запросов
- Управления подключением к БД
- Сбора метрик и статистики
- Обработки ошибок

Автор: AI Assistant
Дата создания: 2024-12-30
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Callable, Dict, Any, Awaitable, Optional
from functools import wraps

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject, User
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramRetryAfter

from infrastructure import get_unit_of_work
from infrastructure.telegram import MessageFactory, MessageStyle
from bot.config.constants import RateLimits

logger = logging.getLogger(__name__)


class LoggingMiddleware(BaseMiddleware):
    """Middleware для логирования всех запросов."""

    async def __call__(
            self,
            handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
            event: TelegramObject,
            data: Dict[str, Any]
    ) -> Any:
        """Логирование входящих запросов."""
        start_time = time.time()

        # Определяем тип события
        if isinstance(event, Message):
            event_type = "message"
            user = event.from_user
            content = event.text or event.content_type
            chat_id = event.chat.id
        elif isinstance(event, CallbackQuery):
            event_type = "callback"
            user = event.from_user
            content = event.data
            chat_id = event.message.chat.id if event.message else None
        else:
            event_type = type(event).__name__
            user = getattr(event, 'from_user', None)
            content = str(event)[:50]
            chat_id = None

        # Логируем начало обработки
        logger.info(
            f"[{event_type.upper()}] "
            f"User: {user.username if user else 'Unknown'} ({user.id if user else 'N/A'}) "
            f"Content: {content}"
        )

        try:
            # Вызываем следующий обработчик
            result = await handler(event, data)

            # Логируем успешное выполнение
            execution_time = time.time() - start_time
            logger.info(
                f"[{event_type.upper()}] Success. "
                f"Time: {execution_time:.3f}s"
            )

            return result

        except Exception as e:
            # Логируем ошибку
            execution_time = time.time() - start_time
            logger.error(
                f"[{event_type.upper()}] Error: {type(e).__name__}: {str(e)}. "
                f"Time: {execution_time:.3f}s",
                exc_info=True
            )
            raise


class DatabaseMiddleware(BaseMiddleware):
    """Middleware для управления подключением к БД."""

    async def __call__(
            self,
            handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
            event: TelegramObject,
            data: Dict[str, Any]
    ) -> Any:
        """Добавляет Unit of Work в контекст."""
        # Создаем UoW и добавляем в data
        async with get_unit_of_work() as uow:
            data['uow'] = uow

            # Если есть пользователь, загружаем его данные
            user = getattr(event, 'from_user', None)
            if user:
                db_user = await uow.users.get_by_telegram_id(user.id)
                if db_user:
                    data['db_user'] = db_user
                    # Обновляем последнюю активность
                    db_user.last_active = datetime.utcnow()
                    await uow.commit()

            return await handler(event, data)


class ThrottlingMiddleware(BaseMiddleware):
    """Middleware для ограничения частоты запросов."""

    def __init__(self):
        self.user_timestamps: Dict[int, Dict[str, list]] = {}
        self.rate_limits = RateLimits()

    async def __call__(
            self,
            handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
            event: TelegramObject,
            data: Dict[str, Any]
    ) -> Any:
        """Проверка лимитов частоты запросов."""
        user = getattr(event, 'from_user', None)
        if not user:
            return await handler(event, data)

        user_id = user.id
        current_time = time.time()

        # Определяем тип действия для лимитов
        action_type = self._get_action_type(event)

        # Получаем лимиты для действия
        limit, window = self._get_rate_limit(action_type)

        # Инициализируем данные пользователя
        if user_id not in self.user_timestamps:
            self.user_timestamps[user_id] = {}

        if action_type not in self.user_timestamps[user_id]:
            self.user_timestamps[user_id][action_type] = []

        # Очищаем старые временные метки
        timestamps = self.user_timestamps[user_id][action_type]
        timestamps[:] = [
            ts for ts in timestamps
            if current_time - ts < window
        ]

        # Проверяем лимит
        if len(timestamps) >= limit:
            # Вычисляем время до следующей попытки
            oldest_timestamp = timestamps[0]
            retry_after = int(window - (current_time - oldest_timestamp))

            logger.warning(
                f"Rate limit exceeded for user {user_id} "
                f"({user.username}). Action: {action_type}"
            )

            # Отвечаем пользователю
            if isinstance(event, CallbackQuery):
                await event.answer(
                    f"Слишком много запросов! "
                    f"Попробуйте через {retry_after} сек.",
                    show_alert=True
                )
            elif isinstance(event, Message):
                await event.answer(
                    f"⚠️ Слишком много запросов!\n"
                    f"Подождите {retry_after} секунд перед следующей попыткой."
                )

            # Не передаем дальше
            return None

        # Добавляем текущую временную метку
        timestamps.append(current_time)

        return await handler(event, data)

    def _get_action_type(self, event: TelegramObject) -> str:
        """Определить тип действия для применения лимитов."""
        if isinstance(event, Message):
            if event.text and event.text.startswith('/'):
                command = event.text.split()[0][1:]
                if command in ['tarot', 'astrology']:
                    return 'feature_command'
                elif command in ['start', 'help', 'menu']:
                    return 'basic_command'
                else:
                    return 'other_command'
            else:
                return 'message'

        elif isinstance(event, CallbackQuery):
            if event.data:
                if event.data.startswith(('tarot_', 'spread_')):
                    return 'tarot_action'
                elif event.data.startswith(('horoscope_', 'natal_')):
                    return 'astrology_action'
                elif event.data.startswith('payment_'):
                    return 'payment_action'
                else:
                    return 'callback'

        return 'other'

    def _get_rate_limit(self, action_type: str) -> tuple[int, int]:
        """Получить лимиты для типа действия."""
        limits = {
            'feature_command': (5, 60),  # 5 в минуту
            'basic_command': (10, 60),  # 10 в минуту
            'tarot_action': (3, 60),  # 3 в минуту
            'astrology_action': (3, 60),  # 3 в минуту
            'payment_action': (5, 300),  # 5 за 5 минут
            'message': (20, 60),  # 20 в минуту
            'callback': (30, 60),  # 30 в минуту
            'other': (15, 60)  # 15 в минуту
        }

        return limits.get(action_type, (15, 60))


class SubscriptionMiddleware(BaseMiddleware):
    """Middleware для проверки подписки."""

    async def __call__(
            self,
            handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
            event: TelegramObject,
            data: Dict[str, Any]
    ) -> Any:
        """Проверка активной подписки и добавление в контекст."""
        user = getattr(event, 'from_user', None)
        if not user:
            return await handler(event, data)

        # Получаем пользователя из БД
        db_user = data.get('db_user')
        if not db_user:
            return await handler(event, data)

        # Проверяем подписку
        uow = data.get('uow')
        if uow:
            subscription = await uow.subscriptions.get_active(db_user.id)
            data['subscription'] = subscription

            # Добавляем уровень подписки
            data['subscription_level'] = db_user.subscription_plan

            # Проверяем, не истекла ли подписка
            if subscription and subscription.end_date < datetime.utcnow():
                # Деактивируем подписку
                subscription.is_active = False
                db_user.subscription_plan = 'free'
                await uow.commit()

                # Уведомляем пользователя
                if isinstance(event, Message):
                    await event.answer(
                        "⚠️ Ваша подписка истекла. "
                        "Некоторые функции могут быть недоступны.\n"
                        "Используйте /subscription для продления."
                    )

        return await handler(event, data)


class MetricsMiddleware(BaseMiddleware):
    """Middleware для сбора метрик."""

    def __init__(self):
        self.metrics = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'commands': {},
            'callbacks': {},
            'response_times': [],
            'users': set(),
            'errors': {}
        }

    async def __call__(
            self,
            handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
            event: TelegramObject,
            data: Dict[str, Any]
    ) -> Any:
        """Сбор метрик использования."""
        start_time = time.time()
        self.metrics['total_requests'] += 1

        # Записываем пользователя
        user = getattr(event, 'from_user', None)
        if user:
            self.metrics['users'].add(user.id)

        # Записываем тип запроса
        if isinstance(event, Message) and event.text:
            if event.text.startswith('/'):
                command = event.text.split()[0]
                self.metrics['commands'][command] = \
                    self.metrics['commands'].get(command, 0) + 1
        elif isinstance(event, CallbackQuery) and event.data:
            callback_prefix = event.data.split(':')[0]
            self.metrics['callbacks'][callback_prefix] = \
                self.metrics['callbacks'].get(callback_prefix, 0) + 1

        try:
            result = await handler(event, data)
            self.metrics['successful_requests'] += 1

            # Записываем время ответа
            response_time = time.time() - start_time
            self.metrics['response_times'].append(response_time)

            # Ограничиваем размер списка
            if len(self.metrics['response_times']) > 1000:
                self.metrics['response_times'] = \
                    self.metrics['response_times'][-1000:]

            return result

        except Exception as e:
            self.metrics['failed_requests'] += 1
            error_type = type(e).__name__
            self.metrics['errors'][error_type] = \
                self.metrics['errors'].get(error_type, 0) + 1
            raise

    def get_metrics(self) -> Dict[str, Any]:
        """Получить собранные метрики."""
        avg_response_time = (
            sum(self.metrics['response_times']) /
            len(self.metrics['response_times'])
            if self.metrics['response_times'] else 0
        )

        return {
            'total_requests': self.metrics['total_requests'],
            'successful_requests': self.metrics['successful_requests'],
            'failed_requests': self.metrics['failed_requests'],
            'success_rate': (
                self.metrics['successful_requests'] /
                self.metrics['total_requests'] * 100
                if self.metrics['total_requests'] > 0 else 0
            ),
            'unique_users': len(self.metrics['users']),
            'average_response_time': avg_response_time,
            'top_commands': sorted(
                self.metrics['commands'].items(),
                key=lambda x: x[1],
                reverse=True
            )[:10],
            'top_callbacks': sorted(
                self.metrics['callbacks'].items(),
                key=lambda x: x[1],
                reverse=True
            )[:10],
            'top_errors': sorted(
                self.metrics['errors'].items(),
                key=lambda x: x[1],
                reverse=True
            )[:5]
        }

    def reset_metrics(self):
        """Сбросить метрики."""
        self.metrics = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'commands': {},
            'callbacks': {},
            'response_times': [],
            'users': set(),
            'errors': {}
        }


class AdminCheckMiddleware(BaseMiddleware):
    """Middleware для проверки прав администратора."""

    async def __call__(
            self,
            handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
            event: TelegramObject,
            data: Dict[str, Any]
    ) -> Any:
        """Проверка админских прав для специфичных команд."""
        # Проверяем только для сообщений с командами
        if isinstance(event, Message) and event.text:
            admin_commands = [
                '/admin', '/broadcast', '/stats', '/users',
                '/system', '/logs', '/backup', '/update'
            ]

            command = event.text.split()[0]
            if command in admin_commands:
                db_user = data.get('db_user')
                if not db_user or not db_user.is_admin:
                    await event.answer(
                        "⛔ У вас нет прав для выполнения этой команды."
                    )
                    logger.warning(
                        f"Unauthorized admin command attempt: "
                        f"{command} by user {event.from_user.id}"
                    )
                    return None

        return await handler(event, data)


class I18nMiddleware(BaseMiddleware):
    """Middleware для интернационализации."""

    async def __call__(
            self,
            handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
            event: TelegramObject,
            data: Dict[str, Any]
    ) -> Any:
        """Установка языка пользователя."""
        db_user = data.get('db_user')

        if db_user:
            # Устанавливаем язык из настроек пользователя
            data['locale'] = db_user.language or 'ru'
        else:
            # Используем язык из Telegram
            user = getattr(event, 'from_user', None)
            if user:
                data['locale'] = user.language_code or 'ru'
            else:
                data['locale'] = 'ru'

        return await handler(event, data)


class ErrorHandlingMiddleware(BaseMiddleware):
    """Middleware для обработки ошибок."""

    async def __call__(
            self,
            handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
            event: TelegramObject,
            data: Dict[str, Any]
    ) -> Any:
        """Обработка необработанных ошибок."""
        try:
            return await handler(event, data)

        except TelegramRetryAfter as e:
            # Обработка превышения лимитов Telegram
            logger.warning(f"Telegram rate limit: retry after {e.retry_after}s")

            if isinstance(event, Message):
                await event.answer(
                    f"⏳ Telegram временно ограничил отправку сообщений.\n"
                    f"Попробуйте через {e.retry_after} секунд."
                )

        except Exception as e:
            # Логируем ошибку
            logger.error(
                f"Unhandled error in middleware: {type(e).__name__}: {str(e)}",
                exc_info=True
            )

            # Пытаемся уведомить пользователя
            try:
                error_message = MessageFactory.create(
                    'critical_error',
                    MessageStyle.HTML
                )

                if isinstance(event, Message):
                    await event.answer(error_message, parse_mode="HTML")
                elif isinstance(event, CallbackQuery):
                    await event.answer(
                        "Произошла ошибка. Попробуйте позже.",
                        show_alert=True
                    )
            except:
                # Если не можем отправить сообщение об ошибке, просто логируем
                logger.error("Failed to send error message to user")


class StateTimeoutMiddleware(BaseMiddleware):
    """Middleware для контроля таймаутов состояний FSM."""

    def __init__(self):
        self.state_timestamps: Dict[int, datetime] = {}

    async def __call__(
            self,
            handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
            event: TelegramObject,
            data: Dict[str, Any]
    ) -> Any:
        """Проверка таймаутов состояний."""
        user = getattr(event, 'from_user', None)
        if not user:
            return await handler(event, data)

        user_id = user.id
        state: FSMContext = data.get('state')

        if state:
            current_state = await state.get_state()

            if current_state:
                # Проверяем таймаут
                if user_id in self.state_timestamps:
                    time_in_state = datetime.utcnow() - self.state_timestamps[user_id]

                    # Импортируем утилиты состояний
                    from bot.states import StateUtils
                    timeout = StateUtils.get_timeout(current_state)

                    if time_in_state.total_seconds() > timeout:
                        # Очищаем состояние
                        await state.clear()

                        # Уведомляем пользователя
                        if isinstance(event, Message):
                            cancel_message = StateUtils.get_cancel_message(current_state)
                            await event.answer(f"⏰ Время ожидания истекло.\n{cancel_message}")

                        # Удаляем временную метку
                        del self.state_timestamps[user_id]

                        return None

                # Обновляем временную метку
                self.state_timestamps[user_id] = datetime.utcnow()
            else:
                # Удаляем временную метку если состояния нет
                if user_id in self.state_timestamps:
                    del self.state_timestamps[user_id]

        return await handler(event, data)


# Экспорт всех middleware
__all__ = [
    'LoggingMiddleware',
    'DatabaseMiddleware',
    'ThrottlingMiddleware',
    'SubscriptionMiddleware',
    'MetricsMiddleware',
    'AdminCheckMiddleware',
    'I18nMiddleware',
    'ErrorHandlingMiddleware',
    'StateTimeoutMiddleware'
]


def setup_middleware(dp):
    """Настройка всех middleware в правильном порядке."""
    # Создаем экземпляры
    logging_middleware = LoggingMiddleware()
    error_middleware = ErrorHandlingMiddleware()
    database_middleware = DatabaseMiddleware()
    throttling_middleware = ThrottlingMiddleware()
    subscription_middleware = SubscriptionMiddleware()
    metrics_middleware = MetricsMiddleware()
    admin_middleware = AdminCheckMiddleware()
    i18n_middleware = I18nMiddleware()
    state_timeout_middleware = StateTimeoutMiddleware()

    # Регистрируем в правильном порядке
    # Сначала обработка ошибок и логирование
    dp.message.middleware(error_middleware)
    dp.callback_query.middleware(error_middleware)

    dp.message.middleware(logging_middleware)
    dp.callback_query.middleware(logging_middleware)

    # Затем метрики
    dp.message.middleware(metrics_middleware)
    dp.callback_query.middleware(metrics_middleware)

    # Проверка частоты запросов
    dp.message.middleware(throttling_middleware)
    dp.callback_query.middleware(throttling_middleware)

    # База данных и пользователь
    dp.message.middleware(database_middleware)
    dp.callback_query.middleware(database_middleware)

    # Подписка и права
    dp.message.middleware(subscription_middleware)
    dp.callback_query.middleware(subscription_middleware)

    dp.message.middleware(admin_middleware)
    dp.callback_query.middleware(admin_middleware)

    # Языки и таймауты
    dp.message.middleware(i18n_middleware)
    dp.callback_query.middleware(i18n_middleware)

    dp.message.middleware(state_timeout_middleware)
    dp.callback_query.middleware(state_timeout_middleware)

    logger.info("All middleware registered successfully")

    return {
        'metrics': metrics_middleware,
        'throttling': throttling_middleware,
        'state_timeout': state_timeout_middleware
    }