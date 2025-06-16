"""
FSM состояния для управления диалогами.

Этот модуль содержит все состояния для:
- Онбординга новых пользователей
- Процессов ввода данных
- Мультишаговых операций
- Управления контекстом диалогов

Автор: AI Assistant
Дата создания: 2024-12-30
"""

from aiogram.fsm.state import State, StatesGroup


class OnboardingStates(StatesGroup):
    """Состояния процесса онбординга новых пользователей."""

    # Приветствие и знакомство
    welcome = State()

    # Ввод имени
    waiting_for_name = State()

    # Выбор интересов
    selecting_interests = State()

    # Ввод данных рождения (опционально)
    asking_birth_data = State()
    waiting_for_birth_date = State()
    waiting_for_birth_time = State()
    waiting_for_birth_place = State()

    # Настройка уведомлений
    setting_notifications = State()

    # Завершение онбординга
    completing = State()


class TarotStates(StatesGroup):
    """Состояния для раздела Таро."""

    # Выбор расклада
    selecting_spread = State()

    # Ввод вопроса для расклада
    waiting_for_question = State()

    # Процесс выбора карт
    selecting_cards = State()
    card_position_1 = State()
    card_position_2 = State()
    card_position_3 = State()
    card_position_4 = State()
    card_position_5 = State()
    card_position_6 = State()
    card_position_7 = State()
    card_position_8 = State()
    card_position_9 = State()
    card_position_10 = State()

    # Просмотр результата
    viewing_result = State()

    # Сохранение расклада
    saving_spread = State()
    adding_notes = State()

    # Обучение
    learning_menu = State()
    viewing_lesson = State()

    # Поиск в истории
    searching_history = State()


class AstrologyStates(StatesGroup):
    """Состояния для раздела астрологии."""

    # Ввод данных рождения
    waiting_for_date = State()
    waiting_for_time = State()
    waiting_for_place = State()
    confirming_data = State()

    # Настройки натальной карты
    configuring_chart = State()
    selecting_house_system = State()
    selecting_planets = State()

    # Транзиты
    selecting_transit_period = State()
    filtering_transits = State()

    # Синастрия (совместимость)
    synastry_partner_data = State()
    synastry_waiting_date = State()
    synastry_waiting_time = State()
    synastry_waiting_place = State()

    # Поиск города
    searching_city = State()

    # Настройки гороскопа
    horoscope_preferences = State()


class SubscriptionStates(StatesGroup):
    """Состояния для управления подпиской."""

    # Выбор плана
    selecting_plan = State()
    viewing_plan_details = State()

    # Выбор периода оплаты
    selecting_period = State()

    # Промокод
    waiting_for_promo = State()

    # Выбор способа оплаты
    selecting_payment_method = State()

    # Процесс оплаты
    processing_payment = State()
    waiting_for_payment = State()

    # Данные для оплаты
    entering_card_data = State()
    entering_crypto_address = State()

    # Отмена подписки
    cancellation_reason = State()
    cancellation_feedback = State()

    # Управление картами
    managing_cards = State()
    adding_card = State()


class FeedbackStates(StatesGroup):
    """Состояния для обратной связи."""

    # Тип обратной связи
    selecting_type = State()

    # Ввод сообщения
    waiting_for_text = State()

    # Дополнительные данные
    waiting_for_screenshot = State()
    waiting_for_contact = State()

    # Оценка
    rating_experience = State()

    # Отзыв о конкретной функции
    feature_feedback = State()


class ProfileStates(StatesGroup):
    """Состояния для управления профилем."""

    # Редактирование профиля
    editing_name = State()
    editing_timezone = State()
    editing_language = State()

    # Настройки приватности
    privacy_settings = State()

    # Удаление аккаунта
    delete_confirmation = State()
    delete_reason = State()

    # Экспорт данных
    export_format = State()
    export_confirmation = State()


class NotificationStates(StatesGroup):
    """Состояния для настройки уведомлений."""

    # Типы уведомлений
    selecting_types = State()

    # Время уведомлений
    setting_daily_time = State()
    setting_weekly_day = State()

    # Настройка контента
    customizing_content = State()


class AdminStates(StatesGroup):
    """Состояния для административных функций."""

    # Рассылка
    broadcast_type = State()
    broadcast_content = State()
    broadcast_confirmation = State()

    # Управление пользователями
    user_search = State()
    user_action = State()

    # Промокоды
    creating_promo = State()
    promo_settings = State()

    # Статистика
    stats_period = State()
    stats_export = State()

    # Модерация
    review_feedback = State()
    review_action = State()


class SupportStates(StatesGroup):
    """Состояния для поддержки пользователей."""

    # Категория проблемы
    selecting_category = State()

    # Описание проблемы
    describing_issue = State()

    # Дополнительная информация
    providing_details = State()
    waiting_for_screenshots = State()

    # Чат с поддержкой
    in_support_chat = State()

    # Оценка поддержки
    rating_support = State()


class PaymentStates(StatesGroup):
    """Состояния для процесса оплаты."""

    # Выбор товара/услуги
    selecting_item = State()

    # Подтверждение
    confirming_purchase = State()

    # Ввод данных оплаты
    payment_method = State()
    card_details = State()
    billing_info = State()

    # Ожидание оплаты
    waiting_payment = State()

    # Результат
    payment_success = State()
    payment_failed = State()


class SearchStates(StatesGroup):
    """Состояния для поиска."""

    # Поиск по раскладам
    searching_spreads = State()

    # Поиск по датам
    searching_by_date = State()

    # Поиск по картам
    searching_by_cards = State()

    # Фильтры
    applying_filters = State()


