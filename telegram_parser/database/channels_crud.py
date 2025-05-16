# database/channels_crud.py

from telethon.tl.types import Channel
from database.alchemy_db import Channels, engine
from sqlalchemy.orm import Session
from sqlalchemy import select, Select



def add_channel(peer_id, title, username: str=None) -> int | None:
    with Session(engine) as connection:
        if get_channel_by_peer_id(peer_id):
            print(f"channel {title} already exist in db")
            return None
        else:
            try:
                new_channel = Channels(
                    peer_id = peer_id,
                    username = username,
                    title = title
                )
                connection.add(new_channel)
                connection.commit()
                print(f"Channel {title} added to db")
                return peer_id # возвращает айди канала который был добавлен
            
            except Exception as error:
                print(f"got error on channel adding: {error}")
                connection.rollback()


def get_all_channels() -> list[dict] | None:
    with Session(engine) as connection:
        channels = connection.scalars(select(Channels)).all()
        if channels:
            result = []
            for channel in channels:
                result.append(
                    {
                        "peer_id": channel.peer_id,
                        "username": channel.username,
                        "title": channel.title
                        # "messages": [{}, {}, {}] # TODO набор всех сообщений
                    }
                )
            return result
        return None


# TODO * подумать над тем чтобы прикрутить к этому dict какую нибудь расширеную статистику канала
def get_channel_by_peer_id(peer_id: int) -> Channels | None:
    with Session(engine) as connection:
        query: Select = select(Channels).where(Channels.peer_id == peer_id)
        result = connection.scalars(query).one_or_none()
        if result:
            channel_obj = result
            return {
                "peer_id": channel_obj.peer_id,
                "username": channel_obj.username,
                "title": channel_obj.title
            }
        return {}
