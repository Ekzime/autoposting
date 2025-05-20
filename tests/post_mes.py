import asyncio
import os
import logging
from aiogram import Bot, Dispatcher
from config import settings
from datetime import datetime 
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s [%(funcName)s] - %(message)s', 
    datefmt='%Y-%m-%d %H:%M:%S'
)

BOT_TOKEN = settings.telegram_bot.bot_token
TEST_CHANNEL_ID = "@testAichenelv2"  # Тестовый канал для отправки сообщений

async def send_test_message():
    if not BOT_TOKEN:
        logging.error("Токен бота не найден в настройках!")
        return

    logging.info(f"Используется токен: ...{BOT_TOKEN[-6:]}")
    logging.info(f"Используется тестовый Channel ID: '{TEST_CHANNEL_ID}' (тип: {type(TEST_CHANNEL_ID)})") 

    bot = Bot(token=BOT_TOKEN)
    
    
    text_message = f"Это тестовое сообщение от бота! Время: {datetime.now()}" 

    chat_id_to_send: str | int 
    chat_id_to_send = TEST_CHANNEL_ID 

    logging.info(f"Попытка отправить сообщение в чат/канал: '{chat_id_to_send}' (тип: {type(chat_id_to_send)})")

    try:
        await bot.send_message(chat_id=chat_id_to_send, text=text_message)
        logging.info(f"Сообщение УСПЕШНО отправлено в канал/чат {chat_id_to_send}!")
    except Exception as e:
        logging.error(f"ОШИБКА при отправке сообщения в {chat_id_to_send}: {e}", exc_info=True)
    finally:
        if hasattr(bot, 'session') and bot.session:
            logging.info("Закрытие сессии бота...")
            await bot.session.close()
            logging.info("Сессия бота закрыта.")

async def test_direct_sending():
    bot = Bot(token=BOT_TOKEN)
    try:
        # Получим информацию о боте
        me = await bot.get_me()
        logging.info(f"Бот: @{me.username} (ID: {me.id})")
        
        # Варианты ID канала для проверки
        channel_ids = [
            "-1002611960841",     # Новый ID как строка
            -1002611960841,       # Новый ID как число
            "@testAichenelv2"     # Username с @
        ]
        
        # Пробуем все варианты
        for chat_id in channel_ids:
            try:
                logging.info(f"Попытка с chat_id={chat_id} (тип: {type(chat_id)})")
                text = f"Тест отправки сообщения в канал, вариант {channel_ids.index(chat_id)+1}. Время: {datetime.now()}"
                await bot.send_message(chat_id=chat_id, text=text)
                logging.info(f"✅ УСПЕХ! Сообщение отправлено в канал {chat_id}")
                break
            except Exception as e:
                logging.error(f"❌ Ошибка при отправке в {chat_id}: {e}")
                
                # Пробуем получить информацию о канале
                try:
                    chat_info = await bot.get_chat(chat_id)
                    logging.info(f"Информация о канале {chat_id}: {chat_info.title} ({chat_info.type})")
                except Exception as e2:
                    logging.error(f"Не удалось получить информацию о канале {chat_id}: {e2}")
    finally:
        await bot.session.close()

if __name__ == "__main__":    
    if os.name == 'nt':  # Для Windows
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
    asyncio.run(test_direct_sending())