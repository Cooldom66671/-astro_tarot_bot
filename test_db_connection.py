"""
Простой тест подключения к БД без использования моделей
"""
import asyncio
import asyncpg
from sqlalchemy.ext.asyncio import create_async_engine
import os
from dotenv import load_dotenv

load_dotenv()


async def test_direct_connection():
    """Тест прямого подключения через asyncpg"""
    print("🔍 Тест прямого подключения к PostgreSQL...")
    
    try:
        # Получаем URL
        db_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/astrotarot")
        
        # Парсим URL для asyncpg
        if db_url.startswith("postgresql+asyncpg://"):
            db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
        
        # Подключаемся
        conn = await asyncpg.connect(db_url)
        
        # Проверяем версию
        version = await conn.fetchval('SELECT version()')
        print(f"✅ Подключение успешно!")
        print(f"   PostgreSQL версия: {version}")
        
        # Проверяем таблицы
        tables = await conn.fetch("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
        """)
        
        print(f"   Найдено таблиц: {len(tables)}")
        
        await conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Ошибка подключения: {e}")
        return False


async def test_sqlalchemy_connection():
    """Тест подключения через SQLAlchemy"""
    print("\n🔍 Тест подключения через SQLAlchemy...")
    
    try:
        # Получаем URL
        db_url = os.getenv("DATABASE_URL")
        if not db_url.startswith("postgresql+asyncpg://"):
            db_url = db_url.replace("postgresql://", "postgresql+asyncpg://")
        
        # Создаем движок
        engine = create_async_engine(db_url, echo=True)
        
        # Проверяем подключение
        async with engine.connect() as conn:
            from sqlalchemy import text
            result = await conn.execute(text("SELECT 1"))
            print("✅ SQLAlchemy подключение успешно!")
        
        await engine.dispose()
        return True
        
    except Exception as e:
        print(f"❌ Ошибка SQLAlchemy: {e}")
        return False


async def main():
    print("=" * 60)
    print("ТЕСТ ПОДКЛЮЧЕНИЯ К БАЗЕ ДАННЫХ")
    print("=" * 60)
    
    # Тестируем оба способа
    direct_ok = await test_direct_connection()
    sqlalchemy_ok = await test_sqlalchemy_connection()
    
    print("\n" + "=" * 60)
    print("РЕЗУЛЬТАТЫ:")
    print("=" * 60)
    print(f"Прямое подключение (asyncpg): {'✅ OK' if direct_ok else '❌ FAIL'}")
    print(f"SQLAlchemy подключение: {'✅ OK' if sqlalchemy_ok else '❌ FAIL'}")
    

if __name__ == "__main__":
    asyncio.run(main())
