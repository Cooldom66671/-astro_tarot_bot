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
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
import redis.asyncio as aioredis
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.redis import RedisJobStore

# Добавляем корневую директорию в путь для импортов
sys.path.insert(0, str(Path(__file__).parent))

# Конфигурация
from config import settings, logger, setup_logging, get_version
from config.constants import BotCommands

# Создаем класс BotInfo если его нет
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

# Импортируем cache_manager вместо get_cache
from infrastructure.cache import cache_manager

# Обработчики и middleware
from bot.handlers import setup_handlers
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

    async def initialize(self):
        """Инициализация всех компонентов."""
        logger.info("=" * 50)
        logger.info(f"{BotInfo.NAME} v{BotInfo.VERSION}")
        logger.info(f"Environment: {self.settings.environment}")
        logger.info("=" * 50)

        try:
            # 1. Инициализируем инфраструктуру
            logger.info("Initializing infrastructure...")
            await init_infrastructure()

            # 2. Инициализируем кэш
            logger.info("Initializing cache...")
            await cache_manager.init()

            # 3. Проверяем/создаем таблицы БД
            await self._init_database()

            # 4. Создаем бота с правильными параметрами для aiogram 3.3.0
            logger.info("Creating bot instance...")
            self.bot = Bot(
                token=self.settings.bot.token.get_secret_value(),
                parse_mode=ParseMode.HTML
            )

            # 5. Создаем диспетчер с нужным хранилищем
            logger.info("Creating dispatcher...")
            storage = await self._create_storage()
            self.dp = Dispatcher(storage=storage)

            # 6. Настраиваем обработчики и middleware
            logger.info("Setting up handlers and middleware...")
            setup_handlers(self.dp)
            setup_middleware(self.dp)

            # 7. Настраиваем планировщик задач
            logger.info("Setting up scheduler...")
            self.scheduler = await self._setup_scheduler()

            # 8. Проверяем бота
            bot_info = await self.bot.get_me()
            logger.info(f"Bot initialized: @{bot_info.username}")

            # 9. Уведомляем админов о запуске
            await self._notify_admins_startup()

            # 10. Устанавливаем команды бота
            await self._set_bot_commands()

            logger.info("Initialization complete!")

        except Exception as e:
            logger.error(f"Initialization failed: {e}", exc_info=True)
            raise

    async def _init_database(self):
        """Инициализация базы данных."""
        from infrastructure.database import init_database

        try:
            await init_database()
            logger.info("Database initialized")
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            # В development продолжаем работу даже без БД
            if self.settings.environment != "development":
                raise

    async def _create_storage(self):
        """Создание хранилища для FSM."""
        if self.settings.redis.url:
            try:
                redis = await aioredis.from_url(
                    self.settings.redis.url,
                    encoding="utf-8",
                    decode_responses=True
                )
                # Проверяем подключение
                await redis.ping()
                logger.info("Using Redis storage for FSM")
                return RedisStorage(redis=redis)
            except Exception as e:
                logger.warning(f"Redis unavailable, falling back to memory storage: {e}")

        logger.info("Using memory storage for FSM")
        return MemoryStorage()

    async def _setup_scheduler(self) -> AsyncIOScheduler:
        """Настройка планировщика задач."""
        jobstores = {}

        # Если есть Redis, используем его для хранения задач
        if self.settings.redis.url:
            try:
                jobstores['default'] = RedisJobStore(
                    host=self.settings.redis.host,
                    port=self.settings.redis.port,
                    db=self.settings.redis.db
                )
                logger.info("Using Redis jobstore for scheduler")
            except Exception as e:
                logger.warning(f"Redis jobstore unavailable: {e}")

        scheduler = AsyncIOScheduler(
            jobstores=jobstores,
            timezone=self.settings.default_timezone,
            job_defaults={
                'coalesce': True,
                'max_instances': 3,
                'misfire_grace_time': 300
            }
        )

        # Добавляем задачи
        # Ежедневная рассылка гороскопов
        if self.settings.features.daily_horoscope:
            scheduler.add_job(
                self._send_daily_horoscopes,
                'cron',
                hour=9,
                minute=0,
                id='daily_horoscopes'
            )

        # Напоминания о продлении подписки
        scheduler.add_job(
            self._check_expiring_subscriptions,
            'cron',
            hour=12,
            minute=0,
            id='subscription_reminders'
        )

        # Сбор статистики
        scheduler.add_job(
            self._collect_daily_stats,
            'cron',
            hour=23,
            minute=55,
            id='daily_stats'
        )

        # Очистка старых данных
        scheduler.add_job(
            self._cleanup_old_data,
            'cron',
            hour=3,
            minute=0,
            day_of_week=0,  # Понедельник
            id='weekly_cleanup'
        )

        # Резервное копирование (ежедневно в 2:00)
        if self.settings.features.enable_backups:
            scheduler.add_job(
                self._backup_database,
                'cron',
                hour=2,
                minute=0,
                id='daily_backup'
            )

        scheduler.start()
        logger.info(f"Scheduler configured with {len(scheduler.get_jobs())} jobs")
        return scheduler

    async def _set_bot_commands(self):
        """Установка команд бота в меню."""
        from aiogram.types import BotCommand, BotCommandScopeDefault

        commands = [
            BotCommand(command="start", description="🚀 Начать работу с ботом"),
            BotCommand(command="menu", description="📱 Главное меню"),
            BotCommand(command="tarot", description="🎴 Расклады Таро"),
            BotCommand(command="astrology", description="⭐ Астрология"),
            BotCommand(command="subscription", description="💎 Управление подпиской"),
            BotCommand(command="help", description="❓ Помощь и поддержка"),
            BotCommand(command="stats", description="📊 Ваша статистика"),
            BotCommand(command="settings", description="⚙️ Настройки"),
            BotCommand(command="about", description="ℹ️ О боте"),
            BotCommand(command="cancel", description="❌ Отменить действие")
        ]

        await self.bot.set_my_commands(
            commands=commands,
            scope=BotCommandScopeDefault()
        )

        logger.info("Bot commands set")

    async def start(self):
        """Запуск бота."""
        await self.initialize()
        self._running = True

        # Настраиваем обработчики сигналов
        self._setup_signal_handlers()

        try:
            if self.settings.bot.use_webhook:
                await self._start_webhook()
            else:
                await self._start_polling()
        except Exception as e:
            logger.error(f"Bot start failed: {e}", exc_info=True)
            raise
        finally:
            await self.shutdown()

    async def _start_polling(self):
        """Запуск бота в режиме polling."""
        logger.info("Starting bot in polling mode...")

        try:
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

        # Устанавливаем webhook
        webhook_url = f"{self.settings.bot.webhook_url}/webhook/{self.settings.bot.token.get_secret_value()}"
        await self.bot.set_webhook(
            url=webhook_url,
            drop_pending_updates=True,
            secret_token=self.settings.bot.webhook_secret
        )

        # Создаем приложение
        app = web.Application()

        # Настраиваем обработчик webhook
        webhook_handler = SimpleRequestHandler(
            dispatcher=self.dp,
            bot=self.bot,
            secret_token=self.settings.bot.webhook_secret
        )

        webhook_handler.register(app, path=f"/webhook/{self.settings.bot.token.get_secret_value()}")
        setup_application(app, self.dp, bot=self.bot)

        # Запускаем web-сервер
        runner = web.AppRunner(app)
        await runner.setup()

        site = web.TCPSite(
            runner,
            host=self.settings.bot.webapp_host,
            port=self.settings.bot.webapp_port
        )

        await site.start()
        logger.info(f"Webhook server started on {self.settings.bot.webapp_host}:{self.settings.bot.webapp_port}")

        # Держим сервер запущенным
        while self._running:
            await asyncio.sleep(1)

    def _setup_signal_handlers(self):
        """Настройка обработчиков сигналов."""
        def signal_handler(sig, frame):
            logger.info(f"Received signal {sig}")
            asyncio.create_task(self.shutdown())

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    async def shutdown(self):
        """Корректное завершение работы."""
        if not self._running:
            return

        self._running = False
        logger.info("Shutting down bot...")

        try:
            # Уведомляем админов
            await self._notify_admins_shutdown()

            # Останавливаем планировщик
            if self.scheduler:
                self.scheduler.shutdown()

            # Закрываем webhook
            if self.settings.bot.use_webhook:
                await self.bot.delete_webhook()

            # Закрываем бота
            if self.bot:
                await self.bot.session.close()

            # Закрываем кэш
            await cache_manager.close()

            # Закрываем инфраструктуру
            await shutdown_infrastructure()

            logger.info("Bot shutdown complete")

        except Exception as e:
            logger.error(f"Error during shutdown: {e}")

    # Задачи планировщика

    async def _send_daily_horoscopes(self):
        """Отправка ежедневных гороскопов."""
        logger.info("Sending daily horoscopes...")

        notification_service = get_notification_service()
        sent_count = await notification_service.send_daily_horoscopes()

        logger.info(f"Daily horoscopes sent to {sent_count} users")

    async def _check_expiring_subscriptions(self):
        """Проверка истекающих подписок."""
        logger.info("Checking expiring subscriptions...")

        notification_service = get_notification_service()
        reminded_count = await notification_service.send_subscription_reminders()

        logger.info(f"Subscription reminders sent to {reminded_count} users")

    async def _collect_daily_stats(self):
        """Сбор ежедневной статистики."""
        logger.info("Collecting daily statistics...")

        analytics_service = get_analytics_service()
        stats = await analytics_service.get_system_statistics()

        # Отправляем админам
        await self._send_stats_to_admins(stats)

        # Сохраняем в БД для истории
        async with get_unit_of_work() as uow:
            await uow.analytics.save_daily_stats(stats)
            await uow.commit()

        logger.info("Daily statistics collected and sent")

    async def _cleanup_old_data(self):
        """Очистка старых данных."""
        logger.info("Cleaning up old data...")

        async with get_unit_of_work() as uow:
            # Удаляем старые логи (старше 30 дней)
            deleted_logs = await uow.logs.delete_old(days=30)

            # Удаляем неактивных пользователей (более 180 дней)
            archived_users = await uow.users.archive_inactive(days=180)

            # Очищаем кэш
            await cache_manager.clear()

            await uow.commit()

            logger.info(
                f"Cleanup completed: {deleted_logs} logs deleted, "
                f"{archived_users} users archived"
            )

    async def _backup_database(self):
        """Резервное копирование базы данных."""
        logger.info("Starting database backup...")

        try:
            # Здесь должен быть код резервного копирования
            # Например, pg_dump для PostgreSQL
            backup_file = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sql"

            # Уведомляем админов
            async with get_unit_of_work() as uow:
                admins = await uow.users.get_admins()
                for admin in admins:
                    await self.bot.send_message(
                        admin.telegram_id,
                        f"✅ Резервная копия создана: {backup_file}"
                    )

            logger.info(f"Backup completed: {backup_file}")

        except Exception as e:
            logger.error(f"Backup failed: {e}")
            await self._notify_admins_error("Backup failed", str(e))

    # Уведомления админам

    async def _notify_admins_startup(self):
        """Уведомление админов о запуске."""
        if not self.bot:
            return

        admin_ids = self.settings.bot.admin_ids

        message = (
            f"🚀 <b>{BotInfo.NAME} запущен!</b>\n\n"
            f"Версия: {BotInfo.VERSION}\n"
            f"Окружение: {self.settings.environment}\n"
            f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )

        for admin_id in admin_ids:
            try:
                await self.bot.send_message(admin_id, message)
            except Exception as e:
                logger.error(f"Failed to notify admin {admin_id}: {e}")

    async def _notify_admins_shutdown(self):
        """Уведомление админов об остановке."""
        if not self.bot:
            return

        admin_ids = self.settings.bot.admin_ids

        message = (
            f"🛑 <b>{BotInfo.NAME} остановлен</b>\n\n"
            f"Время работы: {self._get_uptime()}\n"
            f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )

        for admin_id in admin_ids:
            try:
                await self.bot.send_message(admin_id, message)
            except Exception as e:
                logger.error(f"Failed to notify admin {admin_id}: {e}")

    async def _notify_admins_error(self, error_type: str, error_message: str):
        """Уведомление админов об ошибке."""
        if not self.bot:
            return

        admin_ids = self.settings.bot.admin_ids

        message = (
            f"❌ <b>Ошибка в {BotInfo.NAME}</b>\n\n"
            f"Тип: {error_type}\n"
            f"Сообщение: {error_message}\n"
            f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )

        for admin_id in admin_ids:
            try:
                await self.bot.send_message(admin_id, message)
            except Exception as e:
                logger.error(f"Failed to notify admin {admin_id}: {e}")

    async def _send_stats_to_admins(self, stats: Dict[str, Any]):
        """Отправка статистики админам."""
        if not self.bot:
            return

        admin_ids = self.settings.bot.admin_ids

        message = (
            f"📊 <b>Ежедневная статистика</b>\n\n"
            f"👥 Активных пользователей: {stats.get('active_users', 0)}\n"
            f"📝 Сообщений обработано: {stats.get('messages_processed', 0)}\n"
            f"🎴 Раскладов выполнено: {stats.get('tarot_readings', 0)}\n"
            f"⭐ Гороскопов просмотрено: {stats.get('horoscopes_viewed', 0)}\n"
            f"💎 Новых подписок: {stats.get('new_subscriptions', 0)}\n"
            f"💰 Доход за день: {stats.get('daily_revenue', 0)} ₽"
        )

        for admin_id in admin_ids:
            try:
                await self.bot.send_message(admin_id, message)
            except Exception as e:
                logger.error(f"Failed to send stats to admin {admin_id}: {e}")

    def _get_uptime(self) -> str:
        """Получить время работы бота."""
        uptime = datetime.now() - self._start_time
        days = uptime.days
        hours, remainder = divmod(uptime.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)

        parts = []
        if days > 0:
            parts.append(f"{days} дн.")
        if hours > 0:
            parts.append(f"{hours} ч.")
        if minutes > 0:
            parts.append(f"{minutes} мин.")
        if seconds > 0 or not parts:
            parts.append(f"{seconds} сек.")

        return " ".join(parts)


# Точка входа
async def main():
    """Главная функция запуска."""
    bot = AstroTarotBot()

    try:
        await bot.start()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot crashed: {e}", exc_info=True)
    finally:
        await bot.shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)