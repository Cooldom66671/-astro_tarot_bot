"""
Модуль кастомных исключений для Астро-Таро Бота.

Этот модуль содержит все пользовательские исключения приложения,
организованные по слоям и типам ошибок:
- Базовые исключения приложения
- Ошибки валидации данных
- Ошибки бизнес-логики
- Ошибки доступа и авторизации
- Ошибки внешних сервисов
- Ошибки базы данных

Использование:
    from core.exceptions import ValidationError, SubscriptionRequiredError

    # В бизнес-логике
    if not user.has_subscription:
        raise SubscriptionRequiredError("Функция доступна только по подписке")

    # В валидации
    if not is_valid_name(name):
        raise ValidationError("name", "Недопустимые символы в имени")
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum

from config import logger


class ErrorCode(str, Enum):
    """Коды ошибок для API и логирования."""

    # Общие ошибки (1xxx)
    UNKNOWN_ERROR = "1000"
    VALIDATION_ERROR = "1001"
    NOT_FOUND = "1002"
    ALREADY_EXISTS = "1003"

    # Ошибки аутентификации (2xxx)
    AUTHENTICATION_REQUIRED = "2000"
    AUTHENTICATION_FAILED = "2001"
    TOKEN_EXPIRED = "2002"
    TOKEN_INVALID = "2003"

    # Ошибки авторизации (3xxx)
    ACCESS_DENIED = "3000"
    SUBSCRIPTION_REQUIRED = "3001"
    SUBSCRIPTION_EXPIRED = "3002"
    INSUFFICIENT_PERMISSIONS = "3003"

    # Ошибки бизнес-логики (4xxx)
    BUSINESS_LOGIC_ERROR = "4000"
    DAILY_LIMIT_REACHED = "4001"
    RATE_LIMIT_EXCEEDED = "4002"
    INVALID_STATE_TRANSITION = "4003"
    OPERATION_NOT_ALLOWED = "4004"

    # Ошибки внешних сервисов (5xxx)
    EXTERNAL_SERVICE_ERROR = "5000"
    LLM_API_ERROR = "5001"
    PAYMENT_API_ERROR = "5002"
    GEOCODING_API_ERROR = "5003"
    TELEGRAM_API_ERROR = "5004"

    # Ошибки базы данных (6xxx)
    DATABASE_ERROR = "6000"
    CONNECTION_ERROR = "6001"
    QUERY_ERROR = "6002"
    TRANSACTION_ERROR = "6003"


class BaseAppException(Exception):
    """
    Базовое исключение для всех ошибок приложения.

    Attributes:
        message: Сообщение об ошибке
        code: Код ошибки из ErrorCode
        details: Дополнительные детали ошибки
        user_message: Сообщение для показа пользователю
    """

    def __init__(
            self,
            message: str,
            code: ErrorCode = ErrorCode.UNKNOWN_ERROR,
            details: Optional[Dict[str, Any]] = None,
            user_message: Optional[str] = None
    ):
        """
        Инициализация базового исключения.

        Args:
            message: Техническое сообщение об ошибке
            code: Код ошибки
            details: Дополнительные данные об ошибке
            user_message: Сообщение для пользователя (если отличается)
        """
        self.message = message
        self.code = code
        self.details = details or {}
        self.user_message = user_message or message
        self.timestamp = datetime.utcnow()

        # Логируем ошибку
        logger.error(
            f"{self.__class__.__name__}: {message}",
            extra={
                "error_code": code.value,
                "error_details": details,
                "error_class": self.__class__.__name__
            }
        )

        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        """Преобразовать исключение в словарь для API ответа."""
        return {
            "error": {
                "code": self.code.value,
                "message": self.user_message,
                "details": self.details,
                "timestamp": self.timestamp.isoformat()
            }
        }


# ===== ОШИБКИ ВАЛИДАЦИИ =====

class ValidationError(BaseAppException):
    """
    Ошибка валидации данных.

    Используется когда входные данные не соответствуют ожидаемому формату.
    """

    def __init__(
            self,
            field: str,
            message: str,
            value: Any = None,
            expected_format: Optional[str] = None
    ):
        """
        Args:
            field: Название поля с ошибкой
            message: Описание ошибки
            value: Некорректное значение
            expected_format: Ожидаемый формат
        """
        details = {
            "field": field,
            "value": str(value) if value is not None else None,
            "expected_format": expected_format
        }

        super().__init__(
            message=f"Ошибка валидации поля '{field}': {message}",
            code=ErrorCode.VALIDATION_ERROR,
            details=details,
            user_message=message
        )


class MultipleValidationError(BaseAppException):
    """Множественные ошибки валидации."""

    def __init__(self, errors: List[ValidationError]):
        """
        Args:
            errors: Список ошибок валидации
        """
        self.errors = errors

        details = {
            "errors": [
                {
                    "field": e.details["field"],
                    "message": e.user_message,
                    "value": e.details.get("value")
                }
                for e in errors
            ]
        }

        super().__init__(
            message=f"Обнаружено {len(errors)} ошибок валидации",
            code=ErrorCode.VALIDATION_ERROR,
            details=details,
            user_message="Проверьте правильность введенных данных"
        )


# ===== ОШИБКИ БИЗНЕС-ЛОГИКИ =====

class BusinessLogicError(BaseAppException):
    """Базовая ошибка бизнес-логики."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            code=ErrorCode.BUSINESS_LOGIC_ERROR,
            details=details
        )


