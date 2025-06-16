"""
Модуль интерфейсов репозиториев для Астро-Таро Бота.

Этот модуль содержит абстрактные базовые классы (интерфейсы) для
репозиториев. Репозитории отвечают за сохранение и получение данных
из хранилища (БД, кэш и т.д.) и являются частью паттерна Repository.

Преимущества:
- Изоляция бизнес-логики от деталей хранения данных
- Легкая замена реализации хранилища
- Удобное тестирование через mock-объекты
- Единообразный интерфейс для всех репозиториев

Использование:
    from core.interfaces import IRepository, IUserRepository
    from infrastructure.database import UserRepository

    # Реализация должна наследоваться от интерфейса
    class UserRepository(IUserRepository):
        async def get_by_telegram_id(self, telegram_id: int) -> Optional[User]:
            # Реализация получения из БД
            ...
"""

from abc import ABC, abstractmethod
from typing import (
    TypeVar, Generic, Optional, List, Dict, Any,
    Union, Callable, Type, Tuple
)
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

from config import logger

# Типы для обобщенного репозитория
T = TypeVar('T')  # Тип сущности
ID = TypeVar('ID')  # Тип идентификатора


# ===== БАЗОВЫЕ КЛАССЫ ДЛЯ ФИЛЬТРАЦИИ И СОРТИРОВКИ =====

class SortOrder(str, Enum):
    """Порядок сортировки."""
    ASC = "asc"
    DESC = "desc"


@dataclass
class SortBy:
    """Параметры сортировки."""
    field: str
    order: SortOrder = SortOrder.ASC


@dataclass
class Pagination:
    """Параметры пагинации."""
    page: int = 1
    page_size: int = 20

    @property
    def offset(self) -> int:
        """Вычислить offset для SQL запроса."""
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        """Вычислить limit для SQL запроса."""
        return self.page_size


@dataclass
class Filter:
    """Базовый класс для фильтров."""
    field: str
    operator: str
    value: Any


@dataclass
class FilterGroup:
    """Группа фильтров с логическим оператором."""
    filters: List[Union[Filter, 'FilterGroup']]
    operator: str = "AND"  # AND или OR


@dataclass
class QueryOptions:
    """Опции для сложных запросов."""
    filters: Optional[FilterGroup] = None
    sort_by: Optional[List[SortBy]] = None
    pagination: Optional[Pagination] = None
    include_deleted: bool = False
    lock_for_update: bool = False


# ===== РЕЗУЛЬТАТЫ ЗАПРОСОВ =====

@dataclass
class Page(Generic[T]):
    """Страница результатов с метаданными."""
    items: List[T]
    total: int
    page: int
    page_size: int

    @property
    def total_pages(self) -> int:
        """Общее количество страниц."""
        return (self.total + self.page_size - 1) // self.page_size

    @property
    def has_next(self) -> bool:
        """Есть ли следующая страница."""
        return self.page < self.total_pages

    @property
    def has_previous(self) -> bool:
        """Есть ли предыдущая страница."""
        return self.page > 1


# ===== БАЗОВЫЙ ИНТЕРФЕЙС РЕПОЗИТОРИЯ =====

