import os # Для работы с переменными окружения и файловой системой
import httpx # HTTP клиент для асинхронных запросов
import asyncio # Для асинхронного программирования
import logging # Для логирования
import hashlib # Для генерации хешей контента
import re # Для работы с регулярными выражениями
from datetime import datetime, timedelta  # Для работы с датой и временем

from aiogram import Bot  
from aiogram.types import FSInputFile  # Для отправки файлов в Aiogram 3.x
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest  # Импорт исключений Telegram

# SQLAlchemy для работы с базой данных
from sqlalchemy.orm import sessionmaker  # Для создания сессий БД
from sqlalchemy import select, update  # Для SQL запросов
from database.models import Messages, NewsStatus, engine, SessionLocal, PostingTarget  # Модели и настройки БД

# Импортируем централизованные настройки
from config import settings

# Импортируем репозиторий для работы с целевыми каналами
from database.repositories import posting_target_repository

# Импортируем общие события из trigger_utils
from telegram.bot.utils.trigger_utils import posting_settings_update_event

# Настройка базовой конфигурации логгера
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(module)s - %(funcName)s - %(lineno)d - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Получаем настройки из settings
AI_SERVICE_URL = settings.ai_service.api_url
TELEGRAM_BOT_TOKEN = settings.telegram_bot.bot_token

if not AI_SERVICE_URL: logging.warning("AI_API_URL не задан!") 
if not TELEGRAM_BOT_TOKEN: logging.warning("TELEGRAM_BOT_TOKEN не задан! Постинг не будет работать.")

logging.info("posting_worker.py загружен")

# Глобальные переменные
last_targets_check = datetime.now()  # Время последней проверки целевых каналов


def create_promotional_block() -> str:
    """
    Создает рекламный блок для добавления в конец каждого сообщения.
    Использует настройки из конфигурации для гибкой настройки.
    
    Returns:
        str: Форматированный рекламный блок с встроенными ссылками или пустая строка, если отключен
    """
    # Проверяем, включен ли рекламный блок
    if not settings.telegram_bot.promo_enabled:
        return ""
    
    promo_block = (
        f"\n\n{settings.telegram_bot.promo_title}\n"
        f'<a href="{settings.telegram_bot.promo_crypto_url}">{settings.telegram_bot.promo_crypto_text}</a> '
        f'<a href="{settings.telegram_bot.promo_forex_url}">{settings.telegram_bot.promo_forex_text}</a> '
        f'<a href="{settings.telegram_bot.promo_news_url}">{settings.telegram_bot.promo_news_text}</a>'
    )
    return promo_block


