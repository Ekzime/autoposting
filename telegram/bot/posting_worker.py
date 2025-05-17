# avtoposting/telegram/posting_worker.py

import os # Для работы с переменными окружения и файловой системой
import httpx # HTTP клиент для асинхронных запросов
import asyncio # Для асинхронного программирования
import logging # Для логирования
from datetime import datetime  # Для работы с датой и временем

from aiogram import Bot  

# SQLAlchemy для работы с базой данных
from sqlalchemy.orm import sessionmaker  # Для создания сессий БД
from sqlalchemy import select, update  # Для SQL запросов
from database.models import Messages, NewsStatus, engine, SessionLocal  # Модели и настройки БД

# Библиотека для работы с .env файлами
from dotenv import load_dotenv  

# Настройка базовой конфигурации логгера
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(module)s - %(funcName)s - %(lineno)d - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

load_dotenv()

AI_SERVICE_URL = os.getenv("AI_API_URL")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID")

if not AI_SERVICE_URL: logging.warning("AI_API_URL не задан!") 
if not TELEGRAM_BOT_TOKEN: logging.warning("TELEGRAM_BOT_TOKEN не задан! Постинг не будет работать.")
if not TELEGRAM_CHANNEL_ID: logging.warning("TELEGRAM_CHANNEL_ID не задан! Постинг не будет работать.")

logging.info("posting_worker.py загружен")

async def post_message_to_telegram(
    bot: Bot | None, 
    channel_id_str: str | None, 
    text_to_post: str | None, 
    message_db_id: int
) -> bool:
    """
    Отправляет сообщение в Telegram канал.
    
    Args:
        bot (Bot | None): Экземпляр бота для отправки сообщений
        channel_id_str (str | None): ID канала или username в виде строки
        text_to_post (str | None): Текст для публикации
        message_db_id (int): ID сообщения в базе данных (для логирования)
        
    Returns:
        bool: True если отправка успешна, False в случае ошибки
        
    Действия:
    1. Проверяет наличие всех необходимых данных (бот, ID канала, текст)
    2. Пытается преобразовать ID канала в число, если не получается - использует как строку
    3. Отправляет сообщение через бота
    4. Логирует результат отправки
    """
    
    if not all([bot, channel_id_str, text_to_post]): # message_db_id для лога, не для основной логики отправки
        logging.warning(f"ID {message_db_id}: Недостаточно данных (бот/канал/текст) для отправки в Telegram.")
        return False
    
    # --- ДИАГНОСТИКА ---
    logging.info(f"ID {message_db_id}: Попытка поста. Исходный channel_id_str из .env: '{channel_id_str}' (тип: {type(channel_id_str)})")
    
    chat_id_for_send: str | int
    try:
        # Попытка преобразовать в int. aiogram должен справиться и со строкой, и с int.
        chat_id_for_send = int(channel_id_str) 
        logging.info(f"ID {message_db_id}: channel_id_str успешно преобразован в int: {chat_id_for_send} (тип: {type(chat_id_for_send)})")
    except ValueError:
        chat_id_for_send = channel_id_str # Используем как строку, если не число (например, @username)
        logging.info(f"ID {message_db_id}: channel_id_str не преобразовался в int, используется как строка: '{chat_id_for_send}' (тип: {type(chat_id_for_send)})")
    # --- КОНЕЦ ДИАГНОСТИКИ ---

    try:
        logging.info(f"ID {message_db_id}: Отправка в Telegram. chat_id={chat_id_for_send}, text='{text_to_post[:30]}...'")
        await bot.send_message(chat_id=chat_id_for_send, text=text_to_post) # Используем chat_id_for_send
        logging.info(f"ID {message_db_id}: Сообщение УСПЕШНО отправлено в Telegram канал '{chat_id_for_send}'.")
        return True
    except Exception as e:
        logging.error(f"ID {message_db_id}: ОШИБКА при отправке сообщения в Telegram с chat_id='{chat_id_for_send}': {e}", exc_info=True)
        return False


async def get_messages_for_ai_processing(limit: int = 5) -> list[Messages]:
    """
    Получает сообщения из базы данных для обработки искусственным интеллектом.
    
    Args:
        limit (int): Максимальное количество сообщений для получения. По умолчанию 5.
        
    Returns:
        list[Messages]: Список объектов Messages, готовых для обработки AI.
        
    Действия:
    1. Получает сообщения со статусом NEW из базы данных
    2. Проверяет наличие непустого текста в сообщениях
    3. Сортирует по дате (старые в начале)
    4. Ограничивает количество записей параметром limit
    """
    
    logging.info("Получение сообщений для AI (статус NEW)...")
    
    def _get_sync():
        with SessionLocal() as session:
            query = (
                select(Messages)
                .where(
                    Messages.status == NewsStatus.NEW,
                    Messages.text != None,
                    Messages.text != ""
                )
                .order_by(Messages.date.asc())
                .limit(limit)
            )
            return session.execute(query).scalars().all()
            
    messages = await asyncio.to_thread(_get_sync)
    
    if messages:
        logging.info(f"Найдено {len(messages)} сообщений для AI.")
    else:
        logging.info("Нет сообщений для AI.")
        
    return messages


