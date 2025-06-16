"""
Клиент для работы с OpenAI API.

Этот модуль содержит:
- Интеграцию с ChatGPT для генерации интерпретаций
- Умный выбор модели в зависимости от задачи
- Подсчет и контроль использования токенов
- Streaming ответы для длинных генераций
- Специализированные промпты для Таро и астрологии
"""

import json
from typing import Optional, Dict, Any, List, AsyncGenerator, Tuple
from datetime import datetime
from enum import Enum
import tiktoken

from config import logger, settings
from infrastructure.external_apis.base import BaseAPIClient
from core.exceptions import (
    ExternalAPIError, ValidationError,
    TokenLimitExceededError
)


class OpenAIModel(str, Enum):
    """Доступные модели OpenAI."""
    # GPT-4 модели
    GPT4_TURBO = "gpt-4-turbo-preview"
    GPT4 = "gpt-4"
    GPT4_32K = "gpt-4-32k"

    # GPT-3.5 модели
    GPT35_TURBO = "gpt-3.5-turbo"
    GPT35_TURBO_16K = "gpt-3.5-turbo-16k"

    # Специальные модели
    GPT4_VISION = "gpt-4-vision-preview"


class GenerationType(str, Enum):
    """Типы генерации контента."""
    TAROT_INTERPRETATION = "tarot_interpretation"
    ASTRO_FORECAST = "astro_forecast"
    NATAL_CHART_ANALYSIS = "natal_chart_analysis"
    SYNASTRY_ANALYSIS = "synastry_analysis"
    QUESTION_ANSWER = "question_answer"
    DAILY_HOROSCOPE = "daily_horoscope"


class OpenAIClient(BaseAPIClient):
    """
    Клиент для работы с OpenAI API.

    Специализирован для генерации эзотерического контента.
    """

    # Лимиты токенов для моделей
    MODEL_LIMITS = {
        OpenAIModel.GPT4_TURBO: 128000,
        OpenAIModel.GPT4: 8192,
        OpenAIModel.GPT4_32K: 32768,
        OpenAIModel.GPT35_TURBO: 4096,
        OpenAIModel.GPT35_TURBO_16K: 16384,
        OpenAIModel.GPT4_VISION: 128000
    }

    # Стоимость за 1K токенов (input/output) в долларах
    MODEL_COSTS = {
        OpenAIModel.GPT4_TURBO: (0.01, 0.03),
        OpenAIModel.GPT4: (0.03, 0.06),
        OpenAIModel.GPT4_32K: (0.06, 0.12),
        OpenAIModel.GPT35_TURBO: (0.0005, 0.0015),
        OpenAIModel.GPT35_TURBO_16K: (0.001, 0.002)
    }

    def __init__(
            self,
            api_key: Optional[str] = None,
            default_model: OpenAIModel = OpenAIModel.GPT35_TURBO,
            max_tokens: int = 2000,
            temperature: float = 0.7
    ):
        """
        Инициализация OpenAI клиента.

        Args:
            api_key: API ключ OpenAI
            default_model: Модель по умолчанию
            max_tokens: Максимум токенов в ответе
            temperature: Температура генерации (0-2)
        """
        api_key = api_key or settings.openai.api_key
        if not api_key:
            raise ValidationError("OpenAI API key не указан")

        super().__init__(
            base_url="https://api.openai.com/v1",
            api_key=api_key,
            timeout=60,
            max_retries=3,
            rate_limit_calls=settings.openai.rate_limit_calls,
            rate_limit_period=60,
            cache_ttl=settings.openai.cache_ttl
        )

        self.default_model = default_model
        self.max_tokens = max_tokens
        self.temperature = temperature

        # Инициализация tokenizer
        self._tokenizers: Dict[str, tiktoken.Encoding] = {}

        # Статистика использования
        self.total_tokens_used = 0
        self.total_cost = 0.0

        logger.info(f"OpenAI клиент инициализирован с моделью {default_model}")

    def _get_headers(self) -> Dict[str, str]:
        """Получение заголовков для OpenAI API."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def _get_tokenizer(self, model: OpenAIModel) -> tiktoken.Encoding:
        """
        Получение tokenizer для модели.

        Args:
            model: Модель OpenAI

        Returns:
            Tokenizer для подсчета токенов
        """
        if model not in self._tokenizers:
            try:
                # Определяем encoding для модели
                if "gpt-4" in model:
                    encoding_name = "cl100k_base"
                else:
                    encoding_name = "cl100k_base"

                self._tokenizers[model] = tiktoken.get_encoding(encoding_name)
            except Exception as e:
                logger.warning(f"Не удалось загрузить tokenizer для {model}: {e}")
                # Fallback на базовый tokenizer
                self._tokenizers[model] = tiktoken.get_encoding("cl100k_base")

        return self._tokenizers[model]

    def count_tokens(self, text: str, model: Optional[OpenAIModel] = None) -> int:
        """
        Подсчет токенов в тексте.

        Args:
            text: Текст для подсчета
            model: Модель (если не указана, используется default)

        Returns:
            Количество токенов
        """
        model = model or self.default_model
        tokenizer = self._get_tokenizer(model)
        return len(tokenizer.encode(text))

    def estimate_cost(
            self,
            input_tokens: int,
            output_tokens: int,
            model: Optional[OpenAIModel] = None
    ) -> float:
        """
        Оценка стоимости запроса.

        Args:
            input_tokens: Количество входных токенов
            output_tokens: Количество выходных токенов
            model: Модель

        Returns:
            Примерная стоимость в долларах
        """
        model = model or self.default_model
        input_cost, output_cost = self.MODEL_COSTS.get(model, (0, 0))

        total_cost = (input_tokens / 1000 * input_cost) + (output_tokens / 1000 * output_cost)
        return round(total_cost, 4)

    def _select_model(
            self,
            generation_type: GenerationType,
            estimated_tokens: int
    ) -> OpenAIModel:
        """
        Умный выбор модели в зависимости от задачи.

        Args:
            generation_type: Тип генерации
            estimated_tokens: Примерное количество токенов

        Returns:
            Оптимальная модель
        """
        # Для сложных задач используем GPT-4
        complex_tasks = [
            GenerationType.NATAL_CHART_ANALYSIS,
            GenerationType.SYNASTRY_ANALYSIS
        ]

        if generation_type in complex_tasks:
            # Если нужен большой контекст
            if estimated_tokens > 8000:
                return OpenAIModel.GPT4_TURBO
            else:
                return OpenAIModel.GPT4

        # Для простых задач используем GPT-3.5
        if estimated_tokens > 4000:
            return OpenAIModel.GPT35_TURBO_16K
        else:
            return OpenAIModel.GPT35_TURBO

    def _build_system_prompt(self, generation_type: GenerationType) -> str:
        """
        Построение системного промпта для типа генерации.

        Args:
            generation_type: Тип генерации

        Returns:
            Системный промпт
        """
        prompts = {
            GenerationType.TAROT_INTERPRETATION: """Ты - опытный таролог с глубоким пониманием символизма карт Таро.
