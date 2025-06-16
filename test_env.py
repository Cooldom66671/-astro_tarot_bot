"""
Тест загрузки переменных окружения
"""
import os
from dotenv import load_dotenv

# Загружаем .env
load_dotenv()

print("=" * 60)
print("ПРОВЕРКА ПЕРЕМЕННЫХ ОКРУЖЕНИЯ")
print("=" * 60)

# Проверяем все варианты токена
variants = [
    "BOT_TOKEN",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_TOKEN",
    "TG_BOT_TOKEN"
]

print("🔍 Поиск токена бота:")
found = False
for var in variants:
    value = os.getenv(var)
    if value:
        print(f"✅ {var} = {value[:20]}...{value[-10:]}")
        found = True
    else:
        print(f"❌ {var} = не найдено")

if not found:
    print("\n⚠️  Токен бота не найден ни в одной переменной!")

print("\n🔍 Другие важные переменные:")

# Проверяем другие переменные
other_vars = [
    "DATABASE_URL",
    "REDIS_URL",
    "ENVIRONMENT"
]

for var in other_vars:
    value = os.getenv(var)
    if value:
        # Скрываем пароли в DATABASE_URL
        if "://" in value and "@" in value:
            # Находим и скрываем пароль
            parts = value.split("://")
            if len(parts) > 1 and "@" in parts[1]:
                user_pass, host = parts[1].split("@", 1)
                if ":" in user_pass:
                    user, _ = user_pass.split(":", 1)
                    value = f"{parts[0]}://{user}:****@{host}"
        
        print(f"✅ {var} = {value}")
    else:
        print(f"❌ {var} = не найдено")

print("\n💡 Подсказка:")
print("В файле config/settings.py используется префикс TELEGRAM_BOT_")
print("Убедитесь, что в .env файле переменная называется TELEGRAM_BOT_TOKEN")
print("=" * 60)
