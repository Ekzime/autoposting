import asyncio
import logging
import os
import re
from typing import Dict, List, Optional, Union
from datetime import datetime

from telethon import TelegramClient, events, functions
from telethon.sessions import StringSession
from telethon.tl.types import (
    Channel, 
    Message, 
    PeerChannel,
    MessageEntityTextUrl,
    MessageEntityUrl,
    PeerUser,
    PeerChat
)

# Импорт настроек и фунций для работы с API
from config import settings
from .config import PHOTO_STORAGE
from .telegram_requests import get_message_views

# Импорт функций для работы с базой данных
from database.dao.pars_telegram_acc_repository import ParsingTelegramAccRepository
from database.channels import add_channel, get_channel_by_peer_id
from database.messages import add_message

# Настройка логгера
logger = logging.getLogger(__name__)

# Глобальный клиент Telegram
client = None

# Глобальные идентификаторы для отслеживания состояния
active_account_id = None
active_sources = []

# Событие для принудительного обновления
update_event = asyncio.Event()

# Счетчик обработанных сообщений
TOTAL_HANDLED = 0

def check_message_for_links(message: Message) -> List[str]:
    """
    Проверяет сообщение на наличие ссылок
    
    Args:
        message: объект сообщения Telegram
        
    Returns:
        Список найденных URL-адресов
    """
    found_urls: List[str] = []
    
    # Проверка наличия специальных сущностей в сообщении (встроенные ссылки)
    if message.entities:
        for entity in message.entities:
            if isinstance(entity, MessageEntityUrl):
                found_urls.append(message.text[entity.offset : entity.offset + entity.length])
            elif isinstance(entity, MessageEntityTextUrl):
                found_urls.append(entity.url)
    
    # Если ссылки не найдены через entities, ищем их в тексте через регулярные выражения
    if not found_urls and message.text:
        url_pattern = re.compile(r'https?://\S+|www\.\S+')
        matches = url_pattern.findall(message.text)
        if matches:
            for match in matches:
                if match not in found_urls:
                    found_urls.append(match)
                    
    return found_urls

async def parse_channel_history(channel_identifier: Union[int, str], limit: Optional[int] = None):
    """
    Парсит историю сообщений канала
    
    Args:
        channel_identifier: идентификатор или ссылка на канал
        limit: ограничение количества сообщений для парсинга
    """
    global client
    
    if not client:
        logger.error("Клиент Telegram не инициализирован")
        return
    
    start_timestamp = datetime.now()
    logger.info(f"Начинаю парсинг канала {channel_identifier}")
    
    try:
        # Получаем информацию о канале
        target_entity = await client.get_entity(channel_identifier)
        
        # Проверяем, является ли сущность каналом и добавляем в БД
        if isinstance(target_entity, Channel):
            logger.info(f"Проверка/добавление основного канала '{target_entity.title}' (ID: {target_entity.id}) в БД")
            add_channel(target_entity)
        else:
            logger.warning(f"Целевая сущность {channel_identifier} не является Channel, пропускаем добавление в БД")
            return
    
        count = 0
        # Итерируемся по сообщениям канала
        async for message in client.iter_messages(target_entity):
            if limit and count >= limit:
                break
            
            count += 1
            
            # Обработка фотографий в сообщении
            photo_path = None
            if message.photo:
                photo_path = os.path.join(PHOTO_STORAGE, f"{message.id}.jpg")
                await message.download_media(photo_path)
            
            # Получение ссылок и просмотров
            links = check_message_for_links(message)
            views = await get_message_views(client, message)
            
            # Добавление сообщения в базу данных
            add_message(
                channel_id=target_entity.id,
                message_id=message.id,
                text=message.text,
                date=message.date,
                photo_path=photo_path,
                links=links,
                views=views
            )
            
            if count % 100 == 0:
                logger.info(f"Обработано {count} сообщений из канала {target_entity.title}")
        
        elapsed = datetime.now() - start_timestamp
        logger.info(f"Парсинг канала {target_entity.title} завершен. Обработано {count} сообщений за {elapsed}")
        
    except Exception as e:
        logger.error(f"Ошибка при парсинге канала {channel_identifier}: {e}")

