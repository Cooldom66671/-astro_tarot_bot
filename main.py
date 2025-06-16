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
from typing import Optional

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.redis import RedisStorage
from aioredis import Redis

# Конфигурация
from bot.config import Settings, setup_logging
from bot.config.constants import BotInfo

# Инфраструктура
from infrastructure import (
    init_infrastructure,
    shutdown_infrastructure,
    get_unit_of_work
)

# Обработчики и middleware
from bot.handlers import create_dispatcher
from bot.middleware import MetricsMiddleware

# Сервисы
from bot.services import (
    get_notification_service,
    get_analytics_service,
    get_user_service
)

# Утилиты
from bot.utils import scheduler

# Настройка логирования
logger = logging.getLogger(__name__)


class AstroTarotBot:
    """Основной класс бота."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.bot: Optional[Bot] = None
        self.dp: Optional[Dispatcher] = None
        self.scheduler = None
        self._running = False

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

            # 2. Проверяем/создаем таблицы БД
            await self._init_database()

            # 3. Создаем бота
            logger.info("Creating bot instance...")
            self.bot = Bot(
                token=self.settings.bot_token,
                default=DefaultBotProperties(
                    parse_mode=ParseMode.HTML,
                    link_preview_is_disabled=True
                )
            )

            # 4. Создаем диспетчер с нужным хранилищем
            logger.info("Creating dispatcher...")
            storage = await self._create_storage()
            self.dp = create_dispatcher(storage)

            # 5. Настраиваем планировщик задач
            logger.info("Setting up scheduler...")
            self.scheduler = await self._setup_scheduler()

            # 6. Проверяем бота
            bot_info = await self.bot.get_me()
            logger.info(f"Bot initialized: @{bot_info.username}")

            # 7. Устанавливаем команды
            await self._set_bot_commands()

            logger.info("Initialization completed successfully!")

        except Exception as e:
            logger.error(f"Failed to initialize bot: {e}", exc_info=True)
            raise

    async def start(self):
        """Запуск бота."""
        if not self.bot or not self.dp:
            raise RuntimeError("Bot not initialized. Call initialize() first.")

        self._running = True

        # Запускаем планировщик
        if self.scheduler:
            self.scheduler.start()
            logger.info("Scheduler started")

        # Отправляем уведомление о запуске админам
        await self._notify_admins_startup()

        # Выбираем режим работы
        if self.settings.use_webhook:
            await self._start_webhook()
        else:
            await self._start_polling()

    async def stop(self):
        """Остановка бота."""
        logger.info("Shutting down bot...")
        self._running = False

        # Останавливаем планировщик
        if self.scheduler and self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Scheduler stopped")

        # Отправляем уведомление админам
        await self._notify_admins_shutdown()

        # Закрываем сессию бота
        if self.bot:
            await self.bot.session.close()
            logger.info("Bot session closed")

        # Закрываем инфраструктуру
        await shutdown_infrastructure()

        logger.info("Shutdown completed")

    async def _init_database(self):
        """Инициализация базы данных."""
        logger.info("Checking database...")

        # Здесь должна быть миграция БД
        # Пока просто проверяем подключение
        async with get_unit_of_work() as uow:
            user_count = await uow.users.count_total()
            logger.info(f"Database connected. Users count: {user_count}")

    async def _create_storage(self):
        """Создание хранилища FSM."""
        if self.settings.redis_url:
            try:
                redis = Redis.from_url(self.settings.redis_url)
                await redis.ping()
                logger.info("Using Redis storage for FSM")
                return RedisStorage(redis)
            except Exception as e:
                logger.warning(f"Failed to connect to Redis: {e}")
                logger.info("Falling back to memory storage")

        logger.info("Using memory storage for FSM")
        return MemoryStorage()

    async def _setup_scheduler(self):
        """Настройка планировщика задач."""
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from apscheduler.jobstores.memory import MemoryJobStore

        jobstores = {
            'default': MemoryJobStore()
        }

        scheduler = AsyncIOScheduler(
            jobstores=jobstores,
            timezone='UTC'
        )

        # Добавляем задачи

        # 1. Ежедневная отправка гороскопов (9:00 UTC)
        scheduler.add_job(
            self._send_daily_horoscopes,
            'cron',
            hour=9,
            minute=0,
            id='daily_horoscopes'
        )

        # 2. Проверка истекающих подписок (каждые 6 часов)
        scheduler.add_job(
            self._check_expiring_subscriptions,
            'interval',
            hours=6,
            id='check_subscriptions'
        )

        # 3. Сбор и отправка статистики (ежедневно в 23:00)
        scheduler.add_job(
            self._collect_daily_stats,
            'cron',
            hour=23,
            minute=0,
            id='daily_stats'
        )

        # 4. Очистка старых данных (еженедельно)
        scheduler.add_job(
            self._cleanup_old_data,
            'cron',
            day_of_week='sun',
            hour=3,
            minute=0,
            id='weekly_cleanup'
        )

        # 5. Резервное копирование (ежедневно в 2:00)
        if self.settings.enable_backups:
            scheduler.add_job(
                self._backup_database,
                'cron',
                hour=2,
                minute=0,
                id='daily_backup'
            )

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
        webhook_url = f"{self.settings.webhook_url}/webhook/{self.settings.bot_token}"
        await self.bot.set_webhook(
            url=webhook_url,
            drop_pending_updates=True,
            secret_token=self.settings.webhook_secret
        )

        # Здесь должен быть запуск web-сервера
        # Например, с использованием aiohttp или FastAPI
        logger.info(f"Webhook set: {webhook_url}")

    # Задачи планировщика

    async def _send_daily_horoscopes(self):
        """Отправка ежедневных гороскопов."""
        logger.info("Sending daily horoscopes...")

        notification_service = get_notification_service()

        async with get_unit_of_work() as uow:
            # Получаем пользователей с включенными уведомлениями
            users = await uow.users.get_for_daily_notifications()

            sent_count = 0
            for user in users:
                if user.zodiac_sign:
                    success = await notification_service.send_notification(
                        user.id,
                        "daily_horoscope",
                        {"zodiac_sign": user.zodiac_sign},
                        self.bot
                    )
                    if success:
                        sent_count += 1

                    # Небольшая задержка между отправками
                    await asyncio.sleep(0.1)

            logger.info(f"Daily horoscopes sent: {sent_count}/{len(users)}")

    async def _check_expiring_subscriptions(self):
        """Проверка истекающих подписок."""
        logger.info("Checking expiring subscriptions...")

        notification_service = get_notification_service()

        async with get_unit_of_work() as uow:
            # Подписки, истекающие через 3 дня
            expiring = await uow.subscriptions.get_expiring(days=3)

            for subscription in expiring:
                if not subscription.notified_expiring:
                    await notification_service.send_notification(
                        subscription.user_id,
                        "subscription_expiring",
                        {
                            "days_left": 3,
                            "plan": subscription.plan_name
                        },
                        self.bot
                    )

                    subscription.notified_expiring = True
                    await uow.commit()

            logger.info(f"Processed {len(expiring)} expiring subscriptions")

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
            from infrastructure.cache import get_cache
            cache = await get_cache()
            await cache.clear_expired()

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
        async with get_unit_of_work() as uow:
            admins = await uow.users.get_admins()

            message = (
                f"🚀 <b>{BotInfo.NAME} запущен!</b>\n\n"
                f"Версия: {BotInfo.VERSION}\n"
                f"Окружение: {self.settings.environment}\n"
                f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )

            for admin in admins:
                try:
                    await self.bot.send_message(
                        admin.telegram_id,
                        message,
                        parse_mode="HTML"
                    )
                except Exception as e:
                    logger.error(f"Failed to notify admin {admin.id}: {e}")

    async def _notify_admins_shutdown(self):
        """Уведомление админов об остановке."""
        async with get_unit_of_work() as uow:
            admins = await uow.users.get_admins()

            message = (
                f"🛑 <b>{BotInfo.NAME} остановлен</b>\n\n"
                f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )

            for admin in admins:
                try:
                    await self.bot.send_message(
                        admin.telegram_id,
                        message,
                        parse_mode="HTML"
                    )
                except Exception as e:
                    logger.error(f"Failed to notify admin {admin.id}: {e}")

    async def _notify_admins_error(self, error_type: str, error_message: str):
        """Уведомление админов об ошибке."""
        async with get_unit_of_work() as uow:
            admins = await uow.users.get_admins()

            message = (
                f"🚨 <b>Ошибка в боте!</b>\n\n"
                f"Тип: {error_type}\n"
                f"Сообщение: {error_message}\n"
                f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )

            for admin in admins:
                try:
                    await self.bot.send_message(
                        admin.telegram_id,
                        message,
                        parse_mode="HTML"
                    )
                except:
                    pass

    async def _send_stats_to_admins(self, stats: dict):
        """Отправка статистики админам."""
        analytics_service = get_analytics_service()

        # Форматируем статистику
        message = (
            f"📊 <b>Ежедневная статистика</b>\n\n"
            f"<b>Пользователи:</b>\n"
            f"• Всего: {stats['users']['total']}\n"
            f"• Активных сегодня: {stats['users']['active_today']}\n"
            f"• Активных за неделю: {stats['users']['active_week']}\n\n"
            f"<b>Подписки:</b>\n"
            f"• Активных: {stats['subscriptions']['total_active']}\n"
            f"• Конверсия: {stats['subscriptions']['conversion_rate']:.1f}%\n\n"
            f"<b>Использование:</b>\n"
            f"• Раскладов: {stats['usage']['total_spreads']}\n"
            f"• Гороскопов: {stats['usage']['total_horoscopes']}\n\n"
            f"<b>Финансы:</b>\n"
            f"• Доход сегодня: {stats['revenue']['today']:.0f} ₽\n"
            f"• Доход за месяц: {stats['revenue']['month']:.0f} ₽\n"
            f"• ARPU: {stats['revenue']['arpu']:.0f} ₽"
        )

        async with get_unit_of_work() as uow:
            admins = await uow.users.get_admins()

            for admin in admins:
                try:
                    await self.bot.send_message(
                        admin.telegram_id,
                        message,
                        parse_mode="HTML"
                    )
                except:
                    pass


async def main():
    """Главная функция запуска."""
    # Настройка логирования
    setup_logging()

    # Загрузка настроек
    settings = Settings()

    # Создание и инициализация бота
    bot = AstroTarotBot(settings)

    try:
        # Инициализация
        await bot.initialize()

        # Обработка сигналов для graceful shutdown
        loop = asyncio.get_event_loop()

        def signal_handler(sig, frame):
            logger.info(f"Received signal {sig}")
            asyncio.create_task(bot.stop())
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # Запуск бота
        logger.info("Starting bot...")
        await bot.start()

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        await bot.stop()
        sys.exit(1)


if __name__ == "__main__":
    # Проверка версии Python
    if sys.version_info < (3, 10):
        print("Error: Python 3.10+ is required")
        sys.exit(1)

    # Запуск
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)