import asyncio
import logging
import os
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv
# Загрузка .env файла
load_dotenv()

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Токен бота
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise ValueError("Не задан TELEGRAM_BOT_TOKEN")

# Импорт обработчиков
from telegram.bot.handlers.chenels_handlers import register_handlers

async def main():
    # Создаем бота и диспетчер
    bot = Bot(token=TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    
    # Регистрируем обработчики
    register_handlers(dp)
    
    print("Бот запущен! Доступные команды:")
    print("/set_ch - добавить канал")
    print("/del_ch - удалить канал")
    
    # Запускаем бота
    await dp.start_polling(bot)

if __name__ == "__main__":
    # Для Windows
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    # Запуск
    asyncio.run(main())