async def get_active_account_from_db():
    """
    Получает активный аккаунт для парсинга из базы данных.
    
    Returns:
        dict | None: Словарь с данными аккаунта или None, если аккаунт не найден
    """
    repo = ParsingTelegramAccRepository()
    
    try:
        # Получаем список активных аккаунтов
        active_accounts = repo.get_active_parsing_accounts()
        if active_accounts and len(active_accounts) > 0:
            # Возвращаем первый активный аккаунт
            return active_accounts[0]
        return None
    except Exception as e:
        logger.error(f"Ошибка при получении активного аккаунта: {e}")
        return None

async def get_parsing_sources_from_db():
    """
    Получает список идентификаторов источников для парсинга из базы данных.
    
    Returns:
        list: Список идентификаторов источников
    """
    from database.dao.parsing_source_repository import ParsingSourceRepository
    repo = ParsingSourceRepository()
    
    try:
        # Получаем все источники
        sources = repo.get_all_sources()
        # Извлекаем только идентификаторы источников
        source_identifiers = [source['source_identifier'] for source in sources]
        return source_identifiers
    except Exception as e:
        logger.error(f"Ошибка при получении источников парсинга: {e}")
        return []

async def setup_client(account_data):
    """
    Настраивает и запускает клиент Telegram.
    
    Args:
        account_data (dict): Данные аккаунта для авторизации
        
    Returns:
        TelegramClient | None: Настроенный клиент или None в случае ошибки
    """
    global client
    
    try:
        # Создаем временный файл сессии
        session_file = f"temp_session_{account_data['id']}.session"
        
        # Проверяем, есть ли сохраненная строка сессии
        if account_data.get('session_string'):
            # Если есть строка сессии, используем ее
            client = TelegramClient(
                StringSession(account_data['session_string']),
                settings.telegram_api.api_id,
                settings.telegram_api.api_hash
            )
        else:
            # Иначе создаем клиент с файлом сессии
            client = TelegramClient(
                session_file,
                settings.telegram_api.api_id,
                settings.telegram_api.api_hash
            )
        
        # Подключаемся к серверам Telegram
        await client.connect()
        
        # Проверяем авторизацию
        if not await client.is_user_authorized():
            logger.error(f"Клиент не авторизован. Необходимо выполнить вход в аккаунт {account_data['phone_number']}")
            return None
        
        logger.info(f"Клиент успешно настроен для аккаунта {account_data['phone_number']}")
        return client
    except Exception as e:
        logger.error(f"Ошибка при настройке клиента: {e}")
        return None

async def join_channel_if_needed(source_identifier):
    """
    Присоединяется к каналу, если пользователь еще не является его участником.
    
    Args:
        source_identifier (str): Идентификатор канала (ссылка, username)
        
    Returns:
        Channel | None: Объект канала или None в случае ошибки
    """
    global client
    
    try:
        # Получаем информацию о канале
        entity = await client.get_entity(source_identifier)
        
        # Проверяем, что это канал
        if not isinstance(entity, Channel):
            logger.warning(f"Источник {source_identifier} не является каналом")
            return None
        
        try:
            # Пытаемся получить полную информацию о канале
            # Это удастся только если мы уже участник
            full_channel = await client(functions.channels.GetFullChannelRequest(
                channel=entity
            ))
            logger.info(f"Уже подписан на канал: {entity.title}")
            return entity
        except Exception:
            # Если не удалось, пробуем присоединиться
            try:
                # Проверяем, является ли источник инвайт-ссылкой
                if source_identifier.startswith(('https://t.me/joinchat/', 'https://t.me/+', 't.me/joinchat/', 't.me/+')):
                    # Извлекаем хеш из ссылки
                    if '/joinchat/' in source_identifier:
                        invite_hash = source_identifier.split('/joinchat/')[1]
                    else:
                        invite_hash = source_identifier.split('/+')[1]
                    
                    # Присоединяемся по хешу
                    await client(functions.messages.ImportChatInviteRequest(
                        hash=invite_hash
                    ))
                    
                    # Пытаемся получить канал по хешу после присоединения
                    entity = await client.get_entity(source_identifier)
                    logger.info(f"Успешно присоединился к каналу по инвайт-ссылке: {entity.title}")
                    return entity
                else:
                    # Если это публичный канал, просто возвращаем сущность
                    logger.info(f"Использую публичный канал: {entity.title}")
                    return entity
            except Exception as e:
                logger.error(f"Не удалось присоединиться к каналу {source_identifier}: {e}")
                return None
    except Exception as e:
        logger.error(f"Ошибка при обработке источника {source_identifier}: {e}")
        return None

