"""
Сервисы бизнес-логики бота.

Этот модуль содержит сервисы для:
- Таро гаданий и интерпретаций
- Астрологических расчетов
- Обработки платежей
- Отправки уведомлений
- Управления пользователями
- Аналитики и статистики

Автор: AI Assistant
Дата создания: 2024-12-30
"""

import logging
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional, Tuple
from decimal import Decimal
import asyncio
import random
from abc import ABC, abstractmethod

from infrastructure import get_unit_of_work
from infrastructure.external_apis import get_llm_manager
from infrastructure.cache import get_cache

logger = logging.getLogger(__name__)


class BaseService(ABC):
    """Базовый класс для всех сервисов."""

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self._cache = None

    @property
    async def cache(self):
        """Ленивая инициализация кэша."""
        if self._cache is None:
            self._cache = await get_cache()
        return self._cache

    async def log_action(
            self,
            user_id: int,
            action: str,
            details: Dict[str, Any] = None
    ):
        """Логирование действий пользователя."""
        self.logger.info(
            f"User {user_id} - Action: {action} - "
            f"Details: {details or {} }"
        )


class TarotService(BaseService):
    """Сервис для работы с Таро."""

    # Константы
    TOTAL_CARDS = 78
    MAJOR_ARCANA = 22
    SUITS = ["Жезлы", "Кубки", "Мечи", "Пентакли"]
    COURT_CARDS = ["Паж", "Рыцарь", "Королева", "Король"]

    # База данных карт (упрощенная версия)
    CARDS_DB = {
        0: {
            "name": "Шут",
            "keywords": ["начало", "спонтанность", "свобода", "риск"],
            "element": "Воздух",
            "number": 0,
            "image": "fool.jpg"
        },
        1: {
            "name": "Маг",
            "keywords": ["воля", "мастерство", "действие", "проявление"],
            "element": "Воздух",
            "number": 1,
            "image": "magician.jpg"
        },
        # ... остальные карты
    }

    async def get_card_info(self, card_id: int) -> Dict[str, Any]:
        """Получить информацию о карте."""
        # Проверяем кэш
        cache_key = f"tarot:card:{card_id}"
        cached = await (await self.cache).get(cache_key)
        if cached:
            return cached

        # Получаем из БД или генерируем
        if card_id < self.MAJOR_ARCANA:
            card_info = self.CARDS_DB.get(card_id, self._generate_major_arcana(card_id))
        else:
            card_info = self._generate_minor_arcana(card_id)

        # Кэшируем
        await (await self.cache).set(cache_key, card_info, expire=3600)

        return card_info

    async def generate_daily_card(
            self,
            user_id: int,
            date: date
    ) -> Dict[str, Any]:
        """Генерировать карту дня."""
        async with get_unit_of_work() as uow:
            # Проверяем, есть ли уже карта на сегодня
            existing = await uow.tarot.get_daily_card(user_id, date)
            if existing:
                return {
                    "card_id": existing.cards[0]["id"],
                    "is_reversed": existing.cards[0]["is_reversed"],
                    "interpretation": existing.interpretation,
                    "already_exists": True
                }

            # Генерируем новую карту
            card_id = random.randint(0, self.TOTAL_CARDS - 1)
            is_reversed = random.choice([True, False])

            # Получаем интерпретацию
            card_info = await self.get_card_info(card_id)
            interpretation = await self._generate_interpretation(
                card_info,
                is_reversed,
                "daily",
                user_id
            )

            # Сохраняем
            reading = await uow.tarot.create_reading(
                user_id=user_id,
                spread_type="daily_card",
                cards=[{
                    "id": card_id,
                    "position": 1,
                    "is_reversed": is_reversed
                }],
                interpretation=interpretation
            )
            await uow.commit()

            await self.log_action(user_id, "daily_card", {
                "card_id": card_id,
                "is_reversed": is_reversed
            })

            return {
                "card_id": card_id,
                "is_reversed": is_reversed,
                "interpretation": interpretation,
                "already_exists": False
            }

    async def create_spread(
            self,
            user_id: int,
            spread_type: str,
            question: Optional[str] = None,
            selected_cards: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """Создать расклад."""
        spread_info = self._get_spread_info(spread_type)

        # Если карты не выбраны, генерируем случайные
        if not selected_cards:
            selected_cards = await self._generate_random_cards(
                spread_info["card_count"]
            )

        # Получаем интерпретацию
        interpretation = await self._generate_spread_interpretation(
            spread_type,
            selected_cards,
            question,
            user_id
        )

        # Сохраняем в БД
        async with get_unit_of_work() as uow:
            reading = await uow.tarot.create_reading(
                user_id=user_id,
                spread_type=spread_type,
                question=question,
                cards=selected_cards,
                interpretation=interpretation
            )

            # Обновляем статистику
            await uow.users.increment_tarot_count(user_id)
            await uow.commit()

            await self.log_action(user_id, "create_spread", {
                "spread_type": spread_type,
                "card_count": len(selected_cards)
            })

            return {
                "reading_id": reading.id,
                "cards": selected_cards,
                "interpretation": interpretation,
                "created_at": reading.created_at
            }

    async def get_user_statistics(self, user_id: int) -> Dict[str, Any]:
        """Получить статистику пользователя по Таро."""
        async with get_unit_of_work() as uow:
            stats = await uow.tarot.get_user_statistics(user_id)

            # Дополняем статистику
            if stats["total_spreads"] > 0:
                # Считаем средние показатели
                stats["average_cards_per_spread"] = (
                        stats.get("total_cards", 0) / stats["total_spreads"]
                )

                # Любимая масть
                suits_count = stats.get("suits_count", {})
                if suits_count:
                    favorite_suit = max(suits_count.items(), key=lambda x: x[1])
                    stats["favorite_suit"] = favorite_suit[0]

                # Баланс арканов
                major_count = stats.get("major_arcana_count", 0)
                minor_count = stats.get("minor_arcana_count", 0)
                total = major_count + minor_count
                if total > 0:
                    stats["major_arcana_percentage"] = (major_count / total) * 100

            return stats

    def _get_spread_info(self, spread_type: str) -> Dict[str, Any]:
        """Получить информацию о раскладе."""
        spreads = {
            "three_cards": {
                "name": "Три карты",
                "card_count": 3,
                "positions": ["Прошлое", "Настоящее", "Будущее"],
                "description": "Классический расклад для анализа ситуации"
            },
            "celtic_cross": {
                "name": "Кельтский крест",
                "card_count": 10,
                "positions": [
                    "Ситуация", "Вызов", "Далекое прошлое", "Недавнее прошлое",
                    "Возможное будущее", "Ближайшее будущее", "Ваш подход",
                    "Внешние влияния", "Надежды и страхи", "Итог"
                ],
                "description": "Подробный анализ ситуации"
            },
            "relationship": {
                "name": "Отношения",
                "card_count": 7,
                "positions": [
                    "Вы", "Партнер", "Основа отношений", "Прошлое отношений",
                    "Настоящее", "Будущее", "Совет"
                ],
                "description": "Анализ отношений между людьми"
            },
            "yes_no": {
                "name": "Да/Нет",
                "card_count": 1,
                "positions": ["Ответ"],
                "description": "Быстрый ответ на вопрос"
            },
            "career": {
                "name": "Карьера",
                "card_count": 5,
                "positions": [
                    "Текущая ситуация", "Препятствия", "Скрытые факторы",
                    "Совет", "Результат"
                ],
                "description": "Анализ карьерной ситуации"
            }
        }

        return spreads.get(spread_type, spreads["three_cards"])

    def _generate_major_arcana(self, card_id: int) -> Dict[str, Any]:
        """Генерировать информацию о старшем аркане."""
        # Упрощенная генерация для примера
        arcana_names = [
            "Шут", "Маг", "Верховная Жрица", "Императрица", "Император",
            "Иерофант", "Влюбленные", "Колесница", "Сила", "Отшельник",
            "Колесо Фортуны", "Справедливость", "Повешенный", "Смерть",
            "Умеренность", "Дьявол", "Башня", "Звезда", "Луна", "Солнце",
            "Суд", "Мир"
        ]

        return {
            "name": arcana_names[card_id] if card_id < len(arcana_names) else f"Аркан {card_id}",
            "keywords": ["трансформация", "путь", "урок", "мудрость"],
            "element": "Дух",
            "number": card_id,
            "type": "major"
        }

    def _generate_minor_arcana(self, card_id: int) -> Dict[str, Any]:
        """Генерировать информацию о младшем аркане."""
        # Вычисляем масть и номер
        minor_id = card_id - self.MAJOR_ARCANA
        suit_index = minor_id // 14
        card_in_suit = minor_id % 14

        suit = self.SUITS[suit_index] if suit_index < len(self.SUITS) else "Неизвестная масть"

        if card_in_suit < 10:
            name = f"{card_in_suit + 1} {suit}"
            card_type = "number"
        else:
            court_index = card_in_suit - 10
            name = f"{self.COURT_CARDS[court_index]} {suit}"
            card_type = "court"

        # Элементы мастей
        elements = {
            "Жезлы": "Огонь",
            "Кубки": "Вода",
            "Мечи": "Воздух",
            "Пентакли": "Земля"
        }

        return {
            "name": name,
            "keywords": self._get_minor_keywords(suit, card_in_suit),
            "element": elements.get(suit, "Неизвестно"),
            "number": card_in_suit + 1,
            "suit": suit,
            "type": card_type
        }

    def _get_minor_keywords(self, suit: str, number: int) -> List[str]:
        """Получить ключевые слова для младшего аркана."""
        suit_themes = {
            "Жезлы": ["действие", "энергия", "творчество", "страсть"],
            "Кубки": ["эмоции", "чувства", "интуиция", "отношения"],
            "Мечи": ["мысли", "конфликт", "решение", "ясность"],
            "Пентакли": ["материя", "работа", "деньги", "результат"]
        }

        return suit_themes.get(suit, ["энергия", "потенциал", "развитие", "опыт"])

    async def _generate_random_cards(
            self,
            count: int
    ) -> List[Dict[str, Any]]:
        """Генерировать случайные карты для расклада."""
        selected_ids = random.sample(range(self.TOTAL_CARDS), count)

        cards = []
        for i, card_id in enumerate(selected_ids):
            cards.append({
                "id": card_id,
                "position": i + 1,
                "is_reversed": random.choice([True, False])
            })

        return cards

    async def _generate_interpretation(
            self,
            card_info: Dict[str, Any],
            is_reversed: bool,
            context: str,
            user_id: int
    ) -> str:
        """Генерировать интерпретацию карты."""
        # Формируем промпт для AI
        position_text = "в перевернутом положении" if is_reversed else "в прямом положении"

        prompt = f"""
        Дай интерпретацию карты Таро для контекста '{context}':

        Карта: {card_info['name']} {position_text}
        Ключевые слова: {', '.join(card_info['keywords'])}
        Элемент: {card_info.get('element', 'Неизвестно')}

        Дай краткую интерпретацию (3-4 предложения) в позитивном ключе.
        Учитывай положение карты (прямое/перевернутое).
        """

        llm = await get_llm_manager()
        interpretation = await llm.generate_completion(
            prompt,
            temperature=0.7,
            max_tokens=200
        )

        return interpretation

    async def _generate_spread_interpretation(
            self,
            spread_type: str,
            cards: List[Dict],
            question: Optional[str],
            user_id: int
    ) -> str:
        """Генерировать интерпретацию расклада."""
        spread_info = self._get_spread_info(spread_type)

        # Получаем информацию о картах
        cards_description = []
        for card in cards:
            card_info = await self.get_card_info(card["id"])
            position_name = spread_info["positions"][card["position"] - 1]
            reversed_text = " (перевернутая)" if card["is_reversed"] else ""

            cards_description.append(
                f"{position_name}: {card_info['name']}{reversed_text}"
            )

        # Формируем промпт
        prompt = f"""
        Сделай интерпретацию расклада Таро '{spread_info['name']}':

        {"Вопрос: " + question if question else "Общий расклад"}

        Карты:
        {chr(10).join(cards_description)}

        Дай связную интерпретацию, учитывая:
        1. Значение каждой позиции в раскладе
        2. Взаимосвязи между картами
        3. Общее послание расклада

        Будь конкретным и позитивным. Дай практические советы.
        Ответ должен быть 5-7 предложений.
        """

        llm = await get_llm_manager()
        interpretation = await llm.generate_completion(
            prompt,
            temperature=0.7,
            max_tokens=400
        )

        return interpretation


class AstrologyService(BaseService):
    """Сервис для астрологических расчетов."""

    # Знаки зодиака
    ZODIAC_SIGNS = {
        "aries": {"name": "Овен", "element": "Огонь", "dates": (3, 21, 4, 19)},
        "taurus": {"name": "Телец", "element": "Земля", "dates": (4, 20, 5, 20)},
        "gemini": {"name": "Близнецы", "element": "Воздух", "dates": (5, 21, 6, 20)},
        "cancer": {"name": "Рак", "element": "Вода", "dates": (6, 21, 7, 22)},
        "leo": {"name": "Лев", "element": "Огонь", "dates": (7, 23, 8, 22)},
        "virgo": {"name": "Дева", "element": "Земля", "dates": (8, 23, 9, 22)},
        "libra": {"name": "Весы", "element": "Воздух", "dates": (9, 23, 10, 22)},
        "scorpio": {"name": "Скорпион", "element": "Вода", "dates": (10, 23, 11, 21)},
        "sagittarius": {"name": "Стрелец", "element": "Огонь", "dates": (11, 22, 12, 21)},
        "capricorn": {"name": "Козерог", "element": "Земля", "dates": (12, 22, 1, 19)},
        "aquarius": {"name": "Водолей", "element": "Воздух", "dates": (1, 20, 2, 18)},
        "pisces": {"name": "Рыбы", "element": "Вода", "dates": (2, 19, 3, 20)}
    }

    # Планеты
    PLANETS = [
        "Солнце", "Луна", "Меркурий", "Венера", "Марс",
        "Юпитер", "Сатурн", "Уран", "Нептун", "Плутон"
    ]

    # Дома
    HOUSES = [
        "Личность", "Ресурсы", "Коммуникация", "Дом и семья",
        "Творчество", "Работа и здоровье", "Партнерство", "Трансформация",
        "Философия", "Карьера", "Дружба", "Подсознание"
    ]

    async def get_zodiac_sign(self, birth_date: datetime) -> str:
        """Определить знак зодиака по дате рождения."""
        month = birth_date.month
        day = birth_date.day

        for sign_key, sign_info in self.ZODIAC_SIGNS.items():
            start_month, start_day, end_month, end_day = sign_info["dates"]

            if start_month == month and day >= start_day:
                return sign_key
            elif end_month == month and day <= end_day:
                return sign_key
            elif start_month > end_month:  # Козерог
                if month == start_month and day >= start_day:
                    return sign_key
                elif month == end_month and day <= end_day:
                    return sign_key

        return "aries"  # По умолчанию

    async def generate_horoscope(
            self,
            zodiac_sign: str,
            period_type: str,
            user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Генерировать гороскоп."""
        # Проверяем кэш
        cache_key = f"horoscope:{zodiac_sign}:{period_type}:{date.today()}"
        cached = await (await self.cache).get(cache_key)
        if cached:
            return cached

        # Получаем информацию о знаке
        sign_info = self.ZODIAC_SIGNS.get(zodiac_sign, self.ZODIAC_SIGNS["aries"])

        # Генерируем через AI
        horoscope_data = await self._generate_horoscope_content(
            zodiac_sign,
            sign_info,
            period_type
        )

        # Добавляем дополнительную информацию
        horoscope_data.update({
            "zodiac_sign": zodiac_sign,
            "sign_name": sign_info["name"],
            "element": sign_info["element"],
            "period": period_type,
            "date": date.today().isoformat(),
            "lucky_numbers": self._generate_lucky_numbers(),
            "lucky_color": self._get_lucky_color(zodiac_sign)
        })

        # Кэшируем на сутки
        await (await self.cache).set(cache_key, horoscope_data, expire=86400)

        # Сохраняем в историю если есть пользователь
        if user_id:
            async with get_unit_of_work() as uow:
                await uow.astrology.save_horoscope_view(
                    user_id=user_id,
                    zodiac_sign=zodiac_sign,
                    period_type=period_type
                )
                await uow.commit()

            await self.log_action(user_id, "view_horoscope", {
                "zodiac_sign": zodiac_sign,
                "period_type": period_type
            })

        return horoscope_data

    async def calculate_natal_chart(
            self,
            birth_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Рассчитать натальную карту."""
        # В реальной реализации здесь должны быть
        # астрологические расчеты с использованием
        # специализированных библиотек

        # Упрощенная версия для примера
        birth_date = datetime.fromisoformat(birth_data["date"])
        zodiac_sign = await self.get_zodiac_sign(birth_date)

        # Генерируем позиции планет (упрощенно)
        planets = {}
        for i, planet in enumerate(self.PLANETS):
            sign_index = (i + birth_date.month) % 12
            sign_key = list(self.ZODIAC_SIGNS.keys())[sign_index]
            degree = (birth_date.day * 12 + i * 30) % 360
            house = ((i + birth_date.hour) % 12) + 1

            planets[planet.lower()] = {
                "sign": sign_key,
                "degree": degree,
                "house": house
            }

        # Генерируем дома
        houses = {}
        for i in range(12):
            sign_index = (i + birth_date.month - 1) % 12
            sign_key = list(self.ZODIAC_SIGNS.keys())[sign_index]
            degree = i * 30

            houses[i + 1] = {
                "sign": sign_key,
                "degree": degree,
                "name": self.HOUSES[i]
            }

        # Генерируем аспекты
        aspects = self._calculate_aspects(planets)

        return {
            "birth_data": birth_data,
            "sun_sign": zodiac_sign,
            "planets": planets,
            "houses": houses,
            "aspects": aspects,
            "calculated_at": datetime.utcnow().isoformat()
        }

    async def calculate_transits(
            self,
            natal_chart: Dict[str, Any],
            period: str = "today"
    ) -> List[Dict[str, Any]]:
        """Рассчитать транзиты."""
        # Упрощенная версия
        transits = []

        # Текущие позиции планет (упрощенно)
        current_date = datetime.utcnow()

        for i, planet in enumerate(self.PLANETS[:7]):  # Только видимые планеты
            # Случайный транзит для примера
            if random.random() > 0.5:
                natal_planet = random.choice(list(natal_chart["planets"].keys()))
                aspect = random.choice(["соединение", "трин", "квадрат", "оппозиция", "секстиль"])

                transits.append({
                    "transit_planet": planet,
                    "aspect": aspect,
                    "natal_planet": natal_planet.title(),
                    "exact_date": (current_date + timedelta(days=random.randint(1, 30))).date(),
                    "orb": round(random.uniform(0.1, 3.0), 1),
                    "importance": random.choice(["high", "medium", "low"]),
                    "sphere": random.choice(["career", "love", "health", "finance"])
                })

        # Сортируем по важности и дате
        transits.sort(key=lambda x: (
            {"high": 0, "medium": 1, "low": 2}[x["importance"]],
            x["exact_date"]
        ))

        return transits

    async def calculate_moon_phase(
            self,
            target_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """Рассчитать фазу луны."""
        if not target_date:
            target_date = date.today()

        # Известное новолуние для расчета
        known_new_moon = date(2024, 1, 11)
        days_since = (target_date - known_new_moon).days

        # Лунный цикл ~29.53 дня
        lunar_cycle = 29.53
        phase_days = days_since % lunar_cycle
        lunar_day = int(phase_days) + 1

        # Определяем фазу
        if phase_days < 1.84:
            phase = {"name": "Новолуние", "emoji": "🌑", "illumination": 0}
        elif phase_days < 5.53:
            phase = {"name": "Растущий серп", "emoji": "🌒", "illumination": 25}
        elif phase_days < 9.22:
            phase = {"name": "Первая четверть", "emoji": "🌓", "illumination": 50}
        elif phase_days < 12.91:
            phase = {"name": "Растущая луна", "emoji": "🌔", "illumination": 75}
        elif phase_days < 16.61:
            phase = {"name": "Полнолуние", "emoji": "🌕", "illumination": 100}
        elif phase_days < 20.30:
            phase = {"name": "Убывающая луна", "emoji": "🌖", "illumination": 75}
        elif phase_days < 23.99:
            phase = {"name": "Последняя четверть", "emoji": "🌗", "illumination": 50}
        else:
            phase = {"name": "Убывающий серп", "emoji": "🌘", "illumination": 25}

        # Знак зодиака луны (упрощенно)
        moon_sign_index = int((phase_days / lunar_cycle) * 12)
        moon_sign = list(self.ZODIAC_SIGNS.keys())[moon_sign_index]

        return {
            "date": target_date.isoformat(),
            "lunar_day": lunar_day,
            "phase": phase["name"],
            "emoji": phase["emoji"],
            "illumination": phase["illumination"],
            "moon_sign": moon_sign,
            "moon_sign_name": self.ZODIAC_SIGNS[moon_sign]["name"],
            "recommendations": self._get_moon_recommendations(phase["name"])
        }

    async def calculate_compatibility(
            self,
            person1_data: Dict[str, Any],
            person2_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Рассчитать совместимость (синастрию)."""
        # Получаем знаки зодиака
        date1 = datetime.fromisoformat(person1_data["date"])
        date2 = datetime.fromisoformat(person2_data["date"])

        sign1 = await self.get_zodiac_sign(date1)
        sign2 = await self.get_zodiac_sign(date2)

        # Упрощенный расчет совместимости
        compatibility = self._calculate_sign_compatibility(sign1, sign2)

        # Генерируем детальный анализ через AI
        analysis = await self._generate_compatibility_analysis(
            sign1, sign2, compatibility
        )

        return {
            "person1": {
                "sign": sign1,
                "sign_name": self.ZODIAC_SIGNS[sign1]["name"]
            },
            "person2": {
                "sign": sign2,
                "sign_name": self.ZODIAC_SIGNS[sign2]["name"]
            },
            "overall_compatibility": compatibility["overall"],
            "aspects": compatibility["aspects"],
            "analysis": analysis,
            "advice": compatibility["advice"]
        }

    def _calculate_aspects(self, planets: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Рассчитать аспекты между планетами."""
        aspects = []
        planet_list = list(planets.items())

        for i in range(len(planet_list)):
            for j in range(i + 1, len(planet_list)):
                planet1_name, planet1_data = planet_list[i]
                planet2_name, planet2_data = planet_list[j]

                # Упрощенный расчет углового расстояния
                angle = abs(planet1_data["degree"] - planet2_data["degree"])
                if angle > 180:
                    angle = 360 - angle

                # Определяем аспект
                aspect_type = None
                orb = 0

                if angle <= 8:
                    aspect_type = "соединение"
                    orb = angle
                elif 52 <= angle <= 68:
                    aspect_type = "секстиль"
                    orb = abs(angle - 60)
                elif 82 <= angle <= 98:
                    aspect_type = "квадрат"
                    orb = abs(angle - 90)
                elif 112 <= angle <= 128:
                    aspect_type = "трин"
                    orb = abs(angle - 120)
                elif 172 <= angle <= 188:
                    aspect_type = "оппозиция"
                    orb = abs(angle - 180)

                if aspect_type:
                    aspects.append({
                        "planet1": planet1_name.title(),
                        "planet2": planet2_name.title(),
                        "type": aspect_type,
                        "angle": round(angle, 1),
                        "orb": round(orb, 1),
                        "is_exact": orb < 1
                    })

        return aspects

    def _calculate_sign_compatibility(
            self,
            sign1: str,
            sign2: str
    ) -> Dict[str, Any]:
        """Рассчитать совместимость знаков."""
        # Элементы знаков
        element1 = self.ZODIAC_SIGNS[sign1]["element"]
        element2 = self.ZODIAC_SIGNS[sign2]["element"]

        # Базовая совместимость по элементам
        element_compatibility = {
            ("Огонь", "Огонь"): 90,
            ("Огонь", "Воздух"): 85,
            ("Огонь", "Земля"): 45,
            ("Огонь", "Вода"): 50,
            ("Воздух", "Воздух"): 90,
            ("Воздух", "Земля"): 45,
            ("Воздух", "Вода"): 60,
            ("Земля", "Земля"): 90,
            ("Земля", "Вода"): 85,
            ("Вода", "Вода"): 90
        }

        # Получаем базовую совместимость
        key = tuple(sorted([element1, element2]))
        base_compatibility = element_compatibility.get(key, 70)

        # Добавляем случайные факторы для разнообразия
        variation = random.randint(-10, 10)
        overall = max(40, min(95, base_compatibility + variation))

        # Аспекты совместимости
        aspects = {
            "emotional": random.randint(60, 95),
            "intellectual": random.randint(65, 90),
            "physical": random.randint(70, 95),
            "values": random.randint(60, 85),
            "communication": random.randint(65, 90),
            "longterm": random.randint(60, 85)
        }

        # Советы на основе совместимости
        if overall >= 80:
            advice = "Отличная совместимость! Поддерживайте взаимопонимание."
        elif overall >= 65:
            advice = "Хорошая совместимость. Работайте над компромиссами."
        else:
            advice = "Есть сложности, но любовь преодолевает препятствия."

        return {
            "overall": overall,
            "aspects": aspects,
            "advice": advice,
            "element_match": element1 == element2
        }

    async def _generate_horoscope_content(
            self,
            zodiac_sign: str,
            sign_info: Dict[str, Any],
            period_type: str
    ) -> Dict[str, Any]:
        """Генерировать содержание гороскопа через AI."""
        prompt = f"""
        Составь {period_type} гороскоп для знака {sign_info['name']} ({zodiac_sign}).
        Элемент знака: {sign_info['element']}

        Включи:
        1. Общий прогноз (3-4 предложения)
        2. Любовь и отношения (2-3 предложения)
        3. Карьера и финансы (2-3 предложения)
        4. Здоровье (1-2 предложения)

        Стиль: позитивный, конкретный, с практическими советами.
        """

        llm = await get_llm_manager()
        response = await llm.generate_completion(
            prompt,
            temperature=0.8,
            max_tokens=500
        )

        # Парсим ответ (в реальности нужен более сложный парсинг)
        sections = response.split("\n\n")

        return {
            "general": sections[0] if len(sections) > 0 else "Общий прогноз",
            "love": sections[1] if len(sections) > 1 else "Прогноз в любви",
            "career": sections[2] if len(sections) > 2 else "Прогноз в карьере",
            "health": sections[3] if len(sections) > 3 else "Прогноз здоровья"
        }

    async def _generate_compatibility_analysis(
            self,
            sign1: str,
            sign2: str,
            compatibility: Dict[str, Any]
    ) -> str:
        """Генерировать анализ совместимости через AI."""
        prompt = f"""
        Проанализируй совместимость между {self.ZODIAC_SIGNS[sign1]['name']} и {self.ZODIAC_SIGNS[sign2]['name']}.

        Общая совместимость: {compatibility['overall']}%
        Эмоциональная: {compatibility['aspects']['emotional']}%
        Интеллектуальная: {compatibility['aspects']['intellectual']}%

        Дай краткий анализ (4-5 предложений) их совместимости,
        укажи сильные стороны и возможные сложности.
        Будь позитивным и дай практические советы.
        """

        llm = await get_llm_manager()
        analysis = await llm.generate_completion(
            prompt,
            temperature=0.7,
            max_tokens=300
        )

        return analysis

    def _generate_lucky_numbers(self) -> List[int]:
        """Генерировать счастливые числа."""
        return sorted(random.sample(range(1, 50), 3))

    def _get_lucky_color(self, zodiac_sign: str) -> str:
        """Получить счастливый цвет для знака."""
        colors = {
            "aries": "красный",
            "taurus": "зеленый",
            "gemini": "желтый",
            "cancer": "белый",
            "leo": "золотой",
            "virgo": "коричневый",
            "libra": "розовый",
            "scorpio": "бордовый",
            "sagittarius": "фиолетовый",
            "capricorn": "черный",
            "aquarius": "синий",
            "pisces": "морской волны"
        }

        return colors.get(zodiac_sign, "серебряный")

    def _get_moon_recommendations(self, phase: str) -> Dict[str, str]:
        """Получить рекомендации для лунной фазы."""
        recommendations = {
            "Новолуние": {
                "general": "Время новых начинаний и планирования",
                "avoid": "Избегайте завершения дел",
                "good_for": "Планирование, медитация, постановка целей"
            },
            "Растущий серп": {
                "general": "Время для первых шагов к целям",
                "avoid": "Не сомневайтесь в своих силах",
                "good_for": "Начало проектов, новые знакомства"
            },
            "Первая четверть": {
                "general": "Время преодоления препятствий",
                "avoid": "Не отступайте перед трудностями",
                "good_for": "Решение проблем, принятие решений"
            },
            "Растущая луна": {
                "general": "Время активного роста и развития",
                "avoid": "Избегайте перегрузок",
                "good_for": "Развитие проектов, обучение"
            },
            "Полнолуние": {
                "general": "Время максимальной энергии и завершений",
                "avoid": "Контролируйте эмоции",
                "good_for": "Завершение дел, празднования"
            },
            "Убывающая луна": {
                "general": "Время освобождения и очищения",
                "avoid": "Не начинайте новые проекты",
                "good_for": "Завершение, очищение, отдых"
            },
            "Последняя четверть": {
                "general": "Время переосмысления и отпускания",
                "avoid": "Не цепляйтесь за прошлое",
                "good_for": "Прощение, медитация, планирование"
            },
            "Убывающий серп": {
                "general": "Время отдыха и подготовки",
                "avoid": "Избегайте активных действий",
                "good_for": "Отдых, медитация, восстановление"
            }
        }

        return recommendations.get(phase, {
            "general": "Следуйте своей интуиции",
            "avoid": "Избегайте спешки",
            "good_for": "Саморазвитие"
        })


class PaymentService(BaseService):
    """Сервис для обработки платежей."""

    # Поддерживаемые платежные системы
    PAYMENT_PROVIDERS = {
        "telegram_stars": {
            "name": "Telegram Stars",
            "currency": "XTR",
            "min_amount": 1,
            "max_amount": 10000,
            "commission": 0
        },
        "yookassa": {
            "name": "ЮKassa",
            "currency": "RUB",
            "min_amount": 10,
            "max_amount": 100000,
            "commission": 2.5
        },
        "cryptobot": {
            "name": "Crypto Bot",
            "currency": "USDT",
            "min_amount": 1,
            "max_amount": 10000,
            "commission": 1
        }
    }

    async def create_payment(
            self,
            user_id: int,
            amount: Decimal,
            currency: str,
            provider: str,
            description: str,
            metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Создать платеж."""
        async with get_unit_of_work() as uow:
            # Создаем запись о платеже
            payment = await uow.payments.create(
                user_id=user_id,
                amount=amount,
                currency=currency,
                provider=provider,
                status="pending",
                description=description,
                metadata=metadata or {}
            )
            await uow.commit()

            # В зависимости от провайдера создаем платеж
            if provider == "telegram_stars":
                payment_data = await self._create_telegram_payment(
                    payment, amount, description
                )
            elif provider == "yookassa":
                payment_data = await self._create_yookassa_payment(
                    payment, amount, description
                )
            elif provider == "cryptobot":
                payment_data = await self._create_crypto_payment(
                    payment, amount, description
                )
            else:
                raise ValueError(f"Unknown payment provider: {provider}")

            # Обновляем платеж с данными от провайдера
            payment.provider_payment_id = payment_data.get("provider_id")
            payment.payment_url = payment_data.get("payment_url")
            await uow.commit()

            await self.log_action(user_id, "create_payment", {
                "amount": float(amount),
                "currency": currency,
                "provider": provider
            })

            return {
                "payment_id": payment.id,
                "provider_id": payment_data.get("provider_id"),
                "payment_url": payment_data.get("payment_url"),
                "amount": amount,
                "currency": currency,
                "status": "pending"
            }

    async def process_payment_callback(
            self,
            provider: str,
            callback_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Обработать callback от платежной системы."""
        async with get_unit_of_work() as uow:
            # Находим платеж
            provider_payment_id = callback_data.get("provider_payment_id")
            payment = await uow.payments.get_by_provider_id(
                provider, provider_payment_id
            )

            if not payment:
                logger.error(f"Payment not found: {provider_payment_id}")
                return {"status": "error", "message": "Payment not found"}

            # Обрабатываем в зависимости от провайдера
            if provider == "telegram_stars":
                result = await self._process_telegram_callback(
                    payment, callback_data
                )
            elif provider == "yookassa":
                result = await self._process_yookassa_callback(
                    payment, callback_data
                )
            elif provider == "cryptobot":
                result = await self._process_crypto_callback(
                    payment, callback_data
                )
            else:
                return {"status": "error", "message": "Unknown provider"}

            # Обновляем статус платежа
            payment.status = result["status"]
            payment.completed_at = datetime.utcnow() if result["status"] == "completed" else None

            # Если платеж успешный, активируем услугу
            if result["status"] == "completed":
                await self._activate_service(payment, uow)

            await uow.commit()

            return result

    async def check_payment_status(
            self,
            payment_id: int
    ) -> Dict[str, Any]:
        """Проверить статус платежа."""
        async with get_unit_of_work() as uow:
            payment = await uow.payments.get(payment_id)

            if not payment:
                return {"status": "error", "message": "Payment not found"}

            # Для ожидающих платежей проверяем статус у провайдера
            if payment.status == "pending":
                if payment.provider == "yookassa":
                    # Здесь должна быть проверка через API ЮKassa
                    pass
                elif payment.provider == "cryptobot":
                    # Здесь должна быть проверка через API CryptoBot
                    pass

            return {
                "payment_id": payment.id,
                "status": payment.status,
                "amount": float(payment.amount),
                "currency": payment.currency,
                "created_at": payment.created_at.isoformat(),
                "completed_at": payment.completed_at.isoformat() if payment.completed_at else None
            }

    async def refund_payment(
            self,
            payment_id: int,
            reason: str
    ) -> Dict[str, Any]:
        """Оформить возврат платежа."""
        async with get_unit_of_work() as uow:
            payment = await uow.payments.get(payment_id)

            if not payment:
                return {"status": "error", "message": "Payment not found"}

            if payment.status != "completed":
                return {"status": "error", "message": "Payment not completed"}

            if payment.refunded:
                return {"status": "error", "message": "Already refunded"}

            # Создаем возврат в зависимости от провайдера
            if payment.provider == "yookassa":
                # Здесь должен быть API вызов для возврата
                pass

            # Обновляем статус
            payment.refunded = True
            payment.refunded_at = datetime.utcnow()
            payment.refund_reason = reason

            # Деактивируем услугу
            await self._deactivate_service(payment, uow)

            await uow.commit()

            await self.log_action(payment.user_id, "refund_payment", {
                "payment_id": payment_id,
                "reason": reason
            })

            return {
                "status": "success",
                "payment_id": payment_id,
                "refunded_at": payment.refunded_at.isoformat()
            }

    async def _create_telegram_payment(
            self,
            payment,
            amount: Decimal,
            description: str
    ) -> Dict[str, Any]:
        """Создать платеж через Telegram Stars."""
        # Telegram Stars обрабатываются через sendInvoice
        # Здесь возвращаем данные для создания инвойса
        return {
            "provider_id": f"tg_{payment.id}",
            "payment_url": None,  # Не используется для Telegram
            "invoice_data": {
                "title": "Подписка AstroTarot",
                "description": description,
                "payload": f"payment_{payment.id}",
                "provider_token": "",  # Для Stars не нужен
                "currency": "XTR",
                "prices": [{"label": description, "amount": int(amount)}]
            }
        }

    async def _create_yookassa_payment(
            self,
            payment,
            amount: Decimal,
            description: str
    ) -> Dict[str, Any]:
        """Создать платеж через ЮKassa."""
        # Здесь должна быть интеграция с API ЮKassa
        # Пока возвращаем заглушку
        return {
            "provider_id": f"yk_{payment.id}",
            "payment_url": f"https://yookassa.ru/payment/{payment.id}",
            "confirmation_url": f"https://yookassa.ru/confirm/{payment.id}"
        }

    async def _create_crypto_payment(
            self,
            payment,
            amount: Decimal,
            description: str
    ) -> Dict[str, Any]:
        """Создать платеж через CryptoBot."""
        # Здесь должна быть интеграция с API CryptoBot
        # Пока возвращаем заглушку
        return {
            "provider_id": f"cb_{payment.id}",
            "payment_url": f"https://t.me/CryptoBot?start=pay_{payment.id}",
            "crypto_address": "TXxXxXxXxXxXxXxXxXxXxXxXxXxXxXxXx"
        }

    async def _process_telegram_callback(
            self,
            payment,
            callback_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Обработать callback от Telegram."""
        # Telegram отправляет successful_payment в сообщении
        if callback_data.get("status") == "successful":
            return {"status": "completed", "provider_data": callback_data}
        else:
            return {"status": "failed", "error": callback_data.get("error")}

    async def _process_yookassa_callback(
            self,
            payment,
            callback_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Обработать callback от ЮKassa."""
        # Здесь должна быть обработка вебхука от ЮKassa
        status_map = {
            "succeeded": "completed",
            "canceled": "cancelled",
            "refunded": "refunded",
            "pending": "pending"
        }

        yk_status = callback_data.get("status", "pending")
        return {
            "status": status_map.get(yk_status, "failed"),
            "provider_data": callback_data
        }

    async def _process_crypto_callback(
            self,
            payment,
            callback_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Обработать callback от CryptoBot."""
        # Здесь должна быть обработка вебхука от CryptoBot
        if callback_data.get("status") == "paid":
            return {"status": "completed", "provider_data": callback_data}
        else:
            return {"status": "pending", "provider_data": callback_data}

    async def _activate_service(self, payment, uow):
        """Активировать услугу после успешного платежа."""
        metadata = payment.metadata or {}

        # Если это подписка
        if metadata.get("type") == "subscription":
            plan = metadata.get("plan", "basic")
            duration_days = metadata.get("duration_days", 30)

            await uow.subscriptions.activate_or_extend(
                user_id=payment.user_id,
                plan_name=plan,
                duration_days=duration_days,
                payment_id=payment.id
            )

            # Обновляем план пользователя
            user = await uow.users.get(payment.user_id)
            user.subscription_plan = plan

    async def _deactivate_service(self, payment, uow):
        """Деактивировать услугу при возврате."""
        metadata = payment.metadata or {}

        if metadata.get("type") == "subscription":
            subscription = await uow.subscriptions.get_active(payment.user_id)
            if subscription:
                subscription.is_active = False
                subscription.cancelled_at = datetime.utcnow()
                subscription.cancellation_reason = "refund"


class NotificationService(BaseService):
    """Сервис для отправки уведомлений."""

    # Типы уведомлений
    NOTIFICATION_TYPES = {
        "daily_horoscope": {
            "template": "daily_horoscope",
            "default_time": "09:00"
        },
        "subscription_expiring": {
            "template": "subscription_expiring",
            "days_before": 3
        },
        "new_feature": {
            "template": "new_feature"
        },
        "special_offer": {
            "template": "special_offer"
        }
    }

    async def send_notification(
            self,
            user_id: int,
            notification_type: str,
            data: Dict[str, Any] = None,
            bot=None
    ) -> bool:
        """Отправить уведомление пользователю."""
        async with get_unit_of_work() as uow:
            user = await uow.users.get(user_id)

            if not user or not user.notifications_enabled:
                return False

            # Проверяем настройки уведомлений
            settings = await uow.notifications.get_user_settings(user_id)
            if not settings.get(notification_type, True):
                return False

            # Формируем сообщение
            message = await self._format_notification(
                notification_type,
                user,
                data or {}
            )

            # Отправляем через бота
            if bot:
                try:
                    await bot.send_message(
                        chat_id=user.telegram_id,
                        text=message["text"],
                        reply_markup=message.get("keyboard"),
                        parse_mode="HTML"
                    )

                    # Сохраняем в историю
                    await uow.notifications.create_log(
                        user_id=user_id,
                        notification_type=notification_type,
                        status="sent",
                        data=data
                    )
                    await uow.commit()

                    return True

                except Exception as e:
                    logger.error(
                        f"Failed to send notification to user {user_id}: {e}"
                    )
                    return False

            return False

    async def schedule_notifications(self, bot):
        """Запланировать массовые уведомления."""
        async with get_unit_of_work() as uow:
            # Дневные гороскопы
            users_for_horoscope = await uow.users.get_for_daily_horoscope()

            for user in users_for_horoscope:
                await self.send_notification(
                    user.id,
                    "daily_horoscope",
                    {"zodiac_sign": user.zodiac_sign},
                    bot
                )

            # Истекающие подписки
            expiring_subscriptions = await uow.subscriptions.get_expiring(days=3)

            for subscription in expiring_subscriptions:
                await self.send_notification(
                    subscription.user_id,
                    "subscription_expiring",
                    {
                        "days_left": (subscription.end_date - datetime.utcnow()).days,
                        "plan": subscription.plan_name
                    },
                    bot
                )

    async def _format_notification(
            self,
            notification_type: str,
            user,
            data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Форматировать уведомление."""
        from infrastructure.telegram import Keyboards, MessageBuilder, MessageStyle

        builder = MessageBuilder(MessageStyle.HTML)

        if notification_type == "daily_horoscope":
            builder.add_bold("🌟 Ваш дневной гороскоп готов!").add_line(2)
            builder.add_text(
                f"Доброе утро, {user.display_name}! "
                f"Звезды приготовили для вас особое послание."
            )

            keyboard = await Keyboards.notification_actions(
                action_type="view_horoscope",
                action_data=data.get("zodiac_sign")
            )

        elif notification_type == "subscription_expiring":
            days = data.get("days_left", 0)
            builder.add_bold(f"⏰ Подписка истекает через {days} дн.").add_line(2)
            builder.add_text(
                f"Не упустите возможность продлить подписку "
                f"со скидкой 20%!"
            )

            keyboard = await Keyboards.notification_actions(
                action_type="extend_subscription"
            )

        elif notification_type == "new_feature":
            builder.add_bold("✨ Новая функция!").add_line(2)
            builder.add_text(data.get("description", "Попробуйте прямо сейчас!"))

            keyboard = await Keyboards.notification_actions(
                action_type="try_feature",
                action_data=data.get("feature_id")
            )

        else:
            builder.add_text("У нас есть для вас новости!")
            keyboard = None

        return {
            "text": builder.build(),
            "keyboard": keyboard
        }


class UserService(BaseService):
    """Сервис для управления пользователями."""

    async def register_user(
            self,
            telegram_user,
            referrer_code: Optional[str] = None
    ) -> Dict[str, Any]:
        """Регистрация нового пользователя."""
        async with get_unit_of_work() as uow:
            # Проверяем, существует ли пользователь
            existing = await uow.users.get_by_telegram_id(telegram_user.id)
            if existing:
                return {
                    "user": existing,
                    "is_new": False
                }

            # Создаем нового пользователя
            user_data = {
                "telegram_id": telegram_user.id,
                "username": telegram_user.username,
                "first_name": telegram_user.first_name,
                "last_name": telegram_user.last_name,
                "language": telegram_user.language_code or "ru",
                "subscription_plan": "free"
            }

            # Обрабатываем реферальный код
            referrer = None
            if referrer_code:
                referrer = await uow.users.get_by_referral_code(referrer_code)
                if referrer:
                    user_data["referred_by"] = referrer.id

            # Создаем пользователя
            user = await uow.users.create(**user_data)

            # Генерируем реферальный код
            user.referral_code = await self._generate_referral_code(user.id)

            # Начисляем бонусы за регистрацию
            if referrer:
                await self._process_referral_bonus(referrer, user, uow)

            await uow.commit()

            await self.log_action(user.id, "register", {
                "referrer": referrer_code
            })

            return {
                "user": user,
                "is_new": True,
                "referrer": referrer
            }

    async def update_profile(
            self,
            user_id: int,
            data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Обновить профиль пользователя."""
        async with get_unit_of_work() as uow:
            user = await uow.users.get(user_id)

            if not user:
                return {"status": "error", "message": "User not found"}

            # Обновляем разрешенные поля
            allowed_fields = [
                "display_name", "birth_data", "timezone",
                "language", "notifications_enabled"
            ]

            for field in allowed_fields:
                if field in data:
                    setattr(user, field, data[field])

            # Если обновили данные рождения, пересчитываем знак
            if "birth_data" in data and data["birth_data"]:
                astro_service = AstrologyService()
                birth_date = datetime.fromisoformat(data["birth_data"]["date"])
                user.zodiac_sign = await astro_service.get_zodiac_sign(birth_date)

            await uow.commit()

            await self.log_action(user_id, "update_profile", data)

            return {
                "status": "success",
                "user": user
            }

    async def get_user_statistics(
            self,
            user_id: int
    ) -> Dict[str, Any]:
        """Получить полную статистику пользователя."""
        async with get_unit_of_work() as uow:
            user = await uow.users.get(user_id)

            if not user:
                return {}

            # Собираем статистику из разных источников
            tarot_stats = await uow.tarot.get_user_statistics(user_id)
            astro_stats = await uow.astrology.get_user_statistics(user_id)
            payment_stats = await uow.payments.get_user_statistics(user_id)

            # Считаем общие метрики
            days_with_bot = (datetime.utcnow() - user.created_at).days

            # Определяем уровень активности
            total_actions = (
                    tarot_stats.get("total_spreads", 0) +
                    astro_stats.get("total_horoscopes", 0)
            )

            if total_actions == 0:
                activity_level = "new"
            elif total_actions < 10:
                activity_level = "beginner"
            elif total_actions < 50:
                activity_level = "active"
            elif total_actions < 100:
                activity_level = "expert"
            else:
                activity_level = "master"

            return {
                "user_info": {
                    "id": user.id,
                    "username": user.username,
                    "registered": user.created_at.isoformat(),
                    "days_with_bot": days_with_bot,
                    "subscription": user.subscription_plan,
                    "activity_level": activity_level
                },
                "tarot": tarot_stats,
                "astrology": astro_stats,
                "payments": payment_stats,
                "totals": {
                    "total_actions": total_actions,
                    "favorite_feature": "tarot" if tarot_stats.get("total_spreads", 0) > astro_stats.get(
                        "total_horoscopes", 0) else "astrology"
                }
            }

    async def delete_user_data(
            self,
            user_id: int,
            reason: str
    ) -> Dict[str, Any]:
        """Удалить данные пользователя (GDPR)."""
        async with get_unit_of_work() as uow:
            user = await uow.users.get(user_id)

            if not user:
                return {"status": "error", "message": "User not found"}

            # Анонимизируем данные вместо полного удаления
            user.telegram_id = f"deleted_{user.id}"
            user.username = None
            user.first_name = "Deleted"
            user.last_name = "User"
            user.birth_data = None
            user.is_deleted = True
            user.deleted_at = datetime.utcnow()
            user.deletion_reason = reason

            # Отменяем подписки
            await uow.subscriptions.cancel_all_for_user(user_id)

            await uow.commit()

            await self.log_action(user_id, "delete_account", {
                "reason": reason
            })

            return {
                "status": "success",
                "message": "User data anonymized"
            }

    async def _generate_referral_code(self, user_id: int) -> str:
        """Генерировать уникальный реферальный код."""
        import string
        import random

        while True:
            # Генерируем код из 6 символов
            code = ''.join(
                random.choices(
                    string.ascii_uppercase + string.digits,
                    k=6
                )
            )

            # Проверяем уникальность
            async with get_unit_of_work() as uow:
                existing = await uow.users.get_by_referral_code(code)
                if not existing:
                    return code

    async def _process_referral_bonus(self, referrer, new_user, uow):
        """Обработать реферальный бонус."""
        # Начисляем бонус реферу
        # Например, 7 дней премиума
        subscription = await uow.subscriptions.get_active(referrer.id)

        if subscription:
            # Продлеваем существующую подписку
            subscription.end_date += timedelta(days=7)
        else:
            # Создаем новую подписку
            await uow.subscriptions.create(
                user_id=referrer.id,
                plan_name="basic",
                start_date=datetime.utcnow(),
                end_date=datetime.utcnow() + timedelta(days=7),
                is_active=True,
                payment_id=None  # Бонусная подписка
            )

        # Обновляем счетчик рефералов
        referrer.referral_count += 1

        # Можно также начислить бонус новому пользователю
        # Например, 3 дня базовой подписки
        await uow.subscriptions.create(
            user_id=new_user.id,
            plan_name="basic",
            start_date=datetime.utcnow(),
            end_date=datetime.utcnow() + timedelta(days=3),
            is_active=True,
            payment_id=None
        )


class AnalyticsService(BaseService):
    """Сервис для аналитики и отчетности."""

    async def get_system_statistics(self) -> Dict[str, Any]:
        """Получить общую статистику системы."""
        async with get_unit_of_work() as uow:
            # Пользователи
            total_users = await uow.users.count_total()
            active_today = await uow.users.count_active(days=1)
            active_week = await uow.users.count_active(days=7)
            active_month = await uow.users.count_active(days=30)

            # Подписки
            subscriptions_by_plan = await uow.subscriptions.count_by_plan()
            active_subscriptions = await uow.subscriptions.count_active()

            # Использование
            total_spreads = await uow.tarot.count_total_spreads()
            total_horoscopes = await uow.astrology.count_total_horoscopes()

            # Финансы
            revenue_today = await uow.payments.get_revenue(days=1)
            revenue_month = await uow.payments.get_revenue(days=30)
            revenue_total = await uow.payments.get_revenue()

            return {
                "users": {
                    "total": total_users,
                    "active_today": active_today,
                    "active_week": active_week,
                    "active_month": active_month,
                    "growth_rate": self._calculate_growth_rate(
                        active_month, active_week
                    )
                },
                "subscriptions": {
                    "by_plan": subscriptions_by_plan,
                    "total_active": active_subscriptions,
                    "conversion_rate": (active_subscriptions / total_users * 100) if total_users > 0 else 0
                },
                "usage": {
                    "total_spreads": total_spreads,
                    "total_horoscopes": total_horoscopes,
                    "average_per_user": {
                        "spreads": total_spreads / total_users if total_users > 0 else 0,
                        "horoscopes": total_horoscopes / total_users if total_users > 0 else 0
                    }
                },
                "revenue": {
                    "today": float(revenue_today),
                    "month": float(revenue_month),
                    "total": float(revenue_total),
                    "arpu": float(revenue_month / active_month) if active_month > 0 else 0
                }
            }

    async def generate_user_report(
            self,
            user_id: int,
            period: str = "all"
    ) -> Dict[str, Any]:
        """Генерировать отчет по пользователю."""
        user_service = UserService()
        stats = await user_service.get_user_statistics(user_id)

        # Добавляем временные метрики
        if period != "all":
            # Фильтруем данные по периоду
            # Это упрощенная версия
            pass

        # Генерируем выводы
        insights = self._generate_insights(stats)

        return {
            "statistics": stats,
            "insights": insights,
            "period": period,
            "generated_at": datetime.utcnow().isoformat()
        }

    async def get_popular_content(
            self,
            content_type: str = "all",
            limit: int = 10
    ) -> Dict[str, Any]:
        """Получить популярный контент."""
        async with get_unit_of_work() as uow:
            popular = {}

            if content_type in ["all", "tarot"]:
                # Популярные расклады
                popular_spreads = await uow.tarot.get_popular_spreads(limit)
                popular["spreads"] = popular_spreads

                # Частые карты
                frequent_cards = await uow.tarot.get_most_frequent_cards(limit)
                popular["cards"] = frequent_cards

            if content_type in ["all", "astrology"]:
                # Популярные знаки
                popular_signs = await uow.astrology.get_popular_signs(limit)
                popular["zodiac_signs"] = popular_signs

            return popular

    def _calculate_growth_rate(
            self,
            current_period: int,
            previous_period: int
    ) -> float:
        """Рассчитать темп роста."""
        if previous_period == 0:
            return 100.0 if current_period > 0 else 0.0

        return ((current_period - previous_period) / previous_period) * 100

    def _generate_insights(
            self,
            stats: Dict[str, Any]
    ) -> List[str]:
        """Генерировать инсайты на основе статистики."""
        insights = []

        # Анализ активности
        total_actions = stats["totals"]["total_actions"]
        if total_actions == 0:
            insights.append(
                "Начните свое путешествие с карты дня или дневного гороскопа!"
            )
        elif total_actions < 10:
            insights.append(
                "Вы делаете первые шаги. Попробуйте разные типы раскладов!"
            )
        elif total_actions > 100:
            insights.append(
                "Вы опытный пользователь! Рассмотрите VIP подписку для эксклюзивных функций."
            )

        # Анализ предпочтений
        if stats["totals"]["favorite_feature"] == "tarot":
            insights.append(
                "Вы предпочитаете Таро. Попробуйте также натальную карту!"
            )
        else:
            insights.append(
                "Вы любите астрологию. Откройте для себя мудрость карт Таро!"
            )

        # Анализ подписки
        if stats["user_info"]["subscription"] == "free":
            insights.append(
                "Откройте больше возможностей с подпиской Premium!"
            )

        return insights


# Экспорт сервисов
__all__ = [
    'BaseService',
    'TarotService',
    'AstrologyService',
    'PaymentService',
    'NotificationService',
    'UserService',
    'AnalyticsService'
]

# Singleton экземпляры сервисов
_services = {}


def get_tarot_service() -> TarotService:
    """Получить экземпляр сервиса Таро."""
    if 'tarot' not in _services:
        _services['tarot'] = TarotService()
    return _services['tarot']


def get_astrology_service() -> AstrologyService:
    """Получить экземпляр сервиса астрологии."""
    if 'astrology' not in _services:
        _services['astrology'] = AstrologyService()
    return _services['astrology']


def get_payment_service() -> PaymentService:
    """Получить экземпляр сервиса платежей."""
    if 'payment' not in _services:
        _services['payment'] = PaymentService()
    return _services['payment']


def get_notification_service() -> NotificationService:
    """Получить экземпляр сервиса уведомлений."""
    if 'notification' not in _services:
        _services['notification'] = NotificationService()
    return _services['notification']


def get_user_service() -> UserService:
    """Получить экземпляр сервиса пользователей."""
    if 'user' not in _services:
        _services['user'] = UserService()
    return _services['user']


def get_analytics_service() -> AnalyticsService:
    """Получить экземпляр сервиса аналитики."""
    if 'analytics' not in _services:
        _services['analytics'] = AnalyticsService()
    return _services['analytics']