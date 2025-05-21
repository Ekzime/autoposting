import asyncio
import logging
import os
import re
import sys
import signal
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
    PeerChat,
    MessageViews
)

# Импорт настроек
from config import settings

# Импорт DB-функций
# Используем функции вместо прямых импортов репозиториев
from database.repositories import parsing_telegram_acc_repository, parsing_source_repository
from database.channels import add_channel, get_channel_by_peer_id
from database.messages import add_message

# Настройка логгера
logger = logging.getLogger(__name__)

# Константы
PHOTO_STORAGE = settings.telegram_parser.photo_storage

# Глобальные переменные
client = None
active_account_id = None
active_sources = []
update_event = asyncio.Event()
TOTAL_HANDLED = 0

# Статус запуска
is_running = True

def check_message_for_links(message: Message) -> List[str]:
    """Проверяет сообщение на наличие ссылок"""
    found_urls = []
    
    if message.entities:
        for entity in message.entities:
            if isinstance(entity, MessageEntityUrl):
                found_urls.append(message.text[entity.offset : entity.offset + entity.length])
            elif isinstance(entity, MessageEntityTextUrl):
                found_urls.append(entity.url)
    
    if not found_urls and message.text:
        url_pattern = re.compile(r'https?://\S+|www\.\S+')
        matches = url_pattern.findall(message.text)
        for match in matches:
            if match not in found_urls:
                found_urls.append(match)
                    
    return found_urls

async def get_message_views(client: TelegramClient, message: Message) -> int:
    """Получает количество просмотров сообщения"""
    try:
        views = await asyncio.wait_for(
            client(functions.messages.GetMessagesViewsRequest(
                peer=message.peer_id, id=[message.id], increment=True
            )),
            timeout=10
        )
        return views.views[0].views
    except Exception as e:
        logger.error(f"Ошибка при получении просмотров: {e}")
        return 0

async def get_active_account_from_db():
    """Получает активный аккаунт из БД"""
    try:
        # Выполняем синхронные операции в отдельном потоке
        active_accounts = await asyncio.to_thread(parsing_telegram_acc_repository.get_active_parsing_accounts)
        
        if active_accounts and len(active_accounts) > 0:
            logger.info(f"Найден активный аккаунт: ID {active_accounts[0]['id']}")
            return active_accounts[0]
        
        logger.warning("Нет активных аккаунтов в БД")
        return None
    except Exception as e:
        logger.error(f"Ошибка при получении активного аккаунта: {e}")
        return None

async def get_parsing_sources_from_db():
    """Получает список источников из БД"""
    try:
        sources = await asyncio.to_thread(parsing_source_repository.get_all_sources)
        source_identifiers = [source['source_identifier'] for source in sources]
        logger.info(f"Получено {len(source_identifiers)} источников для парсинга")
        return source_identifiers
    except Exception as e:
        logger.error(f"Ошибка при получении источников: {e}")
        return []

async def setup_client(account_data):
    """Создает и подключает клиент Telegram"""
    global client
    
    try:
        # Проверка API настроек
        if not settings.telegram_api.api_id or not settings.telegram_api.api_hash:
            logger.error("API ID/Hash не настроены")
            return None
        
        # Проверка сессии
        if not account_data.get('session_string'):
            logger.error("Отсутствует строка сессии")
            return None
            
        # Создаем клиента
        client = TelegramClient(
            StringSession(account_data['session_string']),
            settings.telegram_api.api_id,
            settings.telegram_api.api_hash
        )
        
        # Подключаемся с таймаутом
        logger.info("Подключение к Telegram...")
        try:
            await asyncio.wait_for(client.connect(), timeout=30)
        except asyncio.TimeoutError:
            logger.error("Превышен таймаут подключения")
            return None
        except Exception as e:
            logger.error(f"Ошибка подключения: {e}")
            return None
        
        # Проверяем авторизацию
        try:
            is_authorized = await asyncio.wait_for(client.is_user_authorized(), timeout=10)
            if not is_authorized:
                logger.error("Клиент не авторизован")
                return None
            
            # Получаем данные пользователя
            me = await asyncio.wait_for(client.get_me(), timeout=10)
            logger.info(f"Авторизованы как: {me.first_name} {me.last_name or ''}")
            
            return client
        except Exception as e:
            logger.error(f"Ошибка проверки авторизации: {e}")
            return None
    except Exception as e:
        logger.error(f"Ошибка при настройке клиента: {e}")
        return None