async def handle_new_message(event):
    """
    Обрабатывает новое сообщение из канала.
    
    Args:
        event: Событие нового сообщения
    """
    global TOTAL_HANDLED
    
    try:
        message = event.message
        
        # Получаем ID канала из peer_id
        if isinstance(message.peer_id, PeerChannel):
            channel_id = message.peer_id.channel_id
        elif isinstance(message.peer_id, PeerChat):
            channel_id = message.peer_id.chat_id
        elif isinstance(message.peer_id, PeerUser):
            channel_id = message.peer_id.user_id
        else:
            # Для других типов peer_id
            channel_id = getattr(message.peer_id, 'channel_id', None) or getattr(message.peer_id, 'chat_id', None) or getattr(message.peer_id, 'user_id', None)
            if not channel_id:
                logger.warning(f"Не удалось определить ID канала из peer_id: {message.peer_id}")
                return
        
        # Проверяем наличие канала в БД
        channel = get_channel_by_peer_id(channel_id)
        if not channel:
            # Получаем полную информацию о канале
            channel_entity = await client.get_entity(PeerChannel(channel_id))
            if isinstance(channel_entity, Channel):
                # Добавляем канал в БД
                add_channel(channel_entity)
                logger.info(f"Канал '{channel_entity.title}' добавлен в БД")
            else:
                logger.warning(f"Не удалось добавить канал {channel_id} в БД")
                return
        
        # Обрабатываем фотографии в сообщении
        photo_path = None
        if message.photo:
            photo_path = os.path.join(PHOTO_STORAGE, f"{message.id}.jpg")
            await message.download_media(photo_path)
        
        # Получаем ссылки и просмотры
        links = check_message_for_links(message)
        views = await get_message_views(client, message)
        
        # Добавляем сообщение в базу данных
        add_message(
            channel_id=channel_id,
            message_id=message.id,
            text=message.text,
            date=message.date,
            photo_path=photo_path,
            links=links,
            views=views
        )
        
        TOTAL_HANDLED += 1
        logger.info(f"Добавлено новое сообщение из канала {channel_id}, ID сообщения: {message.id}, всего обработано: {TOTAL_HANDLED}")
    except Exception as e:
        logger.error(f"Ошибка при обработке нового сообщения: {e}")

async def setup_message_handlers(channel_entities):
    """
    Настраивает обработчики новых сообщений для списка каналов.
    
    Args:
        channel_entities (list): Список объектов каналов
    """
    global client
    
    try:
        # Очищаем предыдущие обработчики
        try:
            client.remove_event_handler(message_handler_callback, events.NewMessage)
        except Exception:
            # Игнорируем ошибку, если обработчик еще не был установлен
            pass
        
        # Получаем список ID каналов, отфильтровывая None
        channel_ids = [entity.id for entity in channel_entities if entity]
        
        if not channel_ids:
            logger.warning("Нет каналов для настройки обработчиков")
            return
            
        # Регистрируем обработчик для всех каналов
        @client.on(events.NewMessage(chats=channel_ids))
        async def message_handler_callback(event):
            await handle_new_message(event)
        
        logger.info(f"Установлены обработчики для {len(channel_ids)} каналов")
    except Exception as e:
        logger.error(f"Ошибка при настройке обработчиков сообщений: {e}")

