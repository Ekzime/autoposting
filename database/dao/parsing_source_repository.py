from sqlalchemy.orm import Session
from sqlalchemy import select, update, delete 
from typing import List, Optional, Dict, Any, Union
import logging

from database.models import ParsingSourceChannel, PostingTarget
from database.manager import session_scope

class ParsingSourceRepository:
    """
    Репозиторий для работы с источниками парсинга.

    Методы:
        add_source_to_target(posting_target_db_id: int, source_identifier: str, source_title: str | None) -> ParsingSourceChannel | None | str:
            Добавляет новый источник парсинга к указанной цели постинга.

        get_sources_for_target(target_id: int) -> List[Dict[str, Any]]:
            Получает список источников для указанного целевого канала.

        delete_source_by_id(source_id: int) -> bool:
            Удаляет источник парсинга по его ID из базы данных.

        change_target_for_source(source_id: int, new_target_id: int) -> bool:
            Изменяет целевой канал для указанного источника парсинга.

        get_all_sources() -> List[Dict[str, Any]]:
            Получает все источники парсинга из базы данных.
    
    Использует глобальный session_scope для управления сессиями БД.
    """
    def __init__(self):
        logging.debug("Инициализация ParsingSourceRepository")

    def add_source_to_target(self,
                             posting_target_db_id:int,
                             source_identifier:str,
                             source_title:str | None = None) -> ParsingSourceChannel | None | str:
        """
        Добавляет новый источник парсинга к указанной цели постинга.
        
        Args:
            posting_target_db_id (int): ID целевого канала в базе данных
            source_identifier (str): Уникальный идентификатор источника (например, username канала)
            source_title (str | None): Название источника (опционально)
            
        Returns:
            dict | None | str: 
                - Словарь с данными созданного источника при успешном добавлении
                - "exists" если источник уже существует
                - None в случае ошибки
            
        Примечание:
            - Проверяет существование источника с таким идентификатором для данной цели
            - Проверяет существование целевого канала
            - Создает новую запись в БД, если все проверки пройдены
        """
        try:
            with session_scope() as db:
                # Проверяем, существует ли уже такой источник для данной цели
                existing_source = db.execute(select(ParsingSourceChannel).filter_by(source_identifier=source_identifier, 
                                                                                    posting_target_id=posting_target_db_id)).scalar_one_or_none()
                if existing_source:
                    logging.warning(f"Источник с идентификатором {source_identifier} уже существует для целевого канала {posting_target_db_id}")
                    return "exists"
                
                # Проверяем существование целевого канала
                target = db.get(PostingTarget, posting_target_db_id)
                if not target:
                    logging.error(f"Целевой канал с id {posting_target_db_id} не найден")
                    return None
                
                # Создаем новый источник парсинга
                new_source = ParsingSourceChannel(
                    posting_target_id=posting_target_db_id,
                    source_identifier=source_identifier,
                    source_title=source_title
                )
                db.add(new_source)
                db.flush() # Чтобы new_source получил ID, если он автоинкрементный
                
                # Вместо возврата ORM-объекта, возвращаем словарь с данными
                return {
                    "id": new_source.id,
                    "posting_target_id": new_source.posting_target_id,
                    "source_identifier": new_source.source_identifier,
                    "source_title": new_source.source_title,
                    "added_at": new_source.added_at.isoformat() if new_source.added_at else None
                }
        except Exception as e:
            logging.error(f"Ошибка при добавлении источника {source_identifier} в целевой канал {posting_target_db_id}: {e}")
            return None
    
    def get_sources_for_target(self, target_identifier: Union[int, str]) -> List[Dict[str, Any]]:
        """
        Получает список источников для указанного целевого канала.
        
        Args:
            target_identifier: Идентификатор целевого канала. 
                              Может быть либо ID (int), либо названием (str).
        
        Returns:
            List[Dict[str, Any]]: Список словарей с данными источников для указанного целевого канала.
        """
        try:
            with session_scope() as db:
                # Сначала определяем ID целевого канала
                target_id = None
                
                # Если передан числовой ID
                if isinstance(target_identifier, int):
                    target_id = target_identifier
                # Если передано название или другая строка
                elif isinstance(target_identifier, str):
                    # Пытаемся найти канал по названию
                    target = db.execute(
                        select(PostingTarget)
                        .filter(PostingTarget.target_title == target_identifier)
                    ).scalar_one_or_none()
                    
                    # Если не нашли по названию, пробуем по chat_id
                    if not target:
                        target = db.execute(
                            select(PostingTarget)
                            .filter(PostingTarget.target_chat_id == target_identifier)
                        ).scalar_one_or_none()
                    
                    if target:
                        target_id = target.id
                
                # Если не удалось определить ID, возвращаем пустой список
                if target_id is None:
                    logging.warning(f"Целевой канал с идентификатором '{target_identifier}' не найден")
                    return []
                
                # Получаем источники для найденного целевого канала
                sources = db.execute(
                    select(ParsingSourceChannel)
                    .filter_by(posting_target_id=target_id)
                    .order_by(ParsingSourceChannel.id)
                ).scalars().all()
                
                # Преобразуем объекты ORM в словари перед закрытием сессии
                return [
                    {
                        "id": source.id,
                        "source_identifier": source.source_identifier,
                        "source_title": source.source_title,
                        "posting_target_id": source.posting_target_id,
                        "added_at": source.added_at.isoformat() if source.added_at else None
                    }
                    for source in sources
                ]
        except Exception as e:
            logging.error(f"Ошибка при получении источников для целевого канала '{target_identifier}': {e}")
            return []
    
    def delete_source_by_id(self, source_db_id: int) -> bool:
        """
        Удаляет источник парсинга по его ID из базы данных.
        
        Args:
            source_db_id (int): ID источника для удаления
            
        Returns:
            bool: True в случае успешного удаления, False если источник не найден или произошла ошибка
        """
        try:
            with session_scope() as db:
                # Получаем источник по ID
                source = db.get(ParsingSourceChannel, source_db_id)
                if not source:
                    logging.error(f"Источник с id {source_db_id} не найден")
                    return False
                
                # Удаляем источник из базы данных
                db.delete(source)
                return True
        except Exception as e:
            logging.error(f"Ошибка при удалении источника с id {source_db_id}: {e}")
            return False
        
    def change_target_for_source(self, source_db_id: int, new_target_db_id: int) -> bool:
        """
        Изменяет целевой канал для указанного источника парсинга.
        
        Args:
            source_db_id (int): ID источника парсинга
            new_target_db_id (int): ID нового целевого канала
            
        Returns:
            ParsingSourceChannel|None: Обновленный объект источника в случае успеха, 
                                      None если источник/цель не найдены или произошла ошибка
        """
        try:
            with session_scope() as db:
                # Получаем источник по ID
                source = db.get(ParsingSourceChannel, source_db_id)
                if not source:
                    logging.error(f"Источник с id {source_db_id} не найден")
                    return False
                
                # Проверяем существование нового целевого канала
                new_target = db.get(PostingTarget, new_target_db_id)
                if not new_target:
                    logging.error(f"Целевой канал с id {new_target_db_id} не найден")
                    return False
                
                # Проверяем, не создаст ли это дубликат (source_identifier + new_posting_target_db_id)
                # Это важно, так как у нас UniqueConstraint
                existing_for_new_target = db.execute(
                    select(ParsingSourceChannel).filter_by(
                        posting_target_id=new_target_db_id,
                        source_identifier=source.source_identifier # Используем идентификатор текущего источника
                    )
                ).scalar_one_or_none()

                # Если найден дубликат и это не тот же самый источник
                if existing_for_new_target and existing_for_new_target.id != source_db_id:
                    logging.warning(f"Источник {source.source_identifier} уже привязан к target_id {new_target_db_id}.")
                    return None 

                # Обновляем целевой канал для источника
                source.posting_target_id = new_target_db_id
                db.flush()
                return source
        except Exception as e:
            logging.error(f"Ошибка в change_target_for_source для source_id {source_db_id}: {e}", exc_info=True)
            return None
    
    def get_all_sources(self) -> List[Dict[str, Any]]:
        """
        Получает все источники парсинга из базы данных.
        
        Returns:
            List[Dict[str, Any]]: Список словарей с данными всех источников парсинга.
        """
        try:
            with session_scope() as db:
                sources = db.execute(select(ParsingSourceChannel)).scalars().all()
                return [
                    {
                        "id": source.id,
                        "source_identifier": source.source_identifier,
                        "source_title": source.source_title,
                        "posting_target_id": source.posting_target_id,
                        "added_at": source.added_at.isoformat() if source.added_at else None
                    }
                    for source in sources
                ]
        except Exception as e:
            logging.error(f"Ошибка при получении всех источников парсинга: {e}")
            return []

    def update_source(self, source_db_id: int, new_source_identifier: str = None, new_source_title: str = None) -> bool:
        """
        Обновляет информацию об источнике парсинга.
        
        Args:
            source_db_id (int): ID источника парсинга для обновления
            new_source_identifier (str, optional): Новый идентификатор источника
            new_source_title (str, optional): Новое название источника
            
        Returns:
            bool: True в случае успешного обновления, False если источник не найден или произошла ошибка
        """
        try:
            with session_scope() as db:
                # Получаем источник по ID
                source = db.get(ParsingSourceChannel, source_db_id)
                if not source:
                    logging.error(f"Источник с id {source_db_id} не найден")
                    return False
                
                # Если передан новый идентификатор, проверяем на дубликаты
                if new_source_identifier and new_source_identifier != source.source_identifier:
                    # Проверяем, не создаст ли это дубликат для текущего целевого канала
                    existing_source = db.execute(
                        select(ParsingSourceChannel).filter_by(
                            posting_target_id=source.posting_target_id,
                            source_identifier=new_source_identifier
                        )
                    ).scalar_one_or_none()
                    
                    if existing_source and existing_source.id != source_db_id:
                        logging.warning(f"Источник с идентификатором {new_source_identifier} уже существует для целевого канала {source.posting_target_id}")
                        return False
                    
                    source.source_identifier = new_source_identifier
                
                # Обновляем название источника, если оно передано
                if new_source_title is not None:
                    source.source_title = new_source_title
                
                db.flush()
                return True
        except Exception as e:
            logging.error(f"Ошибка при обновлении источника с id {source_db_id}: {e}", exc_info=True)
            return False