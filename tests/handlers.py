import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from config import settings
from telegram.bot.handlers.target_chanels_handlers import router
from telegram.bot.handlers.source_chanels_handlers import router as source_router
from telegram.bot.handlers.telethon_handlers import router as telethon_router

# Настройка логирования
logging.basicConfig(level=logging.DEBUG, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Токен бота
TOKEN = settings.telegram_bot.bot_token
if not TOKEN:
    raise ValueError("Не задан TELEGRAM_BOT_TOKEN")

async def on_startup(bot: Bot):
    logger.info("Бот запущен")
    # Убираем отправку сообщения, чтобы избежать ошибки с ID чата
    # await bot.send_message(chat_id=YOUR_CHAT_ID, text="Бот запущен и готов к работе!")

# Добавим тестовую команду для проверки
async def cmd_test(message: types.Message):
    logger.info("Получена команда /test")
    await message.answer("Тест работает!")

async def main():
    # Создаем бота и диспетчер
    bot = Bot(token=TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    
    # Регистрация тестовой команды
    dp.message.register(cmd_test, Command("test"))
    
    # Регистрируем обработчики
    logger.info("Регистрируем роутер")
    dp.include_router(router)
    dp.include_router(source_router)
    dp.include_router(telethon_router)

    # Выводим все зарегистрированные обработчики
    logger.info("Зарегистрированные обработчики:")
    for router_obj in dp.sub_routers:
        for handler in router_obj.message.handlers:
            logger.info(f"Handler: {handler}")
    
    print("Бот запущен! Доступные команды:")
    print("/set_ch - добавить канал")
    print("/test - проверка работы бота")
    
    # Запускаем бота с обработчиком запуска
    try:
        await dp.start_polling(bot, on_startup=on_startup)
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")

if __name__ == "__main__":
    # Для Windows
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    # Запуск
    asyncio.run(main())