async def get_messages_ready_for_posting(limit: int = 5) -> list[Messages]:
    """
    Получает сообщения из базы данных, готовые для публикации в Telegram канал.
    
    Args:
        limit (int): Максимальное количество сообщений для получения. По умолчанию 5.
        
    Returns:
        list[Messages]: Список объектов Messages, готовых для публикации.
        
    Действия:
    1. Получает сообщения со статусом AI_PROCESSED из базы данных
    2. Проверяет наличие обработанного AI текста в сообщениях
    3. Сортирует по дате (старые в начале)
    4. Ограничивает количество записей параметром limit
    """
    
    logging.info("Получение сообщений для постинга (статус AI_PROCESSED)...")
    
    def _get_sync():
        with SessionLocal() as session:
            query = (
                select(Messages)
                .where(
                    Messages.status == NewsStatus.AI_PROCESSED,
                    Messages.ai_processed_text != None,
                    Messages.ai_processed_text != ""
                )
                .order_by(Messages.date.asc())
                .limit(limit)
            )
            return session.execute(query).scalars().all()
            
    messages = await asyncio.to_thread(_get_sync)
    
    if messages:
        logging.info(f"Найдено {len(messages)} сообщений для постинга.")
    else:
        logging.info("Нет сообщений для постинга.")
        
    return messages


async def _fetch_ai_response(message_id: int, text_to_process: str, service_url: str) -> str | None:
    """
    Отправляет текст в AI сервис и получает обработанный ответ.
    
    Args:
        message_id (int): ID сообщения в базе данных для логирования
        text_to_process (str): Исходный текст для обработки AI
        service_url (str): URL эндпоинта AI сервиса
        
    Returns:
        str | None: Обработанный AI текст или None в случае ошибки/пустого ответа
        
    Действия:
    1. Отправляет POST запрос в AI сервис с текстом
    2. Получает и проверяет ответ от сервиса
    3. Извлекает обработанный текст из ответа
    4. Логирует результаты
    """
    
    logging.info(f"ID {message_id}: Отправка в AI ({service_url}): {text_to_process[:30]}...")
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        # Отправка запроса в AI сервис
        payload = {"posts": [text_to_process]}
        response = await client.post(service_url, json=payload)
        response.raise_for_status()

    response_json = response.json()
    processed_text = None

    # Обработка ответа от AI
    if (response_json and 
        isinstance(response_json, dict) and 
        response_json.get("status") == "success"):
        
        ai_result_list = response_json.get("result")
        
        if ai_result_list and isinstance(ai_result_list, list) and ai_result_list:
            first_item = ai_result_list[0]
            
            if isinstance(first_item, dict) and "text" in first_item:
                processed_text = first_item.get("text")
            elif isinstance(first_item, str):
                processed_text = first_item
            
            if not processed_text:
                processed_text = None 
    
    logging.info(
        f"ID {message_id}: Ответ от AI: "
        f"{processed_text[:50] if processed_text else 'Нет текста (или пустой список от AI)'}"
    )
    return processed_text


