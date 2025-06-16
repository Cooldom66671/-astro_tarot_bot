"""
Модуль управления подключением к PostgreSQL.

Этот модуль отвечает за:
- Создание и управление пулом соединений с PostgreSQL
- Настройка SQLAlchemy Engine и Session
- Управление транзакциями
- Автоматическое переподключение при разрыве связи
- Мониторинг состояния подключений
- Graceful shutdown при остановке приложения
"""

import asyncio
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional, Dict, Any
from urllib.parse import quote_plus

from sqlalchemy import event, pool, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    create_async_engine,
    async_sessionmaker
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool, AsyncAdaptedQueuePool
from sqlalchemy.exc import DBAPIError, SQLAlchemyError

from config import settings, logger
from core.exceptions import DatabaseConnectionError


class Base(DeclarativeBase):
    """
    Базовый класс для всех моделей SQLAlchemy.
    Все таблицы БД должны наследоваться от этого класса.
    """
    pass


class DatabaseConnection:
    """
    Менеджер подключения к PostgreSQL.

    Использует паттерн Singleton для обеспечения единственного
    экземпляра подключения к БД во всем приложении.
    """

    _instance: Optional['DatabaseConnection'] = None
    _engine: Optional[AsyncEngine] = None
    _session_factory: Optional[async_sessionmaker] = None
    _connection_retries: int = 3
    _retry_delay: int = 5

    def __new__(cls) -> 'DatabaseConnection':
        """Реализация паттерна Singleton."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Инициализация менеджера подключений."""
        if not hasattr(self, '_initialized'):
            self._initialized = True
            self._connection_string = self._build_connection_string()
            self._pool_recycle = 3600  # Переподключение каждый час
            self._pool_pre_ping = True  # Проверка соединения перед использованием
            self._echo = settings.database.echo_sql
            self._health_check_interval = 60  # Проверка здоровья каждую минуту
            self._last_health_check = 0
            logger.info("DatabaseConnection инициализирован")

    def _build_connection_string(self) -> str:
        """
        Построение строки подключения к PostgreSQL.

        Returns:
            Строка подключения в формате asyncpg
        """
        # Экранирование специальных символов в пароле
        password = quote_plus(settings.database.password.get_secret_value())

        # Базовая строка подключения
        conn_str = (
            f"postgresql+asyncpg://{settings.database.user}:{password}"
            f"@{settings.database.host}:{settings.database.port}"
            f"/{settings.database.name}"
        )

        # Дополнительные параметры подключения
        params = []
        if settings.database.ssl_mode:
            params.append(f"sslmode={settings.database.ssl_mode}")

        if params:
            conn_str += "?" + "&".join(params)

        logger.debug("Строка подключения к БД построена")
        return conn_str

    async def connect(self) -> None:
        """
        Установка подключения к БД с повторными попытками.

        Raises:
            DatabaseConnectionError: При невозможности подключиться
        """
        for attempt in range(self._connection_retries):
            try:
                logger.info(f"Попытка подключения к БД {attempt + 1}/{self._connection_retries}")

                # Выбор пула соединений в зависимости от окружения
                if settings.is_testing():
                    pool_class = NullPool  # Без пула для тестов
                else:
                    pool_class = AsyncAdaptedQueuePool

                # Создание движка SQLAlchemy
                self._engine = create_async_engine(
                    self._connection_string,
                    echo=self._echo,
                    pool_size=settings.database.pool_size,
                    max_overflow=settings.database.max_overflow,
                    pool_timeout=settings.database.pool_timeout,
                    pool_recycle=self._pool_recycle,
                    pool_pre_ping=self._pool_pre_ping,
                    poolclass=pool_class,
                    connect_args={
                        "server_settings": {
                            "application_name": settings.bot.name,
                            "jit": "off"
                        },
                        "command_timeout": 60,
                        "timeout": settings.database.pool_timeout
                    }
                )

                # Создание фабрики сессий
                self._session_factory = async_sessionmaker(
                    self._engine,
                    class_=AsyncSession,
                    expire_on_commit=False,
                    autoflush=False,
                    autocommit=False
                )

                # Регистрация обработчиков событий
                self._register_event_handlers()

                # Проверка подключения
                await self._verify_connection()

                logger.info("✅ Успешное подключение к PostgreSQL")
                return

            except Exception as e:
                logger.error(f"Ошибка подключения к БД (попытка {attempt + 1}): {e}")

                if attempt < self._connection_retries - 1:
                    await asyncio.sleep(self._retry_delay)
                else:
                    raise DatabaseConnectionError(
                        "Не удалось подключиться к базе данных",
                        details={"attempts": self._connection_retries, "error": str(e)}
                    )

    def _register_event_handlers(self) -> None:
        """Регистрация обработчиков событий SQLAlchemy."""
        if not self._engine:
            return

        @event.listens_for(self._engine.sync_engine, "connect")
        def receive_connect(dbapi_conn, connection_record):
            """Обработчик события подключения."""
            connection_record.info['pid'] = dbapi_conn.get_backend_pid()
            logger.debug(f"Новое подключение к БД, PID: {connection_record.info['pid']}")

        @event.listens_for(self._engine.sync_engine, "checkout")
        def receive_checkout(dbapi_conn, connection_record, connection_proxy):
            """Обработчик получения соединения из пула."""
            pid = connection_record.info.get('pid', 'unknown')
            logger.debug(f"Получено соединение из пула, PID: {pid}")

    async def _verify_connection(self) -> None:
        """
        Проверка работоспособности подключения к БД.

        Raises:
            DatabaseConnectionError: При неработающем подключении
        """
        if not self._engine:
            raise DatabaseConnectionError("Engine не инициализирован")

        try:
            async with self._engine.connect() as conn:
                result = await conn.execute(text("SELECT 1"))
                await result.scalar()

                # Проверка версии PostgreSQL
                version_result = await conn.execute(text("SELECT version()"))
                version = await version_result.scalar()
                logger.info(f"PostgreSQL версия: {version}")

        except Exception as e:
            raise DatabaseConnectionError(
                "Не удалось проверить подключение к БД",
                details={"error": str(e)}
            )

    async def disconnect(self) -> None:
        """Корректное закрытие всех подключений к БД."""
        if self._engine:
            logger.info("Закрытие подключений к БД...")
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None
            logger.info("✅ Подключения к БД закрыты")

    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Асинхронный контекстный менеджер для получения сессии БД.

        Yields:
            AsyncSession: Сессия для работы с БД

        Raises:
            DatabaseConnectionError: При отсутствии подключения
        """
        if not self._session_factory:
            raise DatabaseConnectionError("Подключение к БД не установлено")

        async with self._session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception as e:
                await session.rollback()
                logger.error(f"Ошибка в сессии БД: {e}")
                raise
            finally:
                await session.close()

    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Контекстный менеджер для выполнения транзакций.

        Автоматически откатывает транзакцию при исключении.

        Yields:
            AsyncSession: Сессия в рамках транзакции
        """
        async with self.get_session() as session:
            async with session.begin():
                yield session

    async def health_check(self) -> Dict[str, Any]:
        """
        Проверка состояния подключения к БД.

        Returns:
            Словарь с информацией о состоянии подключения
        """
        current_time = time.time()

        # Ограничение частоты проверок
        if current_time - self._last_health_check < self._health_check_interval:
            return {"status": "cached", "message": "Используется кэшированный результат"}

        self._last_health_check = current_time

        try:
            if not self._engine:
                return {
                    "status": "disconnected",
                    "message": "Engine не инициализирован"
                }

            # Проверка подключения
            async with self._engine.connect() as conn:
                # Базовая проверка
                await conn.execute(text("SELECT 1"))

                # Статистика пула соединений
                pool_status = self._engine.pool.status() if hasattr(self._engine.pool, 'status') else "N/A"

                # Размер БД
                size_result = await conn.execute(
                    text(f"SELECT pg_database_size('{settings.database.name}')")
                )
                db_size = await size_result.scalar()

                # Количество активных соединений
                connections_result = await conn.execute(
                    text("SELECT count(*) FROM pg_stat_activity WHERE datname = :dbname"),
                    {"dbname": settings.database.name}
                )
                active_connections = await connections_result.scalar()

                return {
                    "status": "healthy",
                    "message": "Подключение активно",
                    "details": {
                        "pool_status": pool_status,
                        "database_size_mb": round(db_size / 1024 / 1024, 2),
                        "active_connections": active_connections,
                        "max_connections": settings.database.pool_size
                    }
                }

        except Exception as e:
            logger.error(f"Ошибка health check БД: {e}")
            return {
                "status": "unhealthy",
                "message": "Ошибка при проверке подключения",
                "error": str(e)
            }

    @property
    def engine(self) -> Optional[AsyncEngine]:
        """Получение движка SQLAlchemy."""
        return self._engine

    @property
    def is_connected(self) -> bool:
        """Проверка наличия активного подключения."""
        return self._engine is not None


# Глобальный экземпляр менеджера подключений
db_connection = DatabaseConnection()


# Вспомогательные функции для удобства использования
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Получение сессии БД через глобальный менеджер.

    Yields:
        AsyncSession: Сессия для работы с БД
    """
    async with db_connection.get_session() as session:
        yield session


async def init_database() -> None:
    """Инициализация подключения к БД при запуске приложения."""
    await db_connection.connect()
    logger.info("База данных инициализирована")


async def shutdown_database() -> None:
    """Корректное завершение работы с БД при остановке приложения."""
    await db_connection.disconnect()
    logger.info("Работа с базой данных завершена")