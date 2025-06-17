"""
Middleware для обработки сообщений и событий бота.

Этот модуль содержит:
- Базовые middleware для логирования и обработки ошибок
- Проверку прав доступа и подписок
- Ограничение частоты запросов (throttling)
- Сбор метрик и статистики
- Интернационализацию

Автор: AI Assistant
Дата создания: 2024-12-30
"""

import logging
import time
from typing import Callable, Dict, Any, Optional, Awaitable, TypeVar, cast
from datetime import datetime, timedelta
from collections import defaultdict

from aiogram import BaseMiddleware
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineQuery,
    TelegramObject,
    User,
    Update
)
from aiogram.dispatcher.event.handler import HandlerObject
from aiogram.exceptions import TelegramBadRequest

from infrastructure import get_unit_of_work
from config import settings
from infrastructure.telegram import Keyboards

logger = logging.getLogger(__name__)

# Type alias для обработчика
T = TypeVar('T')
Handler = Callable[[T, Dict[str, Any]], Awaitable[Any]]


class LoggingMiddleware(BaseMiddleware):
    """Middleware для логирования всех событий."""

    async def __call__(
            self,
            handler: Handler[TelegramObject],
            event: TelegramObject,
            data: Dict[str, Any]
    ) -> Any:
        """Логирование входящих событий и времени обработки."""
        start_time = time.time()

        # Определяем тип события
        event_type = event.__class__.__name__.lower()

        # Получаем информацию о пользователе
        user: Optional[User] = None
        if isinstance(event, Update):
            # Извлекаем пользователя из Update
            if event.message:
                user = event.message.from_user
            elif event.callback_query:
                user = event.callback_query.from_user
            elif event.inline_query:
                user = event.inline_query.from_user
        elif hasattr(event, 'from_user'):
            user = event.from_user

        # Логируем начало обработки
        user_info = f"User {user.id} (@{user.username})" if user else "Unknown user"

        # Детали события
        event_details = self._get_event_details(event)

        logger.info(
            f"[{event_type.upper()}] {user_info}: {event_details}"
        )

        try:
            # Вызываем обработчик
            result = await handler(event, data)

            # Логируем успешное выполнение
            execution_time = time.time() - start_time
            logger.info(
                f"[{event_type.upper()}] Processed successfully. "
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

    def _get_event_details(self, event: TelegramObject) -> str:
        """Получить детали события для логирования."""
        if isinstance(event, Message):
            if event.text:
                return f"Text: {event.text[:50]}..."
            elif event.photo:
                return "Photo message"
            elif event.document:
                return "Document message"
            else:
                return "Other message"
        elif isinstance(event, CallbackQuery):
            return f"Callback: {event.data}"
        elif isinstance(event, InlineQuery):
            return f"Inline: {event.query}"
        elif isinstance(event, Update):
            # Для Update рекурсивно получаем детали вложенного события
            if event.message:
                return self._get_event_details(event.message)
            elif event.callback_query:
                return self._get_event_details(event.callback_query)
            elif event.inline_query:
                return self._get_event_details(event.inline_query)
        return "Unknown event"


class DatabaseMiddleware(BaseMiddleware):
    """Middleware для управления подключением к БД."""

    async def __call__(
            self,
            handler: Handler[TelegramObject],
            event: TelegramObject,
            data: Dict[str, Any]
    ) -> Any:
        """Добавляет Unit of Work в контекст."""
        # Создаем UoW и добавляем в data
        async with get_unit_of_work() as uow:
            data['uow'] = uow

            # Извлекаем пользователя из события
            user = self._extract_user(event)
            if user:
                db_user = await uow.users.get_by_telegram_id(user.id)
                if db_user:
                    data['db_user'] = db_user
                    # Обновляем последнюю активность
                    db_user.last_active_at = datetime.utcnow()
                    await uow.users.update(db_user.id, last_active_at=db_user.last_active_at)
                    await uow.commit()

            return await handler(event, data)

    def _extract_user(self, event: TelegramObject) -> Optional[User]:
        """Извлечь пользователя из события."""
        if isinstance(event, Update):
            if event.message:
                return event.message.from_user
            elif event.callback_query:
                return event.callback_query.from_user
            elif event.inline_query:
                return event.inline_query.from_user
        elif hasattr(event, 'from_user'):
            return event.from_user
        return None


class ThrottlingMiddleware(BaseMiddleware):
    """Middleware для ограничения частоты запросов."""

    # Определяем лимиты прямо в классе
    RATE_LIMITS = {
        'feature_command': (5, 60),    # 5 в минуту
        'basic_command': (10, 60),      # 10 в минуту
        'tarot_action': (3, 60),        # 3 в минуту
        'astrology_action': (3, 60),    # 3 в минуту
        'payment_action': (5, 300),     # 5 за 5 минут
        'message': (20, 60),            # 20 в минуту
        'callback': (30, 60),           # 30 в минуту
        'other': (15, 60)               # 15 в минуту
    }

    def __init__(self):
        self.user_timestamps: Dict[int, Dict[str, list]] = {}

    async def __call__(
            self,
            handler: Handler[TelegramObject],
            event: TelegramObject,
            data: Dict[str, Any]
    ) -> Any:
        """Проверка лимитов частоты запросов."""
        # Получаем пользователя
        user = self._extract_user(event)
        if not user:
            return await handler(event, data)

        user_id = user.id

        # Проверяем премиум пользователей (удвоенные лимиты)
        is_premium = data.get('subscription_level', 'free') != 'free'

        # Определяем тип действия
        action_type = self._get_action_type(event)
        limit, window = self._get_rate_limit(action_type, is_premium)

        # Проверяем лимит
        current_time = time.time()

        if user_id not in self.user_timestamps:
            self.user_timestamps[user_id] = {}

        if action_type not in self.user_timestamps[user_id]:
            self.user_timestamps[user_id][action_type] = []

        # Очищаем старые временные метки
        self.user_timestamps[user_id][action_type] = [
            ts for ts in self.user_timestamps[user_id][action_type]
            if current_time - ts < window
        ]

        # Проверяем превышение лимита
        if len(self.user_timestamps[user_id][action_type]) >= limit:
            # Считаем время до следующей возможности
            oldest_timestamp = min(self.user_timestamps[user_id][action_type])
            wait_time = int(window - (current_time - oldest_timestamp))

            # Отвечаем об ограничении
            message = (
                f"⚠️ Слишком много запросов!\n"
                f"Подождите {wait_time} секунд перед следующим действием."
            )

            if isinstance(event, Message):
                await event.answer(message)
            elif isinstance(event, CallbackQuery):
                await event.answer(message, show_alert=True)

            logger.warning(
                f"Rate limit exceeded for user {user_id} "
                f"({action_type}: {len(self.user_timestamps[user_id][action_type])}/{limit})"
            )

            return None

        # Добавляем временную метку
        self.user_timestamps[user_id][action_type].append(current_time)

        return await handler(event, data)

    def _extract_user(self, event: TelegramObject) -> Optional[User]:
        """Извлечь пользователя из события."""
        if isinstance(event, (Message, CallbackQuery, InlineQuery)):
            return event.from_user
        elif isinstance(event, Update):
            if event.message:
                return event.message.from_user
            elif event.callback_query:
                return event.callback_query.from_user
            elif event.inline_query:
                return event.inline_query.from_user
        return None

    def _get_action_type(self, event: TelegramObject) -> str:
        """Определить тип действия для лимитов."""
        if isinstance(event, Message) and event.text:
            command = event.text.split()[0]

            # Команды с особыми лимитами
            feature_commands = ['/tarot', '/horoscope', '/natal', '/compatibility']
            if command in feature_commands:
                return 'feature_command'

            # Платежные команды
            payment_commands = ['/pay', '/subscription', '/premium']
            if command in payment_commands:
                return 'payment_action'

            # Обычные команды
            if command.startswith('/'):
                return 'basic_command'

            return 'message'

        elif isinstance(event, CallbackQuery) and event.data:
            # Callback actions
            if event.data.startswith('tarot:'):
                return 'tarot_action'
            elif event.data.startswith('astrology:'):
                return 'astrology_action'
            elif event.data.startswith(('pay:', 'subscription:')):
                return 'payment_action'

            return 'callback'

        return 'other'

    def _get_rate_limit(self, action_type: str, is_premium: bool) -> tuple:
        """Получить лимиты для типа действия."""
        limit, window = self.RATE_LIMITS.get(action_type, (15, 60))

        # Удваиваем лимиты для премиум пользователей
        if is_premium:
            limit *= 2

        return limit, window


class SubscriptionMiddleware(BaseMiddleware):
    """Middleware для проверки подписки."""

    async def __call__(
            self,
            handler: Handler[TelegramObject],
            event: TelegramObject,
            data: Dict[str, Any]
    ) -> Any:
        """Проверка активной подписки и добавление в контекст."""
        user = self._extract_user(event)
        if not user:
            return await handler(event, data)

        # Получаем пользователя из БД
        db_user = data.get('db_user')
        if not db_user:
            return await handler(event, data)

        # Проверяем подписку
        uow = data.get('uow')
        if uow:
            subscription = await uow.subscriptions.get_active_by_user_id(db_user.id)
            data['subscription'] = subscription

            # Добавляем уровень подписки
            data['subscription_level'] = db_user.subscription_plan if hasattr(db_user, 'subscription_plan') else 'free'

            # Проверяем, не истекла ли подписка
            if subscription and hasattr(subscription, 'end_date') and subscription.end_date < datetime.utcnow():
                # Деактивируем подписку
                subscription.is_active = False
                db_user.subscription_plan = 'free'
                await uow.users.update(db_user.id, subscription_plan='free')
                await uow.subscriptions.update(subscription.id, is_active=False)
                await uow.commit()

                # Уведомляем пользователя
                if isinstance(event, Message):
                    await event.answer(
                        "⚠️ Ваша подписка истекла. "
                        "Некоторые функции могут быть недоступны.\n"
                        "Используйте /subscription для продления."
                    )

        return await handler(event, data)

    def _extract_user(self, event: TelegramObject) -> Optional[User]:
        """Извлечь пользователя из события."""
        if isinstance(event, (Message, CallbackQuery, InlineQuery)):
            return event.from_user
        elif isinstance(event, Update):
            if event.message:
                return event.message.from_user
            elif event.callback_query:
                return event.callback_query.from_user
            elif event.inline_query:
                return event.inline_query.from_user
        return None


class MetricsMiddleware(BaseMiddleware):
    """Middleware для сбора метрик."""

    def __init__(self):
        self.metrics = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'commands': defaultdict(int),
            'callbacks': defaultdict(int),
            'response_times': [],
            'users': set(),
            'errors': defaultdict(int)
        }

    async def __call__(
            self,
            handler: Handler[TelegramObject],
            event: TelegramObject,
            data: Dict[str, Any]
    ) -> Any:
        """Сбор метрик использования."""
        start_time = time.time()
        self.metrics['total_requests'] += 1

        # Получаем пользователя
        user = self._extract_user(event)
        if user:
            self.metrics['users'].add(user.id)

        # Определяем тип события
        if isinstance(event, Message) and event.text and event.text.startswith('/'):
            command = event.text.split()[0]
            self.metrics['commands'][command] += 1
        elif isinstance(event, CallbackQuery) and event.data:
            callback_prefix = event.data.split(':')[0]
            self.metrics['callbacks'][callback_prefix] += 1

        try:
            # Вызываем обработчик
            result = await handler(event, data)

            # Записываем успех
            self.metrics['successful_requests'] += 1

            # Записываем время выполнения
            execution_time = time.time() - start_time
            self.metrics['response_times'].append(execution_time)

            # Ограничиваем размер списка времен
            if len(self.metrics['response_times']) > 1000:
                self.metrics['response_times'] = self.metrics['response_times'][-1000:]

            return result

        except Exception as e:
            # Записываем ошибку
            self.metrics['failed_requests'] += 1
            error_type = type(e).__name__
            self.metrics['errors'][error_type] += 1
            raise

    def _extract_user(self, event: TelegramObject) -> Optional[User]:
        """Извлечь пользователя из события."""
        if isinstance(event, (Message, CallbackQuery, InlineQuery)):
            return event.from_user
        elif isinstance(event, Update):
            if event.message:
                return event.message.from_user
            elif event.callback_query:
                return event.callback_query.from_user
            elif event.inline_query:
                return event.inline_query.from_user
        return None

    def get_metrics(self) -> Dict[str, Any]:
        """Получить текущие метрики."""
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
            'commands': defaultdict(int),
            'callbacks': defaultdict(int),
            'response_times': [],
            'users': set(),
            'errors': defaultdict(int)
        }


