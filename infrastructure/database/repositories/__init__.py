"""
Экспорт репозиториев и реализация Unit of Work.

Этот модуль содержит:
- Импорт и экспорт всех репозиториев
- Реализацию паттерна Unit of Work
- Фабрику для создания репозиториев
- Вспомогательные функции для работы с БД
"""

from typing import Type, TypeVar, Optional, AsyncContextManager
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession

from config import logger
from core.interfaces.repository import IUnitOfWork, IRepositoryFactory
from infrastructure.database.connection import db_connection
from infrastructure.database.repositories.base import BaseRepository

# Импорт конкретных репозиториев
from infrastructure.database.repositories.user import UserRepository
from infrastructure.database.repositories.tarot import TarotRepository
from infrastructure.database.repositories.subscription import SubscriptionRepository

# Экспорт репозиториев
__all__ = [
    # Базовый класс
    'BaseRepository',

    # Конкретные репозитории
    'UserRepository',
    'TarotRepository',
    'SubscriptionRepository',

    # Unit of Work
    'UnitOfWork',
    'get_unit_of_work',

    # Фабрика
    'RepositoryFactory',
    'get_repository'
]

T = TypeVar('T', bound=BaseRepository)


class UnitOfWork(IUnitOfWork):
    """
    Реализация паттерна Unit of Work.

    Управляет транзакциями и предоставляет доступ ко всем репозиториям
    в рамках одной транзакции.
    """

    def __init__(self, session: AsyncSession):
        """
        Инициализация Unit of Work.

        Args:
            session: Сессия БД
        """
        self._session = session
        self._repositories = {}

        # Инициализация репозиториев
        self._users: Optional[UserRepository] = None
        self._tarot: Optional[TarotRepository] = None
        self._subscriptions: Optional[SubscriptionRepository] = None

        logger.debug("UnitOfWork инициализирован")

    @property
    def users(self) -> UserRepository:
        """Репозиторий пользователей."""
        if self._users is None:
            self._users = UserRepository(self._session)
            self._repositories['users'] = self._users
        return self._users

    @property
    def tarot(self) -> TarotRepository:
        """Репозиторий Таро."""
        if self._tarot is None:
            self._tarot = TarotRepository(self._session)
            self._repositories['tarot'] = self._tarot
        return self._tarot

    @property
    def subscriptions(self) -> SubscriptionRepository:
        """Репозиторий подписок."""
        if self._subscriptions is None:
            self._subscriptions = SubscriptionRepository(self._session)
            self._repositories['subscriptions'] = self._subscriptions
        return self._subscriptions

    async def commit(self) -> None:
        """
        Фиксация транзакции.

        Raises:
            DatabaseError: При ошибке фиксации
        """
        try:
            await self._session.commit()
            logger.debug("Транзакция зафиксирована")
        except Exception as e:
            logger.error(f"Ошибка фиксации транзакции: {e}")
            await self.rollback()
            raise

    async def rollback(self) -> None:
        """Откат транзакции."""
        try:
            await self._session.rollback()
            logger.debug("Транзакция откачена")
        except Exception as e:
            logger.error(f"Ошибка отката транзакции: {e}")

    async def close(self) -> None:
        """Закрытие сессии."""
        await self._session.close()
        logger.debug("Сессия закрыта")

    def get_repository(self, name: str) -> Optional[BaseRepository]:
        """
        Получение репозитория по имени.

        Args:
            name: Имя репозитория

        Returns:
            Репозиторий или None
        """
        return self._repositories.get(name)

    def reset_query_counts(self) -> None:
        """Сброс счетчиков запросов во всех репозиториях."""
        for repo in self._repositories.values():
            if hasattr(repo, 'reset_query_count'):
                repo.reset_query_count()

    def get_total_query_count(self) -> int:
        """Получение общего количества запросов."""
        total = 0
        for repo in self._repositories.values():
            if hasattr(repo, 'query_count'):
                total += repo.query_count
        return total

    async def __aenter__(self):
        """Вход в контекстный менеджер."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        Выход из контекстного менеджера.

        При исключении автоматически откатывает транзакцию.
        """
        if exc_type:
            await self.rollback()
        else:
            await self.commit()
        await self.close()


@asynccontextmanager
async def get_unit_of_work() -> AsyncContextManager[UnitOfWork]:
    """
    Получение Unit of Work в виде контекстного менеджера.

    Yields:
        UnitOfWork для работы с репозиториями

    Example:
        async with get_unit_of_work() as uow:
            user = await uow.users.get_by_telegram_id(123456)
            await uow.users.update(user.id, last_activity_at=datetime.utcnow())
            # Автоматический commit при выходе
    """
    async with db_connection.get_session() as session:
        uow = UnitOfWork(session)
        try:
            yield uow
            await uow.commit()
        except Exception:
            await uow.rollback()
            raise
        finally:
            # Логирование статистики
            query_count = uow.get_total_query_count()
            if query_count > 10:
                logger.warning(f"Большое количество запросов в UoW: {query_count}")


