import sys
import asyncio
from telegram.bot.core.bot_instance import bot
from aiogram import Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

parser_task: asyncio.Task | None = None
posting_task: asyncio.Task | None = None

# async def on_startup():
#     """Вызывается автоматически при старте бота"""
#     global parser_task, posting_task
#     parser_task = asyncio.create_task()
#     posting_task = asyncio.create_task()

async def main():
    dp = Dispatcher(storage=MemoryStorage())

    # try:
    #     # Запуск поллинга. При корректном завершении on_shutdown будет вызван автоматически.
    #     await dp.start_polling(bot)
    # finally:
    #     # Гарантированно вызов shutdown и закрываем хранилище
    #     dp.shutdown()
    #     await dp.storage.close()   

if __name__ == "__main__":
    asyncio.run(main())