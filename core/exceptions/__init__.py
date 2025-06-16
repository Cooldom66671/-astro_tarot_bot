"""
Пакет исключений для Астро-Таро Бота.

Этот модуль экспортирует все кастомные исключения приложения
для удобного импорта в других модулях.

Использование:
    # Импорт конкретных исключений
    from core.exceptions import ValidationError, SubscriptionRequiredError

    # Импорт всех исключений
    from core.exceptions import *

    # Использование в коде
    try:
        validate_user_data(data)
    except ValidationError as e:
        logger.error(f"Ошибка валидации: {e.user_message}")
        return {"error": e.to_dict()}
"""

# Импортируем все исключения из модуля custom
from core.exceptions.custom import (
    # Базовые классы и enum
    BaseAppException,
    ErrorCode,

    # Ошибки валидации
    ValidationError,
    MultipleValidationError,

    # Ошибки бизнес-логики
    BusinessLogicError,
    EntityNotFoundError,
    EntityAlreadyExistsError,
    InvalidStateTransitionError,

    # Ошибки доступа и авторизации
    AuthenticationRequiredError,
    AccessDeniedError,
    SubscriptionRequiredError,
    SubscriptionExpiredError,

    # Ошибки лимитов
    RateLimitExceededError,
    DailyLimitReachedError,

    # Ошибки внешних сервисов
    ExternalServiceError,
    LLMAPIError,
    PaymentAPIError,
    GeocodingAPIError,

    # Ошибки базы данных
    DatabaseError,
    DatabaseConnectionError,
    TransactionError,

    # Вспомогательные функции
    handle_exception,
)

# Дополнительные импорты для удобства
from typing import Type, Union

# Тип для всех исключений приложения
AppException = Union[
    ValidationError,
    BusinessLogicError,
    EntityNotFoundError,
    EntityAlreadyExistsError,
    InvalidStateTransitionError,
    AuthenticationRequiredError,
    AccessDeniedError,
    SubscriptionRequiredError,
    SubscriptionExpiredError,
    RateLimitExceededError,
    DailyLimitReachedError,
    ExternalServiceError,
    LLMAPIError,
    PaymentAPIError,
    GeocodingAPIError,
    DatabaseError,
    DatabaseConnectionError,
    TransactionError,
]

# Словарь для быстрого поиска исключения по коду ошибки
ERROR_CODE_TO_EXCEPTION: dict[ErrorCode, Type[BaseAppException]] = {
    ErrorCode.VALIDATION_ERROR: ValidationError,
    ErrorCode.NOT_FOUND: EntityNotFoundError,
    ErrorCode.ALREADY_EXISTS: EntityAlreadyExistsError,
    ErrorCode.AUTHENTICATION_REQUIRED: AuthenticationRequiredError,
    ErrorCode.ACCESS_DENIED: AccessDeniedError,
    ErrorCode.SUBSCRIPTION_REQUIRED: SubscriptionRequiredError,
    ErrorCode.SUBSCRIPTION_EXPIRED: SubscriptionExpiredError,
    ErrorCode.DAILY_LIMIT_REACHED: DailyLimitReachedError,
    ErrorCode.RATE_LIMIT_EXCEEDED: RateLimitExceededError,
    ErrorCode.INVALID_STATE_TRANSITION: InvalidStateTransitionError,
    ErrorCode.LLM_API_ERROR: LLMAPIError,
    ErrorCode.PAYMENT_API_ERROR: PaymentAPIError,
    ErrorCode.GEOCODING_API_ERROR: GeocodingAPIError,
    ErrorCode.DATABASE_ERROR: DatabaseError,
    ErrorCode.CONNECTION_ERROR: DatabaseConnectionError,
    ErrorCode.TRANSACTION_ERROR: TransactionError,
}


def get_exception_by_code(code: ErrorCode) -> Type[BaseAppException]:
    """
    Получить класс исключения по коду ошибки.

    Args:
        code: Код ошибки из ErrorCode

    Returns:
        Type[BaseAppException]: Класс исключения

    Raises:
        KeyError: Если код не найден
    """
    return ERROR_CODE_TO_EXCEPTION.get(code, BaseAppException)


def is_client_error(exc: BaseAppException) -> bool:
    """
    Проверить, является ли ошибка клиентской (4xx).

    Клиентские ошибки - это ошибки валидации, авторизации и т.д.

    Args:
        exc: Исключение

    Returns:
        bool: True если ошибка клиентская
    """
    client_error_codes = {
        ErrorCode.VALIDATION_ERROR,
        ErrorCode.NOT_FOUND,
        ErrorCode.ALREADY_EXISTS,
        ErrorCode.AUTHENTICATION_REQUIRED,
        ErrorCode.AUTHENTICATION_FAILED,
        ErrorCode.TOKEN_EXPIRED,
        ErrorCode.TOKEN_INVALID,
        ErrorCode.ACCESS_DENIED,
        ErrorCode.SUBSCRIPTION_REQUIRED,
        ErrorCode.SUBSCRIPTION_EXPIRED,
        ErrorCode.INSUFFICIENT_PERMISSIONS,
        ErrorCode.DAILY_LIMIT_REACHED,
        ErrorCode.RATE_LIMIT_EXCEEDED,
    }
    return exc.code in client_error_codes


def is_server_error(exc: BaseAppException) -> bool:
    """
    Проверить, является ли ошибка серверной (5xx).

    Серверные ошибки - это ошибки внешних сервисов, БД и т.д.

    Args:
        exc: Исключение

    Returns:
        bool: True если ошибка серверная
    """
    server_error_codes = {
        ErrorCode.UNKNOWN_ERROR,
        ErrorCode.EXTERNAL_SERVICE_ERROR,
        ErrorCode.LLM_API_ERROR,
        ErrorCode.PAYMENT_API_ERROR,
        ErrorCode.GEOCODING_API_ERROR,
        ErrorCode.DATABASE_ERROR,
        ErrorCode.CONNECTION_ERROR,
        ErrorCode.QUERY_ERROR,
        ErrorCode.TRANSACTION_ERROR,
    }
    return exc.code in server_error_codes


# Экспортируем все
__all__ = [
    # Базовые классы
    "BaseAppException",
    "ErrorCode",

    # Ошибки валидации
    "ValidationError",
    "MultipleValidationError",

    # Ошибки бизнес-логики
    "BusinessLogicError",
    "EntityNotFoundError",
    "EntityAlreadyExistsError",
    "InvalidStateTransitionError",

    # Ошибки доступа
    "AuthenticationRequiredError",
    "AccessDeniedError",
    "SubscriptionRequiredError",
    "SubscriptionExpiredError",

    # Ошибки лимитов
    "RateLimitExceededError",
    "DailyLimitReachedError",

    # Ошибки внешних сервисов
    "ExternalServiceError",
    "LLMAPIError",
    "PaymentAPIError",
    "GeocodingAPIError",

    # Ошибки базы данных
    "DatabaseError",
    "DatabaseConnectionError",
    "TransactionError",

    # Функции
    "handle_exception",
    "get_exception_by_code",
    "is_client_error",
    "is_server_error",

    # Типы
    "AppException",
    "ERROR_CODE_TO_EXCEPTION",
]