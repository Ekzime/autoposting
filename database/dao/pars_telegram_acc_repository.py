from sqlalchemy.orm import Session
from sqlalchemy import select, update, delete 
from typing import List, Optional, Dict, Any, Union
import logging

from database.models import ParsingTelegramAccount
from database.manager import session_scope


class ParsingTelegramAccRepository:
    def __init__(self):
        logging.debug("Инициализация ParsingTelegramAccRepository")

    def add_account(self,
                    phone_number:str,
                    session_string:str | None = None) -> Dict[str, Any] | None | str:
        """
        Добавляет новый аккаунт в базу данных.
        """
        try:
            with session_scope() as db:
                # Проверяем, существует ли уже аккаунт с таким номером телефона
                existing_account = db.execute(select(ParsingTelegramAccount).filter_by(phone_number=phone_number)).scalar_one_or_none()
                if existing_account:
                    logging.warning(f"Аккаунт с номером телефона {phone_number} уже существует")
                    return "exists"
                
                # Создаем новый аккаунт
                new_account = ParsingTelegramAccount(
                    phone_number=phone_number,
                    session_string=session_string
                )
                db.add(new_account)
                db.flush()  # Используем flush вместо commit, т.к. commit выполнится автоматически при выходе из контекстного менеджера
                return new_account
        except Exception as e:
            logging.error(f"Ошибка при добавлении аккаунта: {e}")
            return None
        
    def get_account_by_phone(phone_number: str) -> Dict[str, Any] | None:
        """
        Получает аккаунт по номеру телефона.
        """
        try:
            with session_scope() as db:
                account = db.get(ParsingTelegramAccount, phone_number)
                if account:
                    return {
                        'id': account.id,
                        'phone_number': account.phone_number,
                        'session_string': account.session_string,
                        'is_active': account.is_active
                    }
                return None
        except Exception as e:
            logging.error(f"Ошибка при получении аккаунта: {e}")
            return None
    
    def get_account_by_id(account_db_id: int) -> Dict[str, Any] | None:
        """
        Получает аккаунт по его ID.
        """
        try:
            with session_scope() as db:
                account = db.get(ParsingTelegramAccount, account_db_id)
                if account:
                    return {
                        'id': account.id,
                        'phone_number': account.phone_number,
                        'session_string': account.session_string,
                        'is_active': account.is_active
                    }
                return None
        except Exception as e:
            logging.error(f"Ошибка при получении аккаунта: {e}")
            return None

    def get_all_accounts() -> List[Dict[str, Any]]:
        """
        Получает все аккаунты из базы данных.
        """
        try:
            with session_scope() as db:
                accounts = db.execute(select(ParsingTelegramAccount)).scalars().all()
                return [
                    {
                        'id': account.id,
                        'phone_number': account.phone_number,
                        'session_string': account.session_string,
                        'is_active': account.is_active
                    }
                    for account in accounts
                ]
        except Exception as e:
            logging.error(f"Ошибка при получении всех аккаунтов: {e}")
            return []
        
    def update_account_session(self,
                              account_db_id: int,
                              session_string: str,
                              account_telegram_id: int,
                              status: str) -> bool:
        """
        Обновление строки сессии, Telegram ID и статуса после успешной авторизации
            
        Returns:
            bool: True в случае успешного обновления, False в случае ошибки
        """
        try:
            with session_scope() as db:
                account = db.get(ParsingTelegramAccount, account_db_id)
                if account:
                    account.session_string = session_string
                    account.telegram_id = account_telegram_id
                    account.status = status
                    db.commit()
                    return True
                return False
        except Exception as e:  
            logging.error(f"Ошибка при обновлении аккаунта: {e}")
            return False
        
    def update_account_status(self, account_db_id: int | str, status: str) -> bool:
        """
        Обновление статуса аккаунта
        
        Args:
            account_db_id (int | str): ID аккаунта в базе данных
            status (str): Новый статус аккаунта
            
        Returns:
            bool: True в случае успешного обновления, False в случае ошибки
        """
        try:
            with session_scope() as db:
                account = db.get(ParsingTelegramAccount, account_db_id)
                if account:
                    account.status = status
                    return True
                return False
        except Exception as e:
            logging.error(f"Ошибка при обновлении статуса аккаунта: {e}")
            return False
    
    def set_active_status(account_db_id: int, is_active: bool) -> bool:
        """
        Установка статуса активности аккаунта
        
        Args:
            account_db_id (int): ID аккаунта в базе данных
            is_active (bool): Новый статус активности
        """
        try:
            with session_scope() as db:
                account = db.get(ParsingTelegramAccount, account_db_id)
                if account:
                    account.is_active = is_active
                    return True
                return False
        except Exception as e:
            logging.error(f"Ошибка при установке статуса активности аккаунта: {e}")
            return False
    
    def delete_account(account_db_id: int) -> bool:
        """
        Удаление аккаунта из базы данных
        
        Args:
            account_db_id (int): ID аккаунта в базе данных
        """
        try:
            with session_scope() as db:
                account = db.get(ParsingTelegramAccount, account_db_id)
                if account:
                    db.delete(account)
                    return True
                return False
        except Exception as e:
            logging.error(f"Ошибка при удалении аккаунта: {e}")
            return False

    def get_active_parsing_accounts() -> List[Dict[str, Any]]:
        """
        Получение активных аккаунтов для парсинга
        """
        try:
            with session_scope() as db:
                accounts = db.execute(select(ParsingTelegramAccount).filter_by(is_active=True)).scalars().all()
                return [
                    {
                        'id': account.id,
                        'phone_number': account.phone_number,
                        'session_string': account.session_string,
                        'status': account.status
                    }
                    for account in accounts
                ]
        except Exception as e:
            logging.error(f"Ошибка при получении активных аккаунтов для парсинга: {e}")
            return []
                
