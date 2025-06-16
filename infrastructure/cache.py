"""
Модуль для кэширования данных.

Этот модуль содержит:
- Абстрактный интерфейс для кэша
- Redis реализацию с поддержкой TTL
- In-memory кэш как fallback
- Автоматическую сериализацию данных
- Теги для группировки и инвалидации
- Декораторы для кэширования функций
"""

import asyncio
import json
import pickle
import time
from abc import ABC, abstractmethod
from typing import (
    Optional, Any, Dict, List, Union, Callable,
    TypeVar, Set, Tuple
)
from datetime import datetime, timedelta
from functools import wraps
import hashlib
from collections import OrderedDict

import redis.asyncio as redis
from redis.asyncio.connection import ConnectionPool

from config import logger, settings
from core.exceptions import CacheError

T = TypeVar('T')


class CacheBackend(ABC):
    """
    Абстрактный интерфейс для кэш-бэкенда.

    Определяет методы, которые должны быть реализованы
    любым кэш-хранилищем.
    """

    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """Получение значения по ключу."""
        pass

    @abstractmethod
    async def set(
            self,
            key: str,
            value: Any,
            ttl: Optional[int] = None
    ) -> bool:
        """Установка значения с опциональным TTL."""
        pass

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Удаление значения по ключу."""
        pass

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Проверка существования ключа."""
        pass

    @abstractmethod
    async def clear(self) -> bool:
        """Очистка всего кэша."""
        pass

    @abstractmethod
    async def get_many(self, keys: List[str]) -> Dict[str, Any]:
        """Получение нескольких значений."""
        pass

    @abstractmethod
    async def set_many(
            self,
            data: Dict[str, Any],
            ttl: Optional[int] = None
    ) -> bool:
        """Установка нескольких значений."""
        pass

    @abstractmethod
    async def delete_many(self, keys: List[str]) -> int:
        """Удаление нескольких ключей."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Закрытие соединений."""
        pass


