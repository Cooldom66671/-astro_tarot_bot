# Астро-Таро Ассистент

Telegram-бот для персонализированных услуг в области натальной астрологии и тарологии.

## Структура проекта

- `config/` - Конфигурации приложения
- `core/` - Бизнес-логика и сущности
- `infrastructure/` - Работа с БД и внешними сервисами
- `bot/` - Telegram-бот логика
- `services/` - Сервисный слой
- `workers/` - Фоновые задачи
- `api/` - REST API для админки

## Установка

1. Клонируйте репозиторий
2. Создайте виртуальное окружение: `python -m venv venv`
3. Активируйте окружение: `source venv/bin/activate`
4. Установите зависимости: `pip install -r requirements.txt`
5. Скопируйте `.env.example` в `.env` и заполните переменные
6. Запустите миграции: `alembic upgrade head`
7. Запустите бота: `python main.py`

## Разработка

Используйте pre-commit hooks:
```bash
pre-commit install
```

## Docker

```bash
docker-compose up -d
```
# -astro_tarot_bot
