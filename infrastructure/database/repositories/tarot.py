"""
Репозиторий для работы с картами Таро и раскладами.

Этот модуль содержит:
- Работу с колодами и картами
- Создание и сохранение раскладов
- Управление избранными раскладами
- Статистику использования карт
- Поиск и фильтрацию раскладов
"""

from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, date, timedelta
import random
import json

from sqlalchemy import select, func, and_, or_, update, desc, asc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload

from config import logger, SubscriptionTier, ReadingType
from core.interfaces.repository import (
    ITarotReadingRepository, QueryOptions, Pagination, Page
)
from infrastructure.database.models import (
    TarotDeck, TarotCard, TarotSpread, TarotReading,
    SavedReading, CardType, User
)
from infrastructure.database.repositories.base import BaseRepository
from core.exceptions import (
    EntityNotFoundError, ValidationError,
    SubscriptionRequiredError, DailyLimitReachedError
)


class TarotRepository(BaseRepository[TarotReading], ITarotReadingRepository):
    """
    Репозиторий для работы с раскладами Таро.

    Управляет картами, раскладами и историей чтений.
    """

    def __init__(self, session: AsyncSession):
        """
        Инициализация репозитория Таро.

        Args:
            session: Сессия БД
        """
        super().__init__(session, TarotReading)
        self._cards_cache: Optional[Dict[int, List[TarotCard]]] = None

    # Работа с колодами и картами

    async def get_default_deck(self) -> TarotDeck:
        """
        Получение колоды по умолчанию.

        Returns:
            Колода по умолчанию

        Raises:
            EntityNotFoundError: Если колода не найдена
        """
        query = select(TarotDeck).where(
            and_(
                TarotDeck.is_default == True,
                TarotDeck.is_active == True
            )
        )

        result = await self.session.execute(query)
        deck = result.scalar_one_or_none()

        if not deck:
            # Если нет колоды по умолчанию, берем первую активную
            query = select(TarotDeck).where(
                TarotDeck.is_active == True
            ).order_by(TarotDeck.id)

            result = await self.session.execute(query)
            deck = result.scalar_one_or_none()

        if not deck:
            raise EntityNotFoundError(
                "Не найдена активная колода Таро",
                entity_type="TarotDeck"
            )

        return deck

    async def get_deck_by_code(self, code: str) -> Optional[TarotDeck]:
        """
        Получение колоды по коду.

        Args:
            code: Код колоды

        Returns:
            Найденная колода или None
        """
        query = select(TarotDeck).where(
            and_(
                TarotDeck.code == code,
                TarotDeck.is_active == True
            )
        )

        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_deck_cards(
            self,
            deck_id: int,
            card_type: Optional[CardType] = None
    ) -> List[TarotCard]:
        """
        Получение карт колоды.

        Args:
            deck_id: ID колоды
            card_type: Тип карт (опционально)

        Returns:
            Список карт
        """
        # Проверяем кэш
        cache_key = f"{deck_id}:{card_type.value if card_type else 'all'}"

        query = select(TarotCard).where(TarotCard.deck_id == deck_id)

        if card_type:
            query = query.where(TarotCard.card_type == card_type)

        query = query.order_by(TarotCard.card_number)

        result = await self.session.execute(query)
        cards = list(result.scalars().all())

        logger.debug(f"Получено {len(cards)} карт из колоды {deck_id}")
        return cards

    async def get_card_by_id(self, card_id: int) -> Optional[TarotCard]:
        """
        Получение карты по ID.

        Args:
            card_id: ID карты

        Returns:
            Найденная карта или None
        """
        query = select(TarotCard).where(TarotCard.id == card_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    # Работа с раскладами

    async def get_spread_by_code(self, code: str) -> Optional[TarotSpread]:
        """
        Получение расклада по коду.

        Args:
            code: Код расклада

        Returns:
            Найденный расклад или None
        """
        query = select(TarotSpread).where(
            and_(
                TarotSpread.code == code,
                TarotSpread.is_active == True
            )
        )

        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_available_spreads(
            self,
            user_tier: SubscriptionTier
    ) -> List[TarotSpread]:
        """
        Получение доступных раскладов для уровня подписки.

        Args:
            user_tier: Уровень подписки пользователя

        Returns:
            Список доступных раскладов
        """
        query = select(TarotSpread).where(
            TarotSpread.is_active == True
        )

        # Бесплатные пользователи видят только не-премиум расклады
        if user_tier == SubscriptionTier.FREE:
            query = query.where(TarotSpread.is_premium == False)

        query = query.order_by(
            TarotSpread.category,
            TarotSpread.difficulty_level,
            TarotSpread.card_count
        )

        result = await self.session.execute(query)
        return list(result.scalars().all())

    # Создание раскладов

    async def create_reading(
            self,
            user_id: int,
            spread_code: str,
            question: Optional[str] = None,
            deck_code: str = "rider_waite",
            context_data: Optional[Dict[str, Any]] = None
    ) -> TarotReading:
        """
        Создание нового расклада.

        Args:
            user_id: ID пользователя
            spread_code: Код типа расклада
            question: Вопрос пользователя
            deck_code: Код колоды
            context_data: Дополнительный контекст

        Returns:
            Созданный расклад

        Raises:
            ValidationError: При ошибке валидации
            SubscriptionRequiredError: Для премиум раскладов
        """
        # Получаем пользователя
        user_query = select(User).where(User.id == user_id)
        user_result = await self.session.execute(user_query)
        user = user_result.scalar_one_or_none()

        if not user:
            raise EntityNotFoundError(f"Пользователь {user_id} не найден")

        # Получаем тип расклада
        spread = await self.get_spread_by_code(spread_code)
        if not spread:
            raise EntityNotFoundError(f"Расклад {spread_code} не найден")

        # Проверяем доступ к премиум раскладам
        if spread.is_premium and user.subscription_tier == SubscriptionTier.FREE:
            raise SubscriptionRequiredError(
                "Этот расклад доступен только для подписчиков",
                required_tier=SubscriptionTier.BASIC
            )

        # Получаем колоду
        deck = await self.get_deck_by_code(deck_code)
        if not deck:
            deck = await self.get_default_deck()

        # Получаем карты для расклада
        cards_drawn = await self._draw_cards(
            deck_id=deck.id,
            count=spread.card_count
        )

        # Создаем расклад
        reading_type = self._get_reading_type(spread_code)

        reading = await self.create(
            user_id=user_id,
            spread_id=spread.id,
            deck_id=deck.id,
            reading_type=reading_type,
            question=question,
            cards_drawn=cards_drawn,
            context_data=context_data or {}
        )

        # Увеличиваем счетчик использования расклада
        spread.usage_count += 1

        logger.info(
            f"Создан расклад {spread.name} для пользователя {user_id}"
        )

        return reading

    async def _draw_cards(
            self,
            deck_id: int,
            count: int
    ) -> List[Dict[str, Any]]:
        """
        Вытягивание случайных карт из колоды.

        Args:
            deck_id: ID колоды
            count: Количество карт

        Returns:
            Список выпавших карт с позициями
        """
        # Получаем все карты колоды
        cards = await self.get_deck_cards(deck_id)

        if len(cards) < count:
            raise ValidationError(
                f"Недостаточно карт в колоде: {len(cards)} < {count}"
            )

        # Случайно выбираем карты
        selected_cards = random.sample(cards, count)

        # Формируем результат
        cards_drawn = []
        for position, card in enumerate(selected_cards, 1):
            cards_drawn.append({
                "position": position,
                "card_id": card.id,
                "card_number": card.card_number,
                "card_name": card.name,
                "is_reversed": random.choice([True, False])  # 50% шанс
            })

        return cards_drawn

    def _get_reading_type(self, spread_code: str) -> ReadingType:
        """Определение типа расклада по коду."""
        mapping = {
            "card_of_day": ReadingType.CARD_OF_DAY,
            "three_cards": ReadingType.THREE_CARDS,
            "celtic_cross": ReadingType.CELTIC_CROSS,
            "relationship": ReadingType.RELATIONSHIP,
            "career": ReadingType.CAREER,
            "yes_no": ReadingType.YES_NO
        }
        return mapping.get(spread_code, ReadingType.CUSTOM)

    # Получение раскладов

    async def get_user_readings(
            self,
            user_id: int,
            reading_type: Optional[ReadingType] = None,
            pagination: Optional[Pagination] = None
    ) -> List[TarotReading]:
        """
        Получение раскладов пользователя.

        Args:
            user_id: ID пользователя
            reading_type: Тип расклада (опционально)
            pagination: Параметры пагинации

        Returns:
            Список раскладов
        """
        query = select(TarotReading).where(
            TarotReading.user_id == user_id
        ).options(
            selectinload(TarotReading.spread),
            selectinload(TarotReading.deck)
        )

        if reading_type:
            query = query.where(TarotReading.reading_type == reading_type)

        # Сортировка по дате создания (новые первые)
        query = query.order_by(TarotReading.created_at.desc())

        # Применение пагинации
        if pagination:
            offset = (pagination.page - 1) * pagination.size
            query = query.offset(offset).limit(pagination.size)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_today_reading(
            self,
            user_id: int
    ) -> Optional[TarotReading]:
        """
        Получение сегодняшнего расклада "Карта дня".

        Args:
            user_id: ID пользователя

        Returns:
            Сегодняшний расклад или None
        """
        today_start = datetime.combine(date.today(), datetime.min.time())
        today_end = datetime.combine(date.today(), datetime.max.time())

        query = select(TarotReading).where(
            and_(
                TarotReading.user_id == user_id,
                TarotReading.reading_type == ReadingType.CARD_OF_DAY,
                TarotReading.created_at >= today_start,
                TarotReading.created_at <= today_end
            )
        ).options(
            selectinload(TarotReading.spread),
            selectinload(TarotReading.deck)
        )

        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_reading_details(
            self,
            reading_id: int,
            user_id: Optional[int] = None
    ) -> TarotReading:
        """
        Получение детальной информации о раскладе.

        Args:
            reading_id: ID расклада
            user_id: ID пользователя для проверки доступа

        Returns:
            Детальная информация о раскладе

        Raises:
            EntityNotFoundError: Если расклад не найден
            ValidationError: Если нет доступа
        """
        query = select(TarotReading).where(
            TarotReading.id == reading_id
        ).options(
            selectinload(TarotReading.spread),
            selectinload(TarotReading.deck),
            selectinload(TarotReading.saved_reading)
        )

        if user_id:
            query = query.where(TarotReading.user_id == user_id)

        result = await self.session.execute(query)
        reading = result.scalar_one_or_none()

        if not reading:
            raise EntityNotFoundError(
                f"Расклад {reading_id} не найден",
                entity_type="TarotReading",
                entity_id=reading_id
            )

        # Загружаем полную информацию о картах
        card_ids = [card['card_id'] for card in reading.cards_drawn]
        cards_query = select(TarotCard).where(TarotCard.id.in_(card_ids))
        cards_result = await self.session.execute(cards_query)
        cards_dict = {card.id: card for card in cards_result.scalars()}

        # Обогащаем информацию о картах
        for card_data in reading.cards_drawn:
            card = cards_dict.get(card_data['card_id'])
            if card:
                card_data['full_info'] = {
                    'name': card.name,
                    'keywords_upright': card.keywords_upright,
                    'keywords_reversed': card.keywords_reversed,
                    'image_url': card.image_url
                }

        return reading

    # Избранные расклады

    async def add_to_favorites(
            self,
            reading_id: int,
            user_id: int,
            title: Optional[str] = None,
            notes: Optional[str] = None,
            tags: Optional[List[str]] = None
    ) -> SavedReading:
        """
        Добавление расклада в избранное.

        Args:
            reading_id: ID расклада
            user_id: ID пользователя
            title: Название для сохранения
            notes: Заметки пользователя
            tags: Теги для организации

        Returns:
            Сохраненный расклад
        """
        # Проверяем существование расклада и доступ
        reading = await self.get_reading_details(reading_id, user_id)

        # Проверяем, не сохранен ли уже
        existing_query = select(SavedReading).where(
            SavedReading.reading_id == reading_id
        )
        existing_result = await self.session.execute(existing_query)
        saved = existing_result.scalar_one_or_none()

        if saved:
            # Обновляем существующий
            saved.title = title or saved.title
            saved.notes = notes or saved.notes
            saved.tags = tags or saved.tags
        else:
            # Создаем новый
            saved = SavedReading(
                reading_id=reading_id,
                user_id=user_id,
                title=title or f"Расклад от {reading.created_at.strftime('%d.%m.%Y')}",
                notes=notes,
                tags=tags or []
            )
            self.session.add(saved)

        # Помечаем расклад как избранный
        reading.is_favorite = True

        await self.session.flush()
        logger.info(f"Расклад {reading_id} добавлен в избранное")

        return saved

    async def remove_from_favorites(
            self,
            reading_id: int,
            user_id: int
    ) -> bool:
        """
        Удаление расклада из избранного.

        Args:
            reading_id: ID расклада
            user_id: ID пользователя

        Returns:
            True если удалено успешно
        """
        # Находим сохраненный расклад
        query = select(SavedReading).where(
            and_(
                SavedReading.reading_id == reading_id,
                SavedReading.user_id == user_id
            )
        )
        result = await self.session.execute(query)
        saved = result.scalar_one_or_none()

        if saved:
            await self.session.delete(saved)

            # Обновляем флаг в основном раскладе
            reading = await self.get_by_id(reading_id)
            if reading:
                reading.is_favorite = False

            await self.session.flush()
            logger.info(f"Расклад {reading_id} удален из избранного")
            return True

        return False

    async def get_saved_readings(
            self,
            user_id: int,
            tags: Optional[List[str]] = None,
            pagination: Optional[Pagination] = None
    ) -> List[SavedReading]:
        """
        Получение сохраненных раскладов.

        Args:
            user_id: ID пользователя
            tags: Фильтр по тегам
            pagination: Параметры пагинации

        Returns:
            Список сохраненных раскладов
        """
        query = select(SavedReading).where(
            SavedReading.user_id == user_id
        ).options(
            joinedload(SavedReading.reading).selectinload(TarotReading.spread),
            joinedload(SavedReading.reading).selectinload(TarotReading.deck)
        )

        # Фильтр по тегам
        if tags:
            # JSON contains для PostgreSQL
            for tag in tags:
                query = query.where(
                    SavedReading.tags.contains([tag])
                )

        # Сортировка по дате создания
        query = query.order_by(SavedReading.created_at.desc())

        # Пагинация
        if pagination:
            offset = (pagination.page - 1) * pagination.size
            query = query.offset(offset).limit(pagination.size)

        result = await self.session.execute(query)
        return list(result.unique().scalars().all())

    # Статистика

    async def get_user_statistics(
            self,
            user_id: int
    ) -> Dict[str, Any]:
        """
        Получение статистики раскладов пользователя.

        Args:
            user_id: ID пользователя

        Returns:
            Словарь со статистикой
        """
        stats = {
            "total_readings": 0,
            "favorite_readings": 0,
            "readings_by_type": {},
            "most_common_cards": [],
            "last_reading_date": None
        }

        # Общее количество раскладов
        total_query = select(func.count(TarotReading.id)).where(
            TarotReading.user_id == user_id
        )
        total_result = await self.session.execute(total_query)
        stats["total_readings"] = total_result.scalar() or 0

        # Количество избранных
        fav_query = select(func.count(TarotReading.id)).where(
            and_(
                TarotReading.user_id == user_id,
                TarotReading.is_favorite == True
            )
        )
        fav_result = await self.session.execute(fav_query)
        stats["favorite_readings"] = fav_result.scalar() or 0

        # Расклады по типам
        type_query = select(
            TarotReading.reading_type,
            func.count(TarotReading.id)
        ).where(
            TarotReading.user_id == user_id
        ).group_by(TarotReading.reading_type)

        type_result = await self.session.execute(type_query)
        for reading_type, count in type_result:
            stats["readings_by_type"][reading_type.value] = count

        # Последний расклад
        last_query = select(TarotReading.created_at).where(
            TarotReading.user_id == user_id
        ).order_by(TarotReading.created_at.desc()).limit(1)

        last_result = await self.session.execute(last_query)
        last_date = last_result.scalar()
        if last_date:
            stats["last_reading_date"] = last_date.isoformat()

        # Самые частые карты (топ-5)
        stats["most_common_cards"] = await self._get_most_common_cards(user_id, 5)

        return stats

    async def _get_most_common_cards(
            self,
            user_id: int,
            limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Получение самых частых карт пользователя.

        Args:
            user_id: ID пользователя
            limit: Количество карт

        Returns:
            Список карт с частотой
        """
        # Получаем все расклады пользователя
        readings_query = select(TarotReading.cards_drawn).where(
            TarotReading.user_id == user_id
        )
        readings_result = await self.session.execute(readings_query)

        # Подсчитываем частоту карт
        card_counts = {}
        for cards_drawn, in readings_result:
            for card_data in cards_drawn:
                card_id = card_data['card_id']
                card_counts[card_id] = card_counts.get(card_id, 0) + 1

        # Сортируем по частоте
        top_cards = sorted(
            card_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )[:limit]

        # Получаем информацию о картах
        if top_cards:
            card_ids = [card_id for card_id, _ in top_cards]
            cards_query = select(TarotCard).where(TarotCard.id.in_(card_ids))
            cards_result = await self.session.execute(cards_query)
            cards_dict = {card.id: card for card in cards_result.scalars()}

            result = []
            for card_id, count in top_cards:
                card = cards_dict.get(card_id)
                if card:
                    result.append({
                        "card_id": card_id,
                        "card_name": card.name,
                        "card_type": card.card_type.value,
                        "count": count
                    })

            return result

        return []

    async def get_popular_spreads(
            self,
            limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Получение популярных раскладов.

        Args:
            limit: Количество раскладов

        Returns:
            Список популярных раскладов
        """
        query = select(
            TarotSpread,
            TarotSpread.usage_count
        ).where(
            TarotSpread.is_active == True
        ).order_by(
            TarotSpread.usage_count.desc()
        ).limit(limit)

        result = await self.session.execute(query)

        popular = []
        for spread, count in result:
            popular.append({
                "code": spread.code,
                "name": spread.name,
                "card_count": spread.card_count,
                "usage_count": count,
                "is_premium": spread.is_premium
            })

        return popular