async def check_bot_in_channel(bot: Bot, channel_id: str | int) -> bool:
    """
    Проверяет, является ли бот участником канала.
    
    Args:
        bot (Bot): Экземпляр бота для проверки
        channel_id (str | int): ID канала или username
    
    Returns:
        bool: True, если бот является участником канала, иначе False
    """
    try:
        # Пытаемся получить информацию о чате
        chat = await bot.get_chat(channel_id)
        
        # Получаем ID бота
        bot_info = await bot.get_me()
        bot_id = bot_info.id
        
        # Проверяем, является ли бот администратором канала
        try:
            chat_member = await bot.get_chat_member(chat.id, bot_id)
            return True  # Если получили информацию о боте в канале, значит он там есть
        except TelegramBadRequest:
            return False  # Ошибка запроса - скорее всего бота нет в канале
    
    except Exception as e:
        logging.error(f"Ошибка при проверке бота в канале {channel_id}: {e}")
        return False  # В случае ошибки предполагаем, что бота нет в канале


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
    3. Проверяет наличие изображения для сообщения
    4. Отправляет сообщение через бота (с изображением, если оно есть)
    5. Логирует результат отправки
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
        # Проверяем, является ли бот участником канала
        bot_in_channel = await check_bot_in_channel(bot, chat_id_for_send)
        if not bot_in_channel:
            error_msg = f"Бот не является участником канала {chat_id_for_send}. Добавьте бота в канал как администратора."
            logging.error(f"ID {message_db_id}: {error_msg}")
            return False

        # Проверка наличия изображения
        photo_path = f"database/photos/{message_db_id}.jpg"
        has_photo = os.path.exists(photo_path)
        
        if has_photo:
            logging.info(f"ID {message_db_id}: Найдено изображение: {photo_path}")
            # Отправляем сообщение с фото
            logging.info(f"ID {message_db_id}: Отправка в Telegram с фото. chat_id={chat_id_for_send}, text='{text_to_post[:30]}...'")
            
            # Используем FSInputFile вместо открытия файла напрямую
            photo = FSInputFile(photo_path)
            await bot.send_photo(
                chat_id=chat_id_for_send,
                photo=photo,
                caption=text_to_post + create_promotional_block(),
                parse_mode="HTML",
                disable_web_page_preview=True # отключаем превью ссылок в сообщении
            )
        else:
            # Отправляем сообщение без фото
            logging.info(f"ID {message_db_id}: Изображение не найдено, отправка только текста")
            logging.info(f"ID {message_db_id}: Отправка в Telegram. chat_id={chat_id_for_send}, text='{text_to_post[:30]}...'")
            await bot.send_message(
                chat_id=chat_id_for_send, 
                text=text_to_post + create_promotional_block(),
                parse_mode="HTML"
            )
            
        logging.info(f"ID {message_db_id}: Сообщение УСПЕШНО отправлено в Telegram канал '{chat_id_for_send}'.")
        return True
    except TelegramForbiddenError as e:
        error_msg = f"Ошибка доступа: бот не имеет прав для отправки сообщений в канал {chat_id_for_send}. Убедитесь, что бот добавлен в канал как администратор."
        logging.error(f"ID {message_db_id}: {error_msg} Подробности: {e}")
        # Сохраняем дополнительную информацию в сообщении о причине ошибки
        await _update_message_error_info(message_db_id, error_msg)
        return False
    except Exception as e:
        logging.error(f"ID {message_db_id}: ОШИБКА при отправке сообщения в Telegram с chat_id='{chat_id_for_send}': {e}", exc_info=True)
        # Сохраняем информацию об ошибке
        await _update_message_error_info(message_db_id, str(e))
        return False


async def _update_message_error_info(message_id: int, error_info: str) -> None:
    """
    Обновляет информацию об ошибке в сообщении.
    
    Args:
        message_id (int): ID сообщения
        error_info (str): Информация об ошибке
    """
    def _update_sync():
        with SessionLocal() as session:
            message = session.get(Messages, message_id)
            if message:
                # Добавляем поле для хранения ошибки, если его нет
                try:
                    if not hasattr(message, 'error_info'):
                        from sqlalchemy import Column, String
                        Messages.error_info = Column(String(500), nullable=True)
                        logging.info(f"Добавлено поле error_info в модель Messages")
                except Exception as e:
                    logging.warning(f"Не удалось проверить/добавить поле error_info: {e}")
                
                # Сохраняем информацию об ошибке
                try:
                    message.error_info = error_info[:500]  # Ограничиваем длину текста ошибки
                    session.commit()
                    logging.info(f"ID {message_id}: Сохранена информация об ошибке")
                except Exception as e:
                    logging.error(f"ID {message_id}: Ошибка при сохранении информации об ошибке: {e}")
                    session.rollback()
    
    await asyncio.to_thread(_update_sync)


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


