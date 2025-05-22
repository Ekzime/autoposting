from sqlalchemy.orm import Session
from sqlalchemy import select, update, delete 
from typing import List, Optional, Dict, Any
import logging

from database.models import PostingTarget
from database.manager import session_scope

class PostingTargetRepository:
    """
    Репозиторий для управления целевыми каналами для постинга.
    
    Методы:
        set_active_target(target_chat_id_str: str, target_title: str | None) -> PostingTarget | None:
            Устанавливает активную цель для постинга, деактивируя все остальные.
            
        get_all_target_channels() -> List[Dict[str, Any]]:
            Получает список всех целевых каналов из базы данных.
            
        get_active_target() -> Dict[str, Any] | None:
            Получает текущий активный целевой канал.
            
        delete_target(target_id: int) -> bool:
            Удаляет целевой канал по его ID.
            
        update_target(target_id: int, new_data: Dict[str, Any]) -> bool:
            Обновляет данные целевого канала.
    
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
            1. Ищет запись с указанным chat_id
            2. Обновляет существующую запись или создает новую
        """
        try:
            with session_scope() as db:
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
            
    def get_active_target_info(self) -> List[Dict[str, Any]]:
        """
        Получает информацию об активных целях для постинга.
        
        Returns:
            List[Dict[str, Any]]: Список словарей с информацией об активных целях или пустой список
            
        Действия:
            1. Ищет записи с флагом is_active=True
            2. Возвращает данные в виде списка словарей или пустой список если цели не найдены
        """
        with session_scope() as db:
            try:
                targets = db.execute(
                    select(PostingTarget).filter_by(is_active=True)
                ).scalars().all()
                
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
                logging.error(f"Error in get_active_target_info: {e}")
                return []
                
    def get_active_target_chat_id_str(self) -> Optional[str]:
        """
        Получает ID чата первой активной цели для постинга.
        
        Returns:
            Optional[str]: ID чата первой активной цели или None если цели не найдены
        """
        active_targets = self.get_active_target_info()
        if active_targets and len(active_targets) > 0:
            return active_targets[0]["target_chat_id"]
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
        """
        with session_scope() as db:
            try:
                # Ищем и активируем нужный канал
                target = db.execute(
                    select(PostingTarget).where(PostingTarget.target_chat_id == target_chat_id_str)
                ).scalar_one_or_none()
                
                if not target:
                    return False
                
                target.is_active = True
                return True
            except Exception as e:
                logging.error(f"Error in activate_target_by_id: {e}")
                return False

    def get_all_active_target_channels(self) -> List[Dict[str, Any]]:
        """
        Получает список всех активных целей для постинга.
        
        Returns:
            List[Dict[str, Any]]: Список словарей с информацией об активных целях
            
        Действия:
            1. Получает все записи из таблицы PostingTarget с флагом is_active=True
            2. Преобразует их в список словарей
        """
        with session_scope() as db:
            try:
                targets = db.execute(
                    select(PostingTarget).filter_by(is_active=True)
                ).scalars().all()
                
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
                logging.error(f"Error in get_all_active_target_channels: {e}")
                return []

    def toggle_target_active_status(self, target_chat_id_str: str, active_status: bool) -> bool:
        """
        Активирует или деактивирует цель для постинга без влияния на другие цели.
        
        Args:
            target_chat_id_str (str): ID чата цели
            active_status (bool): Новый статус активности
            
        Returns:
            bool: True в случае успеха, False если цель не найдена или произошла ошибка
        """
        with session_scope() as db:
            try:
                target = db.execute(
                    select(PostingTarget).where(PostingTarget.target_chat_id == target_chat_id_str)
                ).scalar_one_or_none()
                
                if not target:
                    return False
                    
                target.is_active = active_status
                return True
            except Exception as e:
                logging.error(f"Error in toggle_target_active_status: {e}")
                return False
                
    def add_or_update_target(self, target_chat_id_str: str, target_title: str | None, is_active: bool) -> PostingTarget | None:
        """
        Добавляет новую или обновляет существующую цель для постинга.
        
        Args:
            target_chat_id_str (str): ID чата целевого канала или @username
            target_title (str | None): Название канала (может быть None)
            is_active (bool): Флаг активности канала
            
        Returns:
            PostingTarget|None: Объект PostingTarget в случае успешного добавления/обновления, None в случае ошибки
        """
        try:
            # Проверяем и корректируем формат ID канала
            corrected_id = self._correct_chat_id_format(target_chat_id_str)
            
            with session_scope() as db:
                # Проверяем, существует ли уже такой канал
                existing_target = db.execute(
                    select(PostingTarget).filter_by(target_chat_id=corrected_id)
                ).scalar_one_or_none()
                
                if existing_target:
                    # Если канал существует, обновляем его
                    if target_title is not None:
                        existing_target.target_title = target_title
                    existing_target.is_active = is_active
                    db.flush()
                    return existing_target
                else:
                    # Если канала нет, создаем новый
                    new_target = PostingTarget(
                        target_chat_id=corrected_id,
                        target_title=target_title,
                        is_active=is_active
                    )
                    db.add(new_target)
                    db.flush()
                    return new_target
        except Exception as e:
            logging.error(f"Ошибка при добавлении/обновлении целевого канала {target_chat_id_str}: {e}")
            return None

    def _correct_chat_id_format(self, chat_id: str) -> str:
        """
        Проверяет и исправляет формат ID канала.
        
        Args:
            chat_id (str): ID канала или @username
            
        Returns:
            str: Исправленный ID канала
        
        Правила:
        1. Если ID начинается с '@', оставляем как есть (публичный канал)
        2. Если ID числовой и начинается с '-100', оставляем как есть (приватный канал, правильный формат)
        3. Если ID числовой, отрицательный, но не начинается с '-100', добавляем префикс '-100'
        4. Если ID не подходит под предыдущие случаи, возвращаем как есть
        """
        # Логируем исходный ID для отладки
        logging.debug(f"Проверка формата ID канала: {chat_id}")
        
        # Публичный канал - оставляем как есть
        if chat_id.startswith('@'):
            return chat_id
        
        # Если это числовой ID
        try:
            # Пробуем преобразовать в число
            numeric_id = int(chat_id)
            
            # Если это отрицательное число (ID канала)
            if numeric_id < 0:
                # Если это уже в формате -100..., оставляем как есть
                if chat_id.startswith('-100'):
                    return chat_id
                
                # Если просто отрицательное число, конвертируем в правильный формат
                # Убираем минус, добавляем префикс -100
                correct_id = f"-100{abs(numeric_id)}"
                logging.info(f"ID канала исправлен с {chat_id} на {correct_id} (добавлен префикс -100)")
                return correct_id
            
            # Если положительное число, предполагаем что пользователь забыл добавить минус
            correct_id = f"-100{numeric_id}"
            logging.info(f"ID канала исправлен с {chat_id} на {correct_id} (добавлены префиксы - и 100)")
            return correct_id
        except ValueError:
            # Если не удалось преобразовать в число, значит это не числовой ID
            # Возможно, это публичный канал без @
            if not chat_id.startswith('@') and not chat_id.startswith('-'):
                # Добавляем @ для публичного канала
                correct_id = f"@{chat_id}"
                logging.info(f"ID канала исправлен с {chat_id} на {correct_id} (добавлен префикс @)")
                return correct_id
        
        # Если не удалось определить формат, возвращаем как есть
        return chat_id


