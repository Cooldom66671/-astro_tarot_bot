"""
Модуль интерфейсов сервисов для Астро-Таро Бота.

Этот модуль содержит абстрактные базовые классы (интерфейсы) для
сервисов. Сервисы содержат бизнес-логику приложения и оркестрируют
работу репозиториев, внешних API и других компонентов.

Преимущества:
- Изоляция бизнес-логики от инфраструктуры
- Переиспользование логики между разными точками входа (бот, API)
- Легкое тестирование бизнес-логики
- Четкое разделение ответственности

Использование:
    from core.interfaces import IUserService
    from services import UserService

    # Реализация должна наследоваться от интерфейса
    class UserService(IUserService):
        async def register_user(self, telegram_data: Dict) -> User:
            # Реализация регистрации
            ...
"""

from abc import ABC, abstractmethod
from typing import (
    Optional, List, Dict, Any, Tuple, Union,
    TypeVar, Generic, Callable, Awaitable
)
from datetime import datetime, date, time
from decimal import Decimal
from io import BytesIO

from config import logger

# Импорт типов для аннотаций
# В реальном коде будут импорты из core.entities
T = TypeVar('T')


# ===== DTO (Data Transfer Objects) =====

class TelegramUserData:
    """DTO для данных пользователя из Telegram."""

    def __init__(
            self,
            telegram_id: int,
            username: Optional[str] = None,
            first_name: Optional[str] = None,
            last_name: Optional[str] = None,
            language_code: Optional[str] = None,
            is_bot: bool = False,
            is_premium: bool = False
    ):
        self.telegram_id = telegram_id
        self.username = username
        self.first_name = first_name
        self.last_name = last_name
        self.language_code = language_code
        self.is_bot = is_bot
        self.is_premium = is_premium


class BirthDataInput:
    """DTO для входных данных рождения."""

    def __init__(
            self,
            name: str,
            date: date,
            time: Optional[time] = None,
            city: str = "",
            latitude: Optional[float] = None,
            longitude: Optional[float] = None,
            timezone: Optional[str] = None
    ):
        self.name = name
        self.date = date
        self.time = time
        self.city = city
        self.latitude = latitude
        self.longitude = longitude
        self.timezone = timezone


class PaymentRequest:
    """DTO для запроса платежа."""

    def __init__(
            self,
            user_id: int,
            plan: str,
            period_months: int = 1,
            promo_code: Optional[str] = None,
            payment_method: Optional[str] = None
    ):
        self.user_id = user_id
        self.plan = plan
        self.period_months = period_months
        self.promo_code = promo_code
        self.payment_method = payment_method


class ServiceResult(Generic[T]):
    """
    Результат выполнения сервисного метода.

    Позволяет возвращать как успешный результат, так и ошибку
    без использования исключений.
    """

    def __init__(
            self,
            success: bool,
            data: Optional[T] = None,
            error: Optional[str] = None,
            error_code: Optional[str] = None
    ):
        self.success = success
        self.data = data
        self.error = error
        self.error_code = error_code

    @classmethod
    def ok(cls, data: T) -> 'ServiceResult[T]':
        """Создать успешный результат."""
        return cls(success=True, data=data)

    @classmethod
    def fail(cls, error: str, error_code: Optional[str] = None) -> 'ServiceResult[T]':
        """Создать результат с ошибкой."""
        return cls(success=False, error=error, error_code=error_code)


# ===== БАЗОВЫЙ ИНТЕРФЕЙС СЕРВИСА =====

