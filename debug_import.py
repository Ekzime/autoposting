"""
Focused diagnostic script to identify where the parser is hanging during import or initialization.
"""
import sys
import logging
import time
import asyncio

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('parser_debug.log')
    ]
)

logger = logging.getLogger("debug_import")

def log_step(message):
    """Log a step with clear separation"""
    logger.info("=" * 30)
    logger.info(message)
    print(f"STEP: {message}")
    
# Start diagnostic process
log_step("Starting diagnostics")

# 1. Check basic imports
log_step("Importing basic modules")
import os
import asyncio
import re
from datetime import datetime
from typing import Dict, List, Optional, Union

# 2. Check config import
log_step("Importing config")
try:
    import config
    from config import settings
    logger.info(f"API ID: {settings.telegram_api.api_id}")
    logger.info(f"API Hash configured: {'Yes' if settings.telegram_api.api_hash else 'No'}")
except Exception as e:
    logger.error(f"Config import error: {e}", exc_info=True)
    sys.exit(1)

# 3. Check Telethon imports
log_step("Importing Telethon modules")
try:
    from telethon import TelegramClient, events, functions
    from telethon.sessions import StringSession
    from telethon.tl.types import (
        Channel, Message, PeerChannel, MessageEntityTextUrl,
        MessageEntityUrl, PeerUser, PeerChat, MessageViews
    )
except Exception as e:
    logger.error(f"Telethon import error: {e}", exc_info=True)
    sys.exit(1)

# 4. Check database imports 
log_step("Importing database modules")
try:
    # Using separate try blocks to identify specific problematic imports
    try:
        from database.dao.pars_telegram_acc_repository import ParsingTelegramAccRepository
        logger.info("ParsingTelegramAccRepository imported successfully")
    except Exception as e:
        logger.error(f"Error importing ParsingTelegramAccRepository: {e}", exc_info=True)
    
    try:
        from database.repositories import parsing_telegram_acc_repository, parsing_source_repository
        logger.info("Database repositories imported successfully")
    except Exception as e:
        logger.error(f"Error importing repositories: {e}", exc_info=True)
    
    try:
        from database.channels import add_channel, get_channel_by_peer_id
        logger.info("Channel database functions imported successfully")
    except Exception as e:
        logger.error(f"Error importing channel functions: {e}", exc_info=True)
    
    try:
        from database.messages import add_message
        logger.info("Message database functions imported successfully")
    except Exception as e:
        logger.error(f"Error importing message functions: {e}", exc_info=True)
except Exception as e:
    logger.error(f"Database import error: {e}", exc_info=True)

# 5. Test database operations
log_step("Testing database operations")
try:
    # Try to get accounts asynchronously
    async def test_db_operation():
        try:
            import asyncio
            accounts = await asyncio.to_thread(parsing_telegram_acc_repository.get_all_accounts)
            logger.info(f"Found {len(accounts)} accounts in database")
            return accounts
        except Exception as e:
            logger.error(f"Error in async database operation: {e}", exc_info=True)
            return []
    
    # Run the test in a new event loop
    try:
        accounts = asyncio.run(test_db_operation())
        if accounts:
            logger.info(f"First account ID: {accounts[0]['id']}, Phone: {accounts[0]['phone_number']}")
    except Exception as e:
        logger.error(f"Error running async test: {e}", exc_info=True)
except Exception as e:
    logger.error(f"Database test error: {e}", exc_info=True)

# 6. Try to initialize the client (but don't connect)
log_step("Testing client initialization (no connection)")
try:
    if settings.telegram_api.api_id and settings.telegram_api.api_hash:
        client = TelegramClient(
            StringSession(),  # Just use an empty session
            settings.telegram_api.api_id,
            settings.telegram_api.api_hash
        )
        logger.info("Client object created successfully")
    else:
        logger.error("Missing API credentials")
except Exception as e:
    logger.error(f"Client creation error: {e}", exc_info=True)

# Done
log_step("Diagnostic script completed")
print("Diagnostics complete. Check parser_debug.log for detailed results.")

async def main():
    print("Создаю клиент Telegram...")
    client = TelegramClient(
        StringSession(),
        settings.telegram_api.api_id,
        settings.telegram_api.api_hash
    )
    
    print("Подключаюсь к Telegram...")
    await client.connect()
    print("Подключено!")
    
    print("Отключаюсь...")
    await client.disconnect()
    print("Скрипт завершен успешно!")

if __name__ == "__main__":
    if sys.platform.startswith('win'):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    asyncio.run(main()) 