Твои интерпретации глубокие, проницательные и персонализированные.
Ты объясняешь значения карт в контексте вопроса и их взаимодействия друг с другом.
Используй эмпатичный и поддерживающий тон, но избегай категоричных утверждений о будущем.""",

            GenerationType.ASTRO_FORECAST: """Ты - профессиональный астролог с глубокими знаниями в области натальной и прогностической астрологии.
Твои прогнозы основаны на точных астрологических расчетах и учитывают индивидуальные особенности натальной карты.
Объясняй астрологические термины простым языком и давай практические советы.""",

            GenerationType.NATAL_CHART_ANALYSIS: """Ты - эксперт в натальной астрологии с многолетним опытом интерпретации карт рождения.
Анализируй все элементы карты: планеты в знаках и домах, аспекты, конфигурации.
Создавай целостный психологический портрет, выделяя сильные стороны и зоны роста.""",

            GenerationType.SYNASTRY_ANALYSIS: """Ты - специалист по синастрической астрологии и анализу совместимости.
Изучай взаимные аспекты между картами, оверлеи домов и композитную карту.
Давай сбалансированный анализ, показывая как гармоничные, так и напряженные аспекты отношений.""",

            GenerationType.QUESTION_ANSWER: """Ты - мудрый эзотерический консультант, сочетающий знания Таро, астрологии и психологии.
Отвечай на вопросы вдумчиво, используя соответствующие эзотерические системы.
Будь эмпатичным, но избегай медицинских и юридических советов.""",

            GenerationType.DAILY_HOROSCOPE: """Ты - астролог, создающий персонализированные ежедневные гороскопы.
