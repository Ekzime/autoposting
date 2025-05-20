import sys
import asyncio
import logging
from aiogram import Dispatcher, Bot
from aiogram.fsm.storage.memory import MemoryStorage
from telegram.bot.posting_worker import run_periodic_tasks as posting_worker_run
from config import settings

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

parser_task = None
posting_task = None 
bot_for_posting_service_instance = None

async def on_startup(bot: Bot):
    """
    Функция, выполняемая при запуске бота.
    Инициализирует бота для сервиса постинга и запускает задачу постинга.
    
    Args:
        bot: Экземпляр основного бота
    """
    global parser_task, posting_task, bot_for_posting_service_instance
    
    # Получаем токен для бота постинга
    token = settings.telegram_bot.bot_token
    if token:
        # Если токен есть - создаем реального бота
        bot_for_posting_service_instance = Bot(token=token)
    else:
        # Если токена нет - создаем фиктивного бота для тестирования
        class DummyBot:
            async def send_message(self, chat_id, text, **kwargs):
                logging.info(f"[DUMMY] Message to {chat_id}: {text[:30]}...")
                await asyncio.sleep(0.1)
            async def close(self):
                await asyncio.sleep(0.01)
        bot_for_posting_service_instance = DummyBot()

    # Запускаем задачу постинга сообщений
    posting_task = asyncio.create_task(posting_worker_run(bot_for_posting_service_instance))

async def on_shutdown(bot: Bot):
    """
    Функция, выполняемая при завершении работы бота.
    Отменяет запущенные задачи и закрывает соединения.
    
    Args:
        bot: Экземпляр основного бота
    """
    global parser_task, posting_task, bot_for_posting_service_instance

    # Отменяем задачу парсера, если она запущена
    if parser_task and not parser_task.done():
        parser_task.cancel()
        try:
            await parser_task
        except asyncio.CancelledError:
            pass

    # Отменяем задачу постинга, если она запущена
    if posting_task and not posting_task.done():
        posting_task.cancel()
        try:
            await posting_task
        except asyncio.CancelledError:
            pass

    # Закрываем соединение бота постинга
    if bot_for_posting_service_instance:
        await bot_for_posting_service_instance.close()

async def main():
    # Use main bot token if available, otherwise use regular bot token
    bot_token = settings.telegram_bot.bot_token_main or settings.telegram_bot.bot_token
    if not bot_token:
        logging.critical("Bot token not found!")
        return

    main_bot = Bot(token=bot_token)
    dp = Dispatcher(storage=MemoryStorage())
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    try:
        await dp.start_polling(main_bot)
    except Exception as e:
        logging.critical(f"Polling error: {e}")
    finally:
        await main_bot.close()
        if dp.storage:
            await dp.storage.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    finally:
        logging.info("App shutdown")