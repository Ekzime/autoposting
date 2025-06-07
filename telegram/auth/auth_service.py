import jwt
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from database.models import AdminSession, SessionLocal
from sqlalchemy import select, update, delete
from config.settings import settings
import logging

logger = logging.getLogger(__name__)

class AuthService:

    @staticmethod
    def generate_session_token(user_id:int, username:str) -> str:
        """
        Генерирует JWT-токен для сессии администратора.    
        """
        payload = {
            'user_id': user_id,
            'username': username,
            'issued_at': datetime.utcnow(),
            'expires_at': (datetime.utcnow() + timedelta(hours=settings.telegram_bot.session_duration_hours)).timestamp()
        }

        token = jwt.encode(payload, settings.telegram_bot.jwt_secret, algorithm='HS256')
        return token
    
    @staticmethod
    def verify_password(password:str) -> bool:
        """
        Проверяет пароль администратора.
        """
        return password == settings.telegram_bot.admin_password
    
    @staticmethod
    def is_admin_allowed(user_id:int) -> bool:
        """проверяет, разрешен ли этот пользователь как администратор"""
        return user_id in settings.telegram_bot.admin_ids
    
    @staticmethod
    def create_session(user_id: int, username: str) -> Optional[str]:
        """Создает новую сессию администратора"""
        try:
            with SessionLocal() as session:
                # удаляем старые сессии для этого пользователя 
                session.execute(
                    delete(AdminSession).where(AdminSession.user_id == user_id)
                )
                # создаем новую сессию
                token = AuthService.generate_session_token(user_id, username)
                expires_at = datetime.utcnow() + timedelta(hours=settings.telegram_bot.session_duration_hours)

                new_session = AdminSession(
                    user_id=user_id,
                    token=token,
                    expires_at=expires_at
                )
                session.add(new_session)
                session.commit()
                logger.info(f"Сессия администратора создана для пользователя {username} (ID: {user_id})")
                return token
            
        except Exception as e:
            logger.error(f"Ошибка при создании сессии администратора: {e}")
            return None
    
    @staticmethod
    def verify_session(user_id: int) -> bool:
        """Проверяет активность сессии администратора"""
        try:
            with SessionLocal() as session:
                admin_session = session.execute(
                    select(AdminSession).where(
                        AdminSession.user_id == user_id,
                        AdminSession.is_active == True,
                        AdminSession.expires_at > datetime.utcnow()
                    )
                ).scalar_one_or_none()
                
                if admin_session:
                    # обновляем время последней активности
                    admin_session.last_activity = datetime.utcnow()
                    session.commit()
                    return True
                return False
        except Exception as e:
            logger.error(f"Ошибка при проверке сессии администратора: {e}")
            return False
        
    