Учитывай текущие транзиты и их влияние на натальную карту человека.
Пиши вдохновляюще, практично и позитивно."""
        }

        return prompts.get(generation_type, prompts[GenerationType.QUESTION_ANSWER])

    async def generate(
            self,
            prompt: str,
            generation_type: GenerationType = GenerationType.QUESTION_ANSWER,
            model: Optional[OpenAIModel] = None,
            max_tokens: Optional[int] = None,
            temperature: Optional[float] = None,
            system_prompt: Optional[str] = None,
            user_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Генерация текста через OpenAI API.

        Args:
            prompt: Основной промпт
            generation_type: Тип генерации
            model: Модель (если не указана, выбирается автоматически)
            max_tokens: Максимум токенов
            temperature: Температура
            system_prompt: Кастомный системный промпт
            user_context: Дополнительный контекст

        Returns:
            Словарь с результатом генерации
        """
        # Подготовка параметров
        max_tokens = max_tokens or self.max_tokens
        temperature = temperature or self.temperature

        # Системный промпт
        if not system_prompt:
            system_prompt = self._build_system_prompt(generation_type)

        # Добавляем контекст пользователя
        if user_context:
            context_str = "\n\nКонтекст пользователя:\n"
            for key, value in user_context.items():
                context_str += f"- {key}: {value}\n"
            system_prompt += context_str

        # Подсчет токенов и выбор модели
        estimated_tokens = self.count_tokens(system_prompt + prompt)
        if not model:
            model = self._select_model(generation_type, estimated_tokens)

        # Проверка лимитов
        model_limit = self.MODEL_LIMITS.get(model, 4096)
        if estimated_tokens + max_tokens > model_limit:
            raise TokenLimitExceededError(
                f"Превышен лимит токенов для {model}: "
                f"{estimated_tokens + max_tokens} > {model_limit}"
            )

        # Подготовка сообщений
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]

        # Запрос к API
        logger.info(f"OpenAI генерация: {generation_type} с моделью {model}")

        try:
            response = await self.post(
                "/chat/completions",
                json_data={
                    "model": model,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "top_p": 0.9,
                    "frequency_penalty": 0.3,
                    "presence_penalty": 0.3
                }
            )

            # Обработка ответа
            choice = response["choices"][0]
            message = choice["message"]
            usage = response["usage"]

            # Обновление статистики
            self.total_tokens_used += usage["total_tokens"]
            cost = self.estimate_cost(
                usage["prompt_tokens"],
                usage["completion_tokens"],
                model
            )
            self.total_cost += cost

            result = {
                "content": message["content"],
                "model": model,
                "generation_type": generation_type,
                "usage": {
                    "prompt_tokens": usage["prompt_tokens"],
                    "completion_tokens": usage["completion_tokens"],
                    "total_tokens": usage["total_tokens"],
                    "estimated_cost": cost
                },
                "finish_reason": choice.get("finish_reason", "stop")
            }

            logger.info(
                f"OpenAI ответ получен: {usage['total_tokens']} токенов, "
                f"стоимость ${cost:.4f}"
            )

            return result

        except Exception as e:
            logger.error(f"Ошибка OpenAI API: {e}")
            raise ExternalAPIError(
                f"Ошибка генерации текста: {str(e)}",
                service_name="OpenAI"
            )

    async def generate_stream(
            self,
            prompt: str,
            generation_type: GenerationType = GenerationType.QUESTION_ANSWER,
            model: Optional[OpenAIModel] = None,
            max_tokens: Optional[int] = None,
            temperature: Optional[float] = None,
            system_prompt: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """
        Генерация текста в streaming режиме.

        Args:
            prompt: Основной промпт
            generation_type: Тип генерации
            model: Модель
            max_tokens: Максимум токенов
            temperature: Температура
            system_prompt: Кастомный системный промпт

        Yields:
            Части сгенерированного текста
        """
        # Подготовка параметров (аналогично generate)
        max_tokens = max_tokens or self.max_tokens
        temperature = temperature or self.temperature

        if not system_prompt:
            system_prompt = self._build_system_prompt(generation_type)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]

        # Выбор модели
        if not model:
            estimated_tokens = self.count_tokens(system_prompt + prompt)
            model = self._select_model(generation_type, estimated_tokens)

        # Streaming запрос
        session = await self._get_session()

        async with session.post(
                f"{self.base_url}/chat/completions",
                headers=self._get_headers(),
                json={
                    "model": model,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "stream": True
                }
        ) as response:
            async for line in response.content:
                line = line.decode('utf-8').strip()
                if line and line.startswith("data: "):
                    data = line[6:]  # Убираем "data: "

                    if data == "[DONE]":
                        break

                    try:
                        chunk = json.loads(data)
                        if "choices" in chunk and chunk["choices"]:
                            delta = chunk["choices"][0].get("delta", {})
                            if "content" in delta:
                                yield delta["content"]
                    except json.JSONDecodeError:
                        continue

    # Специализированные методы для Таро

    async def interpret_tarot_reading(
            self,
            cards: List[Dict[str, Any]],
            spread_type: str,
            question: Optional[str] = None,
            user_data: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Интерпретация расклада Таро.

        Args:
            cards: Список карт с позициями
            spread_type: Тип расклада
            question: Вопрос пользователя
            user_data: Данные о пользователе

        Returns:
            Интерпретация расклада
        """
        # Формирование промпта
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

        prompt += "\nСоздай глубокую, персонализированную интерпретацию, объясняя:\n"
        prompt += "1. Общий смысл расклада\n"
        prompt += "2. Значение каждой карты в её позиции\n"
        prompt += "3. Взаимосвязи между картами\n"
        prompt += "4. Практические советы\n"
        prompt += "5. Заключение и ключевое послание"

        # Генерация
        result = await self.generate(
            prompt=prompt,
            generation_type=GenerationType.TAROT_INTERPRETATION,
            user_context=user_data,
            temperature=0.8  # Больше креативности для интерпретаций
        )

        return result["content"]

    # Специализированные методы для астрологии

    async def analyze_natal_chart(
            self,
            chart_data: Dict[str, Any],
            focus_areas: Optional[List[str]] = None
    ) -> str:
        """
        Анализ натальной карты.

        Args:
            chart_data: Данные натальной карты
            focus_areas: Области для фокуса (карьера, любовь и т.д.)

        Returns:
            Анализ натальной карты
        """
        # Формирование промпта с астрологическими данными
        prompt = "Проанализируй натальную карту:\n\n"

        # Основные показатели
        prompt += f"Солнце: {chart_data.get('sun', 'неизвестно')}\n"
        prompt += f"Луна: {chart_data.get('moon', 'неизвестно')}\n"
        prompt += f"Асцендент: {chart_data.get('ascendant', 'неизвестно')}\n\n"

        # Планеты в знаках
        if "planets" in chart_data:
            prompt += "Планеты:\n"
            for planet, position in chart_data["planets"].items():
                prompt += f"{planet}: {position}\n"
            prompt += "\n"

        # Дома
        if "houses" in chart_data:
            prompt += "Дома:\n"
            for house, info in chart_data["houses"].items():
                prompt += f"{house}: {info}\n"
            prompt += "\n"

        # Аспекты
        if "aspects" in chart_data:
            prompt += "Ключевые аспекты:\n"
            for aspect in chart_data["aspects"][:10]:  # Топ-10 аспектов
                prompt += f"{aspect}\n"
            prompt += "\n"

        # Фокус анализа
        if focus_areas:
            prompt += f"Обрати особое внимание на: {', '.join(focus_areas)}\n\n"

        prompt += "Создай подробный анализ, включая:\n"
        prompt += "1. Общий психологический портрет\n"
        prompt += "2. Сильные стороны и таланты\n"
        prompt += "3. Зоны роста и вызовы\n"
        prompt += "4. Кармические задачи\n"
        prompt += "5. Рекомендации для развития"

        # Генерация с GPT-4 для сложного анализа
        result = await self.generate(
            prompt=prompt,
            generation_type=GenerationType.NATAL_CHART_ANALYSIS,
            model=OpenAIModel.GPT4,
            max_tokens=3000
        )

        return result["content"]

    async def generate_daily_horoscope(
            self,
            sign: str,
            transits: List[str],
            natal_data: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Генерация персонального дневного гороскопа.

        Args:
            sign: Знак зодиака
            transits: Текущие транзиты
            natal_data: Данные натальной карты

        Returns:
            Дневной гороскоп
        """
        prompt = f"Создай персональный гороскоп для {sign} на сегодня.\n\n"

        prompt += "Текущие транзиты:\n"
        for transit in transits:
            prompt += f"- {transit}\n"
        prompt += "\n"

        if natal_data:
            prompt += "Учти особенности натальной карты:\n"
            prompt += f"- Солнце: {natal_data.get('sun', sign)}\n"
            prompt += f"- Луна: {natal_data.get('moon', 'неизвестно')}\n"
            prompt += f"- Асцендент: {natal_data.get('ascendant', 'неизвестно')}\n\n"

        prompt += "Гороскоп должен включать:\n"
        prompt += "- Общую энергетику дня\n"
        prompt += "- Сферы любви и отношений\n"
        prompt += "- Карьеру и финансы\n"
        prompt += "- Здоровье и самочувствие\n"
        prompt += "- Удачные часы и цвета\n"
        prompt += "- Совет дня"

        result = await self.generate(
            prompt=prompt,
            generation_type=GenerationType.DAILY_HOROSCOPE,
            temperature=0.9,  # Больше вариативности
            max_tokens=1000
        )

        return result["content"]

    # Статистика и отчеты

    def get_usage_statistics(self) -> Dict[str, Any]:
        """
        Получение статистики использования.

        Returns:
            Словарь со статистикой
        """
        stats = self.get_metrics()
        stats["openai_usage"] = {
            "total_tokens": self.total_tokens_used,
            "total_cost_usd": round(self.total_cost, 2),
            "average_tokens_per_request": (
                    self.total_tokens_used / max(self._request_count, 1)
            )
        }

        return stats