async def join_channel_if_needed(source_identifier):
    """Присоединяется к каналу если нужно"""
    global client
    
    try:
        # Получаем информацию с таймаутом
        try:
            entity = await asyncio.wait_for(
                client.get_entity(source_identifier), 
                timeout=20
            )
        except asyncio.TimeoutError:
            logger.error(f"Таймаут при получении данных канала {source_identifier}")
            return None
        except Exception as e:
            logger.error(f"Ошибка при получении данных канала {source_identifier}: {e}")
            return None
            
        # Проверяем тип
        if not isinstance(entity, Channel):
            logger.warning(f"Источник {source_identifier} не является каналом")
            return None
            
        logger.info(f"Успешно получен канал: {entity.title}")
        return entity
    except Exception as e:
        logger.error(f"Общая ошибка при подключении к {source_identifier}: {e}")
        return None

async def handle_new_message(event):
    """Обрабатывает новое сообщение"""
    global TOTAL_HANDLED
    
    try:
        message = event.message
        
        # Получаем ID канала
        if isinstance(message.peer_id, PeerChannel):
            channel_id = message.peer_id.channel_id
        elif isinstance(message.peer_id, PeerChat):
            channel_id = message.peer_id.chat_id
        elif isinstance(message.peer_id, PeerUser):
            channel_id = message.peer_id.user_id
        else:
            logger.warning(f"Неизвестный тип peer_id: {message.peer_id}")
            return
            
        # Проверяем канал в БД
        channel = await asyncio.to_thread(get_channel_by_peer_id, channel_id)
        if not channel:
            try:
                channel_entity = await client.get_entity(PeerChannel(channel_id))
                await asyncio.to_thread(add_channel, channel_entity)
            except Exception as e:
                logger.error(f"Ошибка при добавлении канала: {e}")
                return
        
        # Обрабатываем фото
        photo_path = None
        if message.photo and PHOTO_STORAGE:
            try:
                photo_path = os.path.join(PHOTO_STORAGE, f"{message.id}.jpg")
                await asyncio.wait_for(message.download_media(photo_path), timeout=20)
            except Exception as e:
                logger.error(f"Ошибка при скачивании фото: {e}")
                photo_path = None
        
        # Получаем ссылки и просмотры
        links = check_message_for_links(message)
        views = await get_message_views(client, message)
        
        # Добавляем сообщение в БД
        await asyncio.to_thread(
            add_message,
            channel_id=channel_id,
            message_id=message.id,
            text=message.text,
            date=message.date,
            photo_path=photo_path,
            links=links,
            views=views
        )
        
        TOTAL_HANDLED += 1
        logger.info(f"Обработано сообщение ID: {message.id}, всего: {TOTAL_HANDLED}")
    except Exception as e:
        logger.error(f"Ошибка при обработке сообщения: {e}")

async def setup_message_handlers(channel_entities):
    """Настраивает обработчики сообщений"""
    global client
    
    try:
        # Очищаем предыдущие обработчики
        try:
            client.remove_event_handler(handle_new_message, events.NewMessage)
        except:
            pass
            
        # Получаем ID каналов
        channel_ids = [entity.id for entity in channel_entities if entity]
        
        if not channel_ids:
            logger.warning("Нет каналов для отслеживания")
            return
            
        # Настраиваем обработчик
        client.add_event_handler(
            handle_new_message,
            events.NewMessage(chats=channel_ids)
        )
        
        logger.info(f"Настроены обработчики для {len(channel_ids)} каналов")
    except Exception as e:
        logger.error(f"Ошибка при настройке обработчиков: {e}")