class EntityNotFoundError(BaseAppException):
    """Сущность не найдена."""

    def __init__(
            self,
            entity_type: str,
            entity_id: Any,
            details: Optional[Dict[str, Any]] = None
    ):
        """
        Args:
            entity_type: Тип сущности (User, Subscription и т.д.)
            entity_id: ID сущности
            details: Дополнительные детали
        """
        super().__init__(
            message=f"{entity_type} с ID {entity_id} не найден",
            code=ErrorCode.NOT_FOUND,
            details={"entity_type": entity_type, "entity_id": str(entity_id), **(details or {})},
            user_message=f"Запрашиваемый объект не найден"
        )


class EntityAlreadyExistsError(BaseAppException):
    """Сущность уже существует."""

    def __init__(
            self,
            entity_type: str,
            unique_field: str,
            value: Any
    ):
        """
        Args:
            entity_type: Тип сущности
            unique_field: Уникальное поле
            value: Значение, которое уже существует
        """
        super().__init__(
            message=f"{entity_type} с {unique_field}='{value}' уже существует",
            code=ErrorCode.ALREADY_EXISTS,
            details={"entity_type": entity_type, "field": unique_field, "value": str(value)},
            user_message=f"Такой объект уже существует"
        )


class InvalidStateTransitionError(BaseAppException):
    """Недопустимый переход состояния."""

    def __init__(
            self,
            entity_type: str,
            current_state: str,
            target_state: str,
            allowed_states: Optional[List[str]] = None
    ):
        """
        Args:
            entity_type: Тип сущности
            current_state: Текущее состояние
            target_state: Целевое состояние
            allowed_states: Разрешенные состояния
        """
        super().__init__(
            message=f"Невозможен переход {entity_type} из состояния '{current_state}' в '{target_state}'",
            code=ErrorCode.INVALID_STATE_TRANSITION,
            details={
                "entity_type": entity_type,
                "current_state": current_state,
                "target_state": target_state,
                "allowed_states": allowed_states
            },
            user_message="Операция невозможна в текущем состоянии"
        )


# ===== ОШИБКИ ДОСТУПА =====

class AuthenticationRequiredError(BaseAppException):
    """Требуется аутентификация."""

    def __init__(self, resource: Optional[str] = None):
        super().__init__(
            message=f"Требуется аутентификация для доступа к {resource or 'ресурсу'}",
            code=ErrorCode.AUTHENTICATION_REQUIRED,
            details={"resource": resource},
            user_message="Необходимо войти в систему"
        )


