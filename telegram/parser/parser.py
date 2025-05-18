# Импорты стандартных библиотек
import os
import re
import asyncio
import database

# Импорты функций для работы с базой данных
from database.messages import add_message, get_all_messages
from database.models import Channels, Messages, NewsStatus, engine, SessionLocal
from database.channels import (
    get_channel_by_peer_id, 
    add_channel, 
    get_all_channels
)

# Импорты библиотеки Telethon для работы с Telegram API
from telethon import TelegramClient, functions
from telethon.events import NewMessage
from telethon.tl.types import (
    Channel,
    Message,
    MessageEntityTextUrl, 
    MessageEntityUrl, 
    MessageViews,
    PeerUser, 
    PeerChat, 
    PeerChannel
)

# Импорт для работы с SQLAlchemy
from sqlalchemy.orm import sessionmaker

# Импорты локальных модулей
from .config import *
from .telegram_requests import get_message_views

# Импорт для работы с датой и временем
from datetime import datetime



class Parser:
    def __init__(
        self, 
        session_name: str, 
        api_id: int, 
        api_hash: str,
        owner_id: int | None = None
    ):
        self.session_name = session_name
        self.api_id = api_id
        self.api_hash = api_hash
        self.client = TelegramClient(session_name, api_id, api_hash)
        self.owner_id = None
        
    
# Инициализация клиента Telegram
client = TelegramClient(
    SESSION, 
    API_ID, 
    API_HASH
)


def check_message_for_links(message: Message) -> list[str]:
    """
    Проверяет сообщение на наличие ссылок
    Args:
        message: объект сообщения Telegram
    Returns:
        Список найденных URL-адресов
    """
    found_urls: list[str] = []
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
            [
                found_urls.append(match) 
                for match in matches 
                if match not in found_urls
            ]
    return found_urls
            

async def parse_messages(channel_id: int | str, limit: int=None):
    """
    Основная функция парсинга сообщений из канала
    Args:
        channel_id: идентификатор или ссылка на канал
        limit: ограничение количества сообщений для парсинга
    """
    start_timestamp = datetime.now()
    
    # Получаем информацию о канале
    target_entity = await client.get_entity(channel_id)
    
    # Проверяем, является ли сущность каналом и добавляем в БД
    if isinstance(target_entity, Channel):
        print(f"Проверка/добавление основного канала '{target_entity.title}' (ID: {target_entity.id}) в БД.")
        add_channel(target_entity)
    else:
        print(f"Целевая сущность {channel_id} не является Channel, пропускаем добавление в БД.")

    count = 1
    # Итерируемся по сообщениям канала
    async for message in client.iter_messages(target_entity):
        if limit and count == limit: break
        
        print(f"total: {count} message id: {message.id}")

        channel_peer_id_for_message = target_entity.id

        # Обработка фотографий в сообщении
        if message.photo:
            path = os.path.join(PHOTO_STORAGE, f"{message.id}.jpg")
            await message.download_media(path)
        else: 
            path = None
        
        # Получение ссылок и просмотров
        links: list[str | None] = check_message_for_links(message)
        views: int = await get_message_views(client, message)
        
        # Добавление сообщения в базу данных
        add_message(
            channel_id = channel_peer_id_for_message,
            message_id = message.id,
            text = message.text,
            date = message.date, 
            photo_path = path,
            links = links,
            views = views
        )
        count += 1
    print(f"Parsed {count} messages for {datetime.now()-start_timestamp}")


# Счетчик обработанных сообщений
TOTAL_HANDLED = 0

# Обработчик новых сообщений
@client.on(NewMessage(chats=SOURCE_STOGAGE))
async def message_handler(event: NewMessage.Event):
    """
    Обработчик новых сообщений из отслеживаемых каналов
    Args:
        event: событие нового сообщения
    """
    global TOTAL_HANDLED

    message: Message = event.message
    # Обработка фотографий
    if message.photo:
        path = os.path.join(PHOTO_STORAGE, f"{message.id}.jpg")
        await message.download_media(path)
    else: 
        path = None
    
    # Извлечение числового идентификатора канала из объекта peer_id
    if isinstance(message.peer_id, PeerChannel):
        channel_id = message.peer_id.channel_id
    elif isinstance(message.peer_id, PeerChat):
        channel_id = message.peer_id.chat_id
    elif isinstance(message.peer_id, PeerUser):
        channel_id = message.peer_id.user_id
    else:
        channel_id = getattr(message.peer_id, 'channel_id', None) or getattr(message.peer_id, 'chat_id', None) or getattr(message.peer_id, 'user_id', None)
        if channel_id is None:
            print(f"Неизвестный тип peer_id: {type(message.peer_id)}")
            return

    # Проверяем существование канала в БД перед добавлением сообщения
    if not get_channel_by_peer_id(channel_id):
        print(f"Канал с ID {channel_id} не найден в БД. Сообщение не будет добавлено.")
        return
    
    # Добавление сообщения в базу данных
    add_message(
        channel_id = channel_id,
        message_id = message.id,
        views = await get_message_views(client, message),
        date = message.date,
        text = message.text,
        photo_path = path,
        links = check_message_for_links(message)
    )

    TOTAL_HANDLED += 1
    print(f"total parsed: {TOTAL_HANDLED}")


async def main():
    """
    Основная функция запуска парсера
    """
    # Подключение к Telegram
    await client.connect()
    await client.start()
    
    # Пример использования парсера
    # await parse_messages("https://t.me/incrypted", limit=10)
    # for message in get_all_messages():
    #     print(message)

    await client.run_until_disconnected()


# Точка входа в программу
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("KeyboardInterrupt :)")
