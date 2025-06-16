"""
Менеджер для управления LLM провайдерами.

Этот модуль содержит:
- Унифицированный интерфейс для всех LLM
- Автоматический выбор оптимального провайдера
- Fallback стратегию при недоступности
- Балансировку нагрузки между провайдерами
- Кэширование ответов
- Мониторинг использования и затрат
"""

import asyncio
import hashlib
import json
from typing import Optional, Dict, Any, List, Tuple, Union
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field
import random

from config import logger, settings
from infrastructure.external_apis.openai_client import (
    OpenAIClient, OpenAIModel, GenerationType
)
from infrastructure.external_apis.anthropic_client import (
    AnthropicClient, ClaudeModel
)
from core.exceptions import (
    ExternalAPIError, RateLimitExceededError,
    TokenLimitExceededError, LLMProviderError
)
from infrastructure.cache import cache_manager


class LLMProvider(str, Enum):
    """Доступные LLM провайдеры."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    LOCAL = "local"  # Для будущей поддержки локальных моделей


class TaskPriority(str, Enum):
    """Приоритет задачи."""
    LOW = "low"  # Можно использовать дешевые модели
    MEDIUM = "medium"  # Стандартные модели
    HIGH = "high"  # Лучшие модели
    CRITICAL = "critical"  # Только лучшие модели с fallback


@dataclass
class LLMRequest:
    """Запрос к LLM."""
    prompt: str
    generation_type: GenerationType
    priority: TaskPriority = TaskPriority.MEDIUM
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    system_prompt: Optional[str] = None
    user_context: Optional[Dict[str, Any]] = None
    preferred_provider: Optional[LLMProvider] = None
    cache_ttl: Optional[int] = 3600  # 1 час по умолчанию
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LLMResponse:
    """Ответ от LLM."""
    content: str
    provider: LLMProvider
    model: str
    usage: Dict[str, Any]
    cached: bool = False
    generation_time: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class ProviderHealth:
    """Состояние здоровья провайдера."""

    def __init__(self, provider: LLMProvider):
        self.provider = provider
        self.is_available = True
        self.last_error_time: Optional[datetime] = None
        self.error_count = 0
        self.success_count = 0
        self.total_latency = 0.0
        self.rate_limit_reset: Optional[datetime] = None

    @property
    def average_latency(self) -> float:
        """Средняя задержка."""
        total = self.success_count + self.error_count
        return self.total_latency / total if total > 0 else 0.0

    @property
    def error_rate(self) -> float:
        """Процент ошибок."""
        total = self.success_count + self.error_count
        return self.error_count / total if total > 0 else 0.0

    def record_success(self, latency: float) -> None:
        """Записать успешный запрос."""
        self.success_count += 1
        self.total_latency += latency
        self.is_available = True

        # Сброс счетчика ошибок при успехе
        if self.error_count > 0:
            self.error_count = max(0, self.error_count - 1)

    def record_error(self, is_rate_limit: bool = False) -> None:
        """Записать ошибку."""
        self.error_count += 1
        self.last_error_time = datetime.utcnow()

        # При rate limit устанавливаем время сброса
        if is_rate_limit:
            self.rate_limit_reset = datetime.utcnow() + timedelta(minutes=1)

        # Отключаем провайдера при множественных ошибках
        if self.error_count >= 5:
            self.is_available = False
            logger.warning(f"Провайдер {self.provider} отключен из-за ошибок")

    def check_availability(self) -> bool:
        """Проверка доступности."""
        # Проверка rate limit
        if self.rate_limit_reset and datetime.utcnow() < self.rate_limit_reset:
            return False

        # Восстановление после ошибок
        if not self.is_available and self.last_error_time:
            recovery_time = timedelta(minutes=5)
            if datetime.utcnow() - self.last_error_time > recovery_time:
                self.is_available = True
                self.error_count = 0
                logger.info(f"Провайдер {self.provider} восстановлен")

        return self.is_available


class LLMManager:
    """
    Менеджер для управления всеми LLM провайдерами.

    Обеспечивает единый интерфейс и интеллектуальную маршрутизацию.
    """

    def __init__(self):
        """Инициализация менеджера."""
        # Инициализация провайдеров
        self.providers: Dict[LLMProvider, Union[OpenAIClient, AnthropicClient]] = {}
        self._init_providers()

        # Состояние провайдеров
        self.provider_health: Dict[LLMProvider, ProviderHealth] = {
            provider: ProviderHealth(provider)
            for provider in self.providers
        }

        # Статистика
        self.total_requests = 0
        self.cache_hits = 0
        self.total_cost = 0.0

        # Конфигурация
        self.enable_cache = settings.llm.enable_cache
        self.enable_fallback = settings.llm.enable_fallback

        logger.info(f"LLM Manager инициализирован с провайдерами: {list(self.providers.keys())}")

    def _init_providers(self) -> None:
        """Инициализация доступных провайдеров."""
        # OpenAI
        if settings.openai.api_key:
            try:
                self.providers[LLMProvider.OPENAI] = OpenAIClient(
                    api_key=settings.openai.api_key
                )
                logger.info("OpenAI провайдер инициализирован")
            except Exception as e:
                logger.error(f"Ошибка инициализации OpenAI: {e}")

        # Anthropic
        if settings.anthropic.api_key:
            try:
                self.providers[LLMProvider.ANTHROPIC] = AnthropicClient(
                    api_key=settings.anthropic.api_key
                )
                logger.info("Anthropic провайдер инициализирован")
            except Exception as e:
                logger.error(f"Ошибка инициализации Anthropic: {e}")

        if not self.providers:
            raise LLMProviderError("Не удалось инициализировать ни один LLM провайдер")

    def _get_cache_key(self, request: LLMRequest) -> str:
        """Генерация ключа кэша для запроса."""
        cache_data = {
            "prompt": request.prompt,
            "generation_type": request.generation_type,
            "system_prompt": request.system_prompt,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens
        }
        cache_str = json.dumps(cache_data, sort_keys=True)
        return f"llm:{hashlib.md5(cache_str.encode()).hexdigest()}"

    async def _get_from_cache(self, cache_key: str) -> Optional[LLMResponse]:
        """Получение ответа из кэша."""
        if not self.enable_cache:
            return None

        cached_data = await cache_manager.get(cache_key)
        if cached_data:
            self.cache_hits += 1
            logger.debug(f"LLM ответ найден в кэше: {cache_key}")

            # Восстанавливаем объект ответа
            response = LLMResponse(**cached_data)
            response.cached = True
            return response

        return None

    async def _save_to_cache(
            self,
            cache_key: str,
            response: LLMResponse,
            ttl: int
    ) -> None:
        """Сохранение ответа в кэш."""
        if not self.enable_cache or ttl <= 0:
            return

        # Сериализуем ответ
        cache_data = {
            "content": response.content,
            "provider": response.provider,
            "model": response.model,
            "usage": response.usage,
            "metadata": response.metadata
        }

        await cache_manager.set(cache_key, cache_data, ttl)
        logger.debug(f"LLM ответ сохранен в кэш на {ttl}с: {cache_key}")

    def _select_provider(
            self,
            request: LLMRequest,
            exclude_providers: Optional[List[LLMProvider]] = None
    ) -> Tuple[LLMProvider, Union[OpenAIClient, AnthropicClient]]:
        """
        Выбор оптимального провайдера для запроса.

        Args:
            request: Запрос к LLM
            exclude_providers: Провайдеры для исключения

        Returns:
            Кортеж (провайдер, клиент)

        Raises:
            LLMProviderError: Если нет доступных провайдеров
        """
        exclude_providers = exclude_providers or []

        # Если указан предпочтительный провайдер
        if request.preferred_provider and request.preferred_provider not in exclude_providers:
            provider = request.preferred_provider
            if provider in self.providers and self.provider_health[provider].check_availability():
                return provider, self.providers[provider]

        # Фильтруем доступные провайдеры
        available_providers = [
            (p, c) for p, c in self.providers.items()
            if p not in exclude_providers and self.provider_health[p].check_availability()
        ]

        if not available_providers:
            raise LLMProviderError("Нет доступных LLM провайдеров")

        # Выбор по приоритету задачи
        if request.priority == TaskPriority.CRITICAL:
            # Для критических задач выбираем провайдера с лучшей доступностью
            best_provider = min(
                available_providers,
                key=lambda x: self.provider_health[x[0]].error_rate
            )
            return best_provider

        elif request.priority == TaskPriority.LOW:
            # Для низкого приоритета можно использовать случайный выбор
            return random.choice(available_providers)

        else:
            # Для средних задач выбираем по типу генерации
            if request.generation_type in [
                GenerationType.NATAL_CHART_ANALYSIS,
                GenerationType.SYNASTRY_ANALYSIS
            ]:
                # Сложные задачи лучше для Claude
                for provider, client in available_providers:
                    if provider == LLMProvider.ANTHROPIC:
                        return provider, client

            # По умолчанию используем провайдера с лучшей производительностью
            best_provider = min(
                available_providers,
                key=lambda x: self.provider_health[x[0]].average_latency or float('inf')
            )
            return best_provider

    async def generate(
            self,
            request: LLMRequest,
            retry_with_fallback: bool = True
    ) -> LLMResponse:
        """
        Генерация текста через оптимальный провайдер.

        Args:
            request: Запрос к LLM
            retry_with_fallback: Использовать fallback при ошибке

        Returns:
            Ответ от LLM

        Raises:
            LLMProviderError: При невозможности получить ответ
        """
        self.total_requests += 1
        start_time = datetime.utcnow()

        # Проверяем кэш
        cache_key = self._get_cache_key(request)
        cached_response = await self._get_from_cache(cache_key)
        if cached_response:
            return cached_response

        # Попытки с разными провайдерами
        tried_providers = []
        last_error = None

        while True:
            try:
                # Выбираем провайдера
                provider, client = self._select_provider(request, tried_providers)
                tried_providers.append(provider)

                logger.info(f"Используем {provider} для {request.generation_type}")

                # Вызываем соответствующий метод
                if provider == LLMProvider.OPENAI:
                    result = await self._call_openai(client, request)
                elif provider == LLMProvider.ANTHROPIC:
                    result = await self._call_anthropic(client, request)
                else:
                    raise NotImplementedError(f"Провайдер {provider} не реализован")

                # Создаем ответ
                generation_time = (datetime.utcnow() - start_time).total_seconds()
                response = LLMResponse(
                    content=result["content"],
                    provider=provider,
                    model=result["model"],
                    usage=result["usage"],
                    generation_time=generation_time,
                    metadata=result.get("metadata", {})
                )

                # Записываем успех
                self.provider_health[provider].record_success(generation_time)

                # Обновляем статистику стоимости
                if provider == LLMProvider.OPENAI and "estimated_cost" in result["usage"]:
                    self.total_cost += result["usage"]["estimated_cost"]

                # Сохраняем в кэш
                await self._save_to_cache(cache_key, response, request.cache_ttl)

                return response

            except RateLimitExceededError as e:
                logger.warning(f"Rate limit для {provider}: {e}")
                self.provider_health[provider].record_error(is_rate_limit=True)
                last_error = e

            except TokenLimitExceededError as e:
                logger.error(f"Превышен лимит токенов для {provider}: {e}")
                last_error = e
                # Не пробуем другие провайдеры при превышении токенов
                break

            except Exception as e:
                logger.error(f"Ошибка {provider}: {e}")
                self.provider_health[provider].record_error()
                last_error = e

            # Проверяем, нужно ли пробовать другой провайдер
            if not retry_with_fallback or not self.enable_fallback:
                break

            if len(tried_providers) >= len(self.providers):
                break

        # Если все попытки неудачны
        raise LLMProviderError(
            f"Не удалось получить ответ от LLM после {len(tried_providers)} попыток",
            details={"last_error": str(last_error), "tried_providers": tried_providers}
        )

    async def _call_openai(
            self,
            client: OpenAIClient,
            request: LLMRequest
    ) -> Dict[str, Any]:
        """Вызов OpenAI API."""
        return await client.generate(
            prompt=request.prompt,
            generation_type=request.generation_type,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            system_prompt=request.system_prompt,
            user_context=request.user_context
        )

    async def _call_anthropic(
            self,
            client: AnthropicClient,
            request: LLMRequest
    ) -> Dict[str, Any]:
        """Вызов Anthropic API."""
        # Маппинг типов генерации на anthropic
        generation_type_map = {
            GenerationType.TAROT_INTERPRETATION: "tarot_analysis",
            GenerationType.ASTRO_FORECAST: "astro_deep_analysis",
            GenerationType.NATAL_CHART_ANALYSIS: "astro_deep_analysis",
            GenerationType.SYNASTRY_ANALYSIS: "synastry_compatibility",
            GenerationType.QUESTION_ANSWER: "esoteric_counseling",
            GenerationType.DAILY_HOROSCOPE: "general"
        }

        anthropic_type = generation_type_map.get(
            request.generation_type,
            "general"
        )

        return await client.generate(
            prompt=request.prompt,
            generation_type=anthropic_type,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            system_prompt=request.system_prompt,
            context_data=request.user_context
        )

    # Методы для специфичных задач

    async def interpret_tarot(
            self,
            cards: List[Dict[str, Any]],
            spread_type: str,
            question: Optional[str] = None,
            user_data: Optional[Dict[str, Any]] = None,
            priority: TaskPriority = TaskPriority.MEDIUM
    ) -> str:
        """
        Интерпретация расклада Таро.

        Args:
            cards: Выпавшие карты
            spread_type: Тип расклада
            question: Вопрос пользователя
            user_data: Данные о пользователе
            priority: Приоритет задачи

        Returns:
            Интерпретация расклада
        """
        # Формируем промпт
        prompt = f"Интерпретируй расклад Таро '{spread_type}'.\n\n"

        if question:
            prompt += f"Вопрос: {question}\n\n"

        prompt += "Выпавшие карты:\n"
        for card in cards:
            position = card.get("position_meaning", f"Позиция {card['position']}")
            card_name = card["card_name"]
            is_reversed = card.get("is_reversed", False)
            orientation = "перевернутая" if is_reversed else "прямая"

            prompt += f"{position}: {card_name} ({orientation})\n"

        # Создаем запрос
        request = LLMRequest(
            prompt=prompt,
            generation_type=GenerationType.TAROT_INTERPRETATION,
            priority=priority,
            user_context=user_data,
            temperature=0.8,
            cache_ttl=7200  # 2 часа для интерпретаций
        )

        # Генерируем
        response = await self.generate(request)
        return response.content

    async def analyze_natal_chart(
            self,
            chart_data: Dict[str, Any],
            focus_areas: Optional[List[str]] = None,
            analysis_depth: str = "detailed"
    ) -> str:
        """
        Анализ натальной карты.

        Args:
            chart_data: Данные натальной карты
            focus_areas: Области фокуса
            analysis_depth: Глубина анализа

        Returns:
            Анализ натальной карты
        """
        # Для глубокого анализа предпочитаем Claude
        preferred = LLMProvider.ANTHROPIC if analysis_depth == "comprehensive" else None
        priority = TaskPriority.HIGH if analysis_depth == "comprehensive" else TaskPriority.MEDIUM

        # Формируем промпт
        prompt = self._build_natal_chart_prompt(chart_data, focus_areas, analysis_depth)

        request = LLMRequest(
            prompt=prompt,
            generation_type=GenerationType.NATAL_CHART_ANALYSIS,
            priority=priority,
            preferred_provider=preferred,
            max_tokens=4000 if analysis_depth == "comprehensive" else 2500,
            cache_ttl=86400  # 24 часа для натальных карт
        )

        response = await self.generate(request)
        return response.content

    def _build_natal_chart_prompt(
            self,
            chart_data: Dict[str, Any],
            focus_areas: Optional[List[str]],
            analysis_depth: str
    ) -> str:
        """Построение промпта для анализа натальной карты."""
        prompt = f"Проведи {analysis_depth} анализ натальной карты.\n\n"

        # Основные показатели
        prompt += "ОСНОВНЫЕ ПОКАЗАТЕЛИ:\n"
        prompt += f"Солнце: {chart_data.get('sun', 'неизвестно')}\n"
        prompt += f"Луна: {chart_data.get('moon', 'неизвестно')}\n"
        prompt += f"Асцендент: {chart_data.get('ascendant', 'неизвестно')}\n\n"

        # Планеты
        if "planets" in chart_data:
            prompt += "ПЛАНЕТЫ В ЗНАКАХ И ДОМАХ:\n"
            for planet, info in chart_data["planets"].items():
                prompt += f"{planet}: {info}\n"
            prompt += "\n"

        # Аспекты
        if "aspects" in chart_data:
            prompt += "КЛЮЧЕВЫЕ АСПЕКТЫ:\n"
            for aspect in chart_data["aspects"][:15]:
                prompt += f"{aspect}\n"
            prompt += "\n"

        # Фокус анализа
        if focus_areas:
            prompt += f"ОСОБОЕ ВНИМАНИЕ НА: {', '.join(focus_areas)}\n\n"

        # Инструкции по глубине
        if analysis_depth == "basic":
            prompt += "Дай краткий обзор основных черт личности и потенциала."
        elif analysis_depth == "comprehensive":
            prompt += """Проведи комплексный анализ включающий:
