# database/channels_crud.py

from telethon.tl.types import Channel
from database.alchemy_db import Channels, engine
from sqlalchemy.orm import Session
from sqlalchemy import select, Select



# TODO * подумать как можно сразу добавлять все сообщения канала в бд
def add_channel(peer_id, title, username: str=None) -> None:
    with Session(engine) as connection:
        if get_channel_by_peer_id(peer_id):
            print(f"channel {title} already exist in db")
            return
        try:
            new_channel = Channels(
                peer_id = peer_id,
                username = username,
                title = title
            )
            connection.add(new_channel)
            connection.commit()
            print(f"Channel {title} added to db")
        except Exception as error:
            print(f"got error on channel adding: {error}")
            connection.rollback()

# TODO переделать функцию чтобы она возвращала dict
# TODO добавить к параметрам функции опцию которая позволяет выбрать возвращать ли набор всех сообщений для каждого канала
def get_all_channels() -> list[Channels]:
    with Session(engine) as connection:
        channels = connection.scalars(select(Channels)).all()
        return channels


# TODO переделать функцию чтобы можно было вытаскивать dict представляющий канал
# TODO * подумать над тем чтобы прикрутить к этому dict какую нибудь расширеную статистику канала 
def get_channel_by_peer_id(peer_id: int) -> Channels | None:
    with Session(engine) as connection:
        query: Select = select(Channels).where(Channels.peer_id == peer_id)
        result = connection.scalars(query).one_or_none()
        return result
