"""
Модуль для работы с кэшированием.

Предоставляет унифицированный интерфейс для кэширования
с поддержкой Redis и in-memory кэша.
"""

import json
import time
import asyncio
from typing import Optional, Any, Dict, Union
from datetime import datetime, timedelta
import hashlib

try:
    import redis.asyncio as redis

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

from config import logger, settings


class InMemoryCache:
    """Простой in-memory кэш."""

    def __init__(self):
        self._cache: Dict[str, tuple[Any, float]] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[Any]:
        """Получить значение из кэша."""
        async with self._lock:
            if key in self._cache:
                value, expiry = self._cache[key]
                if expiry > time.time():
                    return value
                else:
                    del self._cache[key]
            return None

    async def set(self, key: str, value: Any, ttl: int) -> None:
        """Сохранить значение в кэш."""
        async with self._lock:
            expiry = time.time() + ttl
            self._cache[key] = (value, expiry)

            # Ограничиваем размер кэша
            if len(self._cache) > 10000:
                # Удаляем истекшие записи
                current_time = time.time()
                self._cache = {
                    k: v for k, v in self._cache.items()
                    if v[1] > current_time
                }

                # Если все еще много, удаляем самые старые
                if len(self._cache) > 10000:
                    sorted_items = sorted(
                        self._cache.items(),
                        key=lambda x: x[1][1]
                    )
                    # Оставляем только последние 8000
                    self._cache = dict(sorted_items[-8000:])

    async def delete(self, key: str) -> None:
        """Удалить значение из кэша."""
        async with self._lock:
            self._cache.pop(key, None)

    async def clear(self) -> None:
        """Очистить весь кэш."""
        async with self._lock:
            self._cache.clear()

    async def exists(self, key: str) -> bool:
        """Проверить существование ключа."""
        value = await self.get(key)
        return value is not None