class IRepository(ABC, Generic[T, ID]):
    """
    Базовый интерфейс репозитория с CRUD операциями.

    Параметры типов:
        T: Тип сущности (например, User)
        ID: Тип идентификатора (например, int)
    """

    @abstractmethod
    async def get_by_id(self, id: ID) -> Optional[T]:
        """
        Получить сущность по ID.

        Args:
            id: Идентификатор сущности

        Returns:
            Сущность или None если не найдена
        """
        pass

    @abstractmethod
    async def get_many(self, ids: List[ID]) -> List[T]:
        """
        Получить несколько сущностей по списку ID.

        Args:
            ids: Список идентификаторов

        Returns:
            Список найденных сущностей
        """
        pass

    @abstractmethod
    async def get_all(self, options: Optional[QueryOptions] = None) -> List[T]:
        """
        Получить все сущности с опциональной фильтрацией.

        Args:
            options: Опции запроса (фильтры, сортировка)

        Returns:
            Список сущностей
        """
        pass

    @abstractmethod
    async def get_page(self, options: QueryOptions) -> Page[T]:
        """
        Получить страницу сущностей.

        Args:
            options: Опции запроса с пагинацией

        Returns:
            Страница с метаданными
        """
        pass

    @abstractmethod
    async def find_one(self, **criteria) -> Optional[T]:
        """
        Найти одну сущность по критериям.

        Args:
            **criteria: Критерии поиска

        Returns:
            Первая найденная сущность или None
        """
        pass

    @abstractmethod
    async def find_many(self, **criteria) -> List[T]:
        """
        Найти сущности по критериям.

        Args:
            **criteria: Критерии поиска

        Returns:
            Список найденных сущностей
        """
        pass

    @abstractmethod
    async def create(self, entity: T) -> T:
        """
        Создать новую сущность.

        Args:
            entity: Сущность для создания

        Returns:
            Созданная сущность с заполненным ID

        Raises:
            EntityAlreadyExistsError: Если сущность уже существует
        """
        pass

    @abstractmethod
    async def create_many(self, entities: List[T]) -> List[T]:
        """
        Создать несколько сущностей.

        Args:
            entities: Список сущностей

        Returns:
            Список созданных сущностей
        """
        pass

    @abstractmethod
    async def update(self, entity: T) -> T:
        """
        Обновить существующую сущность.

        Args:
            entity: Сущность с обновленными данными

        Returns:
            Обновленная сущность

        Raises:
            EntityNotFoundError: Если сущность не найдена
        """
        pass

    @abstractmethod
    async def update_partial(self, id: ID, **fields) -> T:
        """
        Частичное обновление сущности.

        Args:
            id: ID сущности
            **fields: Поля для обновления

        Returns:
            Обновленная сущность

        Raises:
            EntityNotFoundError: Если сущность не найдена
        """
        pass

    @abstractmethod
    async def delete(self, id: ID) -> bool:
        """
        Удалить сущность по ID.

        Args:
            id: ID сущности

        Returns:
            True если удалено, False если не найдено
        """
        pass

    @abstractmethod
    async def delete_many(self, ids: List[ID]) -> int:
        """
        Удалить несколько сущностей.

        Args:
            ids: Список ID для удаления

        Returns:
            Количество удаленных сущностей
        """
        pass

    @abstractmethod
    async def exists(self, id: ID) -> bool:
        """
        Проверить существование сущности.

        Args:
            id: ID сущности

        Returns:
            True если существует
        """
        pass

    @abstractmethod
    async def count(self, **criteria) -> int:
        """
        Подсчитать количество сущностей.

        Args:
            **criteria: Критерии подсчета

        Returns:
            Количество сущностей
        """
        pass


# ===== СПЕЦИАЛИЗИРОВАННЫЕ ИНТЕРФЕЙСЫ =====

class IUserRepository(IRepository[Any, int], ABC):
    """Интерфейс репозитория пользователей."""

    @abstractmethod
    async def get_by_telegram_id(self, telegram_id: int) -> Optional[Any]:
        """Получить пользователя по Telegram ID."""
        pass

    @abstractmethod
    async def get_by_username(self, username: str) -> Optional[Any]:
        """Получить пользователя по username."""
        pass

    @abstractmethod
    async def get_active_users(self, days: int = 30) -> List[Any]:
        """Получить активных пользователей за последние N дней."""
        pass

    @abstractmethod
    async def get_subscribers(self, plan: Optional[str] = None) -> List[Any]:
        """Получить пользователей с активной подпиской."""
        pass

    @abstractmethod
    async def search(self, query: str) -> List[Any]:
        """Поиск пользователей по имени или username."""
        pass

    @abstractmethod
    async def update_last_activity(self, user_id: int) -> None:
        """Обновить время последней активности."""
        pass

    @abstractmethod
    async def increment_request_count(self, user_id: int) -> None:
        """Увеличить счетчик запросов."""
        pass


class ISubscriptionRepository(IRepository[Any, int], ABC):
    """Интерфейс репозитория подписок."""

    @abstractmethod
    async def get_by_user_id(self, user_id: int) -> Optional[Any]:
        """Получить подписку пользователя."""
        pass

    @abstractmethod
    async def get_active_subscriptions(self) -> List[Any]:
        """Получить все активные подписки."""
        pass

    @abstractmethod
    async def get_expiring_soon(self, days: int = 3) -> List[Any]:
        """Получить подписки, истекающие в ближайшие N дней."""
        pass

    @abstractmethod
    async def get_by_payment_id(self, payment_id: str) -> Optional[Any]:
        """Получить подписку по ID платежа."""
        pass

    @abstractmethod
    async def activate(self, subscription_id: int, until: datetime) -> Any:
        """Активировать подписку до указанной даты."""
        pass

    @abstractmethod
    async def cancel(self, subscription_id: int, immediate: bool = False) -> Any:
        """Отменить подписку."""
        pass


