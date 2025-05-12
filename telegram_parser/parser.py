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
            

async def parse_messages(channel_id: int | str, limit: int=None):
    """main parsing func"""
    start_timestamp = datetime.now()
    
    target_entity = await client.get_entity(channel_id)
    
    count = 1
    async for message in client.iter_messages(target_entity):
        if limit and count == limit: break
        
        print(f"total: {count} message id: {message.id}")

        if message.photo:
            path = os.path.join(PHOTO_STORAGE, f"{message.id}.jpg")
            await message.download_media(path)
        else: 
            path = None
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
    print(f"Parsed {count} messages for {datetime.now()-start_timestamp}")


# message handler function

TOTAL_HANDLED = 0
@client.on(NewMessage(chats=SOURCE_STOGAGE))
async def message_handler(event: NewMessage.Event):
    global TOTAL_HANDLED

    message: Message = event.message
    if message.photo:
        path = os.path.join(PHOTO_STORAGE, f"{message.id}.jpg")
        await message.download_media(path)
    else: 
        path = None
    add_message(
        channel_id = message.peer_id,
        message_id = message.id,
        views = await get_message_views(client, message),
        date = message.date,
        text = message.message,
        photo_path = ...,
        links = await check_message_for_links(message)
    )

    TOTAL_HANDLED += 1
    print(f"total parsed: {TOTAL_HANDLED}")



async def main():
    await client.connect()
    await client.start()
    
    # пример использования парсера:
    await parse_messages("https://t.me/incrypted", limit=10)
    for message in get_all_messages():
        print(message)

    await client.run_until_disconnected()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("KeyboardInterrupt :)")
