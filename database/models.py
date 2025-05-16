# Импорты для работы с типами и аннотациями
from __future__ import annotations
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

# Создание движка SQLAlchemy
engine = create_engine(DB_URL, echo=False, pool_pre_ping=True)
# Создание фабрики сессий
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Базовый класс для моделей SQLAlchemy
BaseModel = declarative_base()

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

class Channels(BaseModel):
    """
    Модель для хранения информации о Telegram-каналах
    """
    __tablename__ = "channels"

    id:      Mapped[int]      = mapped_column(Integer, primary_key=True, autoincrement=True)  # Уникальный идентификатор
    peer_id: Mapped[int]      = mapped_column(Integer, unique=True, nullable=True)           # ID канала в Telegram
    username: Mapped[str]     = mapped_column(String(100), unique=True, nullable=True)       # Имя пользователя канала
    title:    Mapped[str]     = mapped_column(String(255), nullable=False)                   # Название канала
    
    # Связь один-ко-многим с сообщениями
    messages: Mapped[list[Messages]] = relationship(
        "Messages", back_populates="channel"
    )


class Messages(BaseModel):
    """
    Модель для хранения сообщений из Telegram-каналов
    """
    __tablename__ = "messages"
    __table_args__ = (
        # Обеспечивает уникальность комбинации message_id и channel_id
        UniqueConstraint("message_id", "channel_id", name="uq_message_channel"),
    )

    id:         Mapped[int]           = mapped_column(Integer, primary_key=True, autoincrement=True)  # Уникальный идентификатор
    channel_id: Mapped[int]           = mapped_column(Integer, ForeignKey("channels.peer_id"), nullable=False)  # Внешний ключ на канал
    message_id: Mapped[int]           = mapped_column(Integer, nullable=False)  # ID сообщения в Telegram
    text:       Mapped[str | None]    = mapped_column(Text, nullable=True)     # Текст сообщения
    length:     Mapped[int]           = mapped_column(Integer, nullable=False)  # Длина сообщения
    date:       Mapped[datetime]      = mapped_column(DateTime, nullable=False) # Дата публикации
    photo_path: Mapped[str | None]    = mapped_column(String(100), unique=True, nullable=True)  # Путь к сохраненному фото
    links:      Mapped[list[str] | None] = mapped_column(JSON, nullable=True)  # Список ссылок в сообщении
    views:      Mapped[int]           = mapped_column(Integer, nullable=False, default=0)  # Количество просмотров
    status: Mapped[NewsStatus] = mapped_column(SQLAlchemyEnum(NewsStatus), default=NewsStatus.NEW, index=True)  # Статус обработки
    ai_processed_text: Mapped[str | None] = mapped_column(Text, nullable=True)  # Текст после обработки ИИ

    # Связь многие-к-одному с каналом
    channel: Mapped[Channels] = relationship("Channels", back_populates="messages")

class PostingtTarget(BaseModel):
    __tablename__ = "posting_targets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    target_chat_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True) # Храним как строку (@username или -100число)
    target_title: Mapped[str | None] = mapped_column(String(255), nullable=True) # Название канала 
    is_active: Mapped[bool] = mapped_column(Boolean, default=True) # Активна ли эта настройка
    added_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<PostingTarget(id={self.id}, target_chat_id='{self.target_chat_id}', title='{self.target_title}')>"



# Создание всех таблиц в базе данных
BaseModel.metadata.create_all(engine)