class AccessDeniedError(BaseAppException):
    """Доступ запрещен."""

    def __init__(
            self,
            resource: str,
            reason: Optional[str] = None,
            required_permission: Optional[str] = None
    ):
        """
        Args:
            resource: Ресурс, к которому запрещен доступ
            reason: Причина отказа
            required_permission: Требуемое разрешение
        """
        super().__init__(
            message=f"Доступ к {resource} запрещен: {reason or 'недостаточно прав'}",
            code=ErrorCode.ACCESS_DENIED,
            details={
                "resource": resource,
                "reason": reason,
                "required_permission": required_permission
            },
            user_message="У вас нет доступа к этой функции"
        )


class SubscriptionRequiredError(BaseAppException):
    """Требуется подписка."""

    def __init__(
            self,
            feature: str,
            required_plan: Optional[str] = None,
            current_plan: Optional[str] = None
    ):
        """
        Args:
            feature: Функция, требующая подписку
            required_plan: Требуемый тарифный план
            current_plan: Текущий план пользователя
        """
        super().__init__(
            message=f"Функция '{feature}' требует подписку",
            code=ErrorCode.SUBSCRIPTION_REQUIRED,
            details={
                "feature": feature,
                "required_plan": required_plan,
                "current_plan": current_plan
            },
            user_message=f"Функция '{feature}' доступна только по подписке"
        )


class SubscriptionExpiredError(BaseAppException):
    """Подписка истекла."""

    def __init__(self, expired_at: datetime):
        super().__init__(
            message=f"Подписка истекла {expired_at.strftime('%d.%m.%Y')}",
            code=ErrorCode.SUBSCRIPTION_EXPIRED,
            details={"expired_at": expired_at.isoformat()},
            user_message="Ваша подписка истекла. Пожалуйста, продлите её для продолжения."
        )


# ===== ОШИБКИ ЛИМИТОВ =====

class RateLimitExceededError(BaseAppException):
    """Превышен лимит запросов."""

    def __init__(
            self,
            limit_type: str,
            limit: int,
            period: str,
            retry_after: Optional[int] = None
    ):
        """
        Args:
            limit_type: Тип лимита (per_minute, per_hour и т.д.)
            limit: Значение лимита
            period: Период (minute, hour, day)
            retry_after: Через сколько секунд можно повторить
        """
        super().__init__(
            message=f"Превышен лимит: {limit} запросов в {period}",
            code=ErrorCode.RATE_LIMIT_EXCEEDED,
            details={
                "limit_type": limit_type,
                "limit": limit,
                "period": period,
                "retry_after": retry_after
            },
            user_message="Слишком много запросов. Пожалуйста, подождите немного."
        )


class DailyLimitReachedError(BaseAppException):
    """Достигнут дневной лимит."""

    def __init__(
            self,
            resource: str,
            limit: int,
            used: int,
            reset_at: Optional[datetime] = None
    ):
        """
        Args:
            resource: Ресурс с лимитом
            limit: Дневной лимит
            used: Использовано
            reset_at: Время сброса лимита
        """
        super().__init__(
            message=f"Достигнут дневной лимит для {resource}: {used}/{limit}",
            code=ErrorCode.DAILY_LIMIT_REACHED,
            details={
                "resource": resource,
                "limit": limit,
                "used": used,
                "reset_at": reset_at.isoformat() if reset_at else None
            },
            user_message=f"Вы достигли дневного лимита. Попробуйте завтра."
        )


# ===== ОШИБКИ ВНЕШНИХ СЕРВИСОВ =====

class ExternalServiceError(BaseAppException):
    """Базовая ошибка внешнего сервиса."""

    def __init__(
            self,
            service_name: str,
            message: str,
            status_code: Optional[int] = None,
            response_data: Optional[Dict[str, Any]] = None
    ):
        """
        Args:
            service_name: Название сервиса
            message: Сообщение об ошибке
            status_code: HTTP статус код
            response_data: Данные ответа
        """
        super().__init__(
            message=f"Ошибка сервиса {service_name}: {message}",
            code=ErrorCode.EXTERNAL_SERVICE_ERROR,
            details={
                "service": service_name,
                "status_code": status_code,
                "response": response_data
            },
            user_message="Временная ошибка сервиса. Попробуйте позже."
        )


