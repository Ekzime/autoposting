import asyncio
import logging
import sys
import traceback
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.types import Channel, PeerChannel

from config import settings
from database.repositories import parsing_telegram_acc_repository
from database.models import Messages, Channels, engine
from sqlalchemy.orm import Session
from sqlalchemy import select

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Disable verbose logging from Telethon
logging.getLogger('telethon').setLevel(logging.WARNING)

async def check_channel_messages():
    """Check recent messages from the Incrypted channel"""
    logger.info("Starting channel message check")
    
    # Get active account
    print("Fetching active account...")
    accounts = parsing_telegram_acc_repository.get_active_parsing_accounts()
    if not accounts:
        logger.error("No active accounts found")
        return
    
    print(f"Found {len(accounts)} accounts")
    account = accounts[0]
    print(f"Using account ID: {account['id']}")
    
    # Channel to check
    channel_username = "incrypted"
    
    # Initialize client
    print("Initializing client...")
    client = TelegramClient(
        StringSession(account['session_string']),
        settings.telegram_api.api_id,
        settings.telegram_api.api_hash
    )
    
    try:
        # Connect
        print("Connecting to Telegram...")
        await client.connect()
        print("Connected!")
        
        # Check authorization
        print("Checking authorization...")
        is_authorized = await client.is_user_authorized()
        print(f"Is authorized: {is_authorized}")
        if not is_authorized:
            logger.error("Client is not authorized")
            return
        
        # Get channel entity
        print(f"Getting entity for channel: {channel_username}")
        entity = await client.get_entity(channel_username)
        print(f"Entity type: {type(entity)}")
        if not isinstance(entity, Channel):
            logger.error(f"{channel_username} is not a channel")
            return
        
        print(f"Channel: {entity.title} (ID: {entity.id})")
        
        # Get messages from database
        print("Fetching messages from database...")
        with Session(engine) as session:
            db_messages = session.query(Messages).filter(Messages.channel_id == entity.id).all()
            message_ids = {msg.message_id for msg in db_messages}
            print(f"Found {len(db_messages)} messages in database for this channel")
        
        # Get recent messages from Telegram
        print("Fetching recent messages from Telegram...")
        messages = await client.get_messages(entity, limit=10)
        print(f"Retrieved {len(messages)} recent messages from Telegram")
        
        for msg in messages:
            in_db = msg.id in message_ids
            print(f"Message ID: {msg.id}, Date: {msg.date}, In DB: {in_db}")
            if msg.text:
                print(f"Text preview: {msg.text[:50]}...")
                
                # Check for the specific message about Bitcoin hitting historical maximum
                if "биткоин" in msg.text.lower() and "максимум" in msg.text.lower():
                    print("FOUND BITCOIN HISTORICAL MAXIMUM MESSAGE")
                    print(f"Full text: {msg.text}")
    
    except Exception as e:
        print(f"Error: {e}")
        traceback.print_exc()
    
    finally:
        # Disconnect
        print("Disconnecting client...")
        await client.disconnect()
        print("Client disconnected")

if __name__ == "__main__":
    # Run the async function
    print("Starting script...")
    if sys.platform.startswith('win'):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(check_channel_messages())
    print("Script completed") 