class RepositoryFactory(IRepositoryFactory):
    """
    Фабрика для создания репозиториев.

    Позволяет создавать репозитории динамически по типу.
    """

    # Маппинг типов на классы репозиториев
    _repository_map = {
        'user': UserRepository,
        'users': UserRepository,
        'tarot': TarotRepository,
        'subscription': SubscriptionRepository,
        'subscriptions': SubscriptionRepository,
    }

    def __init__(self, session: AsyncSession):
        """
        Инициализация фабрики.

        Args:
            session: Сессия БД
        """
        self._session = session
        self._cache = {}

    def create_repository(
            self,
            repository_type: str
    ) -> Optional[BaseRepository]:
        """
        Создание репозитория по типу.

        Args:
            repository_type: Тип репозитория

        Returns:
            Экземпляр репозитория или None
        """
        # Проверяем кэш
        if repository_type in self._cache:
            return self._cache[repository_type]

        # Получаем класс репозитория
        repo_class = self._repository_map.get(repository_type.lower())
        if not repo_class:
            logger.error(f"Неизвестный тип репозитория: {repository_type}")
            return None

        # Создаем экземпляр
        repository = repo_class(self._session)
        self._cache[repository_type] = repository

        logger.debug(f"Создан репозиторий типа {repository_type}")
        return repository

    def get_repository_class(
            self,
            repository_type: str
    ) -> Optional[Type[BaseRepository]]:
        """
        Получение класса репозитория по типу.

        Args:
            repository_type: Тип репозитория

        Returns:
            Класс репозитория или None
        """
        return self._repository_map.get(repository_type.lower())

    @classmethod
    def register_repository(
            cls,
            repository_type: str,
            repository_class: Type[BaseRepository]
    ) -> None:
        """
        Регистрация нового типа репозитория.

        Args:
            repository_type: Тип репозитория
            repository_class: Класс репозитория
        """
        cls._repository_map[repository_type.lower()] = repository_class
        logger.info(f"Зарегистрирован репозиторий {repository_type}")


async def get_repository(
        repository_type: str,
        session: Optional[AsyncSession] = None
) -> BaseRepository:
    """
    Быстрое получение репозитория.

    Args:
        repository_type: Тип репозитория
        session: Сессия БД (создается если не указана)

    Returns:
        Экземпляр репозитория

    Raises:
        ValueError: Если тип репозитория неизвестен
    """
    if session is None:
        async with db_connection.get_session() as session:
            factory = RepositoryFactory(session)
            repo = factory.create_repository(repository_type)
            if not repo:
                raise ValueError(f"Неизвестный тип репозитория: {repository_type}")
            return repo
    else:
        factory = RepositoryFactory(session)
        repo = factory.create_repository(repository_type)
        if not repo:
            raise ValueError(f"Неизвестный тип репозитория: {repository_type}")
        return repo


# Вспомогательные функции для частых операций

async def get_user_by_telegram_id(telegram_id: int):
    """
    Быстрое получение пользователя по Telegram ID.

    Args:
        telegram_id: ID в Telegram

    Returns:
        Пользователь или None
    """
    async with get_unit_of_work() as uow:
        return await uow.users.get_by_telegram_id(telegram_id)


async def create_or_update_user_from_telegram(
        telegram_id: int,
        first_name: str,
        last_name: Optional[str] = None,
        username: Optional[str] = None,
        language_code: str = "ru"
):
    """
    Быстрое создание/обновление пользователя.

    Args:
        telegram_id: ID в Telegram
        first_name: Имя
        last_name: Фамилия
        username: Username
        language_code: Язык

    Returns:
        Кортеж (пользователь, создан_новый)
    """
    async with get_unit_of_work() as uow:
        return await uow.users.create_or_update_from_telegram(
            telegram_id=telegram_id,
            first_name=first_name,
            last_name=last_name,
            username=username,
            language_code=language_code
        )


async def create_tarot_reading(
        user_id: int,
        spread_code: str,
        question: Optional[str] = None
):
    """
    Быстрое создание расклада Таро.

    Args:
        user_id: ID пользователя
        spread_code: Код расклада
        question: Вопрос

    Returns:
        Созданный расклад
    """
    async with get_unit_of_work() as uow:
        # Проверяем лимиты пользователя
        await uow.users.increment_reading_count(user_id)

        # Создаем расклад
        reading = await uow.tarot.create_reading(
            user_id=user_id,
            spread_code=spread_code,
            question=question
        )

        return reading


# Статистика и мониторинг

async def get_database_statistics():
    """
    Получение общей статистики по БД.

    Returns:
        Словарь со статистикой
    """
    async with get_unit_of_work() as uow:
        stats = {
            "users": {
                "total": await uow.users.count(),
                "active": await uow.users.get_active_users_count(30),
                "subscriptions": await uow.users.get_subscription_statistics()
            },
            "tarot": {
                "total_readings": await uow.tarot.count(),
                "popular_spreads": await uow.tarot.get_popular_spreads()
            },
            "revenue": await uow.subscriptions.get_revenue_statistics()
        }

        return stats


# Инициализация при импорте
logger.info("Репозитории инициализированы")