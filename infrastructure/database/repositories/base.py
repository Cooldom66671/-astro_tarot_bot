"""
Базовый репозиторий с CRUD операциями.

Этот модуль содержит:
- Абстрактный базовый репозиторий с общими методами
- Реализацию пагинации и фильтрации
- Поддержку транзакций и bulk операций
- Кэширование запросов
- Обработку ошибок и логирование
"""

from typing import (
    TypeVar, Generic, Optional, List, Dict, Any, Type,
    Union, Tuple, Callable
)
from abc import ABC, abstractmethod
from datetime import datetime
import json
from contextlib import asynccontextmanager

from sqlalchemy import select, update, delete, func, and_, or_, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload, contains_eager
from sqlalchemy.sql import Select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from config import logger
from core.interfaces.repository import (
    IRepository, QueryOptions, Pagination, Page, Filter,
    FilterOperator, FilterGroup, SortOrder
)
from core.exceptions import (
    EntityNotFoundError, DatabaseError, ValidationError
)
from infrastructure.database.models.base import BaseModel

# Type variable для обобщенных типов
T = TypeVar('T', bound=BaseModel)


class BaseRepository(Generic[T], IRepository[T], ABC):
    """
    Базовый репозиторий с реализацией CRUD операций.

    Предоставляет общие методы для работы с любыми моделями.
    """

    def __init__(self, session: AsyncSession, model_class: Type[T]):
        """
        Инициализация репозитория.

        Args:
            session: Сессия SQLAlchemy
            model_class: Класс модели для работы
        """
        self.session = session
        self.model_class = model_class
        self._query_count = 0

    @property
    def model_name(self) -> str:
        """Имя модели для логирования."""
        return self.model_class.__name__

    # CREATE операции

    async def create(self, **kwargs) -> T:
        """
        Создание новой записи.

        Args:
            **kwargs: Поля для создания

        Returns:
            Созданная запись

        Raises:
            ValidationError: При ошибке валидации
            DatabaseError: При ошибке БД
        """
        try:
            # Создание экземпляра модели
            instance = self.model_class(**kwargs)

            # Добавление в сессию
            self.session.add(instance)
            await self.session.flush()

            # Обновление из БД для получения defaults
            await self.session.refresh(instance)

            logger.info(f"Создана запись {self.model_name} id={instance.id}")
            return instance

        except IntegrityError as e:
            await self.session.rollback()
            raise ValidationError(
                f"Нарушение уникальности в {self.model_name}",
                details={"error": str(e.orig)}
            )
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Ошибка создания {self.model_name}: {e}")
            raise DatabaseError(f"Ошибка создания записи", details={"error": str(e)})

    async def create_many(self, items: List[Dict[str, Any]]) -> List[T]:
        """
        Массовое создание записей.

        Args:
            items: Список словарей с данными

        Returns:
            Список созданных записей
        """
        try:
            instances = []
            for item_data in items:
                instance = self.model_class(**item_data)
                self.session.add(instance)
                instances.append(instance)

            await self.session.flush()

            # Обновление всех записей
            for instance in instances:
                await self.session.refresh(instance)

            logger.info(f"Создано {len(instances)} записей {self.model_name}")
            return instances

        except Exception as e:
            await self.session.rollback()
            logger.error(f"Ошибка массового создания {self.model_name}: {e}")
            raise DatabaseError("Ошибка массового создания", details={"error": str(e)})

    # READ операции

    async def get_by_id(self, id: int) -> Optional[T]:
        """
        Получение записи по ID.

        Args:
            id: ID записи

        Returns:
            Найденная запись или None
        """
        self._query_count += 1

        query = select(self.model_class).where(self.model_class.id == id)
        result = await self.session.execute(query)

        instance = result.scalar_one_or_none()

        if instance:
            logger.debug(f"Найдена запись {self.model_name} id={id}")
        else:
            logger.debug(f"Не найдена запись {self.model_name} id={id}")

        return instance

    async def get_by_id_or_fail(self, id: int) -> T:
        """
        Получение записи по ID с исключением при отсутствии.

        Args:
            id: ID записи

        Returns:
            Найденная запись

        Raises:
            EntityNotFoundError: Если запись не найдена
        """
        instance = await self.get_by_id(id)
        if not instance:
            raise EntityNotFoundError(
                f"{self.model_name} с id={id} не найден",
                entity_type=self.model_name,
                entity_id=id
            )
        return instance

    async def get_all(
            self,
            options: Optional[QueryOptions] = None
    ) -> List[T]:
        """
        Получение всех записей с опциональной фильтрацией.

        Args:
            options: Опции запроса

        Returns:
            Список записей
        """
        query = self._build_query(options)
        result = await self.session.execute(query)

        instances = result.scalars().all()
        logger.debug(f"Получено {len(instances)} записей {self.model_name}")

        return list(instances)

    async def get_page(
            self,
            pagination: Pagination,
            options: Optional[QueryOptions] = None
    ) -> Page[T]:
        """
        Получение страницы записей.

        Args:
            pagination: Параметры пагинации
            options: Опции запроса

        Returns:
            Страница с записями
        """
        # Построение базового запроса
        query = self._build_query(options)

        # Подсчет общего количества
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0

        # Применение пагинации
        offset = (pagination.page - 1) * pagination.size
        query = query.offset(offset).limit(pagination.size)

        # Получение записей
        result = await self.session.execute(query)
        items = list(result.scalars().all())

        # Расчет страниц
        total_pages = (total + pagination.size - 1) // pagination.size

        logger.debug(
            f"Получена страница {pagination.page}/{total_pages} "
            f"{self.model_name} ({len(items)} записей)"
        )

        return Page(
            items=items,
            total=total,
            page=pagination.page,
            size=pagination.size,
            pages=total_pages
        )

    async def find_one(self, **filters) -> Optional[T]:
        """
        Поиск одной записи по фильтрам.

        Args:
            **filters: Поля для фильтрации

        Returns:
            Найденная запись или None
        """
        query = select(self.model_class)

        # Применение фильтров
        for field, value in filters.items():
            if hasattr(self.model_class, field):
                query = query.where(getattr(self.model_class, field) == value)

        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def find_many(self, **filters) -> List[T]:
        """
        Поиск записей по фильтрам.

        Args:
            **filters: Поля для фильтрации

        Returns:
            Список найденных записей
        """
        query = select(self.model_class)

        # Применение фильтров
        for field, value in filters.items():
            if hasattr(self.model_class, field):
                if isinstance(value, list):
                    query = query.where(getattr(self.model_class, field).in_(value))
                else:
                    query = query.where(getattr(self.model_class, field) == value)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def exists(self, **filters) -> bool:
        """
        Проверка существования записи.

        Args:
            **filters: Поля для фильтрации

        Returns:
            True если запись существует
        """
        query = select(func.count()).select_from(self.model_class)

        for field, value in filters.items():
            if hasattr(self.model_class, field):
                query = query.where(getattr(self.model_class, field) == value)

        result = await self.session.execute(query)
        count = result.scalar() or 0

        return count > 0

    async def count(self, options: Optional[QueryOptions] = None) -> int:
        """
        Подсчет количества записей.

        Args:
            options: Опции запроса

        Returns:
            Количество записей
        """
        query = self._build_query(options)
        count_query = select(func.count()).select_from(query.subquery())

        result = await self.session.execute(count_query)
        return result.scalar() or 0

    # UPDATE операции

    async def update(self, id: int, **kwargs) -> Optional[T]:
        """
        Обновление записи по ID.

        Args:
            id: ID записи
            **kwargs: Поля для обновления

        Returns:
            Обновленная запись или None
        """
        instance = await self.get_by_id(id)
        if not instance:
            return None

        return await self.update_instance(instance, **kwargs)

    async def update_instance(self, instance: T, **kwargs) -> T:
        """
        Обновление экземпляра модели.

        Args:
            instance: Экземпляр для обновления
            **kwargs: Поля для обновления

        Returns:
            Обновленный экземпляр
        """
        try:
            # Обновление полей
            for field, value in kwargs.items():
                if hasattr(instance, field):
                    setattr(instance, field, value)

            await self.session.flush()
            await self.session.refresh(instance)

            logger.info(f"Обновлена запись {self.model_name} id={instance.id}")
            return instance

        except Exception as e:
            await self.session.rollback()
            logger.error(f"Ошибка обновления {self.model_name}: {e}")
            raise DatabaseError("Ошибка обновления записи", details={"error": str(e)})

    async def update_many(
            self,
            filters: Dict[str, Any],
            updates: Dict[str, Any]
    ) -> int:
        """
        Массовое обновление записей.

        Args:
            filters: Фильтры для выбора записей
            updates: Поля для обновления

        Returns:
            Количество обновленных записей
        """
        try:
            stmt = update(self.model_class)

            # Применение фильтров
            for field, value in filters.items():
                if hasattr(self.model_class, field):
                    stmt = stmt.where(getattr(self.model_class, field) == value)

            # Установка значений
            stmt = stmt.values(**updates)

            result = await self.session.execute(stmt)
            count = result.rowcount

            logger.info(f"Обновлено {count} записей {self.model_name}")
            return count

        except Exception as e:
            await self.session.rollback()
            logger.error(f"Ошибка массового обновления {self.model_name}: {e}")
            raise DatabaseError("Ошибка массового обновления", details={"error": str(e)})

    # DELETE операции

    async def delete(self, id: int) -> bool:
        """
        Удаление записи по ID.

        Args:
            id: ID записи

        Returns:
            True если запись удалена
        """
        instance = await self.get_by_id(id)
        if not instance:
            return False

        return await self.delete_instance(instance)

    async def delete_instance(self, instance: T) -> bool:
        """
        Удаление экземпляра модели.

        Args:
            instance: Экземпляр для удаления

        Returns:
            True если удалено успешно
        """
        try:
            await self.session.delete(instance)
            await self.session.flush()

            logger.info(f"Удалена запись {self.model_name} id={instance.id}")
            return True

        except Exception as e:
            await self.session.rollback()
            logger.error(f"Ошибка удаления {self.model_name}: {e}")
            raise DatabaseError("Ошибка удаления записи", details={"error": str(e)})

    async def delete_many(self, ids: List[int]) -> int:
        """
        Массовое удаление записей.

        Args:
            ids: Список ID для удаления

        Returns:
            Количество удаленных записей
        """
        try:
            stmt = delete(self.model_class).where(
                self.model_class.id.in_(ids)
            )

            result = await self.session.execute(stmt)
            count = result.rowcount

            logger.info(f"Удалено {count} записей {self.model_name}")
            return count

        except Exception as e:
            await self.session.rollback()
            logger.error(f"Ошибка массового удаления {self.model_name}: {e}")
            raise DatabaseError("Ошибка массового удаления", details={"error": str(e)})

    # Вспомогательные методы

    def _build_query(self, options: Optional[QueryOptions] = None) -> Select:
        """
        Построение запроса с учетом опций.

        Args:
            options: Опции запроса

        Returns:
            Построенный запрос SQLAlchemy
        """
        query = select(self.model_class)

        if not options:
            return query

        # Применение фильтров
        if options.filters:
            conditions = self._build_filter_conditions(options.filters)
            if conditions is not None:
                query = query.where(conditions)

        # Применение сортировки
        if options.sort:
            for sort_field, order in options.sort:
                if hasattr(self.model_class, sort_field):
                    field = getattr(self.model_class, sort_field)
                    if order == SortOrder.DESC:
                        query = query.order_by(field.desc())
                    else:
                        query = query.order_by(field.asc())

        # Применение отношений для загрузки
        if options.include_relations:
            for relation in options.include_relations:
                if hasattr(self.model_class, relation):
                    query = query.options(selectinload(
                        getattr(self.model_class, relation)
                    ))

        return query

    def _build_filter_conditions(self, filters: List[Union[Filter, FilterGroup]]):
        """
        Построение условий фильтрации.

        Args:
            filters: Список фильтров

        Returns:
            Условия для WHERE
        """
        conditions = []

        for filter_item in filters:
            if isinstance(filter_item, Filter):
                condition = self._build_single_filter(filter_item)
                if condition is not None:
                    conditions.append(condition)

            elif isinstance(filter_item, FilterGroup):
                group_conditions = self._build_filter_conditions(filter_item.filters)
                if group_conditions:
                    if filter_item.operator == "AND":
                        conditions.append(and_(*group_conditions))
                    else:
                        conditions.append(or_(*group_conditions))

        return and_(*conditions) if conditions else None

    def _build_single_filter(self, filter: Filter):
        """
        Построение одного условия фильтра.

        Args:
            filter: Фильтр

        Returns:
            Условие SQLAlchemy
        """
        if not hasattr(self.model_class, filter.field):
            return None

        field = getattr(self.model_class, filter.field)
        value = filter.value

        if filter.operator == FilterOperator.EQ:
            return field == value
        elif filter.operator == FilterOperator.NE:
            return field != value
        elif filter.operator == FilterOperator.GT:
            return field > value
        elif filter.operator == FilterOperator.GTE:
            return field >= value
        elif filter.operator == FilterOperator.LT:
            return field < value
        elif filter.operator == FilterOperator.LTE:
            return field <= value
        elif filter.operator == FilterOperator.IN:
            return field.in_(value if isinstance(value, list) else [value])
        elif filter.operator == FilterOperator.NOT_IN:
            return ~field.in_(value if isinstance(value, list) else [value])
        elif filter.operator == FilterOperator.LIKE:
            return field.like(f"%{value}%")
        elif filter.operator == FilterOperator.ILIKE:
            return field.ilike(f"%{value}%")
        elif filter.operator == FilterOperator.IS_NULL:
            return field.is_(None) if value else field.isnot(None)
        elif filter.operator == FilterOperator.BETWEEN:
            if isinstance(value, list) and len(value) == 2:
                return field.between(value[0], value[1])

        return None

    @asynccontextmanager
    async def transaction(self):
        """
        Контекстный менеджер для транзакций.

        Yields:
            Сессия в рамках транзакции
        """
        async with self.session.begin():
            yield self.session

    async def refresh(self, instance: T) -> T:
        """
        Обновление экземпляра из БД.

        Args:
            instance: Экземпляр для обновления

        Returns:
            Обновленный экземпляр
        """
        await self.session.refresh(instance)
        return instance

    async def execute_raw(self, query: str, params: Optional[Dict] = None) -> Any:
        """
        Выполнение сырого SQL запроса.

        Args:
            query: SQL запрос
            params: Параметры запроса

        Returns:
            Результат выполнения
        """
        try:
            result = await self.session.execute(text(query), params or {})
            return result
        except Exception as e:
            logger.error(f"Ошибка выполнения SQL: {e}")
            raise DatabaseError("Ошибка выполнения запроса", details={"error": str(e)})

    @property
    def query_count(self) -> int:
        """Количество выполненных запросов."""
        return self._query_count

    def reset_query_count(self) -> None:
        """Сброс счетчика запросов."""
        self._query_count = 0