1. Психологический портрет
2. Кармические задачи
3. Таланты и способности  
4. Сферы реализации
5. Текущие циклы развития
6. Практические рекомендации"""

        return prompt

    # Статистика и мониторинг

    def get_statistics(self) -> Dict[str, Any]:
        """Получение статистики работы менеджера."""
        stats = {
            "total_requests": self.total_requests,
            "cache_hits": self.cache_hits,
            "cache_hit_rate": self.cache_hits / max(self.total_requests, 1),
            "total_cost_usd": round(self.total_cost, 2),
            "providers": {}
        }

        # Статистика по провайдерам
        for provider, health in self.provider_health.items():
            stats["providers"][provider] = {
                "is_available": health.is_available,
                "success_count": health.success_count,
                "error_count": health.error_count,
                "error_rate": round(health.error_rate, 3),
                "average_latency": round(health.average_latency, 2)
            }

        return stats

    def reset_statistics(self) -> None:
        """Сброс статистики."""
        self.total_requests = 0
        self.cache_hits = 0
        self.total_cost = 0.0

        for health in self.provider_health.values():
            health.success_count = 0
            health.error_count = 0
            health.total_latency = 0.0

        logger.info("Статистика LLM Manager сброшена")

    async def close(self) -> None:
        """Закрытие всех клиентов."""
        for provider, client in self.providers.items():
            try:
                await client.close()
                logger.info(f"Закрыт клиент {provider}")
            except Exception as e:
                logger.error(f"Ошибка закрытия {provider}: {e}")


# Глобальный экземпляр менеджера
llm_manager = LLMManager()


# Вспомогательные функции для удобства
async def generate_text(
        prompt: str,
        generation_type: GenerationType = GenerationType.QUESTION_ANSWER,
        **kwargs
) -> str:
    """
    Быстрая генерация текста.

    Args:
        prompt: Промпт
        generation_type: Тип генерации
        **kwargs: Дополнительные параметры

    Returns:
        Сгенерированный текст
    """
    request = LLMRequest(
        prompt=prompt,
        generation_type=generation_type,
        **kwargs
    )

    response = await llm_manager.generate(request)
    return response.content