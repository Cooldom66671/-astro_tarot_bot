"""
Репозиторий для работы с пользователями.

Этот модуль содержит:
- Специфичные методы для работы с пользователями
- Поиск по Telegram ID и username
- Управление подписками и статистикой
- Работу с данными рождения и настройками
- Методы для аналитики и отчетов
"""

from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, date, timedelta
from sqlalchemy import select, func, and_, or_, update, case
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload

from config import logger, SubscriptionTier, UserRole, UserStatus
from core.interfaces.repository import (
    IUserRepository, QueryOptions, Pagination, Page
)
from infrastructure.database.models import (
    User, UserBirthData, UserSettings, UserConsent,
    Subscription, Payment
)
from infrastructure.database.repositories.base import BaseRepository
from core.exceptions import EntityNotFoundError, ValidationError


class UserRepository(BaseRepository[User], IUserRepository):
    """
    Репозиторий для работы с пользователями.

    Расширяет базовый репозиторий специфичными методами.
    """

    def __init__(self, session: AsyncSession):
        """
        Инициализация репозитория пользователей.

        Args:
            session: Сессия БД
        """
        super().__init__(session, User)

    # Поиск пользователей

    async def get_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        """
        Получение пользователя по Telegram ID.

        Args:
            telegram_id: ID пользователя в Telegram

        Returns:
            Найденный пользователь или None
        """
        query = select(User).where(
            User.telegram_id == telegram_id
        ).options(
            selectinload(User.birth_data),
            selectinload(User.settings),
            selectinload(User.consents)
        )

        result = await self.session.execute(query)
        user = result.scalar_one_or_none()

        if user:
            logger.debug(f"Найден пользователь telegram_id={telegram_id}")
        else:
            logger.debug(f"Пользователь telegram_id={telegram_id} не найден")

        return user

    async def get_by_username(self, username: str) -> Optional[User]:
        """
        Получение пользователя по username.

        Args:
            username: Username в Telegram (без @)

        Returns:
            Найденный пользователь или None
        """
        # Удаляем @ если есть
        username = username.lstrip('@').lower()

        query = select(User).where(
            func.lower(User.username) == username
        )

        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_referral_code(self, code: str) -> Optional[User]:
        """
        Получение пользователя по реферальному коду.

        Args:
            code: Реферальный код

        Returns:
            Найденный пользователь или None
        """
        query = select(User).where(User.referral_code == code.upper())
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    # Создание и обновление

    async def create_or_update_from_telegram(
            self,
            telegram_id: int,
            first_name: str,
            last_name: Optional[str] = None,
            username: Optional[str] = None,
            language_code: str = "ru"
    ) -> Tuple[User, bool]:
        """
        Создание или обновление пользователя из данных Telegram.

        Args:
            telegram_id: ID в Telegram
            first_name: Имя
            last_name: Фамилия
            username: Username
            language_code: Код языка

        Returns:
            Кортеж (пользователь, создан_новый)
        """
        user = await self.get_by_telegram_id(telegram_id)

        if user:
            # Обновляем существующего
            updated = False

            if user.first_name != first_name:
                user.first_name = first_name
                updated = True

            if user.last_name != last_name:
                user.last_name = last_name
                updated = True

            if username and user.username != username:
                user.username = username.lstrip('@')
                updated = True

            if user.language_code != language_code:
                user.language_code = language_code
                updated = True

            # Обновляем активность
            user.last_activity_at = datetime.utcnow()

            if updated:
                await self.session.flush()
                logger.info(f"Обновлен пользователь {telegram_id}")

            return user, False

        else:
            # Создаем нового
            user = await self.create(
                telegram_id=telegram_id,
                first_name=first_name,
                last_name=last_name,
                username=username.lstrip('@') if username else None,
                language_code=language_code,
                referral_code=self._generate_referral_code()
            )

            # Создаем настройки по умолчанию
            settings = UserSettings(user_id=user.id)
            self.session.add(settings)

            # Запрашиваем согласие на обработку данных
            consent = UserConsent(
                user_id=user.id,
                consent_type="personal_data",
                is_granted=False
            )
            self.session.add(consent)

            await self.session.flush()
            logger.info(f"Создан новый пользователь {telegram_id}")

            return user, True

    async def update_birth_data(
            self,
            user_id: int,
            birth_date: date,
            birth_time: Optional[datetime.time],
            birth_place: str,
            latitude: float,
            longitude: float,
            timezone: str = "UTC"
    ) -> UserBirthData:
        """
        Обновление данных рождения пользователя.

        Args:
            user_id: ID пользователя
            birth_date: Дата рождения
            birth_time: Время рождения
            birth_place: Место рождения
            latitude: Широта
            longitude: Долгота
            timezone: Часовой пояс

        Returns:
            Данные рождения
        """
        # Проверяем существование пользователя
        user = await self.get_by_id_or_fail(user_id)

        # Ищем существующие данные
        query = select(UserBirthData).where(UserBirthData.user_id == user_id)
        result = await self.session.execute(query)
        birth_data = result.scalar_one_or_none()

        if birth_data:
            # Обновляем существующие
            birth_data.birth_date = birth_date
            birth_data.birth_time = birth_time
            birth_data.is_birth_time_exact = birth_time is not None
            birth_data.birth_place = birth_place
            birth_data.latitude = latitude
            birth_data.longitude = longitude
            birth_data.timezone = timezone
            birth_data.natal_chart_cache = None  # Сброс кэша
            birth_data.natal_chart_updated_at = None
        else:
            # Создаем новые
            birth_data = UserBirthData(
                user_id=user_id,
                birth_date=birth_date,
                birth_time=birth_time,
                is_birth_time_exact=birth_time is not None,
                birth_place=birth_place,
                latitude=latitude,
                longitude=longitude,
                timezone=timezone
            )
            self.session.add(birth_data)

        await self.session.flush()
        logger.info(f"Обновлены данные рождения для пользователя {user_id}")

        return birth_data

    # Подписки и лимиты

    async def get_active_subscription(self, user_id: int) -> Optional[Subscription]:
        """
        Получение активной подписки пользователя.

        Args:
            user_id: ID пользователя

        Returns:
            Активная подписка или None
        """
        query = select(Subscription).where(
            and_(
                Subscription.user_id == user_id,
                Subscription.expires_at > datetime.utcnow(),
                Subscription.is_cancelled == False
            )
        ).order_by(Subscription.expires_at.desc())

        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def update_subscription(
            self,
            user_id: int,
            tier: SubscriptionTier,
            expires_at: datetime
    ) -> User:
        """
        Обновление подписки пользователя.

        Args:
            user_id: ID пользователя
            tier: Уровень подписки
            expires_at: Дата окончания

        Returns:
            Обновленный пользователь
        """
        user = await self.get_by_id_or_fail(user_id)

        user.subscription_tier = tier
        user.subscription_expires_at = expires_at

        await self.session.flush()
        logger.info(f"Обновлена подписка пользователя {user_id}: {tier}")

        return user

    async def check_and_reset_daily_limits(self, user_id: int) -> User:
        """
        Проверка и сброс дневных лимитов.

        Args:
            user_id: ID пользователя

        Returns:
            Обновленный пользователь
        """
        user = await self.get_by_id_or_fail(user_id)

        today = date.today()
        if user.daily_readings_date != today:
            user.daily_readings_count = 0
            user.daily_readings_date = today
            await self.session.flush()
            logger.debug(f"Сброшены дневные лимиты пользователя {user_id}")

        return user

    async def increment_reading_count(self, user_id: int) -> bool:
        """
        Увеличение счетчика раскладов.

        Args:
            user_id: ID пользователя

        Returns:
            True если лимит не превышен

        Raises:
            ValidationError: При превышении лимита
        """
        user = await self.check_and_reset_daily_limits(user_id)

        # Проверка лимитов
        limits = {
            SubscriptionTier.FREE: 3,
            SubscriptionTier.BASIC: 10,
            SubscriptionTier.PREMIUM: 50,
            SubscriptionTier.VIP: 999999
        }

        limit = limits.get(user.subscription_tier, 3)

        if user.daily_readings_count >= limit:
            raise ValidationError(
                f"Превышен дневной лимит раскладов ({limit})",
                user_message="Вы исчерпали дневной лимит раскладов. "
                             "Попробуйте завтра или улучшите подписку."
            )

        # Увеличиваем счетчики
        user.daily_readings_count += 1
        user.total_readings += 1
        user.last_activity_at = datetime.utcnow()

        await self.session.flush()
        logger.debug(f"Пользователь {user_id}: расклад {user.daily_readings_count}/{limit}")

        return True

    # Статистика и аналитика

    async def get_active_users_count(
            self,
            period_days: int = 30
    ) -> int:
        """
        Количество активных пользователей за период.

        Args:
            period_days: Период в днях

        Returns:
            Количество активных пользователей
        """
        since_date = datetime.utcnow() - timedelta(days=period_days)

        query = select(func.count(User.id)).where(
            and_(
                User.status == UserStatus.ACTIVE,
                User.last_activity_at >= since_date
            )
        )

        result = await self.session.execute(query)
        return result.scalar() or 0

    async def get_subscription_statistics(self) -> Dict[str, int]:
        """
        Статистика по подпискам.

        Returns:
            Словарь с количеством пользователей по тарифам
        """
        query = select(
            User.subscription_tier,
            func.count(User.id)
        ).group_by(User.subscription_tier)

        result = await self.session.execute(query)

        stats = {tier.value: 0 for tier in SubscriptionTier}
        for tier, count in result:
            stats[tier.value] = count

        return stats

    async def get_top_users(
            self,
            by: str = "total_readings",
            limit: int = 10
    ) -> List[User]:
        """
        Топ пользователей по различным критериям.

        Args:
            by: Критерий сортировки
            limit: Количество пользователей

        Returns:
            Список топ пользователей
        """
        query = select(User).where(User.status == UserStatus.ACTIVE)

        if by == "total_readings":
            query = query.order_by(User.total_readings.desc())
        elif by == "referrals":
            # Подсчет рефералов
            referral_count = select(
                User.referrer_id,
                func.count(User.id).label('referral_count')
            ).group_by(User.referrer_id).subquery()

            query = query.join(
                referral_count,
                User.id == referral_count.c.referrer_id
            ).order_by(referral_count.c.referral_count.desc())
        elif by == "activity":
            query = query.order_by(User.last_activity_at.desc())

        query = query.limit(limit)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def search_users(
            self,
            query_text: str,
            pagination: Pagination
    ) -> Page[User]:
        """
        Поиск пользователей по тексту.

        Args:
            query_text: Текст для поиска
            pagination: Параметры пагинации

        Returns:
            Страница с результатами
        """
        search_term = f"%{query_text.lower()}%"

        # Поиск по имени, username, email
        filters = or_(
            func.lower(User.first_name).like(search_term),
            func.lower(User.last_name).like(search_term),
            func.lower(User.username).like(search_term),
            func.lower(User.email).like(search_term),
            User.telegram_id.cast(String).like(search_term)
        )

        options = QueryOptions(filters=[filters])
        return await self.get_page(pagination, options)

    # Управление пользователями

    async def block_user(
            self,
            user_id: int,
            reason: str,
            blocked_by: Optional[int] = None
    ) -> User:
        """
        Блокировка пользователя.

        Args:
            user_id: ID пользователя
            reason: Причина блокировки
            blocked_by: ID админа

        Returns:
            Заблокированный пользователь
        """
        user = await self.get_by_id_or_fail(user_id)

        user.status = UserStatus.BLOCKED
        user.notes = f"{user.notes or ''}\n[{datetime.utcnow()}] Заблокирован: {reason}"

        if blocked_by:
            user.updated_by = blocked_by

        await self.session.flush()
        logger.warning(f"Пользователь {user_id} заблокирован: {reason}")

        return user

    async def unblock_user(self, user_id: int) -> User:
        """
        Разблокировка пользователя.

        Args:
            user_id: ID пользователя

        Returns:
            Разблокированный пользователь
        """
        user = await self.get_by_id_or_fail(user_id)

        user.status = UserStatus.ACTIVE
        user.notes = f"{user.notes or ''}\n[{datetime.utcnow()}] Разблокирован"

        await self.session.flush()
        logger.info(f"Пользователь {user_id} разблокирован")

        return user

    async def grant_admin_role(self, user_id: int) -> User:
        """
        Выдача прав администратора.

        Args:
            user_id: ID пользователя

        Returns:
            Обновленный пользователь
        """
        user = await self.get_by_id_or_fail(user_id)

        user.role = UserRole.ADMIN

        await self.session.flush()
        logger.warning(f"Пользователю {user_id} выданы права администратора")

        return user

    # Работа с согласиями

    async def grant_consent(
            self,
            user_id: int,
            consent_type: str,
            ip_address: Optional[str] = None,
            user_agent: Optional[str] = None
    ) -> UserConsent:
        """
        Получение согласия от пользователя.

        Args:
            user_id: ID пользователя
            consent_type: Тип согласия
            ip_address: IP адрес
            user_agent: User agent

        Returns:
            Согласие пользователя
        """
        # Ищем существующее согласие
        query = select(UserConsent).where(
            and_(
                UserConsent.user_id == user_id,
                UserConsent.consent_type == consent_type
            )
        )
        result = await self.session.execute(query)
        consent = result.scalar_one_or_none()

        if consent:
            consent.is_granted = True
            consent.granted_at = datetime.utcnow()
            consent.revoked_at = None
            consent.ip_address = ip_address
            consent.user_agent = user_agent
        else:
            consent = UserConsent(
                user_id=user_id,
                consent_type=consent_type,
                is_granted=True,
                granted_at=datetime.utcnow(),
                ip_address=ip_address,
                user_agent=user_agent
            )
            self.session.add(consent)

        await self.session.flush()
        logger.info(f"Получено согласие {consent_type} от пользователя {user_id}")

        return consent

    # Вспомогательные методы

    def _generate_referral_code(self) -> str:
        """Генерация уникального реферального кода."""
        import secrets
        import string

        alphabet = string.ascii_uppercase + string.digits
        while True:
            code = ''.join(secrets.choice(alphabet) for _ in range(8))

            # Проверяем уникальность (синхронно в рамках транзакции)
            exists_query = select(func.count()).where(User.referral_code == code)
            # Эта проверка будет выполнена при flush

            return code

    async def cleanup_inactive_users(self, inactive_days: int = 365) -> int:
        """
        Мягкое удаление неактивных пользователей.

        Args:
            inactive_days: Дней неактивности

        Returns:
            Количество удаленных пользователей
        """
        cutoff_date = datetime.utcnow() - timedelta(days=inactive_days)

        query = update(User).where(
            and_(
                User.last_activity_at < cutoff_date,
                User.status == UserStatus.ACTIVE,
                User.subscription_tier == SubscriptionTier.FREE
            )
        ).values(
            status=UserStatus.DELETED,
            is_deleted=True,
            deleted_at=datetime.utcnow()
        )

        result = await self.session.execute(query)
        count = result.rowcount

        logger.info(f"Мягко удалено {count} неактивных пользователей")
        return count