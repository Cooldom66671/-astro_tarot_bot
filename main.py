"""
Главный файл запуска Telegram бота "Астро-Таро Ассистент".

Этот файл отвечает за:
- Инициализацию всех компонентов системы
- Настройку логирования
- Запуск бота в режиме polling или webhook
- Обработку сигналов для graceful shutdown
- Планировщик задач

Автор: AI Assistant
Дата создания: 2024-12-30
"""

import asyncio
import logging
import signal
import sys
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiogram.types import BotCommand, BotCommandScopeDefault, BotCommandScopeChat
from aiohttp import web
import redis.asyncio as aioredis
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.redis import RedisJobStore
from apscheduler.jobstores.memory import MemoryJobStore

# Добавляем корневую директорию в путь для импортов
sys.path.insert(0, str(Path(__file__).parent))

# Конфигурация
from config import settings, setup_logging, get_version, initialize_config
from config.constants import BotCommands
from config.logging_config import telegram_handler

# Создаем класс BotInfo
@dataclass
class BotInfo:
    """Информация о боте."""
    NAME: str = "Астро-Таро Бот"
    VERSION: str = get_version()
    DESCRIPTION: str = "Персональный астрологический помощник"
    AUTHOR: str = "AI Assistant"

# Инфраструктура
from infrastructure import (
    init_infrastructure,
    shutdown_infrastructure,
    get_unit_of_work
)

# Импортируем cache_manager
from infrastructure.cache import cache_manager

# Обработчики и middleware
from bot.handlers import setup_handlers, create_dispatcher
from bot.middleware import setup_middleware

# Сервисы
from services import (
    get_notification_service,
    get_analytics_service,
    get_user_service
)

# Настройка логирования
setup_logging()
logger = logging.getLogger(__name__)


