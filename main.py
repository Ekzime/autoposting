# Системные библиотеки
import sys  # Для работы с системными параметрами
import asyncio  # Для асинхронного программирования
import logging  # Для логирования
import os

# Импорты для работы с Telegram ботом
from aiogram import Dispatcher, Bot
from aiogram.fsm.storage.memory import MemoryStorage  # Хранилище состояний в памяти

# Импорт воркера для периодической публикации постов
from telegram.bot.posting_worker import run_periodic_tasks as posting_worker_run

# Настройка логирования для отслеживания работы приложения
logging.basicConfig(
    level=logging.INFO,  # Уровень логирования - INFO и выше
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'  # Формат сообщений лога
)

# Установка политики событийного цикла для Windows
# Необходимо для корректной работы asyncio на Windows
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Глобальные переменные для хранения фоновых задач
parser_task: asyncio.Task | None = None  # Задача парсера
posting_task: asyncio.Task | None = None  # Задача публикации постов
bot_for_posting_service_instance: Bot | None = None # Для хранения экземпляра бота для постинга

async def on_startup(bot: Bot): # bot здесь - это main_bot, переданный из start_polling
    global parser_task, posting_task, bot_for_posting_service_instance
    logging.info("on_startup: Запуск фоновых задач...")

    token_for_posting_env = os.getenv("TELEGRAM_BOT_TOKEN") # или TELEGRAM_BOT_TOKEN_POSTING
    
    if token_for_posting_env:
        bot_for_posting_service_instance = Bot(token=token_for_posting_env)
        logging.info("on_startup: Создан Bot instance для сервиса постинга.")
    else:
        logging.warning("on_startup: Токен для постинг-бота не найден! Постинг не будет работать.")
        # Создаем DummyBot если токен не найден, чтобы posting_worker мог запуститься
        class DummyBot: # Определяем DummyBot здесь, если он нужен только в этом контексте
            async def send_message(self, chat_id, text, **kwargs):
                logging.info(f"[DUMMY BOT из main.py on_startup] Сообщение для {chat_id}: {text[:30]}...")
                await asyncio.sleep(0.1)
            async def close(self): # Dummy боту тоже нужен метод close
                logging.info("[DUMMY BOT из main.py on_startup] close() called.")
                await asyncio.sleep(0.01)

        bot_for_posting_service_instance = DummyBot()

    # Передаем созданный или dummy экземпляр в воркер
    posting_task = asyncio.create_task(posting_worker_run(bot_for_posting_service_instance))
    logging.info("on_startup: Задача posting_worker создана.")

async def on_shutdown(bot: Bot): # bot здесь - это main_bot, переданный из start_polling
    """
    Функция, вызываемая при завершении работы бота.
    Отвечает за корректное завершение всех фоновых задач и освобождение ресурсов.
    """
    global parser_task, posting_task, bot_for_posting_service_instance

    logging.info("on_shutdown: Завершение фоновых задач...")
    # Отмена задачи парсера, если она существует и активна
    if parser_task and not parser_task.done():
        parser_task.cancel()
        try:
            await parser_task
        except asyncio.CancelledError:
            logging.info("on_shutdown: Задача парсера успешно отменена.")
    
    # Отмена задачи публикации постов, если она существует и активна
    if posting_task and not posting_task.done():
        posting_task.cancel()
        try:
            await posting_task 
        except asyncio.CancelledError:
            logging.info("on_shutdown: Задача posting_worker успешно отменена.")
    
    # Закрытие сессии бота для постинга, если он был создан
    if bot_for_posting_service_instance:
        logging.info("on_shutdown: Закрытие сессии бота для постинга...")
        await bot_for_posting_service_instance.close() # Используем close() вместо session.close()
        logging.info("on_shutdown: Сессия бота для постинга закрыта.")
            
    # Сессию основного бота (bot) aiogram закроет сам при остановке поллинга.
    # Явная команда bot.session.close() здесь не нужна и может быть даже вредна.
    logging.info(f"on_shutdown: Завершение работы основного бота (ID: {bot.id}). Aiogram позаботится о закрытии его сессии.")

async def main():
    """
    Основная функция приложения.
    Инициализирует и запускает бота, настраивает обработчики событий.
    """
    logging.info("main: Запуск бота...")

    bot_token = os.getenv("TELEGRAM_BOT_TOKEN_MAIN", os.getenv("TELEGRAM_BOT_TOKEN")) 
    if not bot_token:
        logging.critical("main: TELEGRAM_BOT_TOKEN_MAIN (или TELEGRAM_BOT_TOKEN) не найден в переменных окружения для основного бота!")
        return
    
    main_bot = Bot(token=bot_token)

    dp = Dispatcher(storage=MemoryStorage())
    
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # Запуск поллинга бота с обработкой возможных ошибок
    logging.info("main: Попытка запуска поллинга...")
    try:
        await dp.start_polling(main_bot) 
    except Exception as e:
        logging.critical(f"main: Ошибка во время поллинга: {e}", exc_info=True)
    finally:
        # Освобождение ресурсов при завершении работы
        logging.info("main: Поллинг завершен. Закрытие ресурсов...")
        if hasattr(main_bot, 'session') and main_bot.session:
            logging.info("main: Закрытие сессии main_bot (на всякий случай, хотя aiogram должен был это сделать)...")
            await main_bot.close() # Используем close() для корректного закрытия
            logging.info("main: Сессия main_bot закрыта.")

        if dp.storage: 
            await dp.storage.close()
        logging.info("main: Хранилище диспетчера закрыто.")
    

# Точка входа в приложение
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Программа прервана пользователем (KeyboardInterrupt в __main__)")
    finally:
        logging.info("Приложение завершает работу.")