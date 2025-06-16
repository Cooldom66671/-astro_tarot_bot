"""
Модуль для работы с внешними API.

Этот модуль предоставляет:
- Унифицированный доступ ко всем LLM провайдерам
- Клиенты для платежных систем
- Клиенты для геолокации и астрологических данных
- Вспомогательные функции для быстрого доступа
"""

from typing import Optional, Dict, Any, List

from config import logger

# Базовый клиент
from infrastructure.external_apis.base import (
    BaseAPIClient,
    RequestMethod,
    CircuitState
)

# LLM провайдеры
from infrastructure.external_apis.openai_client import (
    OpenAIClient,
    OpenAIModel,
    GenerationType
)

from infrastructure.external_apis.anthropic_client import (
    AnthropicClient,
    ClaudeModel
)

from infrastructure.external_apis.llm_manager import (
    LLMManager,
    LLMProvider,
    LLMRequest,
    LLMResponse,
    TaskPriority,
    llm_manager,
    generate_text
)

# Экспорт основных компонентов
__all__ = [
    # Базовый клиент
    'BaseAPIClient',
    'RequestMethod',
    'CircuitState',

    # OpenAI
    'OpenAIClient',
    'OpenAIModel',
    'GenerationType',

    # Anthropic
    'AnthropicClient',
    'ClaudeModel',

    # LLM Manager
    'LLMManager',
    'LLMProvider',
    'LLMRequest',
    'LLMResponse',
    'TaskPriority',
    'llm_manager',

    # Быстрые функции
    'generate_text',
    'interpret_tarot_cards',
    'analyze_birth_chart',
    'generate_daily_horoscope',
    'answer_question',

    # Утилиты
    'check_api_health',
    'get_api_statistics',
    'estimate_generation_cost'
]


# Вспомогательные функции для быстрого доступа

async def interpret_tarot_cards(
        cards: List[Dict[str, Any]],
        spread_type: str,
        question: Optional[str] = None,
        user_name: Optional[str] = None,
        user_sign: Optional[str] = None
) -> str:
    """
    Быстрая интерпретация карт Таро.

    Args:
        cards: Список выпавших карт
        spread_type: Тип расклада
        question: Вопрос пользователя
        user_name: Имя пользователя
        user_sign: Знак зодиака пользователя

    Returns:
        Интерпретация расклада
    """
    user_data = {}
    if user_name:
        user_data["name"] = user_name
    if user_sign:
        user_data["zodiac_sign"] = user_sign

    try:
        interpretation = await llm_manager.interpret_tarot(
            cards=cards,
            spread_type=spread_type,
            question=question,
            user_data=user_data if user_data else None,
            priority=TaskPriority.MEDIUM
        )

        logger.info(f"Интерпретация расклада '{spread_type}' успешно сгенерирована")
        return interpretation

    except Exception as e:
        logger.error(f"Ошибка интерпретации Таро: {e}")
        # Fallback на простой ответ
        return _generate_fallback_tarot_interpretation(cards, spread_type, question)


async def analyze_birth_chart(
        sun_sign: str,
        moon_sign: Optional[str] = None,
        ascendant: Optional[str] = None,
        planets: Optional[Dict[str, str]] = None,
        houses: Optional[Dict[str, Any]] = None,
        aspects: Optional[List[str]] = None,
        focus_areas: Optional[List[str]] = None
) -> str:
    """
    Быстрый анализ натальной карты.

    Args:
        sun_sign: Солнечный знак
        moon_sign: Лунный знак
        ascendant: Асцендент
        planets: Планеты в знаках
        houses: Дома
        aspects: Аспекты
        focus_areas: Области фокуса

    Returns:
        Анализ натальной карты
    """
    # Формируем данные карты
    chart_data = {
        "sun": sun_sign,
        "moon": moon_sign or "неизвестно",
        "ascendant": ascendant or "неизвестно"
    }

    if planets:
        chart_data["planets"] = planets
    if houses:
        chart_data["houses"] = houses
    if aspects:
        chart_data["aspects"] = aspects

    try:
        analysis = await llm_manager.analyze_natal_chart(
            chart_data=chart_data,
            focus_areas=focus_areas,
            analysis_depth="detailed"
        )

        logger.info("Анализ натальной карты успешно сгенерирован")
        return analysis

    except Exception as e:
        logger.error(f"Ошибка анализа натальной карты: {e}")
        # Fallback на базовый анализ
        return _generate_fallback_chart_analysis(sun_sign, moon_sign, ascendant)


