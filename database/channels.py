from telethon.tl.types import Channel
from database.manager import session_scope
from database.models import Channels, engine, PostingTarget
from sqlalchemy.orm import Session
from sqlalchemy import select, Select, update



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
    

# Методы для работы с таблицей PostingTarget
# =========================================
def set_active_target(target_chat_id_str: str, target_title: str | None) -> PostingTarget | None:
    """ Устанавливает или обновляет АКТИВНУЮ цель для постинга. """
    try:
        with session_scope() as db:
            # Деактивируем все существующие активные цели для постинга
            db.execute(
                update(PostingTarget)
                .where(PostingTarget.is_active == True)
                .values(is_active=False)
            )
            
            # Ищем запись с указанным chat_id
            target_entry = db.execute(
                select(PostingTarget).filter_by(target_chat_id=target_chat_id_str)
            ).scalar_one_or_none()
            
            # Если запись найдена - обновляем её
            if target_entry:
                # Обновляем название если оно передано
                if target_title is not None:
                    target_entry.target_title = target_title
                # Активируем цель
                target_entry.is_active = True
            # Если записи нет - создаём новую
            else:
                target_entry = PostingTarget(
                    target_chat_id=target_chat_id_str,
                    target_title=target_title,
                    is_active=True  # Новая запись сразу активна
                )
                db.add(target_entry)

            return target_entry 
    except Exception as e:
        print(f"got error on set_active_target: {e}")
        return None
        
def get_active_target_info() -> PostingTarget | None: # Переименовал для ясности, что возвращает весь объект
    """ Возвращает объект PostingTarget для текущей активной цели или None. """
    try:
        with session_scope() as db:
            return db.execute(
                select(PostingTarget).filter_by(is_active=True)
            ).scalar_one_or_none()
    except Exception as e:
        print(f"got error on get_active_target_info: {e}")
        return None
    
def get_active_target_chat_id_str() -> str | None:
    """ Получает target_chat_id текущей активной цели или None. """
    active_target = get_active_target_info() 
    if active_target:
        return active_target.target_chat_id
    return None

def deactivate_target_by_id(target_chat_id_to_deactivate: str) -> bool:
    with session_scope() as db:
        try:
            db.execute(
                update(PostingTarget)
                .where(PostingTarget.target_chat_id == target_chat_id_to_deactivate)
                .values(is_active=False)
            )
            db.commit()
            return True
        except Exception as e:
            print(f"got error on deactivate_target_by_id: {e}")
            return False
            
