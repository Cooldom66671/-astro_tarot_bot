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
from urllib.parse import quote_plus, urlparse

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
            self._pool_recycle = getattr(settings.database, 'pool_recycle', 3600)
            self._pool_pre_ping = True
            self._echo = settings.database.echo
            self._health_check_interval = 60
            self._last_health_check = 0
            logger.info("DatabaseConnection инициализирован")

    def _build_connection_string(self) -> str:
        """
        Построение строки подключения к PostgreSQL.

        Returns:
            Строка подключения в формате asyncpg
        """
        # Если уже есть полный URL, проверяем и корректируем его
        db_url = settings.database.url

        if db_url.startswith('postgresql://'):
            # Заменяем на asyncpg драйвер
            db_url = db_url.replace('postgresql://', 'postgresql+asyncpg://', 1)
        elif db_url.startswith('postgres://'):
            # Старый формат Heroku
            db_url = db_url.replace('postgres://', 'postgresql+asyncpg://', 1)
        elif not db_url.startswith('postgresql+asyncpg://'):
            # Если URL не имеет правильного префикса
            logger.warning(f"Неожиданный формат DATABASE_URL: {db_url[:20]}...")
            # Пытаемся построить URL из компонентов
            return self._build_from_components()

        logger.debug("Строка подключения к БД построена из DATABASE_URL")
        return db_url

    def _build_from_components(self) -> str:
        """Построение строки подключения из отдельных компонентов."""
        # Парсим существующий URL чтобы извлечь компоненты
        parsed = urlparse(settings.database.url)

        host = parsed.hostname or 'localhost'
        port = parsed.port or 5432
        username = parsed.username or 'postgres'
        password = parsed.password or 'postgres'
        database = parsed.path.lstrip('/') if parsed.path else 'astrotarot_db'

        # Экранирование специальных символов в пароле
        if password:
            password = quote_plus(password)

        # Строим URL
        conn_str = f"postgresql+asyncpg://{username}:{password}@{host}:{port}/{database}"

        # Дополнительные параметры из query string
        if parsed.query:
            conn_str += f"?{parsed.query}"

        logger.debug("Строка подключения построена из компонентов")
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
                if settings.environment == "testing":
                    pool_class = NullPool  # Без пула для тестов
                else:
                    pool_class = AsyncAdaptedQueuePool

                # Параметры подключения
                connect_args = {
                    "server_settings": {
                        "application_name": settings.bot.name,
                        "jit": "off"
                    },
                    "command_timeout": 60
                }

                # Добавляем timeout если поддерживается
                pool_timeout = getattr(settings.database, 'pool_timeout', 30)
                connect_args["timeout"] = pool_timeout

                # Создание движка SQLAlchemy
                self._engine = create_async_engine(
                    self._connection_string,
                    echo=self._echo,
                    pool_size=settings.database.pool_size,
                    max_overflow=settings.database.max_overflow,
                    pool_timeout=pool_timeout,
                    pool_recycle=self._pool_recycle,
                    pool_pre_ping=self._pool_pre_ping,
                    poolclass=pool_class,
                    connect_args=connect_args
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
            # Получаем PID соединения безопасным способом
            try:
                if hasattr(dbapi_conn, 'get_backend_pid'):
                    pid = dbapi_conn.get_backend_pid()
                else:
                    # Для asyncpg используем другой метод
                    pid = 'async'
                connection_record.info['pid'] = pid
                logger.debug(f"Новое подключение к БД, PID: {pid}")
            except Exception as e:
                logger.debug(f"Не удалось получить PID: {e}")

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

    async def close(self) -> None:
        """Псевдоним для disconnect() для совместимости."""
        await self.disconnect()

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

                # Получаем имя БД из URL
                parsed_url = urlparse(self._connection_string)
                db_name = parsed_url.path.lstrip('/').split('?')[0] or 'astrotarot_db'

                # Размер БД
                try:
                    size_result = await conn.execute(
                        text(f"SELECT pg_database_size('{db_name}')")
                    )
                    db_size = await size_result.scalar()
                except Exception:
                    db_size = 0

                # Количество активных соединений
                try:
                    connections_result = await conn.execute(
                        text("SELECT count(*) FROM pg_stat_activity WHERE datname = :dbname"),
                        {"dbname": db_name}
                    )
                    active_connections = await connections_result.scalar()
                except Exception:
                    active_connections = 0

                # Версия PostgreSQL
                try:
                    version_result = await conn.execute(text("SELECT version()"))
                    pg_version = await version_result.scalar()
                    # Извлекаем только версию
                    import re
                    version_match = re.search(r'PostgreSQL (\d+\.\d+)', pg_version)
                    version = version_match.group(1) if version_match else 'unknown'
                except Exception:
                    version = 'unknown'

                return {
                    "status": "healthy",
                    "message": "Подключение активно",
                    "version": version,
                    "details": {
                        "pool_status": str(pool_status),
                        "database_name": db_name,
                        "database_size_mb": round(db_size / 1024 / 1024, 2) if db_size else 0,
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

    async def execute_raw(self, query: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """
        Выполнение сырого SQL запроса.

        Args:
            query: SQL запрос
            params: Параметры запроса

        Returns:
            Результат выполнения запроса
        """
        async with self.get_session() as session:
            result = await session.execute(text(query), params or {})
            await session.commit()
            return result

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
@asynccontextmanager
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


# Экспорт компонентов
__all__ = [
    'Base',
    'DatabaseConnection',
    'db_connection',
    'get_db_session',
    'init_database',
    'shutdown_database'
]