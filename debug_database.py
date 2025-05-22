import logging
from database.models import Messages, Channels, engine, ParsingSourceChannel
from sqlalchemy.orm import Session

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def check_database():
    """Check database contents and print summary information"""
    try:
        # Check messages
        with Session(engine) as session:
            messages = session.query(Messages).all()
            logger.info(f"Found {len(messages)} messages in database")
            
            # Print message details
            for msg in messages:
                logger.info(f"Message: Channel ID {msg.channel_id}, Message ID {msg.message_id}, "
                           f"Date {msg.date}, Views {msg.views}, "
                           f"Text: {msg.text[:50]}{'...' if msg.text and len(msg.text) > 50 else ''}")
            
            # Check channels
            channels = session.query(Channels).all()
            logger.info(f"Found {len(channels)} channels in database")
            for channel in channels:
                logger.info(f"Channel: ID {channel.id}, Peer ID {channel.peer_id}, "
                           f"Username {channel.username}, Title {channel.title}")
            
            # Check parsing sources
            sources = session.query(ParsingSourceChannel).all()
            logger.info(f"Found {len(sources)} parsing sources in database")
            for source in sources:
                logger.info(f"Source: ID {source.id}, Identifier {source.source_identifier}, "
                           f"Title {source.source_title}, Target ID {source.posting_target_id}")
    
    except Exception as e:
        logger.error(f"Error checking database: {e}")

if __name__ == "__main__":
    check_database() 