class IService(ABC):
    """Базовый интерфейс для всех сервисов."""

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Проверка работоспособности сервиса.

        Returns:
            True если сервис работает нормально
        """
        pass


# ===== ИНТЕРФЕЙС СЕРВИСА ПОЛЬЗОВАТЕЛЕЙ =====

class IUserService(IService, ABC):
    """Интерфейс сервиса для работы с пользователями."""

    @abstractmethod
    async def register_user(self, telegram_data: TelegramUserData) -> Any:
        """
        Регистрация нового пользователя.

        Args:
            telegram_data: Данные из Telegram

        Returns:
            User: Созданный пользователь

        Raises:
            EntityAlreadyExistsError: Если пользователь уже существует
        """
        pass

    @abstractmethod
    async def get_user_by_telegram_id(self, telegram_id: int) -> Optional[Any]:
        """
        Получить пользователя по Telegram ID.

        Args:
            telegram_id: ID в Telegram

        Returns:
            User или None
        """
        pass

    @abstractmethod
    async def update_user_activity(self, user_id: int) -> None:
        """
        Обновить активность пользователя.

        Args:
            user_id: ID пользователя
        """
        pass

    @abstractmethod
    async def set_birth_data(
            self,
            user_id: int,
            birth_data: BirthDataInput
    ) -> Any:
        """
        Установить данные рождения пользователя.

        Args:
            user_id: ID пользователя
            birth_data: Данные рождения

        Returns:
            User: Обновленный пользователь

        Raises:
            EntityNotFoundError: Если пользователь не найден
            ValidationError: Если данные невалидны
        """
        pass

    @abstractmethod
    async def update_settings(
            self,
            user_id: int,
            **settings
    ) -> Any:
        """
        Обновить настройки пользователя.

        Args:
            user_id: ID пользователя
            **settings: Настройки для обновления

        Returns:
            User: Обновленный пользователь
        """
        pass

    @abstractmethod
    async def give_consent(self, user_id: int) -> None:
        """Дать согласие на обработку данных."""
        pass

    @abstractmethod
    async def revoke_consent(self, user_id: int) -> None:
        """Отозвать согласие на обработку данных."""
        pass

    @abstractmethod
    async def block_user(self, user_id: int, reason: str) -> None:
        """Заблокировать пользователя."""
        pass

    @abstractmethod
    async def unblock_user(self, user_id: int) -> None:
        """Разблокировать пользователя."""
        pass

    @abstractmethod
    async def get_user_stats(self, user_id: int) -> Dict[str, Any]:
        """
        Получить статистику пользователя.

        Returns:
            Dict со статистикой (количество раскладов, дней с регистрации и т.д.)
        """
        pass

    @abstractmethod
    async def delete_user_data(self, user_id: int) -> None:
        """
        Удалить все данные пользователя (GDPR).

        Args:
            user_id: ID пользователя
        """
        pass


# ===== ИНТЕРФЕЙС СЕРВИСА ПОДПИСОК =====

class ISubscriptionService(IService, ABC):
    """Интерфейс сервиса для работы с подписками."""

    @abstractmethod
    async def get_user_subscription(self, user_id: int) -> Optional[Any]:
        """Получить подписку пользователя."""
        pass

    @abstractmethod
    async def check_feature_access(
            self,
            user_id: int,
            feature: str
    ) -> bool:
        """
        Проверить доступ к функции.

        Args:
            user_id: ID пользователя
            feature: Название функции

        Returns:
            True если есть доступ
        """
        pass

    @abstractmethod
    async def create_payment(
            self,
            payment_request: PaymentRequest
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Создать платеж для оформления подписки.

        Returns:
            ServiceResult с данными платежа или ошибкой
        """
        pass

    @abstractmethod
    async def process_payment_webhook(
            self,
            payment_data: Dict[str, Any]
    ) -> ServiceResult[None]:
        """
        Обработать вебхук от платежной системы.

        Args:
            payment_data: Данные от платежной системы
        """
        pass

    @abstractmethod
    async def activate_subscription(
            self,
            user_id: int,
            plan: str,
            period_months: int,
            payment_id: Optional[str] = None
    ) -> Any:
        """Активировать подписку."""
        pass

    @abstractmethod
    async def cancel_subscription(
            self,
            user_id: int,
            immediate: bool = False
    ) -> None:
        """Отменить подписку."""
        pass

    @abstractmethod
    async def get_available_plans(self) -> List[Dict[str, Any]]:
        """Получить список доступных тарифных планов."""
        pass

    @abstractmethod
    async def validate_promo_code(
            self,
            code: str,
            user_id: Optional[int] = None
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Проверить промокод.

        Returns:
            ServiceResult с информацией о скидке или ошибкой
        """
        pass

    @abstractmethod
    async def get_expiring_subscriptions(self, days: int = 3) -> List[Any]:
        """Получить подписки, истекающие в ближайшие дни."""
        pass

    @abstractmethod
    async def send_renewal_reminders(self) -> int:
        """
        Отправить напоминания о продлении.

        Returns:
            Количество отправленных напоминаний
        """
        pass


# ===== ИНТЕРФЕЙС СЕРВИСА АСТРОЛОГИИ =====

class IAstrologyService(IService, ABC):
    """Интерфейс сервиса для астрологических расчетов."""

    @abstractmethod
    async def calculate_natal_chart(
            self,
            user_id: int,
            force_recalculate: bool = False
    ) -> ServiceResult[Any]:
        """
        Рассчитать натальную карту пользователя.

        Args:
            user_id: ID пользователя
            force_recalculate: Принудительный пересчет

        Returns:
            ServiceResult с BirthChart или ошибкой
        """
        pass

    @abstractmethod
    async def get_natal_chart_interpretation(
            self,
            user_id: int,
            sections: Optional[List[str]] = None
    ) -> ServiceResult[Dict[str, str]]:
        """
        Получить интерпретацию натальной карты.

        Args:
            user_id: ID пользователя
            sections: Разделы для интерпретации (если None - все)

        Returns:
            ServiceResult с текстами интерпретаций
        """
        pass

    @abstractmethod
    async def calculate_compatibility(
            self,
            user_id: int,
            partner_id: int
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Рассчитать совместимость.

        Returns:
            ServiceResult с данными совместимости
        """
        pass

    @abstractmethod
    async def calculate_forecast(
            self,
            user_id: int,
            start_date: date,
            end_date: date,
            forecast_type: str = "transits"
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Рассчитать прогноз.

        Args:
            user_id: ID пользователя
            start_date: Начало периода
            end_date: Конец периода
            forecast_type: Тип прогноза (transits, progressions, solar_return)
        """
        pass

    @abstractmethod
    async def generate_natal_chart_pdf(
            self,
            user_id: int,
            language: str = "ru"
    ) -> ServiceResult[BytesIO]:
        """
        Сгенерировать PDF отчет натальной карты.

        Returns:
            ServiceResult с BytesIO PDF файла
        """
        pass

    @abstractmethod
    async def get_daily_horoscope(
            self,
            user_id: int,
            date: Optional[date] = None
    ) -> ServiceResult[str]:
        """Получить персональный гороскоп на день."""
        pass

    @abstractmethod
    async def search_city_coordinates(
            self,
            city_name: str
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Найти координаты города.

        Returns:
            ServiceResult с координатами и timezone
        """
        pass


# ===== ИНТЕРФЕЙС СЕРВИСА ТАРО =====

class ITarotService(IService, ABC):
    """Интерфейс сервиса для работы с Таро."""

    @abstractmethod
    async def get_daily_card(
            self,
            user_id: int,
            force_new: bool = False
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Получить карту дня.

        Args:
            user_id: ID пользователя
            force_new: Принудительно новая карта

        Returns:
            ServiceResult с картой и интерпретацией
        """
        pass

    @abstractmethod
    async def create_spread(
            self,
            user_id: int,
            spread_type: str,
            question: Optional[str] = None,
            interactive: bool = False
    ) -> ServiceResult[Any]:
        """
        Создать расклад.

        Args:
            user_id: ID пользователя
            spread_type: Тип расклада
            question: Вопрос для расклада
            interactive: Интерактивный режим

        Returns:
            ServiceResult с раскладом
        """
        pass

    @abstractmethod
    async def draw_card_for_spread(
            self,
            spread_id: int,
            position: int
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Вытянуть карту для позиции в раскладе.

        Args:
            spread_id: ID расклада
            position: Позиция карты
        """
        pass

    @abstractmethod
    async def get_spread_interpretation(
            self,
            spread_id: int
    ) -> ServiceResult[Dict[str, str]]:
        """Получить полную интерпретацию расклада."""
        pass

    @abstractmethod
    async def get_available_spreads(
            self,
            user_id: int
    ) -> List[Dict[str, Any]]:
        """
        Получить доступные типы раскладов.

        Returns:
            Список с информацией о раскладах
        """
        pass

    @abstractmethod
    async def get_user_spread_history(
            self,
            user_id: int,
            limit: int = 10
    ) -> List[Any]:
        """Получить историю раскладов пользователя."""
        pass

    @abstractmethod
    async def check_daily_limit(self, user_id: int) -> Tuple[bool, int]:
        """
        Проверить дневной лимит раскладов.

        Returns:
            (можно_делать_расклад, осталось_раскладов)
        """
        pass

    @abstractmethod
    async def get_card_meaning(
            self,
            card_id: str,
            position: Optional[str] = None,
            context: Optional[str] = None
    ) -> ServiceResult[str]:
        """
        Получить значение карты.

        Args:
            card_id: ID карты
            position: Позиция в раскладе
            context: Контекст (любовь, карьера и т.д.)
        """
        pass


# ===== ИНТЕРФЕЙС СЕРВИСА УВЕДОМЛЕНИЙ =====

class INotificationService(IService, ABC):
    """Интерфейс сервиса уведомлений."""

    @abstractmethod
    async def send_message(
            self,
            user_id: int,
            message: str,
            keyboard: Optional[Any] = None,
            parse_mode: Optional[str] = None
    ) -> bool:
        """Отправить сообщение пользователю."""
        pass

    @abstractmethod
    async def send_photo(
            self,
            user_id: int,
            photo: Union[str, BytesIO],
            caption: Optional[str] = None,
            keyboard: Optional[Any] = None
    ) -> bool:
        """Отправить фото пользователю."""
        pass

    @abstractmethod
    async def send_document(
            self,
            user_id: int,
            document: Union[str, BytesIO],
            filename: str,
            caption: Optional[str] = None
    ) -> bool:
        """Отправить документ пользователю."""
        pass

    @abstractmethod
    async def broadcast_message(
            self,
            user_ids: List[int],
            message: str,
            **kwargs
    ) -> Dict[str, int]:
        """
        Массовая рассылка сообщений.

        Returns:
            Dict со статистикой отправки
        """
        pass

    @abstractmethod
    async def send_daily_reminders(self) -> int:
        """Отправить ежедневные напоминания."""
        pass

    @abstractmethod
    async def send_subscription_reminder(
            self,
            user_id: int,
            days_left: int
    ) -> bool:
        """Напоминание об истечении подписки."""
        pass

    @abstractmethod
    async def notify_admin(
            self,
            message: str,
            level: str = "INFO"
    ) -> bool:
        """Уведомить администратора."""
        pass


# ===== ИНТЕРФЕЙС СЕРВИСА КОНТЕНТА =====

class IContentService(IService, ABC):
    """Интерфейс сервиса для работы с контентом."""

    @abstractmethod
    async def generate_interpretation(
            self,
            template_type: str,
            context: Dict[str, Any],
            tone_of_voice: str = "friend",
            use_cache: bool = True
    ) -> ServiceResult[str]:
        """
        Сгенерировать интерпретацию через LLM.

        Args:
            template_type: Тип шаблона
            context: Контекст для генерации
            tone_of_voice: Тональность
            use_cache: Использовать кэш
        """
        pass

    @abstractmethod
    async def get_template(
            self,
            template_name: str,
            language: str = "ru"
    ) -> Optional[str]:
        """Получить шаблон текста."""
        pass

    @abstractmethod
    async def format_message(
            self,
            template: str,
            **kwargs
    ) -> str:
        """Форматировать сообщение с подстановкой переменных."""
        pass

    @abstractmethod
    async def translate_text(
            self,
            text: str,
            target_language: str,
            source_language: str = "ru"
    ) -> ServiceResult[str]:
        """Перевести текст."""
        pass


# ===== МЕНЕДЖЕР СЕРВИСОВ =====

class IServiceManager(ABC):
    """Интерфейс менеджера сервисов для управления зависимостями."""

    @property
    @abstractmethod
    def users(self) -> IUserService:
        """Сервис пользователей."""
        pass

    @property
    @abstractmethod
    def subscriptions(self) -> ISubscriptionService:
        """Сервис подписок."""
        pass

    @property
    @abstractmethod
    def astrology(self) -> IAstrologyService:
        """Сервис астрологии."""
        pass

    @property
    @abstractmethod
    def tarot(self) -> ITarotService:
        """Сервис Таро."""
        pass

    @property
    @abstractmethod
    def notifications(self) -> INotificationService:
        """Сервис уведомлений."""
        pass

    @property
    @abstractmethod
    def content(self) -> IContentService:
        """Сервис контента."""
        pass

    @abstractmethod
    async def initialize(self) -> None:
        """Инициализировать все сервисы."""
        pass

    @abstractmethod
    async def shutdown(self) -> None:
        """Корректно завершить работу сервисов."""
        pass


# Экспорт
__all__ = [
    # Базовые классы
    "IService",
    "IServiceManager",
    "ServiceResult",

    # Сервисы
    "IUserService",
    "ISubscriptionService",
    "IAstrologyService",
    "ITarotService",
    "INotificationService",
    "IContentService",

    # DTO
    "TelegramUserData",
    "BirthDataInput",
    "PaymentRequest",
]