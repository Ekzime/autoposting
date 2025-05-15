from __future__ import annotations
from datetime import datetime
from sqlalchemy import create_engine, UniqueConstraint, ForeignKey
from sqlalchemy.orm import (
    declarative_base,
    mapped_column,
    Mapped,
    relationship,
    sessionmaker
)
from sqlalchemy.types import String, Text, DateTime, Integer, JSON
from dotenv import load_dotenv
import os
import enum
from sqlalchemy import Enum as SQLAlchemyEnum, Text

load_dotenv()

DB_URL = os.getenv("DB_CONNECT_STRING")
if not DB_URL:
    raise ValueError("Database connection string not found in environment variables")
engine = create_engine(DB_URL, echo=False, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

BaseModel = declarative_base()

class NewsStatus(enum.Enum):
    """
    Класс для хранения статуса новости
    """
    NEW = "new"
    SENT_TO_AI = "sent_to_ai"
    AI_PROCESSED = "ai_processed"
    ERROR_SENDING_TO_AI = "error_sending_to_ai"
    ERROR_AI_PROCESSING = "error_ai_processing"

class Channels(BaseModel):
    __tablename__ = "channels"

    id:      Mapped[int]      = mapped_column(Integer, primary_key=True, autoincrement=True)
    peer_id: Mapped[int]      = mapped_column(Integer, unique=True, nullable=True)
    username: Mapped[str]     = mapped_column(String(100), unique=True, nullable=True)
    title:    Mapped[str]     = mapped_column(String(255), nullable=False)

    messages: Mapped[list[Messages]] = relationship(
        "Messages", back_populates="channel"
    )


class Messages(BaseModel):
    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint("message_id", "channel_id", name="uq_message_channel"),
    )

    id:         Mapped[int]           = mapped_column(Integer, primary_key=True, autoincrement=True)
    channel_id: Mapped[int]           = mapped_column(Integer, ForeignKey("channels.peer_id"), nullable=False)
    message_id: Mapped[int]           = mapped_column(Integer, nullable=False)
    text:       Mapped[str | None]    = mapped_column(Text, nullable=True)
    length:     Mapped[int]           = mapped_column(Integer, nullable=False)
    date:       Mapped[datetime]      = mapped_column(DateTime, nullable=False)
    photo_path: Mapped[str | None]    = mapped_column(String(100), unique=True, nullable=True)
    links:      Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    views:      Mapped[int]           = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[NewsStatus] = mapped_column(SQLAlchemyEnum(NewsStatus), default=NewsStatus.NEW, index=True)
    ai_processed_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    channel: Mapped[Channels] = relationship("Channels", back_populates="messages")


# Создание схемы в базе данных
BaseModel.metadata.create_all(engine)