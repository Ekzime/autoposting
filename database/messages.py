# ./database/messages_crud.py

from sqlalchemy import select, Select, and_, delete
from sqlalchemy.orm import Session
from .models import engine, Messages
from datetime import datetime



def add_message(channel_id, message_id, text, date, photo_path, links, views) -> int | None:
    with Session(engine) as connection:
        # Проверяем наличие сообщения по message_id без привязки к channel_id
        query = select(Messages).where(
            and_(
                Messages.message_id == message_id
            )
        )
        results = connection.execute(query).fetchall()
        
        # Если сообщение есть, проверяем дополнительно
        for result in results:
            # Если такой message_id уже существует для какого-либо канала
            msg = result[0]  # Получаем объект Messages
            print(f"Найдено сообщение в БД: message_id={message_id}, channel_id={msg.channel_id}")
            
            # Если совпадает и channel_id и message_id, это дубликат
            if msg.channel_id == channel_id:
                print(f"message: id:{message_id} already exist for channel {channel_id}")
                return msg.id  # Возвращаем ID существующего сообщения
            
            # Возможно, канал хранится с другим ID, но это то же сообщение
            # Проверяем текст и дату для подтверждения
            if msg.text == text and msg.date == date:
                print(f"message: id:{message_id} уже существует с другим channel_id")
                return msg.id  # Возвращаем ID существующего сообщения
        
        try:
            new_message = Messages(
                channel_id = channel_id,
                message_id = message_id,
                text = text,
                length = len(text) if text else 0,
                date = date,
                photo_path = photo_path,
                links = links,
                views = views
            )
            connection.add(new_message)
            connection.commit()
            print(f"Added new row to Messages\n     chat: {channel_id}\n    message: {message_id}")
            
            # Получаем ID добавленного сообщения
            return new_message.id
        except Exception as e:
            connection.rollback()
            print(f"Error adding message: {e}")
            return None


def get_all_messages() -> list[Messages]:
    with Session(engine) as session:
        messages = session.scalars(select(Messages)).all()
        result = []
        for m in messages:
            result.append({
                "id":           m.id,
                "channel_id":   m.channel_id,
                "message_id":   m.message_id,
                "text":         m.text,
                "length":       m.length,
                "date":         m.date.isoformat(),  # или m.date.timestamp()
                "photo_path":   m.photo_path,
                "links":        m.links,
                "views":        m.views,
            })
        return result
    

def get_messages_by_date(from_date: datetime=None, to_date: datetime=None) -> list[Messages] | None: 
    """if no arguments are passed it returns all database rows"""
    with Session(engine) as connection:
        if not from_date and not to_date: # [- -] return all d
            return get_all_messages()
        
        if from_date and to_date: # [+ +] return a specific time interval
            query = select(Messages).where(
                    and_(
                        Messages.date >=from_date, 
                        Messages.date <= to_date
                    )
                )
            messages: list[Messages] = connection.scalars(query).all()
            return sorted(messages, key=lambda x: x.date)
        
        if from_date is None and to_date: # [- +] returns a segment up to a specific point
            query = select(Messages).where(
                Messages.date <= to_date
            )
            messages = connection.scalars(query).all()
            return sorted(messages, key=lambda x: x.date)
        
        if to_date is None and from_date: # [+ -] returns a segment starting from a specific moment
            query = select(Messages).where(
                Messages.date >= from_date
            )
            messages = connection.scalars(query).all()
            return sorted(messages, key=lambda x: x.date)


def get_message_by_text(target_text: str) -> list[Messages] | None:
    with Session(engine) as connection:
        query: Select = select(Messages).where(Messages.text.contains(target_text))
        messages: list[Messages] = connection.scalars(query).all()
        return sorted(messages, key=lambda x: x.date)


def update_message_photo_path(message_id: int, photo_path: str) -> bool:
    """
    Обновляет путь к фотографии для сообщения по ID.
    
    Args:
        message_id (int): ID сообщения в БД
        photo_path (str): Путь к фотографии
        
    Returns:
        bool: True если обновление успешно, False в случае ошибки
    """
    with Session(engine) as connection:
        try:
            # Получаем сообщение по ID
            message = connection.get(Messages, message_id)
            if not message:
                print(f"Сообщение с ID {message_id} не найдено")
                return False
                
            # Обновляем путь к фото
            message.photo_path = photo_path
            connection.commit()
            print(f"Обновлен путь к фото для сообщения ID {message_id}: {photo_path}")
            return True
        except Exception as e:
            connection.rollback()
            print(f"Ошибка при обновлении пути к фото: {e}")
            return False


def clear_messages_table() -> None:
    with Session(engine) as connection:
        try:
            connection.execute(delete(Messages))
            connection.commit()
            print("Messages table deleted")
        except Exception:
            print("Messages table deleting error")
            connection.rollback()
            raise