"""
Простой запуск бота без сложной инициализации
"""

import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
import os
from dotenv import load_dotenv

load_dotenv()

# Получаем токен
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("Токен бота не найден в переменных окружения!")

# Создаем бота и диспетчер
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


@dp.message(CommandStart())
async def command_start(message: Message) -> None:
    """Обработчик команды /start"""
    await message.answer(
        f"👋 Привет, {message.from_user.first_name}!\n\n"
        "🔮 Я Астро-Таро Бот - твой персональный помощник в мире астрологии и таро.\n\n"
        "Что я умею:\n"
        "🎴 Делать расклады Таро\n"
        "⭐ Строить натальные карты\n"
        "🌙 Рассчитывать совместимость\n"
        "📅 Давать персональные прогнозы\n\n"
        "Используй /help для подробной информации."
    )


@dp.message()
async def echo(message: Message) -> None:
    """Эхо-обработчик для всех остальных сообщений"""
    await message.answer(
        "Я пока не понимаю это сообщение.\n"
        "Используй /start для начала работы или /help для помощи."
    )


async def main() -> None:
    """Основная функция"""
    logger.info("Запуск бота...")

    # Удаляем вебхук (на всякий случай)
    await bot.delete_webhook(drop_pending_updates=True)

    # Получаем информацию о боте
    bot_info = await bot.get_me()
    logger.info(f"Бот запущен: @{bot_info.username}")

    # Запускаем polling
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())