class LearningStates(StatesGroup):
    """Состояния для обучающих материалов."""

    # Выбор курса
    selecting_course = State()

    # Прохождение урока
    viewing_lesson = State()

    # Тест
    taking_quiz = State()
    answering_question = State()

    # Результаты
    viewing_results = State()


class SettingsStates(StatesGroup):
    """Состояния для настроек."""

    # Основные настройки
    main_settings = State()

    # Язык
    selecting_language = State()

    # Часовой пояс
    selecting_timezone = State()

    # Тема оформления
    selecting_theme = State()

    # Сброс настроек
    reset_confirmation = State()


# Группировка состояний по функциональности
USER_STATES = [
    OnboardingStates,
    ProfileStates,
    NotificationStates,
    SettingsStates
]

FEATURE_STATES = [
    TarotStates,
    AstrologyStates,
    LearningStates,
    SearchStates
]

PAYMENT_STATES = [
    SubscriptionStates,
    PaymentStates
]

SUPPORT_STATES = [
    FeedbackStates,
    SupportStates
]

ADMIN_STATES = [
    AdminStates
]

# Все состояния
ALL_STATES = USER_STATES + FEATURE_STATES + PAYMENT_STATES + SUPPORT_STATES + ADMIN_STATES


class StateNames:
    """Человекочитаемые названия состояний для логирования."""

    NAMES = {
        # Онбординг
        OnboardingStates.welcome: "Приветствие",
        OnboardingStates.waiting_for_name: "Ожидание имени",
        OnboardingStates.selecting_interests: "Выбор интересов",
        OnboardingStates.waiting_for_birth_date: "Ввод даты рождения",

        # Таро
        TarotStates.selecting_spread: "Выбор расклада",
        TarotStates.waiting_for_question: "Ввод вопроса",
        TarotStates.selecting_cards: "Выбор карт",

        # Астрология
        AstrologyStates.waiting_for_date: "Ввод даты рождения",
        AstrologyStates.waiting_for_time: "Ввод времени рождения",
        AstrologyStates.waiting_for_place: "Ввод места рождения",

        # Подписка
        SubscriptionStates.selecting_plan: "Выбор тарифа",
        SubscriptionStates.waiting_for_promo: "Ввод промокода",
        SubscriptionStates.processing_payment: "Обработка платежа",

        # Обратная связь
        FeedbackStates.waiting_for_text: "Ввод отзыва",

        # Поддержка
        SupportStates.describing_issue: "Описание проблемы",
        SupportStates.in_support_chat: "Чат с поддержкой",
    }

    @classmethod
    def get_name(cls, state: State) -> str:
        """Получить человекочитаемое название состояния."""
        return cls.NAMES.get(state, str(state))


class StateUtils:
    """Утилиты для работы с состояниями."""

    @staticmethod
    def is_input_state(state: State) -> bool:
        """Проверить, является ли состояние ожиданием ввода."""
        input_states = [
            OnboardingStates.waiting_for_name,
            TarotStates.waiting_for_question,
            AstrologyStates.waiting_for_date,
            AstrologyStates.waiting_for_time,
            AstrologyStates.waiting_for_place,
            SubscriptionStates.waiting_for_promo,
            FeedbackStates.waiting_for_text,
            SupportStates.describing_issue,
        ]
        return state in input_states

    @staticmethod
    def is_payment_state(state: State) -> bool:
        """Проверить, относится ли состояние к оплате."""
        payment_states = []
        for state_group in PAYMENT_STATES:
            payment_states.extend(state_group.__all_states__)
        return state in payment_states

    @staticmethod
    def is_admin_state(state: State) -> bool:
        """Проверить, относится ли состояние к админ функциям."""
        admin_states = []
        for state_group in ADMIN_STATES:
            admin_states.extend(state_group.__all_states__)
        return state in admin_states

    @staticmethod
    def get_timeout(state: State) -> int:
        """Получить таймаут для состояния в секундах."""
        timeouts = {
            # Быстрые действия - 5 минут
            OnboardingStates.waiting_for_name: 300,
            TarotStates.waiting_for_question: 300,

            # Ввод данных - 10 минут
            AstrologyStates.waiting_for_date: 600,
            AstrologyStates.waiting_for_time: 600,
            AstrologyStates.waiting_for_place: 600,

            # Оплата - 15 минут
            SubscriptionStates.processing_payment: 900,
            PaymentStates.waiting_payment: 900,

            # Поддержка - 30 минут
            SupportStates.in_support_chat: 1800,

            # По умолчанию - 10 минут
            "default": 600
        }

        return timeouts.get(state, timeouts["default"])

    @staticmethod
    def get_cancel_message(state: State) -> str:
        """Получить сообщение для отмены состояния."""
        messages = {
            OnboardingStates.waiting_for_name: "Вы можете ввести имя позже в настройках профиля",
            TarotStates.waiting_for_question: "Вы можете сделать расклад без конкретного вопроса",
            AstrologyStates.waiting_for_date: "Данные рождения можно добавить позже в профиле",
            SubscriptionStates.waiting_for_promo: "Продолжим без промокода",
            FeedbackStates.waiting_for_text: "Спасибо за желание оставить отзыв! Вы можете сделать это позже",
            SupportStates.describing_issue: "Если нужна помощь, вы всегда можете написать в /support"
        }

        default = "Действие отменено. Возвращаемся в главное меню."
        return messages.get(state, default)