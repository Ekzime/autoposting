from typing import Optional, Dict, Any
import os
from pydantic import BaseModel, Field, validator, ConfigDict
from pydantic_settings import BaseSettings


class AIServiceSettings(BaseModel):
    """Настройки сервиса искусственного интеллекта"""
    gemini_key: str  # Ключ API для Gemini
    api_url: str = Field(..., description="URL API искусственного интеллекта для фильтрации")
    
    model_config = ConfigDict(extra="allow")


class TelegramBotSettings(BaseModel):
    """Настройки бота Telegram"""
    bot_token: str  # Токен бота Telegram
    bot_token_main: Optional[str] = None  # Опциональный основной токен бота
    
    model_config = ConfigDict(extra="allow")


class TelegramApiSettings(BaseModel):
    """Настройки API Telegram для работы с клиентами"""
    api_id: int  # ID приложения Telegram API
    api_hash: str  # Хеш приложения Telegram API
    
    model_config = ConfigDict(extra="allow")


class TelegramParserSettings(BaseModel):
    """Настройки парсера Telegram"""
    phone_number: Optional[str] = None  # Номер телефона для авторизации в Telegram API
    session: str  # Имя файла сессии Telegram
    photo_storage: str  # Путь для хранения фотографий
    
    model_config = ConfigDict(extra="allow")


class DatabaseSettings(BaseModel):
    """Настройки базы данных"""
    connect_string: str  # Строка подключения к базе данных
    
    model_config = ConfigDict(extra="allow")


class Settings(BaseSettings):
    """Основные настройки приложения, загружаемые из переменных окружения"""
    ai_service: AIServiceSettings  # Настройки сервиса ИИ
    telegram_bot: TelegramBotSettings  # Настройки бота Telegram
    telegram_api: TelegramApiSettings  # Настройки API Telegram для аутентификации
    telegram_parser: TelegramParserSettings  # Настройки парсера Telegram
    database: DatabaseSettings  # Настройки базы данных
    
    model_config = ConfigDict(
        extra="allow",
        env_file='.env',  # Файл с переменными окружения
        env_file_encoding='utf-8',  # Кодировка файла
        env_nested_delimiter='__'  # Разделитель для вложенных настроек
    )
    
    @classmethod
    def create(cls) -> 'Settings':
        """
        Создает экземпляр настроек с заполненными полями из переменных окружения.
        Используется для обхода проблем с вложенными моделями в Pydantic.
        """
        # Загрузка переменных из .env файла
        try:
            from dotenv import load_dotenv
            load_dotenv()
            print("Загружены переменные из .env файла")
        except Exception as e:
            print(f"Ошибка при загрузке .env файла: {e}")
            # Продолжаем работу даже без .env файла
        
        try:
            # Берем API ID и HASH один раз
            api_id = int(os.getenv("API_ID", 0))
            api_hash = os.getenv("API_HASH", "")
            
            print(f"Загруженные настройки API: ID={api_id}, Hash={'настроен' if api_hash else 'не настроен'}")
            
            # Создаем настройки для ИИ сервиса
            ai_service = AIServiceSettings(
                gemini_key=os.getenv("GEMINI_KEY", ""),
                api_url=os.getenv("AI_API_URL", "")
            )
            
            # Настройки для бота Telegram
            telegram_bot = TelegramBotSettings(
                bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
                bot_token_main=os.getenv("TELEGRAM_BOT_TOKEN_MAIN")
            )
            
            # API настройки Telegram
            telegram_api = TelegramApiSettings(
                api_id=api_id,
                api_hash=api_hash
            )
            
            # Настройки парсера Telegram
            telegram_parser = TelegramParserSettings(
                phone_number=os.getenv("PHONE_NUMBER"),
                session=os.getenv("SESSION", ""),
                photo_storage=os.getenv("PHOTO_STORAGE", "database/photos")
            )
            
            # Настройки базы данных
            database = DatabaseSettings(
                connect_string=os.getenv("DB_CONNECT_STRING", "")
            )
            
            # Создаем объект настроек
            return cls(
                ai_service=ai_service,
                telegram_bot=telegram_bot,
                telegram_api=telegram_api,
                telegram_parser=telegram_parser,
                database=database
            )
        except Exception as e:
            print(f"Ошибка при создании настроек: {e}")
            raise


# Создание глобального экземпляра настроек
try:
    print("Инициализация настроек...")
    settings = Settings.create()
    print("Настройки успешно загружены")
except Exception as e:
    import logging
    logging.error(f"Ошибка инициализации настроек: {e}")
    print(f"Критическая ошибка при инициализации настроек: {e}")
    # Создаем минимальный объект для избежания ошибок импорта
    settings = Settings(
        ai_service=AIServiceSettings(gemini_key="", api_url=""),
        telegram_bot=TelegramBotSettings(bot_token=""),
        telegram_api=TelegramApiSettings(api_id=0, api_hash=""),
        telegram_parser=TelegramParserSettings(session="", photo_storage="database/photos"),
        database=DatabaseSettings(connect_string="")
    )
    print("Созданы минимальные настройки по умолчанию") 