class CacheManager:
    """
    Менеджер кэширования.

    Автоматически выбирает между Redis и in-memory кэшем.
    """

    def __init__(self):
        self._redis_client: Optional[redis.Redis] = None
        self._memory_cache = InMemoryCache()
        self._use_redis = False
        self._initialized = False

    async def initialize(self) -> None:
        """Инициализация кэш-менеджера."""
        if self._initialized:
            return

        if REDIS_AVAILABLE and settings.redis.url:
            try:
                self._redis_client = redis.from_url(
                    settings.redis.url,
                    decode_responses=settings.redis.decode_responses,
                    db=settings.redis.db
                )
                # Проверяем соединение
                await self._redis_client.ping()
                self._use_redis = True
                logger.info("Используется Redis для кэширования")
            except Exception as e:
                logger.warning(f"Не удалось подключиться к Redis: {e}")
                logger.info("Используется in-memory кэш")
                self._use_redis = False
        else:
            logger.info("Redis недоступен, используется in-memory кэш")
            self._use_redis = False

        self._initialized = True

    async def get(self, key: str) -> Optional[Any]:
        """
        Получить значение из кэша.

        Args:
            key: Ключ

        Returns:
            Значение или None
        """
        await self.initialize()

        try:
            if self._use_redis:
                value = await self._redis_client.get(key)
                if value:
                    # Десериализуем JSON
                    try:
                        return json.loads(value)
                    except json.JSONDecodeError:
                        return value
            else:
                return await self._memory_cache.get(key)
        except Exception as e:
            logger.error(f"Ошибка получения из кэша: {e}")
            return None

    async def set(
            self,
            key: str,
            value: Any,
            ttl: int = 3600
    ) -> None:
        """
        Сохранить значение в кэш.

        Args:
            key: Ключ
            value: Значение
            ttl: Время жизни в секундах
        """
        await self.initialize()

        try:
            if self._use_redis:
                # Сериализуем в JSON
                if isinstance(value, (dict, list)):
                    value = json.dumps(value)
                await self._redis_client.setex(key, ttl, value)
            else:
                await self._memory_cache.set(key, value, ttl)
        except Exception as e:
            logger.error(f"Ошибка сохранения в кэш: {e}")

    async def delete(self, key: str) -> None:
        """Удалить значение из кэша."""
        await self.initialize()

        try:
            if self._use_redis:
                await self._redis_client.delete(key)
            else:
                await self._memory_cache.delete(key)
        except Exception as e:
            logger.error(f"Ошибка удаления из кэша: {e}")

    async def clear(self, pattern: Optional[str] = None) -> None:
        """
        Очистить кэш.

        Args:
            pattern: Паттерн ключей для удаления (только для Redis)
        """
        await self.initialize()

        try:
            if self._use_redis and pattern:
                # Удаляем по паттерну
                cursor = 0
                while True:
                    cursor, keys = await self._redis_client.scan(
                        cursor,
                        match=pattern,
                        count=100
                    )
                    if keys:
                        await self._redis_client.delete(*keys)
                    if cursor == 0:
                        break
            else:
                await self._memory_cache.clear()
        except Exception as e:
            logger.error(f"Ошибка очистки кэша: {e}")

    async def exists(self, key: str) -> bool:
        """Проверить существование ключа."""
        await self.initialize()

        try:
            if self._use_redis:
                return await self._redis_client.exists(key) > 0
            else:
                return await self._memory_cache.exists(key)
        except Exception as e:
            logger.error(f"Ошибка проверки существования ключа: {e}")
            return False

    async def get_many(self, keys: list[str]) -> Dict[str, Any]:
        """
        Получить несколько значений.

        Args:
            keys: Список ключей

        Returns:
            Словарь {ключ: значение}
        """
        await self.initialize()

        result = {}

        try:
            if self._use_redis:
                values = await self._redis_client.mget(keys)
                for key, value in zip(keys, values):
                    if value:
                        try:
                            result[key] = json.loads(value)
                        except json.JSONDecodeError:
                            result[key] = value
            else:
                for key in keys:
                    value = await self._memory_cache.get(key)
                    if value is not None:
                        result[key] = value
        except Exception as e:
            logger.error(f"Ошибка получения нескольких значений: {e}")

        return result

    async def set_many(
            self,
            mapping: Dict[str, Any],
            ttl: int = 3600
    ) -> None:
        """
        Сохранить несколько значений.

        Args:
            mapping: Словарь {ключ: значение}
            ttl: Время жизни в секундах
        """
        await self.initialize()

        try:
            if self._use_redis:
                # Redis не поддерживает msetex, делаем через pipeline
                pipe = self._redis_client.pipeline()
                for key, value in mapping.items():
                    if isinstance(value, (dict, list)):
                        value = json.dumps(value)
                    pipe.setex(key, ttl, value)
                await pipe.execute()
            else:
                for key, value in mapping.items():
                    await self._memory_cache.set(key, value, ttl)
        except Exception as e:
            logger.error(f"Ошибка сохранения нескольких значений: {e}")

    def make_key(self, *parts: Union[str, int]) -> str:
        """
        Создать ключ из частей.

        Args:
            *parts: Части ключа

        Returns:
            Составной ключ
        """
        return ":".join(str(part) for part in parts)

    def make_hash_key(self, data: Union[str, dict]) -> str:
        """
        Создать хэш-ключ из данных.

        Args:
            data: Данные для хэширования

        Returns:
            Хэш-ключ
        """
        if isinstance(data, dict):
            data = json.dumps(data, sort_keys=True)
        return hashlib.md5(data.encode()).hexdigest()

    async def close(self) -> None:
        """Закрыть соединения."""
        if self._redis_client:
            await self._redis_client.close()


# Глобальный экземпляр
cache_manager = CacheManager()


# Декоратор для кэширования
def cached(
        ttl: int = 3600,
        key_prefix: Optional[str] = None,
        key_func: Optional[callable] = None
):
    """
    Декоратор для кэширования результатов функции.

    Args:
        ttl: Время жизни кэша в секундах
        key_prefix: Префикс ключа
        key_func: Функция для генерации ключа
    """

    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Генерируем ключ
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                # Простая генерация ключа
                key_parts = [key_prefix or func.__name__]
                key_parts.extend(str(arg) for arg in args)
                key_parts.extend(f"{k}:{v}" for k, v in sorted(kwargs.items()))
                cache_key = cache_manager.make_key(*key_parts)

            # Проверяем кэш
            cached_value = await cache_manager.get(cache_key)
            if cached_value is not None:
                return cached_value

            # Вызываем функцию
            result = await func(*args, **kwargs)

            # Сохраняем в кэш
            await cache_manager.set(cache_key, result, ttl)

            return result

        return wrapper

    return decorator


# Экспорт
__all__ = [
    'CacheManager',
    'cache_manager',
    'cached',
    'InMemoryCache',
]