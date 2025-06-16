"""
Клиент для работы с Anthropic Claude API.

Этот модуль содержит:
- Интеграцию с Claude для генерации текста
- Поддержку больших контекстов (до 100K токенов)
- Fallback стратегию для OpenAI
- Специализацию на глубоком анализе
- Адаптированные промпты для эзотерики
"""

import json
from typing import Optional, Dict, Any, List, AsyncGenerator
from datetime import datetime
from enum import Enum

from config import logger, settings
from infrastructure.external_apis.base import BaseAPIClient
from core.exceptions import (
    ExternalAPIError, ValidationError,
    TokenLimitExceededError
)


class ClaudeModel(str, Enum):
    """Доступные модели Claude."""
    CLAUDE_3_OPUS = "claude-3-opus-20240229"
    CLAUDE_3_SONNET = "claude-3-sonnet-20240229"
    CLAUDE_3_HAIKU = "claude-3-haiku-20240307"
    CLAUDE_2_1 = "claude-2.1"
    CLAUDE_2 = "claude-2.0"
    CLAUDE_INSTANT = "claude-instant-1.2"


class AnthropicClient(BaseAPIClient):
    """
    Клиент для работы с Anthropic Claude API.

    Оптимизирован для глубокого анализа и работы с большими контекстами.
    """

    # Лимиты токенов для моделей
    MODEL_LIMITS = {
        ClaudeModel.CLAUDE_3_OPUS: 200000,
        ClaudeModel.CLAUDE_3_SONNET: 200000,
        ClaudeModel.CLAUDE_3_HAIKU: 200000,
        ClaudeModel.CLAUDE_2_1: 100000,
        ClaudeModel.CLAUDE_2: 100000,
        ClaudeModel.CLAUDE_INSTANT: 100000
    }

    # Относительная стоимость моделей (условные единицы)
    MODEL_COSTS = {
        ClaudeModel.CLAUDE_3_OPUS: 3.0,
        ClaudeModel.CLAUDE_3_SONNET: 1.0,
        ClaudeModel.CLAUDE_3_HAIKU: 0.25,
        ClaudeModel.CLAUDE_2_1: 0.8,
        ClaudeModel.CLAUDE_2: 0.8,
        ClaudeModel.CLAUDE_INSTANT: 0.1
    }

    def __init__(
            self,
            api_key: Optional[str] = None,
            default_model: ClaudeModel = ClaudeModel.CLAUDE_3_SONNET,
            max_tokens: int = 4000,
            temperature: float = 0.7
    ):
        """
        Инициализация Anthropic клиента.

        Args:
            api_key: API ключ Anthropic
            default_model: Модель по умолчанию
            max_tokens: Максимум токенов в ответе
            temperature: Температура генерации
        """
        api_key = api_key or settings.anthropic.api_key
        if not api_key:
            raise ValidationError("Anthropic API key не указан")

        super().__init__(
            base_url="https://api.anthropic.com/v1",
            api_key=api_key,
            timeout=120,  # Больше таймаут для больших контекстов
            max_retries=3,
            rate_limit_calls=settings.anthropic.rate_limit_calls,
            rate_limit_period=60,
            cache_ttl=settings.anthropic.cache_ttl
        )

        self.default_model = default_model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.anthropic_version = "2023-06-01"

        # Статистика
        self.total_tokens_used = 0
        self.total_requests = 0

        logger.info(f"Anthropic клиент инициализирован с моделью {default_model}")

    def _get_headers(self) -> Dict[str, str]:
        """Получение заголовков для Anthropic API."""
        return {
            "x-api-key": self.api_key,
            "anthropic-version": self.anthropic_version,
            "Content-Type": "application/json"
        }

    def _estimate_tokens(self, text: str) -> int:
        """
        Примерная оценка токенов.

        Claude использует другой токенизатор, поэтому делаем приблизительную оценку.

        Args:
            text: Текст для оценки

        Returns:
            Примерное количество токенов
        """
        # Примерная оценка: 1 токен ≈ 4 символа
        return len(text) // 4

    def _select_model(
            self,
            task_complexity: str,
            estimated_tokens: int,
            require_latest: bool = False
    ) -> ClaudeModel:
        """
        Выбор оптимальной модели.

        Args:
            task_complexity: Сложность задачи (low, medium, high)
            estimated_tokens: Примерное количество токенов
            require_latest: Требуется ли последняя модель

        Returns:
            Оптимальная модель
        """
        # Для последних возможностей используем Claude 3
        if require_latest:
            if task_complexity == "high":
                return ClaudeModel.CLAUDE_3_OPUS
            elif task_complexity == "medium":
                return ClaudeModel.CLAUDE_3_SONNET
            else:
                return ClaudeModel.CLAUDE_3_HAIKU

        # Для больших контекстов
        if estimated_tokens > 50000:
            return ClaudeModel.CLAUDE_2_1

        # По сложности задачи
        if task_complexity == "high":
            return ClaudeModel.CLAUDE_3_SONNET
        elif task_complexity == "low":
            return ClaudeModel.CLAUDE_INSTANT
        else:
            return self.default_model

    def _build_system_prompt_for_claude(self, generation_type: str) -> str:
        """
        Адаптированные промпты для Claude.

        Claude лучше работает с четкими инструкциями и структурой.

        Args:
            generation_type: Тип генерации

        Returns:
            Системный промпт
        """
        prompts = {
            "tarot_analysis": """Ты - эксперт-таролог с глубоким пониманием символизма и психологии карт Таро.

ТВОИ ПРИНЦИПЫ:
1. Анализируй карты как психологические архетипы
2. Учитывай взаимное влияние карт в раскладе
3. Связывай символизм с конкретной жизненной ситуацией
4. Давай практические, применимые советы
5. Избегай фатализма - подчеркивай свободу выбора

СТРУКТУРА ОТВЕТА:
- Общее впечатление от расклада
- Детальный анализ каждой позиции
- Синтез и взаимосвязи
- Практические рекомендации
- Ключевое послание""",

            "astro_deep_analysis": """Ты - профессиональный астролог-аналитик, специализирующийся на глубинной психологической астрологии.

МЕТОДОЛОГИЯ:
1. Используй целостный подход к анализу карты
2. Выявляй ключевые конфигурации и паттерны
3. Интерпретируй в контексте эволюции личности
4. Учитывай кармические и эволюционные аспекты
5. Предлагай пути трансформации и роста

ФОКУС АНАЛИЗА:
- Ядро личности (Солнце, Луна, Асцендент)
- Доминирующие энергии и стихии
- Ключевые аспектные конфигурации
- Кармические узлы и точки трансформации
- Потенциал развития""",

            "synastry_compatibility": """Ты - специалист по синастрической астрологии и анализу отношений.

ПОДХОД К АНАЛИЗУ:
1. Рассматривай обе карты как равноценные
2. Анализируй энергетический обмен между картами
3. Выявляй точки гармонии и напряжения
4. Предлагай пути гармонизации
5. Учитывай разные типы отношений

СТРУКТУРА АНАЛИЗА:
- Общая энергетическая совместимость
- Эмоциональная связь (Луна, Венера)
- Ментальное взаимодействие (Меркурий, Уран)
- Сексуальная химия (Марс, Плутон)
- Кармические связи (узлы, Сатурн)
- Потенциал роста в отношениях""",

            "esoteric_counseling": """Ты - мудрый эзотерический консультант с глубокими знаниями различных духовных традиций.

ТВОЙ ПОДХОД:
1. Синтезируй мудрость разных традиций
2. Адаптируй ответ к уровню понимания человека
3. Балансируй между духовным и практическим
4. Поддерживай и вдохновляй
5. Способствуй самопознанию

ВАЖНО:
- Не давай медицинских советов
- Не предсказывай конкретные события
- Поощряй личную ответственность
- Уважай свободу выбора"""
        }

        return prompts.get(generation_type, prompts["esoteric_counseling"])

    async def generate(
            self,
            prompt: str,
            system_prompt: Optional[str] = None,
            generation_type: str = "general",
            model: Optional[ClaudeModel] = None,
            max_tokens: Optional[int] = None,
            temperature: Optional[float] = None,
            context_data: Optional[Dict[str, Any]] = None,
            previous_messages: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """
        Генерация текста через Claude API.

        Args:
            prompt: Основной промпт
            system_prompt: Системный промпт
            generation_type: Тип генерации
            model: Модель Claude
            max_tokens: Максимум токенов
            temperature: Температура
            context_data: Дополнительный контекст
            previous_messages: История сообщений

        Returns:
            Результат генерации
        """
        # Подготовка параметров
        max_tokens = max_tokens or self.max_tokens
        temperature = temperature or self.temperature

        # Системный промпт
        if not system_prompt:
            system_prompt = self._build_system_prompt_for_claude(generation_type)

        # Добавляем контекст
        if context_data:
            context_str = "\n\nКОНТЕКСТ:\n"
            for key, value in context_data.items():
                context_str += f"{key}: {value}\n"
            system_prompt += context_str

        # Выбор модели
        if not model:
            estimated_tokens = self._estimate_tokens(prompt + system_prompt)
            task_complexity = self._determine_task_complexity(generation_type)
            model = self._select_model(task_complexity, estimated_tokens)

        # Проверка лимитов
        model_limit = self.MODEL_LIMITS.get(model, 100000)
        estimated_total = self._estimate_tokens(prompt + system_prompt) + max_tokens
        if estimated_total > model_limit:
            raise TokenLimitExceededError(
                f"Превышен лимит токенов для {model}: {estimated_total} > {model_limit}"
            )

        # Подготовка сообщений
        messages = []

        # Добавляем историю если есть
        if previous_messages:
            messages.extend(previous_messages)

        # Добавляем текущий запрос
        messages.append({"role": "user", "content": prompt})

        # Запрос к API
        logger.info(f"Claude генерация: {generation_type} с моделью {model}")

        try:
            response = await self.post(
                "/messages",
                json_data={
                    "model": model,
                    "messages": messages,
                    "system": system_prompt,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "top_p": 0.9,
                    "top_k": 40
                }
            )

            # Обработка ответа
            content = response["content"][0]["text"]
            usage = response.get("usage", {})

            # Обновление статистики
            input_tokens = usage.get("input_tokens", 0)
            output_tokens = usage.get("output_tokens", 0)
            self.total_tokens_used += input_tokens + output_tokens
            self.total_requests += 1

            result = {
                "content": content,
                "model": model,
                "generation_type": generation_type,
                "usage": {
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "total_tokens": input_tokens + output_tokens
                },
                "stop_reason": response.get("stop_reason", "stop_sequence"),
                "model_cost_units": self.MODEL_COSTS.get(model, 1.0)
            }

            logger.info(
                f"Claude ответ получен: {input_tokens + output_tokens} токенов"
            )

            return result

        except Exception as e:
            logger.error(f"Ошибка Claude API: {e}")
            raise ExternalAPIError(
                f"Ошибка генерации текста Claude: {str(e)}",
                service_name="Anthropic"
            )

    def _determine_task_complexity(self, generation_type: str) -> str:
        """Определение сложности задачи."""
        high_complexity = [
            "astro_deep_analysis",
            "synastry_compatibility",
            "natal_full_report"
        ]

        low_complexity = [
            "daily_card",
            "simple_question",
            "affirmation"
        ]

        if generation_type in high_complexity:
            return "high"
        elif generation_type in low_complexity:
            return "low"
        else:
            return "medium"

    # Специализированные методы для эзотерики

    async def analyze_birth_chart_comprehensive(
            self,
            chart_data: Dict[str, Any],
            birth_info: Dict[str, Any],
            analysis_depth: str = "detailed"
    ) -> str:
        """
        Комплексный анализ натальной карты.

        Claude особенно хорош для глубокого анализа больших объемов данных.

        Args:
            chart_data: Полные данные натальной карты
            birth_info: Информация о рождении
            analysis_depth: Глубина анализа (basic, detailed, comprehensive)

        Returns:
            Детальный анализ
        """
        # Формируем структурированный промпт
        prompt = f"""Проведи {analysis_depth} анализ натальной карты.

ДАННЫЕ РОЖДЕНИЯ:
Дата: {birth_info.get('date')}
Время: {birth_info.get('time')}
Место: {birth_info.get('place')}
Координаты: {birth_info.get('lat')}, {birth_info.get('lon')}

ПЛАНЕТЫ В ЗНАКАХ:
"""
        # Добавляем планеты
        for planet, data in chart_data.get("planets", {}).items():
            prompt += f"{planet}: {data['sign']} {data['degree']}° "
            if data.get('retrograde'):
                prompt += "(R) "
            prompt += f"в {data['house']} доме\n"

        prompt += "\nАСПЕКТЫ:\n"
        # Добавляем аспекты
        for aspect in chart_data.get("aspects", [])[:20]:
            prompt += f"{aspect['planet1']} {aspect['type']} {aspect['planet2']} "
            prompt += f"(орб {aspect['orb']}°)\n"

        prompt += "\nДОМА:\n"
        # Добавляем дома
        for i in range(1, 13):
            house_data = chart_data.get("houses", {}).get(str(i), {})
            prompt += f"{i} дом: {house_data.get('sign', '?')} "
            prompt += f"{house_data.get('degree', '?')}°"
            if house_data.get('planets'):
                prompt += f" ({', '.join(house_data['planets'])})"
            prompt += "\n"

        # Дополнительные указания в зависимости от глубины
        if analysis_depth == "comprehensive":
            prompt += """
ПРОВЕДИ АНАЛИЗ ПО СЛЕДУЮЩИМ УРОВНЯМ:

1. ПСИХОЛОГИЧЕСКИЙ ПОРТРЕТ
- Ядро личности (светила и углы)
- Темперамент и эмоциональная природа
- Ментальные особенности
- Мотивация и драйв

2. КАРМИЧЕСКИЙ АНАЛИЗ
- Лунные узлы
- Ретроградные планеты
- Кармические аспекты
- Эволюционная задача души

3. ПОТЕНЦИАЛ РАЗВИТИЯ
- Таланты и способности
- Профессиональное предназначение
- Сферы максимальной реализации
- Духовный путь

4. ПРОГНОСТИЧЕСКИЙ ОБЗОР
- Текущие циклы развития
- Ближайшие важные транзиты
- Периоды трансформации

5. ПРАКТИЧЕСКИЕ РЕКОМЕНДАЦИИ
- Как работать со сложными аспектами
- Методы гармонизации энергий
- Благоприятные практики и техники
"""

        # Генерация с максимальной моделью для глубокого анализа
        model = ClaudeModel.CLAUDE_3_OPUS if analysis_depth == "comprehensive" else None

        result = await self.generate(
            prompt=prompt,
            generation_type="astro_deep_analysis",
            model=model,
            max_tokens=4000 if analysis_depth == "comprehensive" else 2000,
            temperature=0.7
        )

        return result["content"]

    async def analyze_relationship_synastry(
            self,
            person1_chart: Dict[str, Any],
            person2_chart: Dict[str, Any],
            relationship_type: str = "romantic"
    ) -> str:
        """
        Анализ синастрии (совместимости) двух карт.

        Args:
            person1_chart: Данные первой карты
            person2_chart: Данные второй карты
            relationship_type: Тип отношений (romantic, business, friendship)

        Returns:
            Анализ совместимости
        """
        prompt = f"""Проанализируй синастрию для {relationship_type} отношений.

ПЕРСОНА 1:
Солнце: {person1_chart.get('sun')}
Луна: {person1_chart.get('moon')}
Венера: {person1_chart.get('venus')}
Марс: {person1_chart.get('mars')}
Асцендент: {person1_chart.get('asc')}

ПЕРСОНА 2:
Солнце: {person2_chart.get('sun')}
Луна: {person2_chart.get('moon')}  
Венера: {person2_chart.get('venus')}
Марс: {person2_chart.get('mars')}
Асцендент: {person2_chart.get('asc')}

СИНАСТРИЧЕСКИЕ АСПЕКТЫ:
"""

        # Добавляем межкартные аспекты
        synastry_aspects = self._calculate_synastry_aspects(person1_chart, person2_chart)
        for aspect in synastry_aspects[:30]:  # Топ-30 аспектов
            prompt += f"{aspect}\n"

        # Специфика для типа отношений
        if relationship_type == "romantic":
            prompt += """
Обрати особое внимание на:
- Эмоциональную совместимость (Луна-Луна, Луна-Венера)
- Романтическое притяжение (Венера-Марс, Солнце-Луна)
- Сексуальную химию (Марс-Марс, Марс-Плутон)
- Долгосрочный потенциал (Сатурн аспекты)
- Кармические связи (узлы, Плутон)
"""
        elif relationship_type == "business":
            prompt += """
Фокус на:
- Деловую совместимость (Меркурий, Сатурн)
- Общие цели (Солнце, Юпитер)
- Практичность (земные знаки)
- Коммуникацию (Меркурий аспекты)
"""

        result = await self.generate(
            prompt=prompt,
            generation_type="synastry_compatibility",
            max_tokens=3000,
            temperature=0.7
        )

        return result["content"]

    def _calculate_synastry_aspects(
            self,
            chart1: Dict[str, Any],
            chart2: Dict[str, Any]
    ) -> List[str]:
        """Упрощенный расчет синастрических аспектов."""
        # В реальной реализации здесь будет сложная астрологическая логика
        # Пока возвращаем заглушку
        return [
            "П1 Солнце соединение П2 Луна (орб 2°)",
            "П1 Венера трин П2 Марс (орб 3°)",
            "П1 Луна квадрат П2 Сатурн (орб 1°)",
            # ... другие аспекты
        ]

    async def create_tarot_synthesis(
            self,
            readings_history: List[Dict[str, Any]],
            time_period: str = "month"
    ) -> str:
        """
        Создание синтеза из истории раскладов.

        Claude хорошо работает с большими контекстами и может
        проанализировать паттерны в серии раскладов.

        Args:
            readings_history: История раскладов
            time_period: Период анализа

        Returns:
            Синтезированный анализ
        """
        prompt = f"Проанализируй серию раскладов Таро за {time_period} и выяви ключевые темы.\n\n"

        prompt += "ИСТОРИЯ РАСКЛАДОВ:\n\n"

        for i, reading in enumerate(readings_history, 1):
            prompt += f"Расклад {i} ({reading['date']}):\n"
            prompt += f"Вопрос: {reading.get('question', 'Общий расклад')}\n"
            prompt += f"Карты: {', '.join(reading['cards'])}\n"
            prompt += f"Ключевые темы: {reading.get('themes', 'Не указаны')}\n\n"

        prompt += """СОЗДАЙ СИНТЕЗ, ВКЛЮЧАЮЩИЙ:
1. Повторяющиеся карты и их значение
2. Эволюция тем и вопросов
3. Основные уроки периода
4. Тенденции и паттерны
5. Рекомендации на следующий период

Представь это как целостную историю развития человека."""

        result = await self.generate(
            prompt=prompt,
            generation_type="tarot_analysis",
            model=ClaudeModel.CLAUDE_3_SONNET,  # Хороший баланс для анализа
            max_tokens=2500,
            temperature=0.8
        )

        return result["content"]

    # Специальные возможности Claude

    async def analyze_complex_spread(
            self,
            spread_data: Dict[str, Any],
            additional_context: Dict[str, Any],
            analysis_style: str = "psychological"
    ) -> str:
        """
        Анализ сложных раскладов (10+ карт).

        Claude особенно хорош для анализа сложных взаимосвязей.

        Args:
            spread_data: Данные расклада
            additional_context: Дополнительный контекст
            analysis_style: Стиль анализа

        Returns:
            Глубокий анализ расклада
        """
        # Строим детальный промпт
        prompt = f"Проведи {analysis_style} анализ сложного расклада.\n\n"

        prompt += f"ТИП РАСКЛАДА: {spread_data['type']}\n"
        prompt += f"ВОПРОС: {spread_data.get('question', 'Не указан')}\n\n"

        prompt += "КАРТЫ И ПОЗИЦИИ:\n"
        for position in spread_data['positions']:
            prompt += f"{position['number']}. {position['meaning']}: "
            prompt += f"{position['card']} "
            prompt += f"({'перевернутая' if position.get('reversed') else 'прямая'})\n"

        # Добавляем контекст
        if additional_context:
            prompt += "\nДОПОЛНИТЕЛЬНЫЙ КОНТЕКСТ:\n"
            for key, value in additional_context.items():
                prompt += f"- {key}: {value}\n"

        # Стиль анализа
        style_instructions = {
            "psychological": """
Анализируй с точки зрения психологии:
- Внутренние конфликты и их разрешение
- Подсознательные мотивы
- Защитные механизмы
- Потенциал личностного роста""",

            "predictive": """
Фокус на прогностических аспектах:
- Вероятные сценарии развития
- Временные рамки
- Ключевые точки выбора
- Потенциальные препятствия""",

            "spiritual": """
Духовная перспектива:
- Уроки души
- Кармические аспекты  
- Духовные вызовы
- Путь трансформации"""
        }

        prompt += f"\n{style_instructions.get(analysis_style, '')}"

        result = await self.generate(
            prompt=prompt,
            generation_type="tarot_analysis",
            model=ClaudeModel.CLAUDE_3_SONNET,
            max_tokens=3500,
            temperature=0.75
        )

        return result["content"]

    # Статистика

    def get_usage_statistics(self) -> Dict[str, Any]:
        """Получение статистики использования."""
        stats = self.get_metrics()
        stats["anthropic_usage"] = {
            "total_tokens": self.total_tokens_used,
            "total_requests": self.total_requests,
            "average_tokens_per_request": (
                    self.total_tokens_used / max(self.total_requests, 1)
            )
        }

        return stats