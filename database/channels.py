from telethon.tl.types import Channel
from database.models import Channels, engine
from sqlalchemy.orm import Session
from sqlalchemy import select, Select




def add_channel(channel: Channel) -> None:
    with Session(engine) as connection:
        if get_channel_by_peer_id(channel.id):
            print(f"channel {channel.title} already exist in db")
            return
        try:
            new_channel = Channels(         
                peer_id = channel.id,
                username = channel.username,
                title = channel.title
            )
            connection.add(new_channel)
            connection.commit()
            print(f"channel {channel.title} added to db")
        except Exception as error:
            print(f"got error on channel adding: {error}")
            connection.rollback()


def get_all_channels() -> list[Channels]:
    with Session(engine) as connection:
        channels = connection.scalars(select(Channels)).all()
        return channels
    

def get_channel_by_peer_id(peer_id: int) -> Channels | None:
    with Session(engine) as connection:
        query: Select = select(Channels).where(Channels.peer_id == peer_id)
        result = connection.scalars(query).one_or_none()
        return result