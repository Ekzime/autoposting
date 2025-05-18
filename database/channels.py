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
    

# Методы для работы с таблицей PostingTarget
# =========================================
def set_active_target(target_chat_id_str: str, target_title: str | None) -> PostingTarget | None:
    """
    Устанавливает или обновляет активную цель для постинга.
    
    Args:
        target_chat_id_str (str): ID целевого чата/канала в виде строки
        target_title (str | None): Название для целевого чата/канала. Может быть None
        
    Returns:
        PostingTarget | None: Объект PostingTarget с установленными параметрами или None в случае ошибки
        
    Действия:
    1. Деактивирует все существующие активные цели
    2. Ищет запись с указанным chat_id
    3. Если запись найдена - обновляет название и активирует её
    4. Если записи нет - создает новую активную запись
    """
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
        
def get_active_target_info() -> dict | None:
    """
    Получает информацию об активной цели для постинга.
    
    Returns:
        dict | None: Словарь с информацией об активной цели 
                    или None если активная цель не найдена или произошла ошибка
                    
    Действия:
    1. Выполняет запрос к БД для поиска активной цели (is_active=True)
    2. Возвращает словарь с данными или None
    """
    with session_scope() as db:
        try:
            target = db.execute(
                select(PostingTarget).filter_by(is_active=True)
            ).scalar_one_or_none()
            
            if not target:
                return None
                
            return {
                "id": target.id,
                "target_chat_id": target.target_chat_id,
                "target_title": target.target_title,
                "is_active": target.is_active,
                "added_at": target.added_at.isoformat() if target.added_at else None
            }
        except Exception as e:
            print(f"got error on get_active_target_info: {e}")
            return None
        
def get_active_target_chat_id_str() -> str | None:
    """
    Получает ID активного целевого канала в виде строки.
    
    Returns:
        str | None: ID активного целевого канала в виде строки или None, если активный канал не найден
        
    Действия:
    1. Получает информацию об активном канале через get_active_target_info()
    2. Возвращает target_chat_id активного канала или None
    """
    active_target = get_active_target_info() 
    if active_target:
        return active_target["target_chat_id"]
    return None

def deactivate_target_by_id(target_chat_id_to_deactivate: str) -> bool:
    """
    Деактивирует целевой канал по его ID.
    
    Args:
        target_chat_id_to_deactivate (str): ID канала, который нужно деактивировать
        
    Returns:
        bool: True если деактивация прошла успешно, False в случае ошибки
        
    Действия:
    1. Находит запись канала в БД по target_chat_id
    2. Устанавливает флаг is_active в False
    3. Сохраняет изменения
    """
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
            
def get_all_target_channels() -> list[dict]:
    """
    Получает список всех целевых каналов из базы данных.
    
    Returns:
        list[dict]: Список словарей с информацией о каналах, где каждый словарь содержит:
            - id (int): Идентификатор записи в БД
            - target_chat_id (str): ID канала в Telegram
            - target_title (str): Название канала
            - is_active (bool): Флаг активности канала
            - added_at (str): Дата и время добавления в ISO формате
            
    Действия:
    1. Выполняет запрос к БД для получения всех записей PostingTarget
    2. Преобразует каждую запись в словарь с нужными полями
    3. Возвращает список словарей
    """
    with session_scope() as db:
        targets = db.execute(select(PostingTarget)).scalars().all()
        if not targets:
                return False
        return [
            {
                "id": t.id,
                "target_chat_id": t.target_chat_id,
                "target_title": t.target_title,
                "is_active": t.is_active,
                "added_at": t.added_at.isoformat() if t.added_at else None
            }
            for t in targets
        ]

def delete_target_channel(target_chat_id: str) -> bool:
    """
    Удаляет целевой канал из базы данных по его ID.
    
    Args:
        target_chat_id (str): ID канала, который нужно удалить
        
    Returns:
        bool: True если удаление прошло успешно, False в случае ошибки
        
    Действия:
    1. Находит запись канала в БД по target_chat_id
    2. Удаляет запись из БД
    3. Сохраняет изменения
    """
    with session_scope() as db:
        try:
            target = db.execute(
                select(PostingTarget).where(PostingTarget.target_chat_id == target_chat_id)
            ).scalar_one_or_none()
            
            if not target:
                return False
                
            db.delete(target)
            return True
        except Exception as e:
            print(f"got error on delete_target_channel: {e}")
            return False

def activate_target_by_id(target_chat_id_str: str) -> bool:
    """
    Активирует целевой канал по его ID и деактивирует все остальные.
    
    Args:
        target_chat_id_str (str): ID канала, который нужно активировать
        
    Returns:
        bool: True если активация прошла успешно, False в случае ошибки
        
    Действия:
    1. Деактивирует все существующие активные цели
    2. Находит запись канала в БД по target_chat_id
    3. Устанавливает флаг is_active в True для найденного канала
    4. Сохраняет изменения
    """
    with session_scope() as db:
        try:
            # Сначала деактивируем все активные каналы
            db.execute(
                update(PostingTarget)
                .where(PostingTarget.is_active == True)
                .values(is_active=False)
            )
            
            # Затем ищем и активируем нужный канал
            target = db.execute(
                select(PostingTarget).where(PostingTarget.target_chat_id == target_chat_id_str)
            ).scalar_one_or_none()
            
            if not target:
                return False
            
            target.is_active = True
            return True
        except Exception as e:
            print(f"got error on activate_target_by_id: {e}")
            return False
    