class IBirthChartRepository(IRepository[Any, int], ABC):
    """Интерфейс репозитория натальных карт."""

    @abstractmethod
    async def get_by_user_id(self, user_id: int) -> Optional[Any]:
        """Получить натальную карту пользователя."""
        pass

    @abstractmethod
    async def get_cached(self, cache_key: str) -> Optional[Any]:
        """Получить закэшированную карту."""
        pass

    @abstractmethod
    async def save_cached(self, cache_key: str, chart: Any, ttl: int = 3600) -> None:
        """Сохранить карту в кэш."""
        pass

    @abstractmethod
    async def search_by_birth_date(
            self,
            start_date: datetime,
            end_date: datetime
    ) -> List[Any]:
        """Найти карты по диапазону дат рождения."""
        pass


class ITarotReadingRepository(IRepository[Any, int], ABC):
    """Интерфейс репозитория раскладов Таро."""

    @abstractmethod
    async def get_user_readings(
            self,
            user_id: int,
            spread_type: Optional[str] = None,
            limit: int = 10
    ) -> List[Any]:
        """Получить расклады пользователя."""
        pass

    @abstractmethod
    async def get_daily_card(self, user_id: int, date: datetime) -> Optional[Any]:
        """Получить карту дня для пользователя."""
        pass

    @abstractmethod
    async def count_user_readings_today(self, user_id: int) -> int:
        """Подсчитать количество раскладов пользователя за сегодня."""
        pass

    @abstractmethod
    async def get_popular_spreads(self, days: int = 7) -> List[Tuple[str, int]]:
        """Получить популярные расклады за период."""
        pass


class IPaymentRepository(IRepository[Any, str], ABC):
    """Интерфейс репозитория платежей."""

    @abstractmethod
    async def get_by_subscription_id(self, subscription_id: int) -> List[Any]:
        """Получить платежи по подписке."""
        pass

    @abstractmethod
    async def get_user_payments(self, user_id: int) -> List[Any]:
        """Получить все платежи пользователя."""
        pass

    @abstractmethod
    async def get_pending_payments(self) -> List[Any]:
        """Получить ожидающие платежи."""
        pass

    @abstractmethod
    async def update_status(self, payment_id: str, status: str) -> Any:
        """Обновить статус платежа."""
        pass

    @abstractmethod
    async def get_revenue_stats(
            self,
            start_date: datetime,
            end_date: datetime
    ) -> Dict[str, Any]:
        """Получить статистику доходов за период."""
        pass


# ===== UNIT OF WORK ИНТЕРФЕЙС =====

class IUnitOfWork(ABC):
    """
    Интерфейс Unit of Work для управления транзакциями.

    Обеспечивает атомарность операций над несколькими репозиториями.
    """

    # Репозитории
    users: IUserRepository
    subscriptions: ISubscriptionRepository
    birth_charts: IBirthChartRepository
    tarot_readings: ITarotReadingRepository
    payments: IPaymentRepository

    @abstractmethod
    async def __aenter__(self):
        """Начать транзакцию."""
        pass

    @abstractmethod
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Завершить транзакцию (commit или rollback)."""
        pass

    @abstractmethod
    async def commit(self) -> None:
        """Зафиксировать изменения."""
        pass

    @abstractmethod
    async def rollback(self) -> None:
        """Откатить изменения."""
        pass


# ===== ФАБРИКА РЕПОЗИТОРИЕВ =====

class IRepositoryFactory(ABC):
    """Интерфейс фабрики репозиториев."""

    @abstractmethod
    def create_user_repository(self) -> IUserRepository:
        """Создать репозиторий пользователей."""
        pass

    @abstractmethod
    def create_subscription_repository(self) -> ISubscriptionRepository:
        """Создать репозиторий подписок."""
        pass

    @abstractmethod
    def create_birth_chart_repository(self) -> IBirthChartRepository:
        """Создать репозиторий натальных карт."""
        pass

    @abstractmethod
    def create_tarot_reading_repository(self) -> ITarotReadingRepository:
        """Создать репозиторий раскладов Таро."""
        pass

    @abstractmethod
    def create_payment_repository(self) -> IPaymentRepository:
        """Создать репозиторий платежей."""
        pass

    @abstractmethod
    def create_unit_of_work(self) -> IUnitOfWork:
        """Создать Unit of Work."""
        pass


# Экспорт
__all__ = [
    # Базовые классы
    "IRepository",
    "IUnitOfWork",
    "IRepositoryFactory",

    # Специализированные репозитории
    "IUserRepository",
    "ISubscriptionRepository",
    "IBirthChartRepository",
    "ITarotReadingRepository",
    "IPaymentRepository",

    # Вспомогательные классы
    "SortOrder",
    "SortBy",
    "Pagination",
    "Filter",
    "FilterGroup",
    "QueryOptions",
    "Page",
]