async def check_updates_loop():
    """
    Периодически проверяет изменения в базе данных и обновляет 
    список источников для парсинга и активный аккаунт.
    """
    global client, active_account_id, active_sources, update_event
    
    while True:
        try:
            # Проверяем активный аккаунт
            account_data = await get_active_account_from_db()
            
            # Если нет активного аккаунта, ждем и проверяем снова
            if not account_data:
                logger.warning("Нет активного аккаунта для парсинга. Ожидание...")
                if client:
                    await client.disconnect()
                    client = None
                # Ждем 60 секунд или сигнала обновления
                await wait_for_update_or_timeout(60)
                continue
            
            # Проверяем, изменился ли активный аккаунт
            if active_account_id != account_data['id']:
                # Если изменился, перенастраиваем клиент
                if client:
                    await client.disconnect()
                
                active_account_id = account_data['id']
                client = await setup_client(account_data)
                
                if not client:
                    logger.error("Не удалось настроить клиент. Повтор через 60 секунд.")
                    await wait_for_update_or_timeout(60)
                    continue
            
            # Получаем текущие источники для парсинга
            current_sources = await get_parsing_sources_from_db()
            
            # Проверяем, изменился ли список источников
            if set(current_sources) != set(active_sources):
                # Если список изменился, обновляем источники
                active_sources = current_sources
                
                # Присоединяемся к каналам и получаем их сущности
                channel_entities = []
                for source in active_sources:
                    entity = await join_channel_if_needed(source)
                    if entity:
                        channel_entities.append(entity)
                
                # Настраиваем обработчики сообщений для новых каналов
                await setup_message_handlers(channel_entities)
                
                logger.info(f"Обновлен список каналов для парсинга. Отслеживается {len(channel_entities)} каналов.")
            
            # Сбрасываем событие обновления
            update_event.clear()
            
            # Ждем 5 минут или сигнала обновления
            await wait_for_update_or_timeout(300)
            
        except Exception as e:
            logger.error(f"Ошибка в цикле проверки обновлений: {e}")
            await wait_for_update_or_timeout(60)

async def wait_for_update_or_timeout(timeout):
    """
    Ожидает либо сигнала обновления, либо истечения тайм-аута.
    
    Args:
        timeout (int): Время ожидания в секундах
    """
    try:
        await asyncio.wait_for(update_event.wait(), timeout=timeout)
    except asyncio.TimeoutError:
        pass

def trigger_update():
    """
    Вызывает немедленное обновление списка источников и аккаунта.
    Эта функция нужна для использования в обработчиках изменений.
    """
    update_event.set()
    logger.info("Запущено обновление парсера")

async def run_parser():
    """
    Запускает сервис парсера.
    """
    try:
        # Запускаем цикл проверки обновлений
        update_task = asyncio.create_task(check_updates_loop())
        
        # Ждем, пока задача не будет отменена
        await update_task
    except asyncio.CancelledError:
        logger.info("Задача парсера отменена")
        if client:
            await client.disconnect()
    except Exception as e:
        logger.error(f"Неожиданная ошибка в сервисе парсера: {e}")
        if client:
            await client.disconnect()

def start_parser_service():
    """
    Функция для запуска сервиса парсера из внешнего кода.
    
    Returns:
        asyncio.Task: Задача сервиса парсера
    """
    return asyncio.create_task(run_parser())

# Точка входа при запуске скрипта напрямую
if __name__ == "__main__":
    # Настройка логирования
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Запускаем парсер
    asyncio.run(run_parser()) 