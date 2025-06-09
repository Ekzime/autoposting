import sys
import asyncio
import logging

from aiogram import Dispatcher, Bot
from aiogram.fsm.storage.memory import MemoryStorage

from telegram.bot.middleware.auth_middleware import AuthMiddleware
from telegram.bot.handlers.auth_handlers import router as auth_router
from telegram.bot.handlers.target_chanels_handlers import router as target_router
from telegram.bot.handlers.source_chanels_handlers import router as source_router
from telegram.bot.handlers.telethon_handlers import router as telethon_router
from telegram.bot.handlers.help_handlers import router as help_router
from telegram.bot.posting_worker import create_bot, run_periodic_tasks
from telegram.bot.utils.trigger_utils import trigger_posting_settings_update

from telegram.parser.parser_service import start_parser_service, trigger_update as trigger_parser_update

from config import settings

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('bot_log.txt')
    ]
)

logger = logging.getLogger(__name__)

# Вывод диагностической информации
logger.info("===== Запуск приложения =====")
logger.info(f"Платформа: {sys.platform}")
logger.info(f"Python версия: {sys.version}")
logger.info(f"API ID: {settings.telegram_api.api_id}")
logger.info(f"API Hash: {'настроен' if settings.telegram_api.api_hash else 'не настроен'}")
logger.info(f"Bot Token: {'настроен' if settings.telegram_bot.bot_token else 'не настроен'}")

if sys.platform.startswith("win"):
    logger.info("Настройка политики цикла событий для Windows")
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

parser_task = None
posting_task = None

async def main():
    try:
        logger.info("Начало инициализации бота и парсера")
        
        # Получаем токен для бота
        bot_token = settings.telegram_bot.bot_token_main or settings.telegram_bot.bot_token
        if not bot_token:
            logger.critical("Bot token not found!")
            return

        # Создаем бота и диспетчер
        logger.info("Создание экземпляра бота и диспетчера")
        bot = Bot(token=bot_token)
        dp = Dispatcher(storage=MemoryStorage())
        
        # Подключаем middleware аутентификации
        logger.info("Подключение middleware аутентификации")
        dp.message.middleware(AuthMiddleware())
        dp.callback_query.middleware(AuthMiddleware())
        
        logger.info("Регистрация обработчиков")
        dp.include_router(auth_router)  # ПЕРВЫМ для команд авторизации
        dp.include_router(help_router)
        dp.include_router(target_router)
        dp.include_router(source_router)
        dp.include_router(telethon_router)
        
        # Запускаем парсер
        logger.info("Запуск сервиса парсера")
        global parser_task
        parser_task = start_parser_service()
        logger.info("Задача парсинга сообщений запущена")
        
        # Запускаем сервис постинга
        logger.info("Запуск сервиса постинга")
        global posting_task
        try:
            # Создаем бота для постинга
            posting_bot = create_bot()
            # Запускаем задачу постинга
            posting_task = asyncio.create_task(run_periodic_tasks(posting_bot))
            logger.info("Задача постинга сообщений запущена")
        except Exception as e:
            logger.error(f"Ошибка при запуске сервиса постинга: {e}", exc_info=True)
        
        try:
            # Запускаем опрос бота
            logger.info("Запуск опроса бота")
            await dp.start_polling(bot)
        except Exception as e:
            logger.critical(f"Polling error: {e}", exc_info=True)
        finally:
            # Отменяем задачу парсера при завершении
            if parser_task and not parser_task.done():
                logger.info("Отмена задачи парсера")
                parser_task.cancel()
                try:
                    await parser_task
                except asyncio.CancelledError:
                    pass
                    
            # Отменяем задачу постинга при завершении
            if posting_task and not posting_task.done():
                logger.info("Отмена задачи постинга")
                posting_task.cancel()
                try:
                    await posting_task
                except asyncio.CancelledError:
                    pass
                    
            # Закрываем соединения
            logger.info("Закрытие соединений")
            await bot.close()
            if dp.storage:
                await dp.storage.close()
    except Exception as e:
        logger.critical(f"Неожиданная ошибка в main: {e}", exc_info=True)


if __name__ == "__main__":
    try:
        logger.info("Запуск основного цикла приложения")
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Завершение по Ctrl+C")
    except Exception as e:
        logger.critical(f"Критическая ошибка при запуске: {e}", exc_info=True)
    finally:
        logging.info("App shutdown")