async def simplified_process_message(message_id: int, original_text: str):
    """
    Упрощенная обработка сообщения через AI сервис.
    
    Args:
        message_id (int): ID сообщения в базе данных
        original_text (str): Исходный текст сообщения для обработки
        
    Действия:
    1. Проверяет входные данные (текст и URL AI сервиса)
    2. Обновляет статус на "отправляется в AI"
    3. Отправляет текст в AI сервис через _fetch_ai_response()
    4. Обрабатывает возможные ошибки (сеть, HTTP, прочие)
    5. Обновляет статус и результат в БД
    
    Raises:
        httpx.RequestError: При ошибках сети
        httpx.HTTPStatusError: При ошибках HTTP от AI сервиса
        Exception: При прочих ошибках обработки
    """
    
    logging.info(f"Обработка сообщения ID {message_id} через AI...")
    new_status = NewsStatus.ERROR_AI_PROCESSING
    processed_text_from_ai = None
    
    # Проверка входных данных
    if not original_text or not AI_SERVICE_URL:
        logging.warning(f"Сообщение ID {message_id} не имеет текста или AI_SERVICE_URL не задан. Пропуск.")
        await _update_message_status(
            message_id, 
            NewsStatus.ERROR_AI_PROCESSING,
            "Нет текста или URL AI"
        )
        return

    try:
        # Обновление статуса на "отправляется в AI"
        await _update_message_status(message_id, NewsStatus.SENT_TO_AI)
        logging.info(f"ID {message_id}: Статус обновлен на SENT_TO_AI.")

        # Получение ответа от AI
        processed_text_from_ai = await _fetch_ai_response(
            message_id, 
            original_text, 
            AI_SERVICE_URL
        )

        # Определение финального статуса
        if processed_text_from_ai:
            new_status = NewsStatus.AI_PROCESSED
        else:
            new_status = NewsStatus.ERROR_AI_PROCESSING
            processed_text_from_ai = "AI не вернул текст"

    except httpx.RequestError as e:
        logging.error(f"ID {message_id}: Ошибка сети при обращении к AI: {e}")
        new_status = NewsStatus.ERROR_SENDING_TO_AI
        processed_text_from_ai = f"Ошибка сети: {str(e)}"
        
    except httpx.HTTPStatusError as e:
        logging.error(
            f"ID {message_id}: AI сервис вернул HTTP ошибку: "
            f"{e.response.status_code} - {e.response.text}"
        )
        new_status = NewsStatus.ERROR_AI_PROCESSING
        processed_text_from_ai = (
            f"AI ошибка HTTP: {e.response.status_code} - {e.response.text[:100]}"
        )
        
    except Exception as e:
        logging.error(
            f"ID {message_id}: Непредвиденная ошибка при обработке AI: {e}", 
            exc_info=True
        )
        new_status = NewsStatus.ERROR_AI_PROCESSING
        processed_text_from_ai = f"Ошибка: {str(e)[:100]}"
        
    finally:
        # Финальное обновление статуса
        await _update_message_status(
            message_id,
            new_status,
            processed_text_from_ai
        )
        logging.info(
            f"ID {message_id}: Финальный статус в БД: {new_status.value}, "
            "Результат AI сохранен."
        )


async def main_logic(bot_for_posting: Bot | None):
    """
    Основная логика обработки и публикации сообщений.
    
    Args:
        bot_for_posting (Bot | None): Инстанс бота для публикации сообщений.
            Если None, этап публикации будет пропущен.
            
    Действия:
    1. Запускает обработку сообщений через AI
    2. Делает паузу между этапами
    3. Публикует обработанные сообщения в Telegram канал
       (если предоставлен бот и ID канала)
    """
    
    logging.info("main_logic запущен")

    # Этап 1: Обработка AI
    await _process_ai_messages()
    
    await asyncio.sleep(1)  # Пауза между этапами

    # Этап 2: Постинг в Telegram
    if not bot_for_posting or not TELEGRAM_CHANNEL_ID:
        logging.warning(
            "Инстанс бота для постинга или ID канала не предоставлены. "
            "Этап постинга пропускается."
        )
        return
        
    await _process_posting_messages(bot_for_posting)


async def run_periodic_tasks(bot_for_posting: Bot | None):
    """
    Запускает периодические задачи обработки и публикации сообщений.
    
    Args:
        bot_for_posting (Bot | None): Инстанс бота для публикации сообщений.
            Если None, этап публикации будет пропущен.
            
    Действия:
    1. Запускает бесконечный цикл выполнения основной логики
    2. Делает паузу 10 секунд между итерациями
    3. Логирует каждую итерацию
    """
    
    logging.info("Запуск run_periodic_tasks в posting_worker...")
    while True:
        await main_logic(bot_for_posting)
        logging.info("posting_worker: Следующий цикл через 10 секунд...")
        await asyncio.sleep(10)


# Вспомогательные функции
async def _update_message_status(
    message_id: int, 
    status: NewsStatus, 
    processed_text: str | None = None
):
    """
    Обновляет статус сообщения в базе данных.
    
    Args:
        message_id (int): ID сообщения для обновления
        status (NewsStatus): Новый статус для установки
        processed_text (str | None): Обработанный текст сообщения.
            Если None, поле ai_processed_text не обновляется.
            
    Действия:
    1. Создает словарь значений для обновления с новым статусом
    2. Если передан processed_text, добавляет его в значения для обновления
    3. Выполняет SQL-запрос на обновление через синхронную функцию
    4. Коммитит изменения в БД
    """
    
    def _update_sync():
        with SessionLocal() as session:
            update_values = {"status": status}
            if processed_text is not None:
                update_values["ai_processed_text"] = processed_text
                
            stmt = (
                update(Messages)
                .where(Messages.id == message_id)
                .values(**update_values)
            )
            session.execute(stmt)
            session.commit()
            
    await asyncio.to_thread(_update_sync)