class LLMAPIError(ExternalServiceError):
    """Ошибка API языковой модели."""

    def __init__(
            self,
            provider: str,
            message: str,
            model: Optional[str] = None,
            **kwargs
    ):
        super().__init__(
            service_name=f"LLM ({provider})",
            message=message,
            **kwargs
        )
        self.code = ErrorCode.LLM_API_ERROR
        if model:
            self.details["model"] = model


class PaymentAPIError(ExternalServiceError):
    """Ошибка платежной системы."""

    def __init__(
            self,
            provider: str,
            message: str,
            payment_id: Optional[str] = None,
            **kwargs
    ):
        super().__init__(
            service_name=f"Payment ({provider})",
            message=message,
            **kwargs
        )
        self.code = ErrorCode.PAYMENT_API_ERROR
        if payment_id:
            self.details["payment_id"] = payment_id
        self.user_message = "Ошибка при обработке платежа"


class GeocodingAPIError(ExternalServiceError):
    """Ошибка сервиса геокодинга."""

    def __init__(self, message: str, location: Optional[str] = None, **kwargs):
        super().__init__(
            service_name="Geocoding",
            message=message,
            **kwargs
        )
        self.code = ErrorCode.GEOCODING_API_ERROR
        if location:
            self.details["location"] = location
        self.user_message = "Не удалось определить координаты города"


# ===== ОШИБКИ БАЗЫ ДАННЫХ =====

class DatabaseError(BaseAppException):
    """Базовая ошибка базы данных."""

    def __init__(
            self,
            message: str,
            query: Optional[str] = None,
            params: Optional[Dict[str, Any]] = None
    ):
        """
        Args:
            message: Сообщение об ошибке
            query: SQL запрос
            params: Параметры запроса
        """
        super().__init__(
            message=message,
            code=ErrorCode.DATABASE_ERROR,
            details={"query": query, "params": params},
            user_message="Ошибка при работе с базой данных"
        )


class DatabaseConnectionError(DatabaseError):
    """Ошибка подключения к БД."""

    def __init__(self, message: str, host: Optional[str] = None):
        super().__init__(message=f"Ошибка подключения к БД: {message}")
        self.code = ErrorCode.CONNECTION_ERROR
        if host:
            self.details["host"] = host


class TransactionError(DatabaseError):
    """Ошибка транзакции."""

    def __init__(self, message: str, operation: Optional[str] = None):
        super().__init__(message=f"Ошибка транзакции: {message}")
        self.code = ErrorCode.TRANSACTION_ERROR
        if operation:
            self.details["operation"] = operation


# ===== ФУНКЦИИ-ПОМОЩНИКИ =====

def handle_exception(exc: BaseAppException) -> Dict[str, Any]:
    """
    Обработать исключение и вернуть данные для ответа.

    Args:
        exc: Исключение приложения

    Returns:
        Dict с данными ошибки для API ответа
    """
    return exc.to_dict()


# Экспорт всех исключений
__all__ = [
    # Базовые
    "BaseAppException",
    "ErrorCode",

    # Валидация
    "ValidationError",
    "MultipleValidationError",

    # Бизнес-логика
    "BusinessLogicError",
    "EntityNotFoundError",
    "EntityAlreadyExistsError",
    "InvalidStateTransitionError",

    # Доступ
    "AuthenticationRequiredError",
    "AccessDeniedError",
    "SubscriptionRequiredError",
    "SubscriptionExpiredError",

    # Лимиты
    "RateLimitExceededError",
    "DailyLimitReachedError",

    # Внешние сервисы
    "ExternalServiceError",
    "LLMAPIError",
    "PaymentAPIError",
    "GeocodingAPIError",

    # База данных
    "DatabaseError",
    "DatabaseConnectionError",
    "TransactionError",

    # Функции
    "handle_exception",
]