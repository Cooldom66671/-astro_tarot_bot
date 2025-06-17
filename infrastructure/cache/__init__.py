"""
Модуль для кэширования данных.

Этот модуль предоставляет:
- Универсальный интерфейс для кэширования
- Redis и in-memory реализации
- Декораторы для автоматического кэширования
- Поддержку тегов и инвалидации
- Статистику использования кэша

Автор: AI Assistant
Дата создания: 2024-12-30
"""

import logging
import hashlib
import functools
from typing import Optional, Any, List, Dict

logger = logging.getLogger(__name__)


# Функция генерации ключа (определяем до использования)
def cache_key(prefix: str, *args, **kwargs) -> str:
    """
    Генерация ключа кэша из компонентов.

    Args:
        prefix: Префикс ключа
        *args: Позиционные аргументы
        **kwargs: Именованные аргументы

    Returns:
        Сгенерированный ключ
    """
    parts = [prefix]
    parts.extend(str(arg) for arg in args)
    parts.extend(f"{k}:{v}" for k, v in sorted(kwargs.items()))

    key = ":".join(parts)

    # Если ключ слишком длинный, хэшируем его
    if len(key) > 200:
        key = f"{prefix}:{hashlib.md5(key.encode()).hexdigest()}"

    return key


# Проверяем доступность основного модуля cache.py в той же директории
try:
    # Импортируем из текущей директории
    from .cache import (
        # Исключения
        CacheError,

        # Базовые классы
        CacheBackend,
        RedisBackend,
        InMemoryBackend,

        # Менеджер кэша
        CacheManager,
        cache_manager,

        # Функции быстрого доступа
        cache_get,
        cache_set,
        cache_delete,

        # Декораторы
        cached
    )
    cache_available = True
    logger.info("Модуль кэша загружен успешно")

except ImportError as e:
    logger.warning(f"Не удалось импортировать модуль кэша: {e}")
    cache_available = False

    # Создаем заглушки для всех классов и функций

    # Исключение
    class CacheError(Exception):
        """Заглушка для CacheError."""
        pass

    # Базовый класс для бэкендов
    class CacheBackend:
        """Заглушка для CacheBackend."""
        async def get(self, key: str) -> Optional[Any]:
            return None

        async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
            return True

        async def delete(self, key: str) -> bool:
            return True

        async def exists(self, key: str) -> bool:
            return False

        async def clear(self) -> bool:
            return True

        async def get_many(self, keys: List[str]) -> Dict[str, Any]:
            return {}

        async def set_many(self, data: Dict[str, Any], ttl: Optional[int] = None) -> bool:
            return True

        async def delete_many(self, keys: List[str]) -> int:
            return 0

        async def close(self) -> None:
            pass

    # Redis бэкенд
    class RedisBackend(CacheBackend):
        """Заглушка для RedisBackend."""
        def __init__(self, url: Optional[str] = None, max_connections: int = 50,
                     decode_responses: bool = False, key_prefix: str = "astro_bot"):
            self.url = url
            self.key_prefix = key_prefix
            self.max_connections = max_connections

        async def connect(self) -> None:
            pass

        def get_stats(self) -> Dict[str, Any]:
            return {"backend": "redis", "status": "stub"}

    # In-memory бэкенд
    class InMemoryBackend(CacheBackend):
        """Заглушка для InMemoryBackend."""
        def __init__(self, max_size: int = 10000):
            self.max_size = max_size
            self._cache = {}

        def get_stats(self) -> Dict[str, Any]:
            return {"backend": "in-memory", "status": "stub", "size": 0}

    # Менеджер кэша
    class CacheManager:
        """Заглушка для CacheManager."""
        def __init__(self):
            self.backend = InMemoryBackend()  # Добавляем атрибут backend
            self.is_redis = False
            self._initialized = False
            self._tags = {}

        async def init(self) -> None:
            self._initialized = True

        async def get(self, key: str) -> Optional[Any]:
            return None

        async def set(self, key: str, value: Any, ttl: Optional[int] = None,
                      tags: Optional[List[str]] = None) -> bool:
            return True

        async def delete(self, key: str) -> bool:
            return True

        async def clear(self) -> bool:
            return True

        async def invalidate_tag(self, tag: str) -> int:
            return 0

        async def close(self) -> None:
            if self.backend:
                await self.backend.close()

        def get_stats(self) -> Dict[str, Any]:
            return {"status": "stub", "backend": "none"}

    # Создаем глобальный экземпляр
    cache_manager = CacheManager()

    # Функции быстрого доступа
    async def cache_get(key: str) -> Optional[Any]:
        return None

    async def cache_set(key: str, value: Any, ttl: Optional[int] = None) -> bool:
        return True

    async def cache_delete(key: str) -> bool:
        return True

    # Декоратор
    def cached(ttl: int = 3600, prefix: Optional[str] = None, tags: Optional[List[str]] = None):
        def decorator(func):
            return func
        return decorator