async def get_messages_ready_for_posting(limit: int = 5, target_channel_id: str = None) -> list[Messages]:
    """
    Получает сообщения из базы данных, готовые для публикации в конкретный Telegram канал.
    
    Args:
        limit (int): Максимальное количество сообщений для получения. По умолчанию 5.
        target_channel_id (str): ID целевого канала для постинга. Если указан, 
                                будут выбраны только сообщения из источников, 
                                привязанных к этому каналу.
        
    Returns:
        list[Messages]: Список объектов Messages, готовых для публикации.
        
    Действия:
    1. Если указан target_channel_id, получает список источников, привязанных к нему
    2. Получает сообщения со статусом AI_PROCESSED из базы данных
    3. Проверяет наличие обработанного AI текста в сообщениях
    4. Фильтрует сообщения по источникам, если указан target_channel_id
    5. Сортирует по дате (старые в начале)
    6. Ограничивает количество записей параметром limit
    """
    
    logging.info(f"Получение сообщений для постинга (статус AI_PROCESSED) для канала {target_channel_id or 'все каналы'}...")
    
    def _get_sync():
        with SessionLocal() as session:
            # Базовый запрос для получения обработанных сообщений
            base_query = (
                select(Messages)
                .where(
                    Messages.status == NewsStatus.AI_PROCESSED,
                    Messages.ai_processed_text != None,
                    Messages.ai_processed_text != ""
                )
            )
            
            # Если указан целевой канал, фильтруем по источникам
            if target_channel_id:
                # Получаем целевой канал
                target = session.execute(
                    select(PostingTarget).where(PostingTarget.target_chat_id == target_channel_id)
                ).scalar_one_or_none()
                
                if not target:
                    logging.warning(f"Целевой канал {target_channel_id} не найден в БД")
                    return []
                
                # Получаем ID источников, привязанных к этому каналу
                from database.models import ParsingSourceChannel, Channels
                
                # Получаем записи источников парсинга для данного целевого канала
                parsing_sources = session.execute(
                    select(ParsingSourceChannel).where(
                        ParsingSourceChannel.posting_target_id == target.id
                    )
                ).scalars().all()
                
                if not parsing_sources:
                    logging.warning(f"Нет источников парсинга для канала {target_channel_id}")
                    return []
                
                # Получаем идентификаторы источников
                source_identifiers = [ps.source_identifier for ps in parsing_sources]
                
                # Получаем каналы по их идентификаторам (username или ID)
                source_channels = []
                for identifier in source_identifiers:
                    # Пробуем сначала найти по username
                    if identifier.startswith('@'):
                        channel = session.execute(
                            select(Channels).where(Channels.username == identifier[1:])
                        ).scalar_one_or_none()
                    else:
                        # Пробуем найти по peer_id (предполагая, что identifier - это число)
                        try:
                            peer_id = int(identifier)
                            channel = session.execute(
                                select(Channels).where(Channels.peer_id == peer_id)
                            ).scalar_one_or_none()
                        except ValueError:
                            channel = None
                    
                    if channel:
                        source_channels.append(channel)
                
                if not source_channels:
                    logging.warning(f"Нет каналов в БД, соответствующих источникам для {target_channel_id}")
                    return []
                
                # Получаем peer_id каналов-источников
                source_peer_ids = [ch.peer_id for ch in source_channels]
                
                logging.info(f"Фильтрация по источникам {source_peer_ids} для канала {target_channel_id}")
                
                # Фильтруем сообщения только из этих источников
                base_query = base_query.where(Messages.channel_id.in_(source_peer_ids))
            
            # Дополняем запрос сортировкой и лимитом
            query = (
                base_query
                .order_by(Messages.date.asc())
                .limit(limit)
            )
            
            return session.execute(query).scalars().all()
            
    messages = await asyncio.to_thread(_get_sync)
    
    if messages:
        logging.info(f"Найдено {len(messages)} сообщений для постинга в канал {target_channel_id or 'все каналы'}.")
    else:
        logging.info(f"Нет сообщений для постинга в канал {target_channel_id or 'все каналы'}.")
        
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
    1. Проверяет наличие изображения для сообщения
    2. Отправляет POST запрос в AI сервис с текстом и информацией об изображении
    3. Получает и проверяет ответ от сервиса
    4. Извлекает обработанный текст из ответа
    5. Логирует результаты
    """
    
    logging.info(f"ID {message_id}: Отправка в AI ({service_url}): {text_to_process[:30]}...")
    
    # Проверяем наличие изображения
    photo_path = f"database/photos/{message_id}.jpg"
    has_photo = os.path.exists(photo_path)
    
    # Добавляем информацию о наличии изображения в запрос
    payload = {
        "posts": [text_to_process],
        "has_image": has_photo
    }
    
    if has_photo:
        logging.info(f"ID {message_id}: Сообщение содержит изображение, эта информация добавлена в запрос к AI")
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Делаем запрос к API
            response = await client.post(service_url, json=payload)
            
            # Проверяем статус ответа
            if response.status_code != 200:
                logging.error(f"ID {message_id}: Ошибка при запросе к AI: {response.status_code} - {response.text}")
                return None
                
            # Получаем данные из ответа
            response_data = response.json()
            
            # Проверяем структуру ответа
            if not response_data.get('status') == 'success' or 'result' not in response_data:
                logging.error(f"ID {message_id}: Некорректный ответ от AI: {response_data}")
                return None
                
            # Получаем результаты
            result = response_data['result']
            
            # Проверяем, что результат непустой
            if not result or len(result) == 0:
                logging.info(f"ID {message_id}: AI вернул пустой результат - пост отфильтрован как нерелевантный")
                return None
                
            # Извлекаем обработанный текст
            processed_text = result[0].get('text', '') if isinstance(result, list) and len(result) > 0 else ''
            
            # Проверяем, что обработанный текст не пустой и достаточно содержательный
            if not processed_text or len(processed_text) < 10:
                logging.info(f"ID {message_id}: AI вернул слишком короткий результат ({len(processed_text) if processed_text else 0} символов) - пост отфильтрован")
                return None
                
            logging.info(f"ID {message_id}: AI успешно обработал пост: {processed_text[:30]}...")
            return processed_text
            
    except Exception as e:
        logging.error(f"ID {message_id}: Ошибка при запросе к AI: {e}", exc_info=True)
        return None


def generate_content_hash(text: str) -> str:
    """Генерирует хеш для текста, игнорируя пунктуацию и регистр"""
    if not text:
        return ""
    # Приводим к нижнему регистру и удаляем лишние символы
    normalized = re.sub(r'[^\w\s]', '', text.lower())
    # Удаляем лишние пробелы
    normalized = ' '.join(normalized.split())
    return hashlib.md5(normalized.encode()).hexdigest()


async def check_content_duplicate_in_db(content: str, target_channel_id: str = None, hours_back: int = 24) -> bool:
    """
    Проверяет, не был ли уже опубликован похожий контент в последние N часов
    
    Args:
        content (str): Текст для проверки
        target_channel_id (str): ID целевого канала (опционально)
        hours_back (int): Количество часов назад для проверки (по умолчанию 24)
        
    Returns:
        bool: True если дубликат найден, False если контент уникален
    """
    if not content:
        return False
        
    content_hash = generate_content_hash(content)
    if not content_hash:
        return False
    
    def _check_sync():
        with SessionLocal() as session:
            # Создаем базовый запрос
            query = select(Messages).where(
                Messages.status == NewsStatus.POSTED,
                Messages.date >= datetime.now() - timedelta(hours=hours_back)
            )
            
            # Если указан конкретный канал, фильтруем по нему
            if target_channel_id:
                query = query.where(Messages.target_channel_id == target_channel_id)
            
            posted_messages = session.execute(query).scalars().all()
            
            # Проверяем хеши опубликованных сообщений
            for msg in posted_messages:
                if msg.ai_processed_text:
                    existing_hash = generate_content_hash(msg.ai_processed_text)
                    if existing_hash == content_hash:
                        logging.info(f"Найден дубликат: сообщение ID {msg.id} имеет похожий контент")
                        return True
            return False
    
    return await asyncio.to_thread(_check_sync)


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
    4. Проверяет на дубликаты в базе данных
    5. Обрабатывает возможные ошибки (сеть, HTTP, прочие)
    6. Обновляет статус и результат в БД
    
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

        # Проверка результата AI
        if processed_text_from_ai:
            # Проверяем на дубликаты в базе данных
            is_duplicate = await check_content_duplicate_in_db(processed_text_from_ai)
            
            if is_duplicate:
                logging.info(f"ID {message_id}: AI обработал текст, но он является дубликатом уже опубликованного контента")
                new_status = NewsStatus.ERROR_AI_PROCESSING
                processed_text_from_ai = "Контент отфильтрован как дубликат"
            else:
                new_status = NewsStatus.AI_PROCESSED
                logging.info(f"ID {message_id}: Контент уникален, готов к публикации")
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

    # Финальное обновление статуса
    await _update_message_status(message_id, new_status, processed_text_from_ai)
    logging.info(f"ID {message_id}: Обработка завершена. Статус: {new_status.value}")


async def get_messages_with_errors(limit: int = 2, max_retry_count: int = 3) -> list[Messages]:
    """
    Получает сообщения с ошибками, которые можно повторно обработать.
    
    Args:
        limit (int): Максимальное количество сообщений для получения. По умолчанию 2.
        max_retry_count (int): Максимальное количество попыток обработки. По умолчанию 3.
        
    Returns:
        list[Messages]: Список объектов Messages с ошибками для повторной обработки.
        
    Действия:
    1. Получает сообщения со статусами ERROR_AI_PROCESSING и ERROR_POSTING
    2. Фильтрует по количеству попыток обработки (меньше max_retry_count)
    3. Сортирует по дате (старые в начале)
    4. Ограничивает количество записей параметром limit
    """
    
    logging.info("Получение сообщений с ошибками для повторной обработки...")
    
    def _get_sync():
        with SessionLocal() as session:
            # Добавляем поле для хранения количества попыток обработки, если его нет
            try:
                if not hasattr(Messages, 'retry_count'):
                    from sqlalchemy import Column, Integer
                    Messages.retry_count = Column(Integer, default=0)
                    logging.info("Добавлено поле retry_count в модель Messages")
            except Exception as e:
                logging.warning(f"Не удалось проверить/добавить поле retry_count: {e}")
            
            # Запрос на получение сообщений с ошибками
            query = (
                select(Messages)
                .where(
                    (Messages.status == NewsStatus.ERROR_AI_PROCESSING) | 
                    (Messages.status == NewsStatus.ERROR_POSTING),
                    (Messages.retry_count < max_retry_count) | (Messages.retry_count == None)
                )
                .order_by(Messages.date.asc())
                .limit(limit)
            )
            return session.execute(query).scalars().all()
            
    messages = await asyncio.to_thread(_get_sync)
    
    if messages:
        logging.info(f"Найдено {len(messages)} сообщений с ошибками для повторной обработки.")
    else:
        logging.info("Нет сообщений с ошибками для повторной обработки.")
        
    return messages


async def increment_retry_count(message_id: int) -> None:
    """
    Увеличивает счетчик попыток обработки сообщения.
    
    Args:
        message_id (int): ID сообщения для обновления
    """
    
    def _update_sync():
        with SessionLocal() as session:
            message = session.get(Messages, message_id)
            if message:
                if hasattr(message, 'retry_count') and message.retry_count is not None:
                    message.retry_count += 1
                else:
                    message.retry_count = 1
                session.commit()
                logging.info(f"ID {message_id}: Увеличен счетчик попыток обработки до {message.retry_count}")
            else:
                logging.warning(f"ID {message_id}: Сообщение не найдено для обновления счетчика попыток")
                
    await asyncio.to_thread(_update_sync)


async def process_error_messages() -> None:
    """
    Повторно обрабатывает сообщения с ошибками.
    
    Действия:
    1. Получает сообщения с ошибками обработки AI и постинга
    2. Для каждого сообщения:
       - Увеличивает счетчик попыток
       - В зависимости от статуса ошибки повторно обрабатывает через AI или отправляет в постинг
    """
    logging.info("Запуск обработки сообщений с ошибками")
    
    messages = await get_messages_with_errors(limit=2)
    
    if not messages:
        return
        
    for msg in messages:
        # Увеличиваем счетчик попыток
        await increment_retry_count(msg.id)
        
        if msg.status == NewsStatus.ERROR_AI_PROCESSING:
            # Повторная обработка через AI
            if msg.text:
                logging.info(f"ID {msg.id}: Повторная отправка в AI")
                await simplified_process_message(msg.id, msg.text)
            else:
                logging.warning(f"ID {msg.id}: Отсутствует текст для повторной обработки")
                await _update_message_status(
                    msg.id,
                    NewsStatus.ERROR_PERMANENT,
                    "Отсутствует исходный текст для обработки"
                )
        
        elif msg.status == NewsStatus.ERROR_POSTING:
            # Повторная отправка в постинг (статус остается AI_PROCESSED)
            if msg.ai_processed_text:
                logging.info(f"ID {msg.id}: Сброс статуса на AI_PROCESSED для повторного постинга")
                await _update_message_status(msg.id, NewsStatus.AI_PROCESSED)
            else:
                logging.warning(f"ID {msg.id}: Отсутствует обработанный текст для повторного постинга")
                await _update_message_status(
                    msg.id,
                    NewsStatus.ERROR_PERMANENT,
                    "Отсутствует обработанный текст для постинга"
                )
        
        await asyncio.sleep(1)  # Пауза между обработкой сообщений


async def mark_permanently_failed_messages() -> None:
    """
    Помечает сообщения, которые не удалось обработать после максимального количества попыток.
    """
    def _update_sync():
        with SessionLocal() as session:
            # Запрос на обновление статуса сообщений с превышенным количеством попыток
            stmt = (
                update(Messages)
                .where(
                    ((Messages.status == NewsStatus.ERROR_AI_PROCESSING) | 
                     (Messages.status == NewsStatus.ERROR_POSTING)),
                    Messages.retry_count >= 3
                )
                .values(status=NewsStatus.ERROR_PERMANENT)
            )
            result = session.execute(stmt)
            session.commit()
            return result.rowcount
            
    updated_count = await asyncio.to_thread(_update_sync)
    
    if updated_count > 0:
        logging.info(f"Помечено {updated_count} сообщений как необратимо проблемные (ERROR_PERMANENT)")


async def main_logic(bot_for_posting: Bot | None):
    """
    Основная логика обработки и публикации сообщений.
    
    Args:
        bot_for_posting (Bot | None): Инстанс бота для публикации сообщений.
            Если None, этап публикации будет пропущен.
            
    Действия:
    1. Запускает обработку сообщений через AI
    2. Делает паузу между этапами
    3. Публикует обработанные сообщения в Telegram каналы
       (если предоставлен бот и каналы настроены в базе данных)
    4. Обрабатывает сообщения с ошибками
    5. Помечает окончательно проблемные сообщения
    """
    
    logging.info("main_logic запущен")

    # Этап 1: Обработка AI
    await _process_ai_messages()
    
    await asyncio.sleep(1)  # Пауза между этапами

    # Этап 2: Постинг в Telegram
    if not bot_for_posting:
        logging.warning(
            "Инстанс бота для постинга не предоставлен. "
            "Этап постинга пропускается."
        )
        return
    
    # Получаем все активные целевые каналы из базы данных
    active_targets = await asyncio.to_thread(posting_target_repository.get_all_active_target_channels)
    
    if not active_targets:
        logging.info("Нет активных целевых каналов в базе данных. Постинг пропускается.")
        return
    
    logging.info(f"Найдено {len(active_targets)} активных целевых каналов для постинга.")
    
    # Обрабатываем постинг для каждого канала отдельно
    for target in active_targets:
        target_id = target["target_chat_id"]
        logging.info(f"Обработка постинга для канала {target_id}")
        
        # Получаем сообщения для конкретного канала
        messages = await get_messages_ready_for_posting(limit=2, target_channel_id=target_id)
        
        if not messages:
            logging.info(f"Нет сообщений для постинга в канал {target_id}.")
            continue
            
        logging.info(f"Найдено {len(messages)} сообщений для постинга в канал {target_id}.")
        
        # Создаем список с одним текущим каналом
        channel = [{
            "target_chat_id": target_id,
            "target_title": target.get("target_title", "Без названия")
        }]
        
        # Отправляем сообщения в этот канал
        await _process_posting_messages_multi_channel(bot_for_posting, channel, messages)
        
        # Небольшая пауза между обработкой разных каналов
        await asyncio.sleep(1)
    
    # Этап 3: Обработка сообщений с ошибками
    await process_error_messages()
    
    # Этап 4: Пометка окончательно проблемных сообщений
    await mark_permanently_failed_messages()


async def run_periodic_tasks(bot_for_posting: Bot | None):
    """
    Запускает периодические задачи обработки и публикации сообщений.
    
    Args:
        bot_for_posting (Bot | None): Инстанс бота для публикации сообщений.
            Если None, этап публикации будет пропущен.
            
    Действия:
    1. Запускает бесконечный цикл выполнения основной логики
    2. Периодически проверяет обновления в настройках каналов
    3. Делает паузу между итерациями
    4. Логирует каждую итерацию
    """
    
    global last_targets_check
    
    logging.info("Запуск run_periodic_tasks в posting_worker...")
    while True:
        await main_logic(bot_for_posting)
        
        # Проверяем, прошло ли 30 секунд с последней проверки целевых каналов
        # или было вызвано событие обновления
        current_time = datetime.now()
        if posting_settings_update_event.is_set() or (current_time - last_targets_check).total_seconds() > 30:
            if posting_settings_update_event.is_set():
                logging.info("Получено событие обновления настроек целевых каналов.")
                posting_settings_update_event.clear()
            else:
                logging.info("Плановая проверка обновлений в настройках целевых каналов...")
                
            last_targets_check = current_time
            # Здесь нет необходимости в дополнительных действиях, 
            # так как main_logic получает актуальные данные при каждом вызове
        
        logging.info("posting_worker: Следующий цикл через 10 секунд...")
        try:
            # Ждем событие обновления с таймаутом
            await asyncio.wait_for(posting_settings_update_event.wait(), timeout=10)
            logging.info("Получено событие обновления, начинаем новую итерацию")
        except asyncio.TimeoutError:
            # Тайм-аут истек, продолжаем штатно
            pass


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


async def _process_posting_messages_multi_channel(bot: Bot, target_channels: list[dict], messages: list[Messages]):
    """
    Обрабатывает сообщения для постинга в несколько Telegram каналов.
    
    Args:
        bot (Bot): Экземпляр бота Telegram для отправки сообщений
        target_channels (list[dict]): Список словарей с информацией о целевых каналах
        messages (list[Messages]): Список сообщений для постинга
        
    Действия:
    1. Для каждого сообщения:
       - Проверяет наличие обработанного AI текста
       - Если текст есть - отправляет во все Telegram каналы из списка
       - Обновляет статус сообщения в БД (POSTED или ERROR_POSTING)
    2. Делает паузу 1 секунду между отправкой сообщений
    
    Returns:
        None
    """
    if not messages:
        logging.info("Нет сообщений для постинга в мультиканальном режиме.")
        return
    
    if not target_channels:
        logging.info("Нет целевых каналов для постинга.")
        return
    
    channels_str = ", ".join([f"{ch.get('target_title', 'Без названия')}({ch['target_chat_id']})" for ch in target_channels])
    logging.info(f"Постинг {len(messages)} сообщений в каналы: {channels_str}")
    
    for msg in messages:
        if not msg.ai_processed_text:
            logging.warning(
                f"Сообщение ID {msg.id} (для мультиканального постинга) не имеет "
                "обработанного текста. Пропуск."
            )
            continue
        
        # Отправляем сообщение во все каналы из списка
        overall_success = True  # Предполагаем успех для всех каналов
        posting_results = []
        
        for channel in target_channels:
            channel_id = channel["target_chat_id"]
            channel_title = channel.get("target_title", "Без названия")
            
            success = await post_message_to_telegram(
                bot,
                channel_id,
                msg.ai_processed_text,
                msg.id
            )
            
            posting_results.append({
                "channel_id": channel_id,
                "channel_title": channel_title,
                "success": success
            })
            
            if not success:
                overall_success = False
            
            # Небольшая пауза между отправками в разные каналы
            await asyncio.sleep(0.5)
        
        # Определяем итоговый статус сообщения
        status = NewsStatus.POSTED if overall_success else NewsStatus.ERROR_POSTING
        
        # Формируем детальный отчет о постинге
        result_details = ", ".join([
            f"{r['channel_title']}({r['channel_id']}): {'OK' if r['success'] else 'ОШИБКА'}"
            for r in posting_results
        ])
        
        logging.info(f"ID {msg.id}: Результаты постинга: {result_details}")
        
        # Обновляем статус сообщения в БД
        await _update_message_status(msg.id, status)
        logging.info(f"ID {msg.id}: Финальный статус в БД: {status.value}")
        
        # Пауза перед обработкой следующего сообщения
        await asyncio.sleep(1)


def create_bot():
    """
    Создает и возвращает экземпляр бота для постинга.
    
    Returns:
        Bot: Экземпляр бота для постинга
    """
    token = settings.telegram_bot.bot_token
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


async def _process_posting_messages(bot: Bot, channel_id: str):
    """
    Обрабатывает сообщения для постинга в Telegram канал (для обратной совместимости).
    
    Args:
        bot (Bot): Экземпляр бота Telegram для отправки сообщений
        channel_id (str): Идентификатор канала для отправки
        
    Действия:
        Делегирует работу функции _process_posting_messages_multi_channel
        для обеспечения обратной совместимости.
    """
    # Получаем сообщения специфично для этого канала
    messages = await get_messages_ready_for_posting(limit=2, target_channel_id=channel_id)
    
    if not messages:
        logging.info(f"Нет сообщений, готовых к постингу в канал {channel_id}, в этом цикле.")
        return
    
    # Создаем список с одним каналом
    single_channel = [{
        "target_chat_id": channel_id,
        "target_title": f"Канал {channel_id}"
    }]
    
    # Делегируем работу мультиканальной функции
    await _process_posting_messages_multi_channel(bot, single_channel, messages)


def trigger_update():
    """
    Вызывает немедленное обновление списка целевых каналов для постинга.
    Эта функция используется для обновления настроек постинга из других модулей.
    """
    posting_settings_update_event.set()
    logging.info("Запущено обновление настроек постинга из posting_worker")


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
