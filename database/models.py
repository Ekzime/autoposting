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
from sqlalchemy.types import String, Text, DateTime, Integer, JSON, Boolean, BigInteger

# Импорты для работы с перечислениями
import enum
from sqlalchemy import Enum as SQLAlchemyEnum, Text

# Импорт централизованных настроек
from config import settings


# Получение строки подключения к БД из настроек
DB_URL = settings.database.connect_string
if not DB_URL:
    raise ValueError("Database connection string not found in settings")


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
    - ERROR_PERMANENT: окончательная ошибка после нескольких попыток
    """
    NEW = "new"
    SENT_TO_AI = "sent_to_ai"
    AI_PROCESSED = "ai_processed"
    ERROR_SENDING_TO_AI = "error_sending_to_ai"
    ERROR_AI_PROCESSING = "error_ai_processing"
    POSTED = "posted"  
    ERROR_POSTING = "error_posting"
    ERROR_PERMANENT = "error_permanent"


class ParsingSourceChannel(BaseModel):
    __tablename__ = "parsing_source_channels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_identifier: Mapped[str] = mapped_column(String(255), nullable=False) 
    source_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Внешний ключ, ссылающийся на id в таблице posting_targets
    posting_target_id: Mapped[int] = mapped_column(ForeignKey("posting_targets.id"), nullable=False)
    posting_target: Mapped["PostingTarget"] = relationship(back_populates="parsing_sources")
    added_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("source_identifier", "posting_target_id", name="uq_source_for_target"),
    )

    def __repr__(self):
        return f"<ParsingSourceChannel(id={self.id}, source='{self.source_identifier}', target_id={self.posting_target_id})>"

class ParsingTelegramAccount(BaseModel):
    __tablename__ = "parsing_telegram_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    phone_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)  # Формат: +XXXXXXXXXXX с кодом страны
    session_string: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending_auth", index=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    added_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<ParsingTelegramAccount(id={self.id}, phone={self.phone_number}, status={self.status}, active={self.is_active})>"
    

class Channels(BaseModel):
    __tablename__ = "channels"

    id:       Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True) # Уникальный идентификатор
    peer_id:  Mapped[int] = mapped_column(BigInteger, unique=True, nullable=True) # ID канала в Telegram
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=True) # Имя пользователя канала
    title:    Mapped[str] = mapped_column(String(255), nullable=False) # Название канала
    
    messages: Mapped[list[Messages]] = relationship("Messages", back_populates="channel") # Связь один-ко-многим с сообщениями

    
    def __repr__(self):
        return f"peer_id: {self.peer_id} username: {self.username} title: {self.title}"
    


class Messages(BaseModel):
    __tablename__ = "messages"
    __table_args__ = (UniqueConstraint("message_id", "channel_id", name="uq_message_channel"),) # Обеспечивает уникальность комбинации message_id и channel_id

    id:         Mapped[int]               = mapped_column(Integer, primary_key=True, autoincrement=True)  # Уникальный идентификатор
    channel_id: Mapped[int]               = mapped_column(BigInteger, ForeignKey("channels.peer_id"), nullable=False)  # Внешний ключ на канал
    message_id: Mapped[int]               = mapped_column(Integer, nullable=False)  # ID сообщения в Telegram
    text:       Mapped[str | None]        = mapped_column(Text, nullable=True)     # Текст сообщения
    length:     Mapped[int]               = mapped_column(Integer, nullable=False)  # Длина сообщения
    date:       Mapped[datetime]          = mapped_column(DateTime, nullable=False) # Дата публикации
    photo_path: Mapped[str | None]        = mapped_column(String(100), unique=True, nullable=True)  # Путь к сохраненному фото
    links:      Mapped[list[str] | None]  = mapped_column(JSON, nullable=True)  # Список ссылок в сообщении
    views:      Mapped[int]               = mapped_column(Integer, nullable=False, default=0)  # Количество просмотров
    status:     Mapped[NewsStatus]        = mapped_column(SQLAlchemyEnum(NewsStatus), default=NewsStatus.NEW, index=True)  # Статус обработки
    ai_processed_text: Mapped[str | None] = mapped_column(Text, nullable=True)  # Текст после обработки ИИ
    retry_count: Mapped[int]              = mapped_column(Integer, default=0)  # Счетчик попыток обработки
    error_info: Mapped[str | None]        = mapped_column(String(500), nullable=True)  # Подробная информация об ошибке

    channel: Mapped[Channels] = relationship("Channels", back_populates="messages")  # Связь многие-к-одному с каналом
   
   
    def __repr__(self):
        return f"channel_id: {self.channel_id} message_id: {self.message_id} text: {self.text} views: {self.views}"



class PostingTarget(BaseModel):
    __tablename__ = "posting_targets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    target_chat_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True) # Храним как строку (@username или -100число)
    target_title: Mapped[str | None] = mapped_column(String(255), nullable=True) # Название канала 
    is_active: Mapped[bool] = mapped_column(Boolean, default=True) # Активна ли эта настройка
    added_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    parsing_sources: Mapped[list["ParsingSourceChannel"]] = relationship(
        back_populates="posting_target",
        cascade="all, delete-orphan" # Если удаляем PostingtTarget, удаляем и связанные с ним источники парсинга
    )
    
    def __repr__(self):
        return f"<PostingTarget(id={self.id}, target_chat_id='{self.target_chat_id}', title='{self.target_title}')>"



# Создание всех таблиц в базе данных
BaseModel.metadata.create_all(engine)