# Дополнительные утилиты
async def cache_clear() -> bool:
    """Очистить весь кэш."""
    try:
        return await cache_manager.clear()
    except Exception as e:
        logger.error(f"Ошибка очистки кэша: {e}")
        return False


async def invalidate_cache(tag: str) -> int:
    """
    Инвалидировать все ключи с определенным тегом.

    Args:
        tag: Тег для инвалидации

    Returns:
        Количество удаленных ключей
    """
    try:
        if hasattr(cache_manager, 'invalidate_tag'):
            return await cache_manager.invalidate_tag(tag)
        return 0
    except Exception as e:
        logger.error(f"Ошибка инвалидации тега {tag}: {e}")
        return 0


async def get_cache_stats() -> Dict[str, Any]:
    """
    Получить статистику использования кэша.

    Returns:
        Словарь со статистикой
    """
    try:
        if hasattr(cache_manager, 'get_stats'):
            return cache_manager.get_stats()
        return {"status": "unavailable"}
    except Exception as e:
        logger.error(f"Ошибка получения статистики кэша: {e}")
        return {"status": "error", "error": str(e)}


async def cache_exists(key: str) -> bool:
    """
    Проверить существование ключа в кэше.

    Args:
        key: Ключ для проверки

    Returns:
        True если ключ существует
    """
    try:
        if hasattr(cache_manager, 'backend') and cache_manager.backend:
            if hasattr(cache_manager.backend, 'exists'):
                return await cache_manager.backend.exists(key)
        # Fallback - пытаемся получить значение
        value = await cache_get(key)
        return value is not None
    except Exception as e:
        logger.error(f"Ошибка проверки существования ключа {key}: {e}")
        return False


async def cache_get_many(keys: List[str]) -> Dict[str, Any]:
    """
    Получить несколько значений из кэша.

    Args:
        keys: Список ключей

    Returns:
        Словарь {ключ: значение}
    """
    try:
        if hasattr(cache_manager, 'backend') and cache_manager.backend:
            if hasattr(cache_manager.backend, 'get_many'):
                return await cache_manager.backend.get_many(keys)

        # Fallback - получаем по одному
        result = {}
        for key in keys:
            value = await cache_get(key)
            if value is not None:
                result[key] = value
        return result
    except Exception as e:
        logger.error(f"Ошибка получения нескольких ключей: {e}")
        return {}


async def cache_set_many(data: Dict[str, Any], ttl: Optional[int] = None) -> bool:
    """
    Установить несколько значений в кэш.

    Args:
        data: Словарь {ключ: значение}
        ttl: Время жизни в секундах

    Returns:
        True если все значения установлены успешно
    """
    try:
        if hasattr(cache_manager, 'backend') and cache_manager.backend:
            if hasattr(cache_manager.backend, 'set_many'):
                return await cache_manager.backend.set_many(data, ttl)

        # Fallback - устанавливаем по одному
        success = True
        for key, value in data.items():
            if not await cache_set(key, value, ttl):
                success = False
        return success
    except Exception as e:
        logger.error(f"Ошибка установки нескольких ключей: {e}")
        return False


