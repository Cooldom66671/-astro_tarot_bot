"""
Базовые классы и миксины для моделей SQLAlchemy.

Этот модуль содержит:
- Базовый класс с общими полями для всех таблиц
- Миксины для добавления функциональности
- Абстрактные базовые классы для разных типов моделей
- Утилиты для работы с моделями
- Автоматическое управление временными метками
"""

from datetime import datetime
from typing import Any, Dict, Optional, Type, TypeVar, List
from uuid import uuid4

from sqlalchemy import (
    BigInteger, Column, DateTime, String, Boolean,
    Integer, func, text, Index, event
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import Session, declarative_mixin
from sqlalchemy.sql import expression

from config import logger
from infrastructure.database.connection import Base

# Type variable для обобщенных типов
T = TypeVar('T', bound='BaseModel')


class BaseModel(Base):
    """
    Базовый класс для всех моделей приложения.

    Содержит общие поля и методы, которые должны быть
    у каждой таблицы в базе данных.
    """

    __abstract__ = True  # Это абстрактный класс, таблица не создается

    # Первичный ключ - автоинкрементный BIGINT
    id = Column(
        BigInteger,
        primary_key=True,
        index=True,
        comment="Уникальный идентификатор записи"
    )

    # Временные метки
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="Дата и время создания записи"
    )

    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="Дата и время последнего обновления"
    )

    @declared_attr
    def __tablename__(cls) -> str:
        """
        Автоматическое определение имени таблицы.

        Преобразует CamelCase в snake_case и добавляет 's' для множественного числа.
        Например: UserProfile -> user_profiles
        """
        name = cls.__name__
        # CamelCase в snake_case
        table_name = ''
        for i, char in enumerate(name):
            if i > 0 and char.isupper() and name[i - 1].islower():
                table_name += '_'
            table_name += char.lower()

        # Добавляем 's' для множественного числа, если не заканчивается на 's'
        if not table_name.endswith('s'):
            table_name += 's'

        return table_name

    def __repr__(self) -> str:
        """Строковое представление модели для отладки."""
        return f"<{self.__class__.__name__}(id={self.id})>"

    def to_dict(self, exclude: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Преобразование модели в словарь.

        Args:
            exclude: Список полей для исключения

        Returns:
            Словарь с данными модели
        """
        exclude = exclude or []
        data = {}

        for column in self.__table__.columns:
            if column.name not in exclude:
                value = getattr(self, column.name)

                # Преобразование специальных типов
                if isinstance(value, datetime):
                    value = value.isoformat()
                elif hasattr(value, 'value'):  # Enum
                    value = value.value

                data[column.name] = value

        return data

    def update_from_dict(self, data: Dict[str, Any]) -> None:
        """
        Обновление полей модели из словаря.

        Args:
            data: Словарь с новыми значениями
        """
        for key, value in data.items():
            if hasattr(self, key) and key not in ['id', 'created_at']:
                setattr(self, key, value)

        logger.debug(f"Обновлена модель {self.__class__.__name__} id={self.id}")

    @classmethod
    def create_indexes(cls) -> List[Index]:
        """
        Создание дополнительных индексов для модели.

        Переопределите в дочерних классах для добавления индексов.
        """
        return []


@declarative_mixin
class TimestampMixin:
    """
    Миксин для добавления временных меток с дополнительной функциональностью.

    Добавляет автоматическое обновление updated_at при изменении записи.
    """

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
        comment="Время создания записи"
    )

    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        index=True,
        comment="Время последнего обновления"
    )

    @property
    def age_seconds(self) -> float:
        """Возраст записи в секундах."""
        if self.created_at:
            return (datetime.utcnow() - self.created_at).total_seconds()
        return 0.0

    @property
    def is_recently_updated(self) -> bool:
        """Была ли запись обновлена в последние 24 часа."""
        if self.updated_at:
            return (datetime.utcnow() - self.updated_at).days < 1
        return False


@declarative_mixin
class SoftDeleteMixin:
    """
    Миксин для мягкого удаления записей.

    Вместо физического удаления помечает записи как удаленные.
    """

    is_deleted = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=expression.false(),
        index=True,
        comment="Флаг мягкого удаления"
    )

    deleted_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Время удаления записи"
    )

    deleted_by = Column(
        BigInteger,
        nullable=True,
        comment="ID пользователя, удалившего запись"
    )

    def soft_delete(self, deleted_by_id: Optional[int] = None) -> None:
        """
        Мягкое удаление записи.

        Args:
            deleted_by_id: ID пользователя, выполняющего удаление
        """
        self.is_deleted = True
        self.deleted_at = datetime.utcnow()
        self.deleted_by = deleted_by_id
        logger.info(f"Мягкое удаление {self.__class__.__name__} id={self.id}")

    def restore(self) -> None:
        """Восстановление мягко удаленной записи."""
        self.is_deleted = False
        self.deleted_at = None
        self.deleted_by = None
        logger.info(f"Восстановление {self.__class__.__name__} id={self.id}")

    @declared_attr
    def __mapper_args__(cls):
        """Автоматическая фильтрация удаленных записей."""
        return {
            "confirm_deleted_rows": False
        }


@declarative_mixin
class UUIDMixin:
    """
    Миксин для добавления UUID в качестве дополнительного идентификатора.

    Полезно для публичных API, где не хочется показывать последовательные ID.
    """

    uuid = Column(
        UUID(as_uuid=True),
        nullable=False,
        unique=True,
        default=uuid4,
        index=True,
        comment="UUID для внешних интеграций"
    )

    @classmethod
    def get_by_uuid(cls: Type[T], session: Session, uuid: str) -> Optional[T]:
        """
        Получение записи по UUID.

        Args:
            session: Сессия БД
            uuid: UUID записи

        Returns:
            Найденная запись или None
        """
        return session.query(cls).filter(cls.uuid == uuid).first()


@declarative_mixin
class AuditMixin:
    """
    Миксин для аудита изменений.

    Отслеживает кто и когда создал/изменил запись.
    """

    created_by = Column(
        BigInteger,
        nullable=True,
        comment="ID пользователя, создавшего запись"
    )

    updated_by = Column(
        BigInteger,
        nullable=True,
        comment="ID пользователя, последним изменившего запись"
    )

    version = Column(
        Integer,
        nullable=False,
        default=1,
        comment="Версия записи для оптимистичной блокировки"
    )

    def increment_version(self) -> None:
        """Инкремент версии при обновлении."""
        self.version = (self.version or 0) + 1


class BaseUserModel(BaseModel, TimestampMixin, SoftDeleteMixin):
    """
    Базовый класс для моделей, связанных с пользователями.

    Включает временные метки и мягкое удаление.
    """
    __abstract__ = True


class BaseTransactionModel(BaseModel, TimestampMixin, UUIDMixin):
    """
    Базовый класс для моделей транзакций и платежей.

    Включает UUID для внешних систем.
    """
    __abstract__ = True


class BaseCachedModel(BaseModel, TimestampMixin):
    """
    Базовый класс для кэшируемых моделей.

    Добавляет поля для управления кэшем.
    """
    __abstract__ = True

    cache_key = Column(
        String(255),
        nullable=True,
        index=True,
        comment="Ключ кэша"
    )

    cache_expires_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Время истечения кэша"
    )

    @property
    def is_cache_valid(self) -> bool:
        """Проверка валидности кэша."""
        if not self.cache_expires_at:
            return False
        return datetime.utcnow() < self.cache_expires_at

    def invalidate_cache(self) -> None:
        """Инвалидация кэша."""
        self.cache_expires_at = datetime.utcnow()


# Регистрация глобальных event listeners
@event.listens_for(BaseModel, 'before_update', propagate=True)
def receive_before_update(mapper, connection, target):
    """
    Автоматическое обновление updated_at перед сохранением.

    Работает для всех наследников BaseModel.
    """
    if hasattr(target, 'updated_at'):
        target.updated_at = datetime.utcnow()

    # Инкремент версии для аудита
    if hasattr(target, 'version'):
        target.version = (target.version or 0) + 1


# Вспомогательные функции
def create_all_indexes(engine) -> None:
    """
    Создание всех кастомных индексов для моделей.

    Args:
        engine: SQLAlchemy engine
    """
    for model_class in Base.__subclasses__():
        if hasattr(model_class, 'create_indexes'):
            indexes = model_class.create_indexes()
            for index in indexes:
                index.create(engine, checkfirst=True)

    logger.info("Все кастомные индексы созданы")


def get_model_statistics() -> Dict[str, int]:
    """
    Получение статистики по всем моделям.

    Returns:
        Словарь с количеством записей в каждой таблице
    """
    stats = {}
    for model_class in Base.__subclasses__():
        if not model_class.__abstract__:
            table_name = model_class.__tablename__
            stats[table_name] = 0  # Будет заполнено при реальном подсчете

    return stats