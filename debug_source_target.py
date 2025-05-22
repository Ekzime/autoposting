import logging
import sys
from sqlalchemy import select
from database.models import SessionLocal, PostingTarget, ParsingSourceChannel, Channels

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

def debug_source_target_relations():
    """Отладка связей между источниками и целевыми каналами"""
    with SessionLocal() as session:
        # Получаем все целевые каналы
        targets = session.execute(select(PostingTarget)).scalars().all()
        logging.info(f"Найдено {len(targets)} целевых каналов:")
        
        for target in targets:
            logging.info(f"Целевой канал: ID {target.id}, chat_id={target.target_chat_id}, title={target.target_title}, активен={target.is_active}")
            
            # Получаем все источники для данного целевого канала
            sources = session.execute(
                select(ParsingSourceChannel).where(
                    ParsingSourceChannel.posting_target_id == target.id
                )
            ).scalars().all()
            
            logging.info(f"Найдено {len(sources)} источников для целевого канала {target.target_chat_id}:")
            for source in sources:
                logging.info(f"  Источник: ID {source.id}, identifier={source.source_identifier}, title={source.source_title}")
                
                # Проверяем, есть ли соответствующий канал в базе
                channel = None
                if source.source_identifier.startswith('@'):
                    username = source.source_identifier[1:]  # Убираем @ из начала
                    channel = session.execute(
                        select(Channels).where(Channels.username == username)
                    ).scalar_one_or_none()
                    logging.info(f"  Поиск канала по username '{username}': {channel is not None}")
                else:
                    try:
                        peer_id = int(source.source_identifier)
                        channel = session.execute(
                            select(Channels).where(Channels.peer_id == peer_id)
                        ).scalar_one_or_none()
                        logging.info(f"  Поиск канала по peer_id {peer_id}: {channel is not None}")
                    except ValueError:
                        logging.warning(f"  Невозможно преобразовать {source.source_identifier} в число для поиска по peer_id")
                
                if channel:
                    logging.info(f"  Найден канал в БД: ID {channel.id}, peer_id={channel.peer_id}, username={channel.username}")
                else:
                    logging.warning(f"  ПРОБЛЕМА: Канал с идентификатором {source.source_identifier} не найден в БД!")

        # Проверяем все каналы в БД
        channels = session.execute(select(Channels)).scalars().all()
        logging.info(f"Всего каналов в БД: {len(channels)}")
        for channel in channels:
            logging.info(f"Канал в БД: ID {channel.id}, peer_id={channel.peer_id}, username={channel.username}, title={channel.title}")

if __name__ == "__main__":
    try:
        from config import settings  # Инициализация настроек
        debug_source_target_relations()
    except KeyboardInterrupt:
        logging.info("Программа прервана пользователем.")
    except Exception as e:
        logging.critical(f"Критическая ошибка: {e}", exc_info=True) 