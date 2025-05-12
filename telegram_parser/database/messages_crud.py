# ./database/messages_crud.py
import re
from sqlalchemy import select, Select, and_, delete
from sqlalchemy.orm import Session
from database.alchemy_db import engine, Messages
from datetime import datetime
from telethon.types import Channel
from telethon.types import Message
from telegram_requests import get_message_views



def add_message(channel_id, message_id, text, date, photo_path, links, views) -> None:
    with Session(engine) as connection:
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
        print(f"Added new row to Messages\n     chat: {channel_id} message: {message_id}")



    with Session(engine) as connection:
        messages = connection.scalars(select(Messages)).all()
        return sorted(messages, key=lambda x: x.date)


def get_messages_by_channel(channel: Channel) -> list[Messages]:
    if not isinstance(channel, Channel):
        raise TypeError(f"channel: {channel} must be 'Channel' type")
    with Session(engine) as connection:
        ...


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
            messages: list[Messages] = connection.scalars(query).all()
            return sorted(messages, key=lambda x: x.date)
        
        if to_date is None and from_date: # [+ -] returns a segment starting from a specific moment
            query = select(Messages).where(
                Messages.date >= from_date
            )
            messages: list[Messages] = connection.scalars(query).all()
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