async def cache_delete_many(keys: List[str]) -> int:
    """
    Удалить несколько ключей из кэша.

    Args:
        keys: Список ключей для удаления

    Returns:
        Количество удаленных ключей
    """
    try:
        if hasattr(cache_manager, 'backend') and cache_manager.backend:
            if hasattr(cache_manager.backend, 'delete_many'):
                return await cache_manager.backend.delete_many(keys)

        # Fallback - удаляем по одному
        deleted = 0
        for key in keys:
            if await cache_delete(key):
                deleted += 1
        return deleted
    except Exception as e:
        logger.error(f"Ошибка удаления нескольких ключей: {e}")
        return 0


# Контекстный менеджер для временного кэша
class TempCache:
    """Контекстный менеджер для временного кэширования."""

    def __init__(self, prefix: str = "temp", ttl: int = 300):
        self.prefix = prefix
        self.ttl = ttl
        self.keys = []

    async def set(self, key: str, value: Any) -> bool:
        """Установить значение во временный кэш."""
        full_key = f"{self.prefix}:{key}"
        self.keys.append(full_key)
        return await cache_set(full_key, value, self.ttl)

    async def get(self, key: str) -> Optional[Any]:
        """Получить значение из временного кэша."""
        full_key = f"{self.prefix}:{key}"
        return await cache_get(full_key)

    async def __aenter__(self):
        """Вход в контекст."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Выход из контекста - очистка временных ключей."""
        if self.keys:
            await cache_delete_many(self.keys)


# Декоратор с более гибкими опциями
def cached_result(
    ttl: int = 3600,
    prefix: Optional[str] = None,
    tags: Optional[List[str]] = None,
    key_builder: Optional[callable] = None,
    condition: Optional[callable] = None
):
    """
    Расширенный декоратор для кэширования результатов.

    Args:
        ttl: Время жизни кэша в секундах
        prefix: Префикс для ключа кэша
        tags: Теги для группировки
        key_builder: Функция для построения ключа
        condition: Функция проверки, нужно ли кэшировать результат
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Проверяем условие кэширования
            if condition and not condition(*args, **kwargs):
                return await func(*args, **kwargs)

            # Строим ключ
            if key_builder:
                generated_key = key_builder(*args, **kwargs)
            else:
                if not prefix:
                    func_prefix = f"{func.__module__}.{func.__name__}"
                else:
                    func_prefix = prefix

                generated_key = cache_key(func_prefix, *args, **kwargs)

            # Проверяем кэш
            cached_value = await cache_get(generated_key)
            if cached_value is not None:
                logger.debug(f"Cache hit for {generated_key}")
                return cached_value

            # Вызываем функцию
            logger.debug(f"Cache miss for {generated_key}")
            result = await func(*args, **kwargs)

            # Сохраняем в кэш
            if result is not None:  # Не кэшируем None
                await cache_manager.set(generated_key, result, ttl, tags)

            return result

        # Добавляем метод для инвалидации
        async def invalidate(*args, **kwargs):
            if key_builder:
                generated_key = key_builder(*args, **kwargs)
            else:
                if not prefix:
                    func_prefix = f"{func.__module__}.{func.__name__}"
                else:
                    func_prefix = prefix

                generated_key = cache_key(func_prefix, *args, **kwargs)

            return await cache_delete(generated_key)

        wrapper.invalidate = invalidate
        return wrapper

    return decorator


# Экспорт всех компонентов
__all__ = [
    # Основной менеджер
    'cache_manager',

    # Быстрые функции
    'cache_get',
    'cache_set',
    'cache_delete',
    'cache_clear',
    'cache_exists',
    'cache_get_many',
    'cache_set_many',
    'cache_delete_many',

    # Утилиты
    'invalidate_cache',
    'get_cache_stats',
    'cache_key',

    # Декораторы
    'cached',
    'cached_result',

    # Классы
    'CacheError',
    'CacheBackend',
    'RedisBackend',
    'InMemoryBackend',
    'CacheManager',
    'TempCache',

    # Флаг доступности
    'cache_available'
]

# Финальная проверка
if cache_available:
    logger.info("Модуль кэширования полностью инициализирован")
else:
    logger.warning("Модуль кэширования работает в режиме заглушек")