from typing import Optional
from pydantic import BaseModel, Field, validator
from pydantic_settings import BaseSettings


class AIServiceSettings(BaseModel):
    """Настройки сервиса искусственного интеллекта"""
    gemini_key: str  # Ключ API для Gemini
    api_url: str = Field(..., description="URL API искусственного интеллекта для фильтрации")


class TelegramBotSettings(BaseModel):
    """Настройки бота Telegram"""
    bot_token: str  # Токен бота Telegram
    bot_token_main: Optional[str] = None  # Опциональный основной токен бота


class TelegramParserSettings(BaseModel):
    """Настройки парсера Telegram"""
    phone_number: Optional[str] = None  # Номер телефона для авторизации в Telegram API
    api_id: int  # ID приложения Telegram API
    api_hash: str  # Хеш приложения Telegram API
    session: str  # Имя файла сессии Telegram
    photo_storage: str  # Путь для хранения фотографий


class DatabaseSettings(BaseModel):
    """Настройки базы данных"""
    connect_string: str  # Строка подключения к базе данных


class Settings(BaseSettings):
    """Основные настройки приложения, загружаемые из переменных окружения"""
    ai_service: AIServiceSettings  # Настройки сервиса ИИ
    telegram_bot: TelegramBotSettings  # Настройки бота Telegram
    telegram_parser: TelegramParserSettings  # Настройки парсера Telegram
    database: DatabaseSettings  # Настройки базы данных
    
    class Config:
        """Конфигурация для загрузки настроек"""
        env_file = '.env'  # Файл с переменными окружения
        env_file_encoding = 'utf-8'  # Кодировка файла
        env_nested_delimiter = '__'  # Разделитель для вложенных настроек
        
    @classmethod
    def from_env(cls):
        """Создание настроек из переменных окружения"""
        return cls(
            ai_service=AIServiceSettings(
                gemini_key=cls._get_env("GEMINI_KEY"),
                api_url=cls._get_env("AI_API_URL")
            ),
            telegram_bot=TelegramBotSettings(
                bot_token=cls._get_env("TELEGRAM_BOT_TOKEN"),
                bot_token_main=cls._get_env("TELEGRAM_BOT_TOKEN_MAIN", None)
            ),
            telegram_parser=TelegramParserSettings(
                phone_number=cls._get_env("PHONE_NUMBER", None),
                api_id=int(cls._get_env("API_ID")),
                api_hash=cls._get_env("API_HASH"),
                session=cls._get_env("SESSION"),
                photo_storage=cls._get_env("PHOTO_STORAGE")
            ),
            database=DatabaseSettings(
                connect_string=cls._get_env("DB_CONNECT_STRING")
            )
        )
    
    @staticmethod
    def _get_env(key, default=...):
        """Вспомогательный метод для получения переменных окружения с обработкой ошибок"""
        import os
        value = os.environ.get(key, default)
        if value is ...:
            raise ValueError(f"Переменная окружения {key} не установлена")
        return value


# Создание глобального экземпляра настроек
settings = Settings.from_env() 