from __future__ import annotations # работа с типами и аннотациями

from datetime import datetime

# Импорты SQLAlchemy для работы с БД
from sqlalchemy import create_engine, UniqueConstraint, ForeignKey
from sqlalchemy.orm import (
    declarative_base,
    mapped_column,
    Mapped,
    relationship,
    sessionmaker
)
from sqlalchemy.types import String, Text, DateTime, Integer, JSON, Boolean

# Импорты для работы с переменными окружения
from dotenv import load_dotenv
import os

# Импорты для работы с перечислениями
import enum
from sqlalchemy import Enum as SQLAlchemyEnum, Text



# Загрузка переменных окружения
load_dotenv()

# Получение строки подключения к БД из переменных окружения
DB_URL = os.getenv("DB_CONNECT_STRING")
if not DB_URL:
    raise ValueError("Database connection string not found in environment variables")


engine = create_engine(DB_URL, echo=False, pool_pre_ping=True) # Создание движка SQLAlchemy
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine) # Создание фабрики сессий
BaseModel = declarative_base() # Базовый класс для моделей SQLAlchemy



class NewsStatus(enum.Enum):
    """
    Перечисление для отслеживания статуса обработки новости:
    - NEW: новая запись
    - SENT_TO_AI: отправлено на обработку ИИ
    - AI_PROCESSED: обработано ИИ
    - ERROR_SENDING_TO_AI: ошибка при отправке к ИИ
    - ERROR_AI_PROCESSING: ошибка при обработке ИИ
    - POSTED: опубликовано
    - ERROR_POSTING: ошибка при публикации
    """
    NEW = "new"
    SENT_TO_AI = "sent_to_ai"
    AI_PROCESSED = "ai_processed"
    ERROR_SENDING_TO_AI = "error_sending_to_ai"
    ERROR_AI_PROCESSING = "error_ai_processing"
    POSTED = "posted"  
    ERROR_POSTING = "error_posting"



class Channel(BaseModel):
    __tablename__ = "channels"

    id:       Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True) # Уникальный идентификатор
    peer_id:  Mapped[int] = mapped_column(Integer, unique=True, nullable=True) # ID канала в Telegram
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=True) # Имя пользователя канала
    title:    Mapped[str] = mapped_column(String(255), nullable=False) # Название канала

    owner_id: Mapped[int] = mapped_column(Integer, ForeignKey("telegram_users.tg_id"), nullable=True) # ID владельца канала
    messages: Mapped[list[Messages]] = relationship("Messages", back_populates="channel") # Связь один-ко-многим с сообщениями

    
    def __repr__(self):
        return f"peer_id: {self.peer_id} username: {self.username} title: {self.title}"
    


class Messages(BaseModel):
    __tablename__ = "messages"
    __table_args__ = (UniqueConstraint("message_id", "channel_id", name="uq_message_channel"),) # Обеспечивает уникальность комбинации message_id и channel_id

    id:         Mapped[int]               = mapped_column(Integer, primary_key=True, autoincrement=True)  # Уникальный идентификатор
    channel_id: Mapped[int]               = mapped_column(Integer, ForeignKey("channels.peer_id"), nullable=False)  # Внешний ключ на канал
    message_id: Mapped[int]               = mapped_column(Integer, nullable=False)  # ID сообщения в Telegram
    text:       Mapped[str | None]        = mapped_column(Text, nullable=True)     # Текст сообщения
    length:     Mapped[int]               = mapped_column(Integer, nullable=False)  # Длина сообщения
    date:       Mapped[datetime]          = mapped_column(DateTime, nullable=False) # Дата публикации
    photo_path: Mapped[str | None]        = mapped_column(String(100), unique=True, nullable=True)  # Путь к сохраненному фото
    links:      Mapped[list[str] | None]  = mapped_column(JSON, nullable=True)  # Список ссылок в сообщении
    views:      Mapped[int]               = mapped_column(Integer, nullable=False, default=0)  # Количество просмотров
    status:     Mapped[NewsStatus]        = mapped_column(SQLAlchemyEnum(NewsStatus), default=NewsStatus.NEW, index=True)  # Статус обработки
    ai_processed_text: Mapped[str | None] = mapped_column(Text, nullable=True)  # Текст после обработки ИИ

    channel: Mapped[Channel] = relationship("Channels", back_populates="messages")  # Связь многие-к-одному с каналом
   
   
    def __repr__(self):
        return f"channel_id: {self.channel_id} message_id: {self.message_id} text: {self.text} views: {self.views}"



class TelegramUser(BaseModel):
    __tablename__ = "telegram_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True) # Уникальный идентификатор
    tg_id: Mapped[int] = mapped_column(Integer, nullable=False, unique=True) # ID пользователя в Telegram
    username: Mapped[str | None] = mapped_column(String(100), nullable=True) # Имя пользователя Telegram
    first_name: Mapped[str | None] = mapped_column(String(100), nullable=True) # Имя пользователя Telegram
    last_name: Mapped[str | None] = mapped_column(String(100), nullable=True) # Фамилия пользователя Telegram

    managed_channels: Mapped[list[int, str]] = relationship("Channels", back_populates="manager") # Связь один-ко-многим с каналами

    def __repr__(self):
        return f"<TelegramUser(id={self.id}, tg_id={self.tg_id}, username='{self.username}')>"


# Создание всех таблиц в базе данных
BaseModel.metadata.create_all(engine)