async def _process_ai_messages():
    """
    Обрабатывает сообщения с помощью AI.
    
    Действия:
    1. Получает до 2-х сообщений из БД, готовых к AI обработке
    2. Для каждого сообщения:
       - Проверяет наличие текста
       - Если текст есть - обрабатывает через simplified_process_message()
       - Если текста нет - помечает ошибкой
    3. Делает паузу 1 секунду между обработкой сообщений
    
    Returns:
        None
        
    Raises:
        Ошибки пробрасываются наверх для обработки в вызывающем коде
    """
    
    messages = await get_messages_for_ai_processing(limit=2)
    
    if not messages:
        logging.info("Нет новых сообщений для AI обработки в этом цикле.")
        return
        
    logging.info(f"Обработка AI для {len(messages)} сообщений.")
    
    for msg in messages:
        if msg.text:
            await simplified_process_message(msg.id, msg.text)
        else:
            logging.warning(f"Сообщение ID {msg.id} (для AI) имеет пустой текст. Пропуск.")
            await _update_message_status(
                msg.id,
                NewsStatus.ERROR_AI_PROCESSING,
                "Сообщение имеет пустой текст (None)"
            )
        await asyncio.sleep(1)


async def _process_posting_messages(bot: Bot):
    """
    Обрабатывает сообщения для постинга в Telegram канал.
    
    Args:
        bot (Bot): Экземпляр бота Telegram для отправки сообщений
        
    Действия:
    1. Получает до 2-х сообщений из БД, готовых к постингу
    2. Для каждого сообщения:
       - Проверяет наличие обработанного AI текста
       - Если текст есть - отправляет в Telegram канал
       - Обновляет статус сообщения в БД (POSTED или ERROR_POSTING)
    3. Делает паузу 1 секунду между отправкой сообщений
    
    Returns:
        None
        
    Raises:
        Ошибки пробрасываются наверх для обработки в вызывающем коде
    """
    messages = await get_messages_ready_for_posting(limit=2)
    
    if not messages:
        logging.info("Нет сообщений, готовых к постингу, в этом цикле.")
        return
        
    logging.info(f"Постинг для {len(messages)} сообщений...")
    
    for msg in messages:
        if not msg.ai_processed_text:
            logging.warning(
                f"Сообщение ID {msg.id} (для постинга) не имеет "
                "обработанного текста. Пропуск."
            )
            continue
            
        success = await post_message_to_telegram(
            bot,
            TELEGRAM_CHANNEL_ID,
            msg.ai_processed_text,
            msg.id
        )
        
        status = NewsStatus.POSTED if success else NewsStatus.ERROR_POSTING
        await _update_message_status(msg.id, status)
        logging.info(f"ID {msg.id}: Статус после постинга в БД: {status.value}")
        
        await asyncio.sleep(1)


def create_bot():
    """
    Создает и возвращает экземпляр бота для постинга.
    
    Returns:
        Bot: Экземпляр бота для постинга
    """
    token = os.getenv("TELEGRAM_BOT_TOKEN") or None
    if not token: 
        raise ValueError("Token value getting error! token is None")
    
    bot_instance = Bot(token=token)
    logging.info(f"Создан бот для постинга (токен: ...{token[-4:]}).")
    
    return bot_instance


def close_bot_session():
    """
    Закрывает сессию бота.
    
    Действия:
    1. Проверяет наличие сессии и ее закрытость
    2. Если сессия открыта, закрывает ее
    3. Логирует закрытие сессии
    """
    if (
        bot_instance and 
        hasattr(bot_instance, 'session') and 
        bot_instance.session and 
        hasattr(bot_instance.session, 'closed') and
        not bot_instance.session.closed 
    ): 
        logging.info("Закрытие сессии бота...")
        try:
            if loop.is_running():
                loop.run_until_complete(bot_instance.session.close())
            else:
                asyncio.run(bot_instance.session.close())
        except Exception as e:
            logging.error(f"Ошибка закрытия сессии: {e}")
            
    logging.info("Работа posting_worker.py завершена")


if __name__ == "__main__":
    """
    Запускает основной скрипт posting_worker.py.
    
    Действия:
    1. Создает экземпляр бота для постинга
    2. Запускает периодические задачи
    3. Логирует завершение работы
    """
    logging.info("Запуск posting_worker.py как отдельного скрипта...")
    
    bot_instance = create_bot()

    loop = asyncio.get_event_loop()
    
    try:
        loop.run_until_complete(run_periodic_tasks(bot_instance))
    except KeyboardInterrupt:
        logging.info("Программа прервана пользователем.")
    except Exception as e:
        logging.critical(f"Критическая ошибка: {e}", exc_info=True)
    finally:
        close_bot_session()
