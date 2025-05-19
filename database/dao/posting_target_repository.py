from sqlalchemy.orm import Session
from sqlalchemy import select, update, delete 
from typing import List, Optional, Dict, Any
import logging

from database.models import PostingTarget
from database.manager import session_scope

class PostingTargetRepository:
    """
    Репозиторий для управления целевыми каналами для постинга.
    
    Этот класс предоставляет методы для работы с таблицей PostingTarget в базе данных:
    - Добавление новых целевых каналов
    - Активация/деактивация каналов
    - Получение списка всех каналов
    - Управление активным каналом для публикации
    
    Использует глобальный session_scope для управления сессиями БД.
    """
    def __init__(self):
        logging.debug("Инициализация PostingTargetRepository")
    
    def set_active_target(self, target_chat_id_str: str, target_title: str | None) -> PostingTarget | None:
        """
        Устанавливает активную цель для постинга.
        
        Args:
            target_chat_id_str (str): ID чата целевого канала
            target_title (str | None): Название целевого канала (опционально)
            
        Returns:
            PostingTarget | None: Объект активной цели или None в случае ошибки
            
        Действия:
            1. Деактивирует все существующие активные цели
            2. Ищет запись с указанным chat_id
            3. Обновляет существующую запись или создает новую
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
            logging.error(f"Error in set_active_target: {e}")
            return None
            
    def get_active_target_info(self) -> Optional[Dict[str, Any]]:
        """
        Получает информацию об активной цели для постинга.
        
        Returns:
            Optional[Dict[str, Any]]: Словарь с информацией об активной цели или None
            
        Действия:
            1. Ищет запись с флагом is_active=True
            2. Возвращает данные в виде словаря или None если цель не найдена
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
                logging.error(f"Error in get_active_target_info: {e}")
                return None
                
    def get_active_target_chat_id_str(self) -> Optional[str]:
        """
        Получает ID чата активной цели для постинга.
        
        Returns:
            Optional[str]: ID чата активной цели или None если цель не найдена
        """
        active_target = self.get_active_target_info()
        if active_target:
            return active_target["target_chat_id"]
        return None

    def deactivate_target_by_id(self, target_chat_id_to_deactivate: str) -> bool:
        """
        Деактивирует цель для постинга по ID чата.
        
        Args:
            target_chat_id_to_deactivate (str): ID чата цели для деактивации
            
        Returns:
            bool: True в случае успеха, False в случае ошибки
        """
        with session_scope() as db:
            try:
                db.execute(
                    update(PostingTarget)
                    .where(PostingTarget.target_chat_id == target_chat_id_to_deactivate)
                    .values(is_active=False)
                )
                return True
            except Exception as e:
                logging.error(f"Error in deactivate_target_by_id: {e}")
                return False
                
    def get_all_target_channels(self) -> List[Dict[str, Any]]:
        """
        Получает список всех целей для постинга.
        
        Returns:
            List[Dict[str, Any]]: Список словарей с информацией о целях
            
        Действия:
            1. Получает все записи из таблицы PostingTarget
            2. Преобразует их в список словарей
        """
        with session_scope() as db:
            try:
                targets = db.execute(select(PostingTarget)).scalars().all()
                if not targets:
                    return []
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
            except Exception as e:
                logging.error(f"Error in get_all_target_channels: {e}")
                return []

    def delete_target_channel(self, target_chat_id: str) -> bool:
        """
        Удаляет цель для постинга по ID чата.
        
        Args:
            target_chat_id (str): ID чата цели для удаления
            
        Returns:
            bool: True в случае успеха, False если цель не найдена или произошла ошибка
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
                logging.error(f"Error in delete_target_channel: {e}")
                return False

    def activate_target_by_id(self, target_chat_id_str: str) -> bool:
        """
        Активирует цель для постинга по ID чата.
        
        Args:
            target_chat_id_str (str): ID чата цели для активации
            
        Returns:
            bool: True в случае успеха, False если цель не найдена или произошла ошибка
            
        Действия:
            1. Деактивирует все существующие активные цели
            2. Находит и активирует указанную цель
        """
        with session_scope() as db:
            try:
                # Затем ищем и активируем нужный канал
                target = db.execute(
                    select(PostingTarget).where(PostingTarget.target_chat_id == target_chat_id_str)
                ).scalar_one_or_none()
                
                if not target:
                    return False

                # Сначала деактивируем все активные каналы
                db.execute(
                    update(PostingTarget)
                    .where(PostingTarget.is_active == True)
                    .values(is_active=False)
                )
                
                target.is_active = True
                return True
            except Exception as e:
                logging.error(f"Error in activate_target_by_id: {e}")
                return False