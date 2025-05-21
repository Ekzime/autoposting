import sys
import asyncio
import logging
from aiogram import Dispatcher, Bot
from aiogram.fsm.storage.memory import MemoryStorage
from telegram.bot.handlers.target_chanels_handlers import router as target_router
from telegram.bot.handlers.source_chanels_handlers import router as source_router
from telegram.bot.handlers.telethon_handlers import router as telethon_router
from telegram.parser.parser_service import start_parser_service
from config import settings

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

parser_task = None

async def main():
    # Получаем токен для бота
    bot_token = settings.telegram_bot.bot_token_main or settings.telegram_bot.bot_token
    if not bot_token:
        logging.critical("Bot token not found!")
        return

    # Создаем бота и диспетчер
    bot = Bot(token=bot_token)
    dp = Dispatcher(storage=MemoryStorage())
    
    # Регистрация обработчиков
    dp.include_router(target_router)
    dp.include_router(source_router)
    dp.include_router(telethon_router)
    
    # Запускаем парсер
    global parser_task
    parser_task = start_parser_service()
    logging.info("Задача парсинга сообщений запущена")
    
    try:
        # Запускаем опрос бота
        await dp.start_polling(bot)
    except Exception as e:
        logging.critical(f"Polling error: {e}")
    finally:
        # Отменяем задачу парсера при завершении
        if parser_task and not parser_task.done():
            parser_task.cancel()
            try:
                await parser_task
            except asyncio.CancelledError:
                pass
                
        # Закрываем соединения
        await bot.close()
        if dp.storage:
            await dp.storage.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    finally:
        logging.info("App shutdown")