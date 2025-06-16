"""
Скрипт для проверки корректности установки проекта.
"""

import sys
import importlib
import os
from pathlib import Path


def check_python_version():
    """Проверка версии Python."""
    print(f"Python версия: {sys.version}")
    if sys.version_info < (3, 11):
        print("❌ Требуется Python 3.11 или выше!")
        return False
    print("✅ Версия Python корректная")
    return True


def check_imports():
    """Проверка установки основных пакетов."""
    packages = [
        ('aiogram', '3.3.0'),
        ('sqlalchemy', '2.0.23'),
        ('pydantic', '2.5.3'),
        ('asyncpg', '0.29.0'),
        ('redis', '5.0.1'),
        ('alembic', '1.13.1'),
    ]

    all_ok = True
    for package, version in packages:
        try:
            mod = importlib.import_module(package)
            installed_version = getattr(mod, '__version__', 'unknown')
            print(f"✅ {package} {installed_version} установлен")
        except ImportError:
            print(f"❌ {package} не установлен!")
            all_ok = False

    return all_ok


def check_directories():
    """Проверка наличия необходимых директорий."""
    dirs = ['logs', 'uploads', 'backups', 'static', 'config', 'bot', 'infrastructure']

    all_ok = True
    for dir_name in dirs:
        dir_path = Path(dir_name)
        if dir_path.exists():
            print(f"✅ Директория {dir_name}/ существует")
        else:
            print(f"❌ Директория {dir_name}/ не найдена!")
            all_ok = False

    return all_ok


def check_env_file():
    """Проверка наличия .env файла."""
    if Path('.env').exists():
        print("✅ Файл .env существует")

        # Проверяем основные переменные
        from dotenv import load_dotenv
        load_dotenv()

        required_vars = ['BOT_TOKEN', 'DATABASE_URL']
        missing_vars = []

        for var in required_vars:
            if not os.getenv(var):
                missing_vars.append(var)

        if missing_vars:
            print(f"⚠️  Не заполнены переменные: {', '.join(missing_vars)}")
            return False
        else:
            print("✅ Основные переменные окружения заполнены")
            return True
    else:
        print("❌ Файл .env не найден! Создайте его из .env.example")
        return False


def check_config_imports():
    """Проверка импорта конфигурации."""
    try:
        from config import settings, logger
        print("✅ Модуль config импортируется корректно")
        return True
    except Exception as e:
        print(f"❌ Ошибка импорта config: {e}")
        return False


def main():
    """Основная функция проверки."""
    print("=" * 50)
    print("🔍 Проверка установки Астро-Таро Бота")
    print("=" * 50)

    checks = [
        ("Версия Python", check_python_version),
        ("Установка пакетов", check_imports),
        ("Структура директорий", check_directories),
        ("Файл окружения", check_env_file),
        ("Импорт конфигурации", check_config_imports),
    ]

    results = []
    for name, check_func in checks:
        print(f"\n📋 {name}:")
        results.append(check_func())
        print()

    print("=" * 50)
    if all(results):
        print("✅ Все проверки пройдены успешно!")
        print("\nСледующие шаги:")
        print("1. Заполните .env файл вашими данными")
        print("2. Настройте базу данных PostgreSQL")
        print("3. Запустите миграции: alembic upgrade head")
        print("4. Запустите бота: python main.py")
    else:
        print("❌ Некоторые проверки не пройдены. Исправьте ошибки выше.")
    print("=" * 50)


if __name__ == "__main__":
    main()