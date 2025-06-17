"""
Пользовательские исключения для приложения.

Этот модуль содержит все кастомные исключения,
используемые в приложении для обработки ошибок.
"""

from typing import Optional, Dict, Any


class BaseAppException(Exception):
    """Базовое исключение приложения."""

    def __init__(
            self,
            message: str,
            details: Optional[Dict[str, Any]] = None,
            status_code: Optional[int] = None
    ):
        super().__init__(message)
        self.message = message
        self.details = details or {}
        self.status_code = status_code


# Исключения для внешних API

class ExternalAPIError(BaseAppException):
    """Ошибка при работе с внешним API."""

    def __init__(
            self,
            message: str,
            service_name: Optional[str] = None,
            status_code: Optional[int] = None,
            details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, details, status_code)
        self.service_name = service_name


class APITimeoutError(ExternalAPIError):
    """Превышено время ожидания ответа от API."""

    def __init__(
            self,
            message: str,
            service_name: Optional[str] = None,
            timeout: Optional[float] = None
    ):
        super().__init__(message, service_name)
        self.timeout = timeout


class RateLimitExceededError(ExternalAPIError):
    """Превышен лимит запросов к API."""

    def __init__(
            self,
            message: str,
            retry_after: Optional[int] = None,
            service_name: Optional[str] = None
    ):
        super().__init__(message, service_name)
        self.retry_after = retry_after


class TokenLimitExceededError(ExternalAPIError):
    """Превышен лимит токенов для LLM."""

    def __init__(
            self,
            message: str,
            tokens_used: Optional[int] = None,
            token_limit: Optional[int] = None
    ):
        super().__init__(message)
        self.tokens_used = tokens_used
        self.token_limit = token_limit


# Исключения валидации

class ValidationError(BaseAppException):
    """Ошибка валидации данных."""

    def __init__(
            self,
            message: str,
            field: Optional[str] = None,
            value: Optional[Any] = None
    ):
        super().__init__(message)
        self.field = field
        self.value = value


# Исключения для LLM

class LLMProviderError(BaseAppException):
    """Ошибка провайдера LLM."""
    pass


# Исключения бизнес-логики

class BusinessLogicError(BaseAppException):
    """Ошибка бизнес-логики."""
    pass


class InsufficientCreditsError(BusinessLogicError):
    """Недостаточно кредитов для выполнения операции."""

    def __init__(
            self,
            message: str,
            required_credits: Optional[int] = None,
            available_credits: Optional[int] = None
    ):
        super().__init__(message)
        self.required_credits = required_credits
        self.available_credits = available_credits


class UserNotFoundError(BusinessLogicError):
    """Пользователь не найден."""

    def __init__(self, user_id: Optional[int] = None, username: Optional[str] = None):
        message = "Пользователь не найден"
        if user_id:
            message = f"Пользователь с ID {user_id} не найден"
        elif username:
            message = f"Пользователь {username} не найден"
        super().__init__(message)
        self.user_id = user_id
        self.username = username


class ResourceNotFoundError(BusinessLogicError):
    """Ресурс не найден."""

    def __init__(
            self,
            resource_type: str,
            resource_id: Optional[Any] = None
    ):
        message = f"{resource_type} не найден"
        if resource_id:
            message = f"{resource_type} с ID {resource_id} не найден"
        super().__init__(message)
        self.resource_type = resource_type
        self.resource_id = resource_id


class PermissionDeniedError(BusinessLogicError):
    """Отказано в доступе."""

    def __init__(
            self,
            message: str = "Недостаточно прав для выполнения операции",
            required_permission: Optional[str] = None
    ):
        super().__init__(message)
        self.required_permission = required_permission


# Исключения базы данных

class DatabaseError(BaseAppException):
    """Ошибка базы данных."""
    pass


class DuplicateEntryError(DatabaseError):
    """Попытка создать дублирующую запись."""

    def __init__(
            self,
            message: str,
            table: Optional[str] = None,
            field: Optional[str] = None,
            value: Optional[Any] = None
    ):
        super().__init__(message)
        self.table = table
        self.field = field
        self.value = value


# Исключения аутентификации

class AuthenticationError(BaseAppException):
    """Ошибка аутентификации."""
    status_code = 401


class InvalidCredentialsError(AuthenticationError):
    """Неверные учетные данные."""

    def __init__(self):
        super().__init__("Неверный логин или пароль")


class TokenExpiredError(AuthenticationError):
    """Токен истек."""

    def __init__(self):
        super().__init__("Токен аутентификации истек")


class InvalidTokenError(AuthenticationError):
    """Недействительный токен."""

    def __init__(self):
        super().__init__("Недействительный токен аутентификации")


# Исключения конфигурации

class ConfigurationError(BaseAppException):
    """Ошибка конфигурации."""

    def __init__(
            self,
            message: str,
            config_key: Optional[str] = None
    ):
        super().__init__(message)
        self.config_key = config_key


class MissingConfigurationError(ConfigurationError):
    """Отсутствует обязательная конфигурация."""

    def __init__(self, config_key: str):
        super().__init__(
            f"Отсутствует обязательный параметр конфигурации: {config_key}",
            config_key
        )


# Экспорт всех исключений
__all__ = [
    # Базовые
    'BaseAppException',

    # Внешние API
    'ExternalAPIError',
    'APITimeoutError',
    'RateLimitExceededError',
    'TokenLimitExceededError',

    # Валидация
    'ValidationError',

    # LLM
    'LLMProviderError',

    # Бизнес-логика
    'BusinessLogicError',
    'InsufficientCreditsError',
    'UserNotFoundError',
    'ResourceNotFoundError',
    'PermissionDeniedError',

    # База данных
    'DatabaseError',
    'DuplicateEntryError',

    # Аутентификация
    'AuthenticationError',
    'InvalidCredentialsError',
    'TokenExpiredError',
    'InvalidTokenError',

    # Конфигурация
    'ConfigurationError',
    'MissingConfigurationError',
]