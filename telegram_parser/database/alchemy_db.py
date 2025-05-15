from __future__ import annotations
from datetime import datetime
from sqlalchemy import create_engine, UniqueConstraint, ForeignKey
from sqlalchemy.orm import (
    declarative_base,
    mapped_column,
    Mapped,
    relationship
)
from sqlalchemy.types import (
    String, 
    Text, 
    DateTime, 
    Integer, 
    JSON
)



# Правильный URL для MySQL (без .db):
DB_URL = "mysql+pymysql://root@127.0.0.1:3306/parser.db"
engine = create_engine(DB_URL, echo=True, pool_pre_ping=True)

BaseModel = declarative_base()



class Channels(BaseModel):
    __tablename__ = "channels"

    id:       Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    peer_id:  Mapped[int] = mapped_column(Integer, unique=True, nullable=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=True)
    title:    Mapped[str] = mapped_column(String(255), nullable=False)

    messages: Mapped[list[Messages]] = relationship("Messages", back_populates="channel")



class Messages(BaseModel):
    __tablename__ = "messages"
    __table_args__ = (UniqueConstraint("message_id", "channel_id", name="uq_message_channel"),)

    id:         Mapped[int]              = mapped_column(Integer, primary_key=True, autoincrement=True)
    channel_id: Mapped[int]              = mapped_column(Integer, ForeignKey("channels.peer_id"), nullable=False)
    message_id: Mapped[int]              = mapped_column(Integer, nullable=False)
    text:       Mapped[str | None]       = mapped_column(Text, nullable=True)
    length:     Mapped[int]              = mapped_column(Integer, nullable=False)
    date:       Mapped[datetime]         = mapped_column(DateTime, nullable=False)
    photo_path: Mapped[str | None]       = mapped_column(String(100), unique=True, nullable=True)
    links:      Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    views:      Mapped[int]              = mapped_column(Integer, nullable=False, default=0)

    channel:    Mapped[Channels] = relationship("Channels", back_populates="messages")


BaseModel.metadata.create_all(engine)