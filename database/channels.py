from telethon.tl.types import Channel
from database.manager import session_scope
from database.models import Channels, engine, PostingTarget
from sqlalchemy.orm import Session
from sqlalchemy import select, Select, update



def add_channel(channel: Channel) -> None:
    """
    Добавляет новый канал в базу данных.
    
    Args:
        channel (Channel): Объект канала Telethon, содержащий информацию о канале
        
    Действия:
    1. Проверяет существование канала в БД по peer_id
    2. Если канал уже существует - пропускает добавление
    3. Создает новую запись в таблице Channels с данными канала
    4. Коммитит транзакцию
    
    Raises:
        Exception: При ошибках добавления в БД выполняется откат транзакции
    """
    with Session(engine) as connection:
        # Проверяем существование канала по peer_id
        existing_by_peer_id = get_channel_by_peer_id(channel.id)
        if existing_by_peer_id:
            print(f"Channel {channel.title} already exists in db with peer_id={channel.id}")
            return
            
        # Проверяем существование канала по username, если он есть
        if channel.username:
            query = select(Channels).where(Channels.username == channel.username)
            existing_by_username = connection.scalars(query).one_or_none()
            if existing_by_username:
                print(f"Channel {channel.title} already exists with username={channel.username}")
                
                # Если найден канал с тем же именем, но другим ID, обновляем ID
                if existing_by_username.peer_id != channel.id:
                    print(f"Updating channel peer_id from {existing_by_username.peer_id} to {channel.id}")
                    existing_by_username.peer_id = channel.id
                    try:
                        connection.commit()
                        print(f"Updated channel {channel.title} peer_id")
                    except Exception as error:
                        print(f"Error updating channel peer_id: {error}")
                        connection.rollback()
                return
        
        # Если канал не существует, добавляем его
        try:
            new_channel = Channels(         
                peer_id = channel.id,
                username = channel.username,
                title = channel.title
            )
            connection.add(new_channel)
            connection.commit()
            print(f"Channel {channel.title} added to db with peer_id={channel.id}")
        except Exception as error:
            print(f"Error adding channel: {error}")
            connection.rollback()


def get_all_channels() -> list[Channels]:
    """
    Получает список всех каналов из базы данных.
    
    Returns:
        list[Channels]: Список объектов Channels, содержащих информацию о каналах
        
    Действия:
    1. Создает сессию подключения к БД
    2. Выполняет SELECT-запрос для получения всех записей из таблицы Channels
    3. Возвращает список объектов Channels
    """
    with Session(engine) as connection:
        channels = connection.scalars(select(Channels)).all()
        return channels
    

def get_channel_by_peer_id(peer_id: int) -> Channels | None:
    """
    Получает канал из базы данных по его peer_id.
    
    Args:
        peer_id (int): Идентификатор канала в Telegram
        
    Returns:
        Channels | None: Объект канала из БД или None, если канал не найден
        
    Действия:
    1. Создает сессию подключения к БД
    2. Выполняет SELECT-запрос для поиска канала по peer_id
    3. Возвращает найденный канал или None
    """
    with Session(engine) as connection:
        query: Select = select(Channels).where(Channels.peer_id == peer_id)
        result = connection.scalars(query).one_or_none()
        return result