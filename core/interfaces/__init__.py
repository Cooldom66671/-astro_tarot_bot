"""
Пакет интерфейсов для Астро-Таро Бота.

Этот модуль экспортирует все интерфейсы приложения для удобного
импорта в других модулях. Интерфейсы определяют контракты для
репозиториев и сервисов без привязки к конкретной реализации.

Использование:
    # Импорт интерфейсов репозиториев
    from core.interfaces import IUserRepository, IUnitOfWork

    # Импорт интерфейсов сервисов
    from core.interfaces import IUserService, ISubscriptionService

    # Импорт вспомогательных классов
    from core.interfaces import ServiceResult, QueryOptions
"""

# Импорт из модуля repository
from core.interfaces.repository import (
    # Базовые интерфейсы
    IRepository,
    IUnitOfWork,
    IRepositoryFactory,

    # Специализированные репозитории
    IUserRepository,
    ISubscriptionRepository,
    IBirthChartRepository,
    ITarotReadingRepository,
    IPaymentRepository,

    # Вспомогательные классы для запросов
    SortOrder,
    SortBy,
    Pagination,
    Filter,
    FilterGroup,
    QueryOptions,
    Page,
)

# Импорт из модуля service
from core.interfaces.service import (
    # Базовые интерфейсы
    IService,
    IServiceManager,
    ServiceResult,

    # Сервисы
    IUserService,
    ISubscriptionService,
    IAstrologyService,
    ITarotService,
    INotificationService,
    IContentService,

    # DTO (Data Transfer Objects)
    TelegramUserData,
    BirthDataInput,
    PaymentRequest,
)

# Дополнительные типы для удобства
from typing import TypeVar, Protocol, runtime_checkable

# Типовые переменные для обобщенных интерфейсов
T = TypeVar('T')  # Для сущностей
ID = TypeVar('ID')  # Для идентификаторов


# Протоколы для duck typing
@runtime_checkable
class Identifiable(Protocol):
    """Протокол для сущностей с идентификатором."""
    id: int


@runtime_checkable
class Timestamped(Protocol):
    """Протокол для сущностей с временными метками."""
    created_at: 'datetime'
    updated_at: 'datetime'


@runtime_checkable
class SoftDeletable(Protocol):
    """Протокол для сущностей с мягким удалением."""
    deleted_at: 'Optional[datetime]'
    is_deleted: bool


# Вспомогательные функции для проверки интерфейсов
def implements_repository(obj: any) -> bool:
    """
    Проверить, реализует ли объект интерфейс репозитория.

    Args:
        obj: Объект для проверки

    Returns:
        bool: True если реализует IRepository
    """
    required_methods = [
        'get_by_id', 'get_all', 'create', 'update', 'delete',
        'exists', 'count', 'find_one', 'find_many'
    ]

    return all(hasattr(obj, method) for method in required_methods)


def implements_service(obj: any) -> bool:
    """
    Проверить, реализует ли объект интерфейс сервиса.

    Args:
        obj: Объект для проверки

    Returns:
        bool: True если реализует IService
    """
    return hasattr(obj, 'health_check')


def validate_dto(dto_class: type, data: dict) -> bool:
    """
    Проверить, соответствуют ли данные DTO классу.

    Args:
        dto_class: Класс DTO
        data: Данные для проверки

    Returns:
        bool: True если данные валидны
    """
    try:
        # Пытаемся создать экземпляр DTO
        dto_class(**data)
        return True
    except (TypeError, ValueError):
        return False


# Константы для конфигурации
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100
DEFAULT_CACHE_TTL = 3600  # 1 час

# Словарь для маппинга имен сервисов на интерфейсы
SERVICE_INTERFACES = {
    'users': IUserService,
    'subscriptions': ISubscriptionService,
    'astrology': IAstrologyService,
    'tarot': ITarotService,
    'notifications': INotificationService,
    'content': IContentService,
}

# Словарь для маппинга имен репозиториев на интерфейсы
REPOSITORY_INTERFACES = {
    'users': IUserRepository,
    'subscriptions': ISubscriptionRepository,
    'birth_charts': IBirthChartRepository,
    'tarot_readings': ITarotReadingRepository,
    'payments': IPaymentRepository,
}


# Декоратор для проверки реализации интерфейса
def implements(*interfaces):
    """
    Декоратор для явного указания реализуемых интерфейсов.

    Использование:
        @implements(IUserService, INotificationService)
        class UserService:
            ...
    """

    def decorator(cls):
        cls.__interfaces__ = interfaces

        # Проверяем, что класс реализует все методы интерфейсов
        for interface in interfaces:
            for attr_name in dir(interface):
                if attr_name.startswith('_'):
                    continue

                attr = getattr(interface, attr_name)
                if hasattr(attr, '__isabstractmethod__') and attr.__isabstractmethod__:
                    if not hasattr(cls, attr_name):
                        raise NotImplementedError(
                            f"{cls.__name__} должен реализовать метод {attr_name} "
                            f"из интерфейса {interface.__name__}"
                        )

        return cls

    return decorator


# Пример использования интерфейсов в type hints
"""
Примеры использования в коде:

# В сервисах
class UserService:
    def __init__(self, repo: IUserRepository, uow: IUnitOfWork):
        self.repo = repo
        self.uow = uow

    async def get_user(self, user_id: int) -> ServiceResult[User]:
        user = await self.repo.get_by_id(user_id)
        if not user:
            return ServiceResult.fail("Пользователь не найден")
        return ServiceResult.ok(user)

# В обработчиках
async def handle_command(
    service: IUserService,
    telegram_data: TelegramUserData
) -> None:
    result = await service.register_user(telegram_data)
    if not result.success:
        await send_error(result.error)
"""

# Экспорт всех интерфейсов и вспомогательных элементов
__all__ = [
    # ===== Интерфейсы репозиториев =====
    # Базовые
    "IRepository",
    "IUnitOfWork",
    "IRepositoryFactory",

    # Специализированные
    "IUserRepository",
    "ISubscriptionRepository",
    "IBirthChartRepository",
    "ITarotReadingRepository",
    "IPaymentRepository",

    # Классы для запросов
    "SortOrder",
    "SortBy",
    "Pagination",
    "Filter",
    "FilterGroup",
    "QueryOptions",
    "Page",

    # ===== Интерфейсы сервисов =====
    # Базовые
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

    # ===== Дополнительные элементы =====
    # Протоколы
    "Identifiable",
    "Timestamped",
    "SoftDeletable",

    # Функции проверки
    "implements_repository",
    "implements_service",
    "validate_dto",

    # Декораторы
    "implements",

    # Константы
    "DEFAULT_PAGE_SIZE",
    "MAX_PAGE_SIZE",
    "DEFAULT_CACHE_TTL",
    "SERVICE_INTERFACES",
    "REPOSITORY_INTERFACES",
]