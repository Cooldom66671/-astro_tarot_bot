"""
Базовый класс для интеграции с внешними API.

Этот модуль содержит:
- Абстрактный базовый клиент с retry логикой
- Rate limiting и управление квотами
- Обработку ошибок и таймаутов
- Логирование и метрики
- Кэширование ответов
- Circuit breaker паттерн
"""

import asyncio
import time
import json
from abc import ABC, abstractmethod
from typing import (
    Optional, Dict, Any, Type, TypeVar, List,
    Callable, Union, Tuple
)
from datetime import datetime, timedelta
from enum import Enum
from functools import wraps
import hashlib

import aiohttp
from aiohttp import ClientTimeout, ClientError, ContentTypeError
import backoff

from config import logger, settings
from core.exceptions import (
    ExternalAPIError, RateLimitExceededError,
    APITimeoutError, ValidationError
)

T = TypeVar('T')


class RequestMethod(str, Enum):
    """HTTP методы запросов."""
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"


class CircuitState(str, Enum):
    """Состояния Circuit Breaker."""
    CLOSED = "closed"  # Нормальная работа
    OPEN = "open"  # Блокировка запросов
    HALF_OPEN = "half_open"  # Тестовый режим


class BaseAPIClient(ABC):
    """
    Базовый класс для всех внешних API клиентов.

    Предоставляет общую функциональность для работы с HTTP API.
    """

    def __init__(
            self,
            base_url: str,
            api_key: Optional[str] = None,
            timeout: int = 30,
            max_retries: int = 3,
            rate_limit_calls: Optional[int] = None,
            rate_limit_period: Optional[int] = None,
            cache_ttl: Optional[int] = None
    ):
        """
        Инициализация базового API клиента.

        Args:
            base_url: Базовый URL API
            api_key: API ключ
            timeout: Таймаут запросов в секундах
            max_retries: Максимум повторных попыток
            rate_limit_calls: Количество вызовов для rate limit
            rate_limit_period: Период rate limit в секундах
            cache_ttl: Время жизни кэша в секундах
        """
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.timeout = ClientTimeout(total=timeout)
        self.max_retries = max_retries

        # Rate limiting
        self.rate_limit_calls = rate_limit_calls
        self.rate_limit_period = rate_limit_period
        self._call_times: List[float] = []

        # Circuit breaker
        self._circuit_state = CircuitState.CLOSED
        self._circuit_failures = 0
        self._circuit_last_failure_time: Optional[float] = None
        self._circuit_success_count = 0
        self._circuit_failure_threshold = 5
        self._circuit_recovery_timeout = 60  # секунд
        self._circuit_success_threshold = 3

        # Кэширование
        self.cache_ttl = cache_ttl
        self._cache: Dict[str, Tuple[Any, float]] = {}

        # Метрики
        self._request_count = 0
        self._error_count = 0
        self._total_request_time = 0.0

        # Сессия aiohttp (создается при первом использовании)
        self._session: Optional[aiohttp.ClientSession] = None

        logger.info(f"Инициализирован {self.__class__.__name__} для {base_url}")

    @property
    def name(self) -> str:
        """Имя клиента для логирования."""
        return self.__class__.__name__

    @abstractmethod
    def _get_headers(self) -> Dict[str, str]:
        """
        Получение заголовков для запросов.

        Должно быть реализовано в наследниках.

        Returns:
            Словарь заголовков
        """
        pass

    # Rate limiting

    def _check_rate_limit(self) -> None:
        """
        Проверка rate limit.

        Raises:
            RateLimitExceededError: При превышении лимита
        """
        if not self.rate_limit_calls or not self.rate_limit_period:
            return

        now = time.time()

        # Очищаем старые вызовы
        self._call_times = [
            t for t in self._call_times
            if now - t < self.rate_limit_period
        ]

        # Проверяем лимит
        if len(self._call_times) >= self.rate_limit_calls:
            oldest_call = min(self._call_times)
            wait_time = self.rate_limit_period - (now - oldest_call)

            raise RateLimitExceededError(
                f"Rate limit exceeded for {self.name}",
                retry_after=int(wait_time) + 1
            )

        # Записываем текущий вызов
        self._call_times.append(now)

    # Circuit breaker

    def _check_circuit_breaker(self) -> None:
        """
        Проверка состояния Circuit Breaker.

        Raises:
            ExternalAPIError: Если circuit открыт
        """
        now = time.time()

        if self._circuit_state == CircuitState.OPEN:
            # Проверяем, пора ли перейти в HALF_OPEN
            if (self._circuit_last_failure_time and
                    now - self._circuit_last_failure_time > self._circuit_recovery_timeout):

                logger.info(f"{self.name}: Circuit breaker переходит в HALF_OPEN")
                self._circuit_state = CircuitState.HALF_OPEN
                self._circuit_success_count = 0
            else:
                raise ExternalAPIError(
                    f"{self.name} временно недоступен (circuit open)",
                    service_name=self.name
                )

    def _on_request_success(self) -> None:
        """Обработка успешного запроса для circuit breaker."""
        if self._circuit_state == CircuitState.HALF_OPEN:
            self._circuit_success_count += 1

            if self._circuit_success_count >= self._circuit_success_threshold:
                logger.info(f"{self.name}: Circuit breaker закрыт")
                self._circuit_state = CircuitState.CLOSED
                self._circuit_failures = 0

        elif self._circuit_state == CircuitState.CLOSED:
            self._circuit_failures = 0

    def _on_request_failure(self) -> None:
        """Обработка неудачного запроса для circuit breaker."""
        self._circuit_failures += 1
        self._circuit_last_failure_time = time.time()

        if self._circuit_failures >= self._circuit_failure_threshold:
            logger.warning(f"{self.name}: Circuit breaker открыт после {self._circuit_failures} ошибок")
            self._circuit_state = CircuitState.OPEN

    # Кэширование

    def _get_cache_key(
            self,
            method: str,
            endpoint: str,
            params: Optional[Dict] = None
    ) -> str:
        """Генерация ключа кэша."""
        cache_data = {
            "method": method,
            "endpoint": endpoint,
            "params": params or {}
        }
        cache_str = json.dumps(cache_data, sort_keys=True)
        return hashlib.md5(cache_str.encode()).hexdigest()

    def _get_from_cache(self, cache_key: str) -> Optional[Any]:
        """Получение из кэша."""
        if not self.cache_ttl:
            return None

        if cache_key in self._cache:
            data, timestamp = self._cache[cache_key]
            if time.time() - timestamp < self.cache_ttl:
                logger.debug(f"{self.name}: Использован кэш для {cache_key}")
                return data
            else:
                del self._cache[cache_key]

        return None

    def _save_to_cache(self, cache_key: str, data: Any) -> None:
        """Сохранение в кэш."""
        if self.cache_ttl:
            self._cache[cache_key] = (data, time.time())

            # Ограничиваем размер кэша
            if len(self._cache) > 1000:
                # Удаляем самые старые записи
                sorted_items = sorted(
                    self._cache.items(),
                    key=lambda x: x[1][1]
                )
                for key, _ in sorted_items[:100]:
                    del self._cache[key]

    # HTTP запросы

    async def _get_session(self) -> aiohttp.ClientSession:
        """Получение или создание сессии aiohttp."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=self.timeout,
                connector=aiohttp.TCPConnector(
                    limit=100,
                    limit_per_host=30,
                    ttl_dns_cache=300
                )
            )
        return self._session

    @backoff.on_exception(
        backoff.expo,
        (aiohttp.ClientError, asyncio.TimeoutError),
        max_tries=3,
        max_time=60
    )
    async def _make_request(
            self,
            method: RequestMethod,
            endpoint: str,
            params: Optional[Dict[str, Any]] = None,
            json_data: Optional[Dict[str, Any]] = None,
            data: Optional[Any] = None,
            headers: Optional[Dict[str, str]] = None,
            use_cache: bool = True
    ) -> Any:
        """
        Выполнение HTTP запроса с retry и обработкой ошибок.

        Args:
            method: HTTP метод
            endpoint: Endpoint (без base_url)
            params: Query параметры
            json_data: JSON данные для отправки
            data: Данные для отправки (не JSON)
            headers: Дополнительные заголовки
            use_cache: Использовать кэш

        Returns:
            Ответ API

        Raises:
            ExternalAPIError: При ошибке API
            APITimeoutError: При таймауте
            RateLimitExceededError: При превышении rate limit
        """
        # Проверки перед запросом
        self._check_rate_limit()
        self._check_circuit_breaker()

        # Проверяем кэш для GET запросов
        cache_key = None
        if method == RequestMethod.GET and use_cache:
            cache_key = self._get_cache_key(method, endpoint, params)
            cached_data = self._get_from_cache(cache_key)
            if cached_data is not None:
                return cached_data

        # Формируем URL
        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        # Заголовки
        request_headers = self._get_headers()
        if headers:
            request_headers.update(headers)

        # Метрики
        self._request_count += 1
        start_time = time.time()

        logger.debug(f"{self.name} {method} {url}")

        try:
            session = await self._get_session()

            async with session.request(
                    method=method,
                    url=url,
                    params=params,
                    json=json_data,
                    data=data,
                    headers=request_headers
            ) as response:
                # Логирование времени ответа
                request_time = time.time() - start_time
                self._total_request_time += request_time

                logger.debug(
                    f"{self.name} {method} {url} - "
                    f"Status: {response.status}, Time: {request_time:.2f}s"
                )

                # Обработка ответа
                if response.status == 429:  # Too Many Requests
                    retry_after = response.headers.get('Retry-After', '60')
                    raise RateLimitExceededError(
                        f"Rate limit exceeded for {self.name}",
                        retry_after=int(retry_after)
                    )

                if response.status >= 500:
                    self._on_request_failure()
                    raise ExternalAPIError(
                        f"{self.name} server error: {response.status}",
                        service_name=self.name,
                        status_code=response.status
                    )

                if response.status >= 400:
                    error_text = await response.text()
                    self._on_request_failure()
                    raise ExternalAPIError(
                        f"{self.name} client error: {error_text}",
                        service_name=self.name,
                        status_code=response.status
                    )

                # Успешный ответ
                self._on_request_success()

                # Парсинг ответа
                content_type = response.headers.get('Content-Type', '')

                if 'application/json' in content_type:
                    result = await response.json()
                elif 'text/' in content_type:
                    result = await response.text()
                else:
                    result = await response.read()

                # Кэширование успешного ответа
                if cache_key:
                    self._save_to_cache(cache_key, result)

                return result

        except asyncio.TimeoutError:
            self._error_count += 1
            self._on_request_failure()
            raise APITimeoutError(
                f"Timeout for {self.name} after {self.timeout.total}s",
                service_name=self.name
            )

        except aiohttp.ClientError as e:
            self._error_count += 1
            self._on_request_failure()
            raise ExternalAPIError(
                f"{self.name} connection error: {str(e)}",
                service_name=self.name
            )

        except Exception as e:
            self._error_count += 1
            self._on_request_failure()
            logger.error(f"Unexpected error in {self.name}: {e}")
            raise

    # Удобные методы

    async def get(
            self,
            endpoint: str,
            params: Optional[Dict[str, Any]] = None,
            **kwargs
    ) -> Any:
        """GET запрос."""
        return await self._make_request(
            RequestMethod.GET,
            endpoint,
            params=params,
            **kwargs
        )

    async def post(
            self,
            endpoint: str,
            json_data: Optional[Dict[str, Any]] = None,
            data: Optional[Any] = None,
            **kwargs
    ) -> Any:
        """POST запрос."""
        return await self._make_request(
            RequestMethod.POST,
            endpoint,
            json_data=json_data,
            data=data,
            **kwargs
        )

    async def put(
            self,
            endpoint: str,
            json_data: Optional[Dict[str, Any]] = None,
            **kwargs
    ) -> Any:
        """PUT запрос."""
        return await self._make_request(
            RequestMethod.PUT,
            endpoint,
            json_data=json_data,
            **kwargs
        )

    async def patch(
            self,
            endpoint: str,
            json_data: Optional[Dict[str, Any]] = None,
            **kwargs
    ) -> Any:
        """PATCH запрос."""
        return await self._make_request(
            RequestMethod.PATCH,
            endpoint,
            json_data=json_data,
            **kwargs
        )

    async def delete(
            self,
            endpoint: str,
            **kwargs
    ) -> Any:
        """DELETE запрос."""
        return await self._make_request(
            RequestMethod.DELETE,
            endpoint,
            **kwargs
        )

    # Управление ресурсами

    async def close(self) -> None:
        """Закрытие клиента и освобождение ресурсов."""
        if self._session and not self._session.closed:
            await self._session.close()
            logger.info(f"{self.name}: Сессия закрыта")

    async def __aenter__(self):
        """Вход в контекстный менеджер."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Выход из контекстного менеджера."""
        await self.close()

    # Метрики и статистика

    def get_metrics(self) -> Dict[str, Any]:
        """
        Получение метрик клиента.

        Returns:
            Словарь с метриками
        """
        avg_request_time = (
            self._total_request_time / self._request_count
            if self._request_count > 0 else 0
        )

        return {
            "client": self.name,
            "base_url": self.base_url,
            "metrics": {
                "total_requests": self._request_count,
                "total_errors": self._error_count,
                "error_rate": self._error_count / max(self._request_count, 1),
                "average_request_time": avg_request_time,
                "cache_size": len(self._cache),
                "circuit_state": self._circuit_state.value,
                "circuit_failures": self._circuit_failures
            },
            "rate_limit": {
                "calls": self.rate_limit_calls,
                "period": self.rate_limit_period,
                "current_calls": len(self._call_times)
            }
        }

    def reset_metrics(self) -> None:
        """Сброс метрик."""
        self._request_count = 0
        self._error_count = 0
        self._total_request_time = 0.0
        logger.info(f"{self.name}: Метрики сброшены")

    def clear_cache(self) -> None:
        """Очистка кэша."""
        self._cache.clear()
        logger.info(f"{self.name}: Кэш очищен")