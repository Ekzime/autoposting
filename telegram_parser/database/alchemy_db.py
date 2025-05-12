# ./database/alchemy_db.py
from __future__ import annotations
from sqlalchemy import create_engine, Engine, UniqueConstraint
from sqlalchemy import ForeignKey
from sqlalchemy.orm import (
    declarative_base, DeclarativeBase, 
    mapped_column, Mapped,
    relationship
)
from sqlalchemy.types import String, DateTime, Integer, JSON



DB_URL = "sqlite:///./database/parser.db"
engine: Engine = create_engine(DB_URL)
BaseModel: DeclarativeBase = declarative_base()



class Messages(BaseModel):
    """
    columns:
        id:             Mapped[int]             
        channel_id:     Mapped[int]             
        message_id:     Mapped[int]             
        text:           Mapped[str | None]      
        length:         Mapped[int]             
        date:           Mapped[DateTime]        
        photo_path:     Mapped[str | None]      
        links:          Mapped[list[str | None]]
        views:          Mapped[int]             
    
    """
    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint('message_id', 'channel_id', name='message_id: channel_id - must be unique'),
    )
    
    id:         Mapped[int]                 = mapped_column(primary_key=True, autoincrement=True)
    channel_id: Mapped[int]                 = mapped_column(Integer, ForeignKey("channels.peer_id"), nullable=False)
    message_id: Mapped[int]                 = mapped_column(Integer, unique=False, nullable=False)
    text:       Mapped[str | None]          = mapped_column(String, nullable=True)
    length:     Mapped[int]                 = mapped_column(Integer, nullable=False)
    date:       Mapped[DateTime]            = mapped_column(DateTime, nullable=False)
    photo_path: Mapped[str | None]          = mapped_column(String, unique=True, nullable=True)
    links:      Mapped[list[str | None]]    = mapped_column(JSON, nullable=True)
    views:      Mapped[int]                 = mapped_column(Integer, nullable=False, default=0)
    
    channel: Mapped[Channels] = relationship("Channels", back_populates="messages")


    def __str__(self):
        return f"<Message\
        (\
            id: {self.id}\
            channel_id: {self.channel_id}\
            message_id: {self.message_id}\
            text: {self.text}\
            length: {self.length}\
            date: {self.date}\
            photo_path: {self.photo_path}\
            links: {self.links}\
            views: {self.views}\
        )>"



class  Channels(BaseModel):
    """
    columns:
        id: Mapped[int]
        peer_id: Mapped[int]
        username: Mapped[str]
        title: Mapped[str]
        messages: Mapped[list[Messages]]
    """
    __tablename__ = "channels"
    
    id:             Mapped[int]             = mapped_column(primary_key=True, autoincrement=True)
    peer_id:        Mapped[int]             = mapped_column(Integer, nullable=True, unique=True)
    username:       Mapped[str]             = mapped_column(String, nullable=True, unique=True)
    title:          Mapped[str]             = mapped_column(String, nullable=False)
    
    messages: Mapped[list[Messages]] = relationship("Messages", back_populates="channel")
    
    
    def __str__(self):
        return f"id: {self.id}\npeer_id: {self.peer_id}\nusername: {self.username}\ntitle: {self.title}\nmessages: {self.messages}"
    

BaseModel.metadata.create_all(engine)