async def check_updates_loop():
    """Основной цикл проверки обновлений"""
    global client, active_account_id, active_sources, is_running
    
    logger.info("Запуск основного цикла проверки")
    
    # Счетчик для отладки
    attempt_count = 0
    max_attempts = 3
    
    while is_running:
        try:
            attempt_count += 1
            logger.info(f"Начало итерации #{attempt_count}")
            
            # Для отладки
            if attempt_count > max_attempts:
                logger.info(f"Достигнуто максимальное число попыток ({max_attempts}), завершаем...")
                break
                
            # Получаем активный аккаунт
            account_data = await get_active_account_from_db()
            
            if not account_data:
                logger.warning("Нет активного аккаунта, ожидание 30 сек...")
                await asyncio.sleep(30)
                continue
                
            # Проверяем изменения аккаунта
            if active_account_id != account_data['id']:
                logger.info(f"Смена активного аккаунта на ID: {account_data['id']}")
                
                # Отключаем предыдущий клиент
                if client:
                    await client.disconnect()
                    
                # Настраиваем новый клиент
                active_account_id = account_data['id']
                client = await setup_client(account_data)
                
                if not client:
                    logger.error("Ошибка настройки клиента")
                    active_account_id = None
                    await asyncio.sleep(30)
                    continue
            
            # Получаем источники
            current_sources = await get_parsing_sources_from_db()
            
            if not current_sources:
                logger.warning("Нет источников для парсинга")
                await asyncio.sleep(30)
                continue
                
            # Проверяем изменения в источниках
            if set(current_sources) != set(active_sources):
                logger.info("Обновление списка источников")
                active_sources = current_sources
                
                # Подключаемся к каналам
                channel_entities = []
                for source in active_sources:
                    entity = await join_channel_if_needed(source)
                    if entity:
                        channel_entities.append(entity)
                        
                # Настраиваем обработчики
                if channel_entities:
                    await setup_message_handlers(channel_entities)
                    logger.info(f"Отслеживается {len(channel_entities)} каналов")
                else:
                    logger.warning("Не удалось подключиться ни к одному каналу")
            
            # Ждем до следующей проверки
            logger.info("Ожидание 60 секунд")
            await asyncio.sleep(60)
            
        except Exception as e:
            logger.error(f"Ошибка в цикле обновлений: {e}")
            await asyncio.sleep(30)

async def run_parser():
    """Запускает сервис парсера"""
    global is_running
    
    try:
        # Проверяем папку для фото
        if PHOTO_STORAGE and not os.path.exists(PHOTO_STORAGE):
            try:
                os.makedirs(PHOTO_STORAGE)
                logger.info(f"Создана папка для фото: {PHOTO_STORAGE}")
            except Exception as e:
                logger.error(f"Ошибка создания папки для фото: {e}")
        
        # Запускаем основной цикл
        logger.info("Запуск основного цикла парсера")
        await check_updates_loop()
        
        # Отключаем клиент
        if client:
            await client.disconnect()
            logger.info("Клиент отключен")
            
    except asyncio.CancelledError:
        logger.info("Задача отменена")
        if client:
            await client.disconnect()
    except Exception as e:
        logger.error(f"Неожиданная ошибка в парсере: {e}")
        if client:
            await client.disconnect()

def signal_handler(sig, frame):
    """Обработчик сигналов для корректного завершения"""
    global is_running
    print("Получен сигнал завершения, останавливаем парсер...")
    is_running = False

def start_parser_service():
    """Функция для запуска сервиса из других модулей"""
    logger.info("Запуск сервиса парсера")
    return asyncio.create_task(run_parser())

# Точка входа при запуске напрямую
if __name__ == "__main__":
    print("Скрипт parser_service.py запущен напрямую")
    
    # Настройка логирования
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('parser_debug.log')
        ]
    )
    
    # Более тихий лог для некоторых модулей
    logging.getLogger('telethon').setLevel(logging.WARNING)
    logging.getLogger('asyncio').setLevel(logging.WARNING)
    
    print("Запуск парсера...")
    
    try:
        # Настраиваем для Windows
        if sys.platform.startswith('win'):
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
        # Регистрируем обработчик сигналов
        signal.signal(signal.SIGINT, signal_handler)
        
        asyncio.run(asyncio.wait_for(run_parser()))
        print("Парсер завершил работу")
    except KeyboardInterrupt:
        print("Прервано пользователем")
    except Exception as e:
        print(f"Критическая ошибка: {e}")
        import traceback
        traceback.print_exc() 