async def generate_daily_horoscope(
        zodiac_sign: str,
        personal_data: Optional[Dict[str, Any]] = None,
        current_transits: Optional[List[str]] = None
) -> str:
    """
    Генерация персонального дневного гороскопа.

    Args:
        zodiac_sign: Знак зодиака
        personal_data: Персональные данные (луна, асцендент)
        current_transits: Текущие транзиты

    Returns:
        Дневной гороскоп
    """
    prompt = f"Создай персональный гороскоп для {zodiac_sign} на сегодня.\n\n"

    if current_transits:
        prompt += "Учти текущие транзиты:\n"
        for transit in current_transits:
            prompt += f"- {transit}\n"
        prompt += "\n"

    context = {"zodiac_sign": zodiac_sign}
    if personal_data:
        context.update(personal_data)

    try:
        horoscope = await generate_text(
            prompt=prompt,
            generation_type=GenerationType.DAILY_HOROSCOPE,
            user_context=context,
            temperature=0.9,
            max_tokens=800,
            cache_ttl=3600  # 1 час для гороскопов
        )

        logger.info(f"Гороскоп для {zodiac_sign} сгенерирован")
        return horoscope

    except Exception as e:
        logger.error(f"Ошибка генерации гороскопа: {e}")
        return _generate_fallback_horoscope(zodiac_sign)


async def answer_question(
        question: str,
        context: Optional[str] = None,
        user_data: Optional[Dict[str, Any]] = None,
        use_tarot: bool = False,
        use_astrology: bool = False
) -> str:
    """
    Ответ на вопрос пользователя.

    Args:
        question: Вопрос
        context: Дополнительный контекст
        user_data: Данные пользователя
        use_tarot: Использовать символизм Таро
        use_astrology: Использовать астрологию

    Returns:
        Ответ на вопрос
    """
    prompt = question

    if context:
        prompt = f"{context}\n\nВопрос: {question}"

    # Добавляем указания по использованию систем
    system_additions = []
    if use_tarot:
        system_additions.append("Используй символизм и мудрость Таро")
    if use_astrology:
        system_additions.append("Примени астрологические знания")

    system_prompt = None
    if system_additions:
        system_prompt = "Ты эзотерический консультант. " + ". ".join(system_additions) + "."

    try:
        answer = await generate_text(
            prompt=prompt,
            generation_type=GenerationType.QUESTION_ANSWER,
            system_prompt=system_prompt,
            user_context=user_data,
            temperature=0.8,
            priority=TaskPriority.MEDIUM
        )

        return answer

    except Exception as e:
        logger.error(f"Ошибка ответа на вопрос: {e}")
        return "Извините, сейчас я не могу ответить на ваш вопрос. Попробуйте переформулировать или задать другой вопрос."


# Утилиты для мониторинга

async def check_api_health() -> Dict[str, Any]:
    """
    Проверка здоровья всех API.

    Returns:
        Статус всех внешних API
    """
    health_report = {
        "timestamp": datetime.utcnow().isoformat(),
        "llm_providers": {},
        "other_apis": {}
    }

    # Проверка LLM провайдеров
    llm_stats = llm_manager.get_statistics()
    for provider, stats in llm_stats["providers"].items():
        health_report["llm_providers"][provider] = {
            "available": stats["is_available"],
            "error_rate": stats["error_rate"],
            "average_latency": stats["average_latency"]
        }

    # Здесь можно добавить проверку других API
    # (платежные системы, геолокация и т.д.)

    return health_report


def get_api_statistics() -> Dict[str, Any]:
    """
    Получение статистики использования всех API.

    Returns:
        Статистика по всем API
    """
    stats = {
        "llm": llm_manager.get_statistics(),
        "cache_effectiveness": {
            "hit_rate": llm_manager.cache_hits / max(llm_manager.total_requests, 1),
            "total_cached": llm_manager.cache_hits
        }
    }

    # Добавляем статистику отдельных провайдеров если доступны
    for provider_name, provider in llm_manager.providers.items():
        if hasattr(provider, 'get_usage_statistics'):
            stats[f"{provider_name}_detailed"] = provider.get_usage_statistics()

    return stats