class RedisBackend(CacheBackend):
    """
    Redis реализация кэш-бэкенда.

    Использует Redis для распределенного кэширования
    с поддержкой TTL и тегов.
    """

    def __init__(
            self,
            url: Optional[str] = None,
            max_connections: int = 50,
            decode_responses: bool = False,
            key_prefix: str = "astro_bot"
    ):
        """
        Инициализация Redis бэкенда.

        Args:
            url: URL подключения к Redis
            max_connections: Максимум соединений в пуле
            decode_responses: Декодировать ответы
            key_prefix: Префикс для всех ключей
        """
        self.url = url or settings.redis.url
        self.key_prefix = key_prefix
        self.pool: Optional[ConnectionPool] = None
        self.client: Optional[redis.Redis] = None
        self._stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "deletes": 0
        }

        logger.info(f"Инициализация Redis backend: {self.url}")

    async def connect(self) -> None:
        """Установка соединения с Redis."""
        if not self.client:
            self.pool = ConnectionPool.from_url(
                self.url,
                max_connections=max_connections,
                decode_responses=False  # Для поддержки бинарных данных
            )
            self.client = redis.Redis(connection_pool=self.pool)

            # Проверка соединения
            try:
                await self.client.ping()
                logger.info("✅ Подключение к Redis установлено")
            except Exception as e:
                logger.error(f"❌ Ошибка подключения к Redis: {e}")
                raise CacheError(f"Не удалось подключиться к Redis: {e}")

    def _make_key(self, key: str) -> str:
        """Добавление префикса к ключу."""
        return f"{self.key_prefix}:{key}"

    def _serialize(self, value: Any) -> bytes:
        """
        Сериализация значения.

        Пробует JSON, затем pickle для сложных объектов.
        """
        try:
            # Сначала пробуем JSON для простых типов
            if isinstance(value, (str, int, float, bool, list, dict)):
                return json.dumps(value).encode('utf-8')
        except (TypeError, ValueError):
            pass

        # Для сложных объектов используем pickle
        return pickle.dumps(value)

    def _deserialize(self, data: bytes) -> Any:
        """Десериализация значения."""
        if not data:
            return None

        # Пробуем JSON
        try:
            return json.loads(data.decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass

        # Пробуем pickle
        try:
            return pickle.loads(data)
        except Exception as e:
            logger.error(f"Ошибка десериализации: {e}")
            return None

    async def get(self, key: str) -> Optional[Any]:
        """Получение значения из Redis."""
        await self.connect()

        full_key = self._make_key(key)
        try:
            data = await self.client.get(full_key)
            if data is None:
                self._stats["misses"] += 1
                return None

            self._stats["hits"] += 1
            return self._deserialize(data)

        except Exception as e:
            logger.error(f"Ошибка получения из Redis: {e}")
            return None

    async def set(
            self,
            key: str,
            value: Any,
            ttl: Optional[int] = None
    ) -> bool:
        """Установка значения в Redis."""
        await self.connect()

        full_key = self._make_key(key)
        try:
            data = self._serialize(value)

            if ttl:
                result = await self.client.setex(full_key, ttl, data)
            else:
                result = await self.client.set(full_key, data)

            self._stats["sets"] += 1
            return bool(result)

        except Exception as e:
            logger.error(f"Ошибка записи в Redis: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """Удаление ключа из Redis."""
        await self.connect()

        full_key = self._make_key(key)
        try:
            result = await self.client.delete(full_key)
            self._stats["deletes"] += 1
            return bool(result)

        except Exception as e:
            logger.error(f"Ошибка удаления из Redis: {e}")
            return False

    async def exists(self, key: str) -> bool:
        """Проверка существования ключа."""
        await self.connect()

        full_key = self._make_key(key)
        try:
            return bool(await self.client.exists(full_key))
        except Exception as e:
            logger.error(f"Ошибка проверки существования: {e}")
            return False

    async def clear(self) -> bool:
        """Очистка всех ключей с префиксом."""
        await self.connect()

        try:
            pattern = f"{self.key_prefix}:*"
            cursor = 0
            deleted = 0

            # Используем SCAN для безопасного удаления
            while True:
                cursor, keys = await self.client.scan(
                    cursor,
                    match=pattern,
                    count=100
                )

                if keys:
                    deleted += await self.client.delete(*keys)

                if cursor == 0:
                    break

            logger.info(f"Очищено {deleted} ключей из Redis")
            return True

        except Exception as e:
            logger.error(f"Ошибка очистки Redis: {e}")
            return False

    async def get_many(self, keys: List[str]) -> Dict[str, Any]:
        """Получение нескольких значений."""
        await self.connect()

        if not keys:
            return {}

        full_keys = [self._make_key(key) for key in keys]
        try:
            values = await self.client.mget(full_keys)

            result = {}
            for key, value in zip(keys, values):
                if value is not None:
                    result[key] = self._deserialize(value)
                    self._stats["hits"] += 1
                else:
                    self._stats["misses"] += 1

            return result

        except Exception as e:
            logger.error(f"Ошибка множественного получения: {e}")
            return {}

    async def set_many(
            self,
            data: Dict[str, Any],
            ttl: Optional[int] = None
    ) -> bool:
        """Установка нескольких значений."""
        await self.connect()

        if not data:
            return True

        try:
            # Подготовка данных
            pipe = self.client.pipeline()

            for key, value in data.items():
                full_key = self._make_key(key)
                serialized = self._serialize(value)

                if ttl:
                    pipe.setex(full_key, ttl, serialized)
                else:
                    pipe.set(full_key, serialized)

            results = await pipe.execute()
            self._stats["sets"] += len(data)

            return all(results)

        except Exception as e:
            logger.error(f"Ошибка множественной установки: {e}")
            return False

    async def delete_many(self, keys: List[str]) -> int:
        """Удаление нескольких ключей."""
        await self.connect()

        if not keys:
            return 0

        full_keys = [self._make_key(key) for key in keys]
        try:
            deleted = await self.client.delete(*full_keys)
            self._stats["deletes"] += deleted
            return deleted

        except Exception as e:
            logger.error(f"Ошибка множественного удаления: {e}")
            return 0

    async def add_to_set(self, key: str, *values) -> int:
        """Добавление в множество (для тегов)."""
        await self.connect()

        full_key = self._make_key(key)
        try:
            return await self.client.sadd(full_key, *values)
        except Exception as e:
            logger.error(f"Ошибка добавления в set: {e}")
            return 0

    async def get_set_members(self, key: str) -> Set[str]:
        """Получение членов множества."""
        await self.connect()

        full_key = self._make_key(key)
        try:
            members = await self.client.smembers(full_key)
            return {m.decode('utf-8') if isinstance(m, bytes) else m for m in members}
        except Exception as e:
            logger.error(f"Ошибка получения set: {e}")
            return set()

    async def close(self) -> None:
        """Закрытие соединения."""
        if self.client:
            await self.client.close()
        if self.pool:
            await self.pool.disconnect()

        logger.info("Redis соединение закрыто")

    def get_stats(self) -> Dict[str, Any]:
        """Получение статистики."""
        total = self._stats["hits"] + self._stats["misses"]
        hit_rate = self._stats["hits"] / total if total > 0 else 0

        return {
            **self._stats,
            "hit_rate": round(hit_rate, 3),
            "total_operations": total
        }


class InMemoryBackend(CacheBackend):
    """
    In-memory реализация кэша.

    Используется как fallback при недоступности Redis.
    """

    def __init__(self, max_size: int = 10000):
        """
        Инициализация in-memory кэша.

        Args:
            max_size: Максимальный размер кэша
        """
        self.max_size = max_size
        self._cache: OrderedDict[str, Tuple[Any, Optional[float]]] = OrderedDict()
        self._lock = asyncio.Lock()
        self._stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0
        }

        logger.info(f"InMemory backend инициализирован (max_size={max_size})")

    def _is_expired(self, expire_time: Optional[float]) -> bool:
        """Проверка истечения TTL."""
        if expire_time is None:
            return False
        return time.time() > expire_time

    def _evict_if_needed(self) -> None:
        """Вытеснение старых записей при превышении размера."""
        while len(self._cache) >= self.max_size:
            # Удаляем самую старую запись (FIFO)
            self._cache.popitem(last=False)
            self._stats["evictions"] += 1

    async def get(self, key: str) -> Optional[Any]:
        """Получение значения из памяти."""
        async with self._lock:
            if key in self._cache:
                value, expire_time = self._cache[key]

                if self._is_expired(expire_time):
                    del self._cache[key]
                    self._stats["misses"] += 1
                    return None

                # Перемещаем в конец (LRU)
                self._cache.move_to_end(key)
                self._stats["hits"] += 1
                return value

            self._stats["misses"] += 1
            return None

    async def set(
            self,
            key: str,
            value: Any,
            ttl: Optional[int] = None
    ) -> bool:
        """Установка значения в память."""
        async with self._lock:
            expire_time = None
            if ttl:
                expire_time = time.time() + ttl

            self._evict_if_needed()
            self._cache[key] = (value, expire_time)
            return True

    async def delete(self, key: str) -> bool:
        """Удаление из памяти."""
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    async def exists(self, key: str) -> bool:
        """Проверка существования."""
        async with self._lock:
            if key in self._cache:
                _, expire_time = self._cache[key]
                if self._is_expired(expire_time):
                    del self._cache[key]
                    return False
                return True
            return False

    async def clear(self) -> bool:
        """Очистка кэша."""
        async with self._lock:
            self._cache.clear()
            return True

    async def get_many(self, keys: List[str]) -> Dict[str, Any]:
        """Получение нескольких значений."""
        result = {}
        for key in keys:
            value = await self.get(key)
            if value is not None:
                result[key] = value
        return result

    async def set_many(
            self,
            data: Dict[str, Any],
            ttl: Optional[int] = None
    ) -> bool:
        """Установка нескольких значений."""
        for key, value in data.items():
            await self.set(key, value, ttl)
        return True

    async def delete_many(self, keys: List[str]) -> int:
        """Удаление нескольких ключей."""
        deleted = 0
        for key in keys:
            if await self.delete(key):
                deleted += 1
        return deleted

    async def close(self) -> None:
        """Закрытие (для совместимости)."""
        pass

    def get_stats(self) -> Dict[str, Any]:
        """Получение статистики."""
        total = self._stats["hits"] + self._stats["misses"]
        hit_rate = self._stats["hits"] / total if total > 0 else 0

        return {
            **self._stats,
            "hit_rate": round(hit_rate, 3),
            "size": len(self._cache),
            "max_size": self.max_size
        }


class CacheManager:
    """
    Менеджер кэша с автоматическим выбором бэкенда.

    Использует Redis если доступен, иначе in-memory.
    """

    def __init__(self):
        """Инициализация менеджера."""
        self.backend: Optional[CacheBackend] = None
        self.is_redis = False
        self._initialized = False
        self._tags: Dict[str, Set[str]] = {}  # tag -> keys

    async def init(self) -> None:
        """Инициализация бэкенда."""
        if self._initialized:
            return

        # Пробуем Redis
        if settings.redis.enabled:
            try:
                self.backend = RedisBackend()
                await self.backend.connect()
                self.is_redis = True
                logger.info("Используется Redis backend для кэша")
            except Exception as e:
                logger.warning(f"Redis недоступен: {e}, используем in-memory")

        # Fallback на in-memory
        if not self.backend:
            self.backend = InMemoryBackend(
                max_size=settings.cache.max_memory_items
            )
            self.is_redis = False
            logger.info("Используется in-memory backend для кэша")

        self._initialized = True

    async def get(self, key: str) -> Optional[Any]:
        """Получение значения."""
        await self.init()
        return await self.backend.get(key)

    async def set(
            self,
            key: str,
            value: Any,
            ttl: Optional[int] = None,
            tags: Optional[List[str]] = None
    ) -> bool:
        """
        Установка значения с тегами.

        Args:
            key: Ключ
            value: Значение
            ttl: Время жизни в секундах
            tags: Теги для группировки
        """
        await self.init()

        result = await self.backend.set(key, value, ttl)

        # Сохраняем теги
        if result and tags:
            for tag in tags:
                if tag not in self._tags:
                    self._tags[tag] = set()
                self._tags[tag].add(key)

        return result

    async def delete(self, key: str) -> bool:
        """Удаление значения."""
        await self.init()

        # Удаляем из тегов
        for tag_keys in self._tags.values():
            tag_keys.discard(key)

        return await self.backend.delete(key)

    async def invalidate_tag(self, tag: str) -> int:
        """
        Инвалидация всех ключей с тегом.

        Args:
            tag: Тег для инвалидации

        Returns:
            Количество удаленных ключей
        """
        await self.init()

        if tag not in self._tags:
            return 0

        keys = list(self._tags[tag])
        deleted = await self.backend.delete_many(keys)

        # Очищаем тег
        del self._tags[tag]

        logger.info(f"Инвалидировано {deleted} ключей с тегом '{tag}'")
        return deleted

    async def clear(self) -> bool:
        """Очистка всего кэша."""
        await self.init()
        self._tags.clear()
        return await self.backend.clear()

    def cache_key_wrapper(
            self,
            prefix: str,
            ttl: Optional[int] = 3600,
            tags: Optional[List[str]] = None
    ):
        """
        Декоратор для кэширования результатов функций.

        Args:
            prefix: Префикс для ключа
            ttl: Время жизни кэша
            tags: Теги для инвалидации
        """

        def decorator(func: Callable) -> Callable:
            @wraps(func)
            async def wrapper(*args, **kwargs):
                # Генерируем ключ
                key_parts = [prefix]
                key_parts.extend(str(arg) for arg in args)
                key_parts.extend(f"{k}:{v}" for k, v in sorted(kwargs.items()))

                cache_key = ":".join(key_parts)
                cache_key = hashlib.md5(cache_key.encode()).hexdigest()

                # Проверяем кэш
                cached = await self.get(cache_key)
                if cached is not None:
                    return cached

                # Вызываем функцию
                result = await func(*args, **kwargs)

                # Сохраняем в кэш
                await self.set(cache_key, result, ttl, tags)

                return result

            return wrapper

        return decorator

    def get_stats(self) -> Dict[str, Any]:
        """Получение статистики."""
        if not self._initialized or not self.backend:
            return {"status": "not_initialized"}

        stats = {
            "backend": "redis" if self.is_redis else "in-memory",
            "tags_count": len(self._tags),
            "total_tagged_keys": sum(len(keys) for keys in self._tags.values())
        }

        if hasattr(self.backend, 'get_stats'):
            stats.update(self.backend.get_stats())

        return stats

    async def close(self) -> None:
        """Закрытие соединений."""
        if self.backend:
            await self.backend.close()


# Глобальный экземпляр
cache_manager = CacheManager()


# Вспомогательные функции
async def cache_get(key: str) -> Optional[Any]:
    """Быстрое получение из кэша."""
    return await cache_manager.get(key)


async def cache_set(
        key: str,
        value: Any,
        ttl: Optional[int] = None
) -> bool:
    """Быстрая установка в кэш."""
    return await cache_manager.set(key, value, ttl)


async def cache_delete(key: str) -> bool:
    """Быстрое удаление из кэша."""
    return await cache_manager.delete(key)


# Декоратор для кэширования
def cached(
        ttl: int = 3600,
        prefix: Optional[str] = None,
        tags: Optional[List[str]] = None
):
    """
    Декоратор для кэширования результатов функций.

    Args:
        ttl: Время жизни в секундах
        prefix: Префикс ключа (по умолчанию имя функции)
        tags: Теги для группировки

    Example:
        @cached(ttl=300, tags=["user_data"])
        async def get_user_stats(user_id: int):
            # Дорогая операция
            return stats
    """

    def decorator(func: Callable) -> Callable:
        cache_prefix = prefix or func.__name__
        return cache_manager.cache_key_wrapper(cache_prefix, ttl, tags)(func)

    return decorator