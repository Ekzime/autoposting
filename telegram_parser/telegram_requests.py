from telethon import TelegramClient, functions
from telethon.tl.types import MessageViews, Message



async def get_message_views(client: TelegramClient, message: Message) -> int:
    views: MessageViews = await client(
        functions.messages.GetMessagesViewsRequest(
            peer=message.peer_id, id=[message.id], increment=True
        ) 
    )
    views_count: int = views.views[0].views
    return views_count
    