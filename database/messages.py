# ./database/messages_crud.py

from sqlalchemy import select, Select, and_, delete
from sqlalchemy.orm import Session
from .models import engine, Messages
from datetime import datetime



def add_message(channel_id, message_id, text, date, photo_path, links, views) -> None:
    with Session(engine) as connection:
        query = select(Messages).where(
            and_(
                Messages.channel_id == channel_id,
                Messages.message_id == message_id
            )
        )
        result = connection.execute(query).first()
        if result:
            print(f"message: id:{message_id} already exist")
            return
        
        connection.add(
            Messages(
                channel_id = channel_id,
                message_id = message_id,
                text = text,
                length = len(text),
                date = date,
                photo_path = photo_path,
                links = links,
                views = views
            )
        )
        connection.commit()
        print(f"Added new row to Messages\n     chat: {channel_id}\n    message: {message_id}")


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