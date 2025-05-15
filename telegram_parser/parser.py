# ./parser.py

import os
import re
import asyncio
import database
from database.messages_crud import add_message, get_all_messages
from database.channels_crud import (
    get_channel_by_peer_id, 
    add_channel, 
    get_all_channels
)

from telethon import TelegramClient, functions
from telethon.events import NewMessage
from telethon.types import Channel, Message
from telethon.tl.types import Channel, Message
from telethon.tl.types import MessageEntityTextUrl, MessageEntityUrl, MessageViews
 
from datetime import datetime
from config import *
from telegram_requests import get_message_views



client = TelegramClient(
    SESSION, 
    API_ID, 
    API_HASH
)


def check_message_for_links(message: Message) -> list[str]:
    found_urls: list[str] = []
    if message.entities:
        for entity in message.entities:
            if isinstance(entity, MessageEntityUrl):
                found_urls.append(message.text[entity.offset : entity.offset + entity.length])
            elif isinstance(entity, MessageEntityTextUrl):
                found_urls.append(entity.url)
        
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


# TODO решить вопрос с поведением функции await client.download_media() когда в сообщении несколько изображений
async def return_photo_path(message: Message) -> str | None:
    if not message.media:
        return None
    path = os.path.join(PHOTO_STORAGE, f"{message.peer_id}_{message.id}.jpeg")
    await client.download_media(message=message, file=path)
    
    return path


async def parse_messages(channel_id: int | str, limit: int=None):
    """main parsing func"""
    start_timestamp = datetime.now()
    
    target_entity = await client.get_entity(channel_id)
    
    count =  1
    async for message in client.iter_messages(target_entity):
        message: Message = message # определяем правильный тип (почему то вс код не отобраает поля обьекта message без явного определения)
        
        if (limit and count == limit): break # если достигнут лимит(глубина) парсинга прекращаем цикл
        if not message.message: continue # если сообщение не содержит никакого текста тогда пропускаем итерацию
        
        print(f"total: {count} message id: {message.id}")
                
        path: str  = await return_photo_path(message)
        links: list[str | None] = check_message_for_links(message)
        views: int = await get_message_views(client, message)
        
        add_message(
            channel_id = message.chat.id,
            message_id = message.id,
            text = message.text,
            date = message.date, 
            photo_path = path,
            links = links,
            views = views
        )
    
    count += 1
    print(f"parsing time: {datetime.now() - start_timestamp}")


async def init_channels():
    print("start initializing channels storage")
    
    channels = 0
    new_channels = 0
    for channel in SOURCE_STOGAGE:
        print(f"processing for '{channel}'")
        channel = await client.get_entity(channel)
        channel_id = add_channel(channel.id, channel.title, channel.username)
        if channel_id:
            print(f"channel {channel_id} not in db, adding started...")
            new_channels += 1
            await parse_messages(channel.id)
        channels += 1
    
    print(f"Total initialized channels: {channels}\nAdded: {new_channels} new channels")


TOTAL_HANDLED = 0
@client.on(NewMessage(chats=SOURCE_STOGAGE))
async def message_handler(event: NewMessage.Event):
    global TOTAL_HANDLED

    message: Message = event.message
    
    if not message.message: return

    views = await get_message_views(client, message)
    path = await return_photo_path(message)
    links = check_message_for_links(message)
    
    add_message(
        channel_id = message.peer_id,
        message_id = message.id,
        views = views,
        date = message.date,
        text = message.message,
        photo_path = path,
        links = links
    )

    TOTAL_HANDLED += 1
    print(f"total parsed: {TOTAL_HANDLED}")


async def main():
    await client.connect()
    await client.start()
    
    await init_channels()
    
    # пример использования парсера:
    # await parse_messages("https://t.me/incrypted", limit=10)
    # for message in get_all_messages():
    #     print(message)
    
    channels = get_all_channels()
    print(channels)

    await client.run_until_disconnected()



if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("KeyboardInterrupt :)")
