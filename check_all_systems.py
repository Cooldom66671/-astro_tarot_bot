"""
Расширенная проверка всех систем проекта.
"""

import asyncio
import sys
import os
from pathlib import Path


async def check_database_connection():
    """Проверка подключения к PostgreSQL."""
    print("🔍 Проверка подключения к базе данных...")
    try:
        from infrastructure.database import db_connection

        # Проверяем подключение
        health = await db_connection.health_check()
        if health.get('status') == 'healthy':
            print("✅ База данных доступна")
            print(f"   Версия: {health.get('version', 'unknown')}")
            return True
        else:
            print("❌ База данных недоступна")
            print(f"   Статус: {health}")
            return False
    except Exception as e:
        print(f"❌ Ошибка подключения к БД: {e}")
        print("\n💡 Решение:")
        print("1. Убедитесь, что PostgreSQL запущен:")
        print("   brew services start postgresql@16  # macOS")
        print("   sudo systemctl start postgresql    # Linux")
        print("2. Проверьте DATABASE_URL в .env файле")
        print("3. Создайте базу данных если её нет:")
        print("   createdb astrotarot_db")
        return False


async def check_redis_connection():
    """Проверка подключения к Redis."""
    print("\n🔍 Проверка подключения к Redis...")
    try:
        import redis.asyncio as redis
        from config import settings

        # Получаем URL из настроек
        redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

        # Подключаемся
        r = redis.from_url(redis_url)
        await r.ping()
        await r.close()

        print("✅ Redis доступен")
        return True
    except Exception as e:
        print(f"❌ Ошибка подключения к Redis: {e}")
        print("\n💡 Решение:")
        print("1. Убедитесь, что Redis запущен:")
        print("   brew services start redis  # macOS")
        print("   sudo systemctl start redis # Linux")
        print("2. Проверьте REDIS_URL в .env файле")
        return False


def check_bot_token():
    """Проверка корректности токена бота."""
    print("\n🔍 Проверка токена бота...")
    try:
        from config import settings

        token = settings.bot.token.get_secret_value()

        # Базовая проверка формата
        if ':' not in token or len(token) < 40:
            print("❌ Токен имеет неверный формат")
            return False

        print("✅ Токен загружен и имеет правильный формат")
        print(f"   ID бота: {token.split(':')[0]}")
        return True
    except Exception as e:
        print(f"❌ Ошибка с токеном: {e}")
        return False


def check_migrations():
    """Проверка состояния миграций."""
    print("\n🔍 Проверка миграций Alembic...")

    # Проверяем наличие alembic.ini
    if not Path('alembic.ini').exists():
        print("❌ Файл alembic.ini не найден")
        print("\n💡 Решение:")
        print("1. Инициализируйте Alembic:")
        print("   alembic init alembic")
        return False

    # Проверяем директорию версий
    versions_dir = Path('alembic/versions')
    if not versions_dir.exists():
        print("❌ Директория alembic/versions не найдена")
        print("\n💡 Решение:")
        print("1. Создайте директорию:")
        print("   mkdir -p alembic/versions")
        return False

    # Проверяем наличие миграций
    migrations = list(versions_dir.glob('*.py'))
    if not migrations:
        print("⚠️  Нет миграций")
        print("\n💡 Создайте первую миграцию:")
        print("   alembic revision --autogenerate -m 'Initial migration'")
        return False

    print(f"✅ Найдено миграций: {len(migrations)}")
    return True


def check_external_apis():
    """Проверка настроек внешних API."""
    print("\n🔍 Проверка внешних API...")

    apis = {
        'OPENAI_API_KEY': 'OpenAI API',
        'ANTHROPIC_API_KEY': 'Anthropic API',
        'YOOKASSA_SHOP_ID': 'ЮKassa',
        'TELEGRAM_PAYMENTS_TOKEN': 'Telegram Payments'
    }

    configured = []
    missing = []

    for env_var, name in apis.items():
        if os.getenv(env_var):
            configured.append(name)
        else:
            missing.append(name)

    if configured:
        print(f"✅ Настроены: {', '.join(configured)}")

    if missing:
        print(f"⚠️  Не настроены: {', '.join(missing)}")
        print("   (Это нормально, если вы их пока не используете)")

    return True


def check_file_permissions():
    """Проверка прав на директории."""
    print("\n🔍 Проверка прав доступа к директориям...")

    dirs_to_check = ['logs', 'uploads', 'backups']
    all_ok = True

    for dir_name in dirs_to_check:
        dir_path = Path(dir_name)
        if dir_path.exists():
            # Проверяем возможность записи
            test_file = dir_path / '.test_write'
            try:
                test_file.touch()
                test_file.unlink()
                print(f"✅ {dir_name}/ - запись разрешена")
            except Exception as e:
                print(f"❌ {dir_name}/ - нет прав на запись: {e}")
                all_ok = False
        else:
            print(f"❌ {dir_name}/ - директория не существует")
            all_ok = False

    if not all_ok:
        print("\n💡 Решение:")
        print("1. Создайте директории и установите права:")
        print("   mkdir -p logs uploads backups")
        print("   chmod 755 logs uploads backups")

    return all_ok


async def main():
    """Основная функция проверки."""
    print("=" * 60)
    print("🔍 РАСШИРЕННАЯ ПРОВЕРКА ВСЕХ СИСТЕМ")
    print("=" * 60)

    # Проверки
    checks = [
        ("Токен бота", check_bot_token),
        ("База данных", check_database_connection),
        ("Redis", check_redis_connection),
        ("Миграции", check_migrations),
        ("Внешние API", check_external_apis),
        ("Права доступа", check_file_permissions),
    ]

    results = {}

    for name, check_func in checks:
        try:
            if asyncio.iscoroutinefunction(check_func):
                results[name] = await check_func()
            else:
                results[name] = check_func()
        except Exception as e:
            print(f"\n❌ Ошибка при проверке {name}: {e}")
            results[name] = False

    # Итоговый отчет
    print("\n" + "=" * 60)
    print("📊 ИТОГОВЫЙ ОТЧЕТ:")
    print("=" * 60)

    failed = []
    for name, result in results.items():
        status = "✅" if result else "❌"
        print(f"{status} {name}")
        if not result:
            failed.append(name)

    print("=" * 60)

    if not failed:
        print("\n🎉 Все проверки пройдены успешно!")
        print("\n🚀 Следующий шаг: запуск миграций")
        print("   alembic upgrade head")
        print("\n🤖 Затем запуск бота:")
        print("   python main.py")
    else:
        print(f"\n⚠️  Не пройдены проверки: {', '.join(failed)}")
        print("\nИсправьте ошибки выше и запустите проверку снова.")

    return len(failed) == 0


if __name__ == "__main__":
    # Для Windows
    if sys.platform.startswith('win'):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    # Запускаем проверки
    success = asyncio.run(main())
    sys.exit(0 if success else 1)