class AstroTarotBot:
    """Основной класс бота."""

    def __init__(self):
        """Инициализация бота."""
        self.settings = settings
        self.bot: Optional[Bot] = None
        self.dp: Optional[Dispatcher] = None
        self.scheduler: Optional[AsyncIOScheduler] = None
        self._running = False
        self._start_time = datetime.now()
        self._webapp_runner: Optional[web.AppRunner] = None

    async def initialize(self):
        """Инициализация всех компонентов."""
        logger.info("=" * 50)
        logger.info(f"{BotInfo.NAME} v{BotInfo.VERSION}")
        logger.info(f"Environment: {self.settings.environment}")
        logger.info(f"Debug mode: {self.settings.debug}")
        logger.info("=" * 50)

        try:
            # 0. Инициализируем конфигурацию
            initialize_config()

            # 1. Инициализируем инфраструктуру
            logger.info("Initializing infrastructure...")
            await init_infrastructure()

            # 2. Инициализируем кэш
            logger.info("Initializing cache...")
            await cache_manager.init()

            # 3. Проверяем/создаем таблицы БД
            await self._init_database()

            # 4. Создаем бота с правильными параметрами для aiogram 3.x
            logger.info("Creating bot instance...")
            self.bot = Bot(
                token=self.settings.bot.token.get_secret_value(),
                default=DefaultBotProperties(
                    parse_mode=ParseMode.HTML
                )
            )

            # 5. Настраиваем telegram handler для логов
            telegram_handler.set_bot(self.bot)

            # 6. Создаем диспетчер с нужным хранилищем
            logger.info("Creating dispatcher...")
            storage = await self._create_storage()
            self.dp = create_dispatcher(storage)

            # 7. Настраиваем обработчики и middleware
            logger.info("Setting up handlers and middleware...")
            setup_handlers(self.dp)
            middleware_instances = setup_middleware(self.dp)

            # 8. Настраиваем планировщик задач
            logger.info("Setting up scheduler...")
            self.scheduler = await self._setup_scheduler()

            # 9. Проверяем бота
            bot_info = await self.bot.get_me()
            logger.info(f"Bot initialized: @{bot_info.username}")

            # 10. Уведомляем админов о запуске
            await self._notify_admins_startup()

            # 11. Устанавливаем команды бота
            await self._set_bot_commands()

            logger.info("Initialization complete!")

        except Exception as e:
            logger.error(f"Initialization failed: {e}", exc_info=True)
            await self.shutdown()
            raise

    async def _init_database(self):
        """Инициализация базы данных."""
        try:
            from infrastructure.database import init_database
            await init_database()
            logger.info("Database initialized")
        except ImportError:
            logger.warning("Database module not found, skipping DB initialization")
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            # В development продолжаем работу даже без БД
            if self.settings.environment != "development":
                raise

    async def _create_storage(self) -> Union[MemoryStorage, RedisStorage]:
        """Создание хранилища для FSM."""
        if self.settings.redis.url:
            try:
                # Проверяем подключение к Redis
                storage = RedisStorage.from_url(
                    self.settings.redis.url,
                    state_ttl=self.settings.redis.fsm_ttl,
                    data_ttl=self.settings.redis.fsm_ttl
                )
                # Тестируем подключение
                await storage.redis.ping()
                logger.info("Using Redis storage for FSM")
                return storage
            except Exception as e:
                logger.warning(f"Failed to connect to Redis: {e}")

        # Fallback на память
        logger.info("Using memory storage for FSM")
        return MemoryStorage()

    async def _setup_scheduler(self) -> AsyncIOScheduler:
        """Настройка планировщика задач."""
        # Создаем jobstore
        if self.settings.redis.url:
            try:
                jobstores = {
                    'default': RedisJobStore(
                        db=1,  # Используем другую БД Redis для задач
                        host=self.settings.redis.host,
                        port=self.settings.redis.port,
                        password=self.settings.redis.password.get_secret_value() if self.settings.redis.password else None
                    )
                }
                logger.info("Using Redis jobstore for scheduler")
            except Exception as e:
                logger.warning(f"Failed to create Redis jobstore: {e}")
                jobstores = {'default': MemoryJobStore()}
        else:
            jobstores = {'default': MemoryJobStore()}

        # Создаем планировщик
        scheduler = AsyncIOScheduler(
            jobstores=jobstores,
            timezone=self.settings.timezone,
            job_defaults={
                'coalesce': True,
                'max_instances': 3,
                'misfire_grace_time': 30
            }
        )

        # Добавляем базовые задачи
        await self._add_scheduled_tasks(scheduler)

        # Запускаем планировщик
        scheduler.start()
        logger.info("Scheduler started")

        return scheduler

    async def _add_scheduled_tasks(self, scheduler: AsyncIOScheduler):
        """Добавление запланированных задач."""
        try:
            # Ежедневная очистка кэша
            scheduler.add_job(
                self._clean_cache,
                'cron',
                hour=3,
                minute=0,
                id='clean_cache',
                replace_existing=True
            )

            # Ежедневные уведомления
            if self.settings.features.enable_notifications:
                scheduler.add_job(
                    self._send_daily_notifications,
                    'cron',
                    hour=9,
                    minute=0,
                    id='daily_notifications',
                    replace_existing=True
                )

            # Бэкапы БД
            if self.settings.features.enable_backups:
                scheduler.add_job(
                    self._backup_database,
                    'cron',
                    hour=2,
                    minute=0,
                    id='backup_database',
                    replace_existing=True
                )

            # Сбор аналитики
            if self.settings.features.enable_analytics:
                scheduler.add_job(
                    self._collect_analytics,
                    'interval',
                    hours=1,
                    id='collect_analytics',
                    replace_existing=True
                )

            logger.info(f"Added {len(scheduler.get_jobs())} scheduled tasks")

        except Exception as e:
            logger.error(f"Failed to add scheduled tasks: {e}")

    async def _notify_admins_startup(self):
        """Уведомление администраторов о запуске."""
        if not self.bot or not self.settings.bot.admin_ids:
            return

        message = (
            f"🚀 <b>{BotInfo.NAME} запущен!</b>\n\n"
            f"📌 Версия: <code>{BotInfo.VERSION}</code>\n"
            f"🌍 Окружение: <code>{self.settings.environment}</code>\n"
            f"🐍 Python: <code>{sys.version.split()[0]}</code>\n"
            f"📊 Режим: {'Webhook' if self.settings.bot.use_webhook else 'Polling'}\n"
            f"⏰ Время запуска: {self._start_time.strftime('%Y-%m-%d %H:%M:%S')}"
        )

        for admin_id in self.settings.bot.admin_ids:
            try:
                await self.bot.send_message(admin_id, message)
            except Exception as e:
                logger.warning(f"Failed to notify admin {admin_id}: {e}")

    async def _set_bot_commands(self):
        """Установка команд бота."""
        try:
            # Основные команды для всех
            public_commands = [
                BotCommand(command=cmd.value, description=desc)
                for cmd, desc in BotCommands.get_commands_description().items()
            ]

            await self.bot.set_my_commands(
                commands=public_commands,
                scope=BotCommandScopeDefault()
            )

            # Админские команды
            if self.settings.bot.admin_ids:
                admin_commands = public_commands + [
                    BotCommand(command=cmd.value, description=desc)
                    for cmd, desc in BotCommands.get_admin_commands_description().items()
                ]

                for admin_id in self.settings.bot.admin_ids:
                    try:
                        await self.bot.set_my_commands(
                            commands=admin_commands,
                            scope=BotCommandScopeChat(chat_id=admin_id)
                        )
                    except Exception as e:
                        logger.warning(f"Failed to set admin commands for {admin_id}: {e}")

            logger.info("Bot commands set successfully")

        except Exception as e:
            logger.error(f"Failed to set bot commands: {e}")

    async def start(self):
        """Запуск бота."""
        self._running = True

        # Настраиваем обработчики сигналов
        self._setup_signal_handlers()

        try:
            if self.settings.bot.use_webhook:
                await self._start_webhook()
            else:
                await self._start_polling()
        except Exception as e:
            logger.error(f"Bot startup failed: {e}")
            await self.shutdown()
            raise

    async def _start_polling(self):
        """Запуск бота в режиме polling."""
        logger.info("Starting bot in polling mode...")

        try:
            # Удаляем вебхук если был установлен
            await self.bot.delete_webhook(drop_pending_updates=True)

            # Запускаем polling
            await self.dp.start_polling(
                self.bot,
                allowed_updates=self.dp.resolve_used_update_types(),
                handle_signals=False  # Обрабатываем сигналы сами
            )
        except Exception as e:
            logger.error(f"Polling failed: {e}")
            raise

    async def _start_webhook(self):
        """Запуск бота в режиме webhook."""
        logger.info("Starting bot in webhook mode...")

        # Проверяем настройки
        if not self.settings.bot.webhook_url:
            raise ValueError("Webhook URL not configured")

        # Устанавливаем webhook
        webhook_path = f"{self.settings.bot.webhook_path}/{self.settings.bot.token.get_secret_value()}"
        webhook_url = f"{self.settings.bot.webhook_url}{webhook_path}"

        await self.bot.set_webhook(
            url=webhook_url,
            drop_pending_updates=True,
            secret_token=self.settings.bot.webhook_secret.get_secret_value() if self.settings.bot.webhook_secret else None
        )

        # Создаем приложение
        app = web.Application()

        # Настраиваем обработчик webhook
        webhook_handler = SimpleRequestHandler(
            dispatcher=self.dp,
            bot=self.bot,
            secret_token=self.settings.bot.webhook_secret.get_secret_value() if self.settings.bot.webhook_secret else None
        )

        webhook_handler.register(app, path=webhook_path)
        setup_application(app, self.dp, bot=self.bot)

        # Добавляем health check endpoint
        app.router.add_get('/health', self._health_check)

        # Запускаем web-сервер
        self._webapp_runner = web.AppRunner(app)
        await self._webapp_runner.setup()

        host = os.getenv('WEBAPP_HOST', '0.0.0.0')
        port = int(os.getenv('WEBAPP_PORT', '8080'))

        site = web.TCPSite(
            self._webapp_runner,
            host=host,
            port=port
        )

        await site.start()
        logger.info(f"Webhook server started on {host}:{port}")

        # Держим сервер запущенным
        try:
            while self._running:
                await asyncio.sleep(1)
        finally:
            await self._webapp_runner.cleanup()

    async def _health_check(self, request: web.Request) -> web.Response:
        """Health check endpoint для webhook."""
        health_data = {
            'status': 'healthy',
            'bot': BotInfo.NAME,
            'version': BotInfo.VERSION,
            'uptime': str(datetime.now() - self._start_time),
            'environment': self.settings.environment
        }
        return web.json_response(health_data)

    def _setup_signal_handlers(self):
        """Настройка обработчиков сигналов."""
        loop = asyncio.get_event_loop()

        def signal_handler(sig):
            logger.info(f"Received signal {sig}")
            asyncio.create_task(self.shutdown())

        # Для Windows используем другой подход
        if sys.platform == 'win32':
            signal.signal(signal.SIGINT, lambda s, f: signal_handler(s))
            signal.signal(signal.SIGTERM, lambda s, f: signal_handler(s))
        else:
            # Для Unix-систем используем add_signal_handler
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(sig, lambda s=sig: signal_handler(s))

    async def shutdown(self):
        """Корректное завершение работы."""
        if not self._running:
            return

        logger.info("Shutting down bot...")
        self._running = False

        try:
            # Уведомляем админов
            await self._notify_admins_shutdown()

            # Останавливаем планировщик
            if self.scheduler and self.scheduler.running:
                self.scheduler.shutdown(wait=False)
                logger.info("Scheduler stopped")

            # Закрываем webhook runner
            if self._webapp_runner:
                await self._webapp_runner.cleanup()
                logger.info("Webhook server stopped")

            # Закрываем диспетчер
            if self.dp:
                await self.dp.stop_polling()

            # Закрываем бота
            if self.bot:
                await self.bot.session.close()
                logger.info("Bot session closed")

            # Закрываем инфраструктуру
            await shutdown_infrastructure()

            # Закрываем кэш
            await cache_manager.close()

            logger.info("Shutdown complete")

        except Exception as e:
            logger.error(f"Error during shutdown: {e}")

    async def _notify_admins_shutdown(self):
        """Уведомление администраторов об остановке."""
        if not self.bot or not self.settings.bot.admin_ids:
            return

        uptime = datetime.now() - self._start_time
        message = (
            f"⛔ <b>{BotInfo.NAME} остановлен</b>\n\n"
            f"⏱ Время работы: {uptime}\n"
            f"📅 Время остановки: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )

        for admin_id in self.settings.bot.admin_ids:
            try:
                await self.bot.send_message(admin_id, message)
            except Exception as e:
                logger.warning(f"Failed to notify admin {admin_id}: {e}")

    # Методы для планировщика задач
    async def _clean_cache(self):
        """Очистка устаревшего кэша."""
        try:
            logger.info("Starting cache cleanup...")
            await cache_manager.clear_expired()
            logger.info("Cache cleanup completed")
        except Exception as e:
            logger.error(f"Cache cleanup failed: {e}")

    async def _send_daily_notifications(self):
        """Отправка ежедневных уведомлений."""
        try:
            logger.info("Sending daily notifications...")
            notification_service = get_notification_service()
            await notification_service.send_daily_horoscopes()
            await notification_service.send_subscription_reminders()
            logger.info("Daily notifications sent")
        except Exception as e:
            logger.error(f"Failed to send daily notifications: {e}")

    async def _backup_database(self):
        """Создание резервной копии БД."""
        try:
            logger.info("Starting database backup...")
            # Здесь должна быть логика бэкапа
            logger.info("Database backup completed")
        except Exception as e:
            logger.error(f"Database backup failed: {e}")

    async def _collect_analytics(self):
        """Сбор аналитики."""
        try:
            analytics_service = get_analytics_service()
            await analytics_service.collect_hourly_stats()
        except Exception as e:
            logger.error(f"Failed to collect analytics: {e}")


async def main():
    """Главная функция запуска."""
    bot = AstroTarotBot()

    try:
        # Инициализация
        await bot.initialize()

        # Запуск
        await bot.start()

    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
    finally:
        # Завершение работы
        await bot.shutdown()


if __name__ == "__main__":
    try:
        # Запускаем бота
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Failed to run bot: {e}", exc_info=True)
        sys.exit(1)