class AdminCheckMiddleware(BaseMiddleware):
    """Middleware для проверки прав администратора."""

    async def __call__(
            self,
            handler: Handler[TelegramObject],
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
                user = event.from_user
                # Проверяем по списку админов из конфига
                if user.id not in settings.bot.admin_ids:
                    await event.answer(
                        "⛔ У вас нет прав для выполнения этой команды."
                    )
                    logger.warning(
                        f"Unauthorized admin command attempt: "
                        f"{command} by user {user.id}"
                    )
                    return None

        return await handler(event, data)


class I18nMiddleware(BaseMiddleware):
    """Middleware для интернационализации."""

    def __init__(self):
        self.translations = {
            'ru': {},  # Русский по умолчанию
            'en': {
                'welcome': 'Welcome!',
                'menu': 'Menu',
                'back': 'Back',
                'cancel': 'Cancel',
                'error': 'Error occurred',
                'success': 'Success!',
                'loading': 'Loading...',
                'premium_required': 'Premium subscription required',
                'rate_limit': 'Too many requests. Please wait.'
            }
        }

    async def __call__(
            self,
            handler: Handler[TelegramObject],
            event: TelegramObject,
            data: Dict[str, Any]
    ) -> Any:
        """Добавление функций перевода в контекст."""
        # Получаем язык пользователя
        user = self._extract_user(event)
        language_code = 'ru'  # По умолчанию русский

        if user:
            # Из настроек пользователя
            db_user = data.get('db_user')
            if db_user and hasattr(db_user, 'language'):
                language_code = db_user.language
            # Или из языка Telegram
            elif hasattr(user, 'language_code') and user.language_code:
                # Берем только первые 2 символа (en_US -> en)
                language_code = user.language_code[:2]

        # Функция перевода
        def _(key: str, **kwargs) -> str:
            """Получить перевод по ключу."""
            translations = self.translations.get(language_code, {})
            text = translations.get(key, key)

            # Подставляем параметры
            if kwargs:
                try:
                    text = text.format(**kwargs)
                except KeyError:
                    pass

            return text

        # Добавляем в контекст
        data['_'] = _
        data['language_code'] = language_code

        return await handler(event, data)

    def _extract_user(self, event: TelegramObject) -> Optional[User]:
        """Извлечь пользователя из события."""
        if isinstance(event, (Message, CallbackQuery, InlineQuery)):
            return event.from_user
        elif isinstance(event, Update):
            if event.message:
                return event.message.from_user
            elif event.callback_query:
                return event.callback_query.from_user
            elif event.inline_query:
                return event.inline_query.from_user
        return None


class ErrorHandlingMiddleware(BaseMiddleware):
    """Middleware для обработки ошибок."""

    async def __call__(
            self,
            handler: Handler[TelegramObject],
            event: TelegramObject,
            data: Dict[str, Any]
    ) -> Any:
        """Обработка ошибок с уведомлением пользователя."""
        try:
            return await handler(event, data)

        except TelegramBadRequest as e:
            # Ошибки Telegram API
            logger.error(f"Telegram API error: {e}")

            error_messages = {
                "message is not modified": "Сообщение не изменилось",
                "message to delete not found": "Сообщение уже удалено",
                "message can't be deleted": "Невозможно удалить сообщение",
                "query is too old": "Запрос устарел",
                "bot was blocked by the user": "Бот заблокирован пользователем"
            }

            # Ищем подходящее сообщение
            user_message = "Произошла ошибка при обработке запроса"
            for error_key, message in error_messages.items():
                if error_key in str(e).lower():
                    user_message = message
                    break

            # Уведомляем пользователя
            if isinstance(event, CallbackQuery):
                await event.answer(f"❌ {user_message}", show_alert=True)
            elif isinstance(event, Message):
                await event.answer(f"❌ {user_message}")

        except Exception as e:
            # Другие ошибки
            logger.error(f"Unhandled error: {type(e).__name__}: {e}", exc_info=True)

            # Уведомляем пользователя
            error_message = (
                "❌ Произошла непредвиденная ошибка.\n"
                "Попробуйте повторить действие позже.\n\n"
                "Если ошибка повторяется, обратитесь в поддержку: /help"
            )

            try:
                if isinstance(event, CallbackQuery):
                    await event.answer("❌ Произошла ошибка", show_alert=True)
                    if event.message:
                        await event.message.answer(error_message)
                elif isinstance(event, Message):
                    await event.answer(error_message)
            except:
                # Если не удалось отправить сообщение об ошибке
                pass

            # Уведомляем админов о критических ошибках
            if settings.bot.developer_id and hasattr(data, 'bot'):
                try:
                    bot = data['bot']
                    error_report = (
                        f"🚨 <b>Критическая ошибка</b>\n\n"
                        f"<b>Тип:</b> <code>{type(e).__name__}</code>\n"
                        f"<b>Сообщение:</b> <code>{str(e)}</code>\n"
                        f"<b>Пользователь:</b> {self._get_user_info(event)}\n"
                        f"<b>Время:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                    )
                    await bot.send_message(
                        settings.bot.developer_id,
                        error_report,
                        parse_mode="HTML"
                    )
                except:
                    pass

    def _get_user_info(self, event: TelegramObject) -> str:
        """Получить информацию о пользователе для отчета."""
        user = None
        if isinstance(event, (Message, CallbackQuery, InlineQuery)):
            user = event.from_user
        elif isinstance(event, Update):
            if event.message:
                user = event.message.from_user
            elif event.callback_query:
                user = event.callback_query.from_user

        if user:
            return f"{user.id} (@{user.username})"
        return "Unknown"


class StateTimeoutMiddleware(BaseMiddleware):
    """Middleware для автоматического сброса состояний по таймауту."""

    def __init__(self, timeout_minutes: int = 30):
        self.timeout = timedelta(minutes=timeout_minutes)
        self.state_timestamps: Dict[int, datetime] = {}

    async def __call__(
            self,
            handler: Handler[TelegramObject],
            event: TelegramObject,
            data: Dict[str, Any]
    ) -> Any:
        """Проверка и сброс устаревших состояний."""
        # Получаем пользователя
        user = self._extract_user(event)
        if not user:
            return await handler(event, data)

        user_id = user.id
        current_time = datetime.utcnow()

        # Проверяем состояние
        fsm_context = data.get('state')
        if fsm_context:
            current_state = await fsm_context.get_state()

            if current_state:
                # Проверяем таймаут
                if user_id in self.state_timestamps:
                    last_activity = self.state_timestamps[user_id]
                    if current_time - last_activity > self.timeout:
                        # Сбрасываем состояние
                        await fsm_context.clear()

                        # Уведомляем пользователя
                        if isinstance(event, Message):
                            keyboard = await Keyboards.main_menu()
                            await event.answer(
                                "⏰ Время сессии истекло.\n"
                                "Пожалуйста, начните заново.",
                                reply_markup=keyboard
                            )

                        # Удаляем временную метку
                        del self.state_timestamps[user_id]

                        return None

                # Обновляем временную метку
                self.state_timestamps[user_id] = current_time
            else:
                # Удаляем временную метку если состояния нет
                if user_id in self.state_timestamps:
                    del self.state_timestamps[user_id]

        return await handler(event, data)

    def _extract_user(self, event: TelegramObject) -> Optional[User]:
        """Извлечь пользователя из события."""
        if isinstance(event, (Message, CallbackQuery, InlineQuery)):
            return event.from_user
        elif isinstance(event, Update):
            if event.message:
                return event.message.from_user
            elif event.callback_query:
                return event.callback_query.from_user
            elif event.inline_query:
                return event.inline_query.from_user
        return None


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
    'StateTimeoutMiddleware',
    'setup_middleware'
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

    # Регистрируем в правильном порядке для aiogram 3.x
    # Для глобальных middleware используем update.outer_middleware

    # Сначала обработка ошибок и логирование (для всех типов событий)
    dp.update.outer_middleware(error_middleware)
    dp.update.outer_middleware(logging_middleware)
    dp.update.outer_middleware(metrics_middleware)

    # База данных и пользователь
    dp.update.outer_middleware(database_middleware)

    # Подписка и права
    dp.update.outer_middleware(subscription_middleware)

    # Языки для всех типов
    dp.update.outer_middleware(i18n_middleware)

    # Затем специфичные middleware для message и callback_query
    # Проверка частоты запросов
    dp.message.middleware(throttling_middleware)
    dp.callback_query.middleware(throttling_middleware)

    # Проверка админских прав только для сообщений
    dp.message.middleware(admin_middleware)

    # Таймауты состояний
    dp.message.middleware(state_timeout_middleware)
    dp.callback_query.middleware(state_timeout_middleware)

    logger.info("All middleware registered successfully")

    return {
        'metrics': metrics_middleware,
        'throttling': throttling_middleware,
        'state_timeout': state_timeout_middleware
    }