async def estimate_generation_cost(
        text_length: int,
        generation_type: GenerationType,
        provider: Optional[LLMProvider] = None
) -> Dict[str, float]:
    """
    Оценка стоимости генерации.

    Args:
        text_length: Примерная длина текста
        generation_type: Тип генерации
        provider: Конкретный провайдер

    Returns:
        Оценка стоимости для разных провайдеров
    """
    # Примерная оценка токенов
    estimated_tokens = text_length // 4  # ~4 символа на токен

    costs = {}

    # OpenAI
    if not provider or provider == LLMProvider.OPENAI:
        # Выбираем модель по типу генерации
        if generation_type in [GenerationType.NATAL_CHART_ANALYSIS, GenerationType.SYNASTRY_ANALYSIS]:
            # GPT-4 для сложных задач
            input_cost = 0.03  # $0.03 per 1K tokens
            output_cost = 0.06  # $0.06 per 1K tokens
        else:
            # GPT-3.5 для простых
            input_cost = 0.0005
            output_cost = 0.0015

        costs["openai"] = {
            "estimated_cost_usd": (estimated_tokens / 1000) * (input_cost + output_cost),
            "model": "gpt-4" if input_cost > 0.01 else "gpt-3.5-turbo"
        }

    # Anthropic (относительная оценка)
    if not provider or provider == LLMProvider.ANTHROPIC:
        # Claude обычно дороже GPT-3.5, но дешевле GPT-4
        base_cost = 0.002  # Примерная средняя стоимость
        costs["anthropic"] = {
            "estimated_cost_usd": (estimated_tokens / 1000) * base_cost * 2,
            "model": "claude-3-sonnet"
        }

    return costs


# Fallback функции для отказоустойчивости

def _generate_fallback_tarot_interpretation(
        cards: List[Dict[str, Any]],
        spread_type: str,
        question: Optional[str]
) -> str:
    """Базовая интерпретация при недоступности LLM."""
    interpretation = f"Расклад '{spread_type}'"
    if question:
        interpretation += f" на вопрос: {question}\n\n"
    else:
        interpretation += "\n\n"

    interpretation += "Выпавшие карты:\n"
    for i, card in enumerate(cards, 1):
        card_name = card.get("card_name", "Неизвестная карта")
        is_reversed = card.get("is_reversed", False)
        interpretation += f"{i}. {card_name} ({'перевернутая' if is_reversed else 'прямая'})\n"

    interpretation += "\nК сожалению, подробная интерпретация временно недоступна. "
    interpretation += "Пожалуйста, попробуйте позже или обратитесь к администратору."

    return interpretation


def _generate_fallback_chart_analysis(
        sun_sign: str,
        moon_sign: Optional[str],
        ascendant: Optional[str]
) -> str:
    """Базовый анализ карты при недоступности LLM."""
    analysis = f"Базовый анализ натальной карты:\n\n"
    analysis += f"Солнце в {sun_sign} - это ваш основной знак, определяющий "
    analysis += "ядро личности, жизненную энергию и путь самореализации.\n\n"

    if moon_sign:
        analysis += f"Луна в {moon_sign} - отвечает за эмоциональную природу, "
        analysis += "подсознание и внутренний мир.\n\n"

    if ascendant:
        analysis += f"Асцендент в {ascendant} - показывает, как вы проявляете "
        analysis += "себя в мире и как вас воспринимают окружающие.\n\n"

    analysis += "Для получения подробного анализа попробуйте позже."

    return analysis


def _generate_fallback_horoscope(zodiac_sign: str) -> str:
    """Базовый гороскоп при недоступности LLM."""
    return (
        f"Гороскоп для {zodiac_sign} на сегодня:\n\n"
        f"Сегодня благоприятный день для {zodiac_sign}. "
        "Звезды советуют прислушаться к своей интуиции и "
        "не бояться новых начинаний. Будьте внимательны к знакам судьбы.\n\n"
        "Для получения персонального гороскопа попробуйте позже."
    )


# Инициализация при импорте
logger.info("Модуль external_apis инициализирован")

# Проверка доступности провайдеров при старте
try:
    from datetime import datetime

    available_providers = []
    for provider in LLMProvider:
        if provider in llm_manager.providers:
            available_providers.append(provider.value)

    if available_providers:
        logger.info(f"Доступные LLM провайдеры: {', '.join(available_providers)}")
    else:
        logger.warning("Нет доступных LLM провайдеров!")

except Exception as e:
    logger.error(f"Ошибка инициализации external_apis: {e}")