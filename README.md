# 🤖 AutoPosting - AI-Powered Content Aggregation System

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com)
[![Aiogram](https://img.shields.io/badge/Aiogram-3.x-blue.svg)](https://aiogram.dev)
[![Google Gemini](https://img.shields.io/badge/Google-Gemini%20AI-orange.svg)](https://ai.google.dev)

## 📋 Оглавление
1. [Описание проекта](#-описание-проекта)
2. [Архитектура системы](#-архитектура-системы)  
3. [Основные компоненты](#-основные-компоненты)
4. [AI сервис с Gemini](#-ai-сервис-с-gemini)
5. [Установка и настройка](#-установка-и-настройка)
6. [Команды бота](#-команды-бота)
7. [Запуск системы](#-запуск-системы)
8. [Мониторинг](#-мониторинг)

---

## 🎯 Описание проекта

**AutoPosting** - это автоматизированная система для агрегации, фильтрации и публикации контента из Telegram-каналов с использованием искусственного интеллекта Google Gemini.

### ✨ Ключевые возможности

- 🔍 **Умная фильтрация** - AI удаляет рекламу, спам и низкокачественный контент
- 🚫 **Предотвращение дубликатов** - интеллектуальная система кеширования с автоочисткой
- 📝 **Обработка текста** - улучшение качества и переформулирование контента с разбивкой на абзацы
- 📢 **Автоматический рекламный блок** - встраивание ссылок на ваши каналы в каждое сообщение
- 🤖 **Управление через бота** - полный контроль системы через Telegram бота
- 📊 **Мониторинг в реальном времени** - статистика и логирование всех процессов
- ⚡ **Высокая производительность** - обработка батчей постов и асинхронная архитектура

### 🔄 Принцип работы

```
📱 Источники        🤖 AI Обработка        📢 Публикация
┌─────────────┐    ┌──────────────────┐    ┌─────────────┐
│ Telegram    │───▶│ Google Gemini    │───▶│ Целевые     │
│ каналы      │    │ • Фильтрация     │    │ каналы      │
│ (источники) │    │ • Дедупликация   │    │             │
└─────────────┘    │ • Переформулир.  │    └─────────────┘
                   └──────────────────┘
                            │
                   ┌──────────────────┐
                   │ Кеш + AutoClear  │
                   │ (24h cycle)      │
                   └──────────────────┘
```

---

## 🏗️ Архитектура системы

```
┌─────────────────────────────────────────────────────────────┐
│                     AutoPosting System                     │
├─────────────────────────────────────────────────────────────┤
│  🎮 Management Bot (Aiogram 3.x)                          │
│  ├── Command Handlers                                      │
│  ├── FSM States                                           │
│  └── Admin Interface                                       │
├─────────────────────────────────────────────────────────────┤
│  📥 Content Parser (Telethon)                             │
│  ├── Multi-account Support                                │
│  ├── Channel Monitoring                                   │
│  └── Message Collection                                    │
├─────────────────────────────────────────────────────────────┤
│  🤖 AI Service (FastAPI + Google Gemini)                  │
│  ├── Content Filtering                                    │
│  ├── Duplicate Detection                                  │
│  ├── Auto Cache Clear (24h)                              │
│  └── Batch Processing                                     │
├─────────────────────────────────────────────────────────────┤
│  📤 Posting Worker                                         │
│  ├── Content Publishing                                   │
│  ├── Error Handling                                       │
│  └── Status Tracking                                      │
├─────────────────────────────────────────────────────────────┤
│  🗄️ Database Layer (PostgreSQL)                           │
│  ├── Messages & Status                                    │
│  ├── Accounts & Channels                                  │
│  └── Configuration                                        │
└─────────────────────────────────────────────────────────────┘
```

---

## 🧩 Основные компоненты

### 1. **🤖 Management Bot** (`telegram/bot/`)
- **Aiogram 3.x** - современный фреймворк для Telegram ботов
- **FSM система** - управление состояниями диалогов
- **Административные команды** - полный контроль системы
- **Мониторинг и статистика** - отслеживание работы всех компонентов

### 2. **📥 Content Parser** (`telegram/parser/`)
- **Telethon** - парсинг через пользовательские аккаунты
- **Multi-account поддержка** - несколько аккаунтов для стабильности
- **Канал мониторинг** - отслеживание новых сообщений
- **Фильтрация источников** - настраиваемые правила парсинга

### 3. **🤖 AI Service** (`AIservice/`)
- **Google Gemini 1.5 Flash** - современная языковая модель
- **FastAPI** - высокопроизводительный REST API
- **Интеллектуальная фильтрация** - удаление спама и рекламы
- **Система кеширования** - предотвращение дубликатов
- **Автоочистка кеша** - каждые 24 часа

### 4. **📤 Posting Worker** (`telegram/bot/posting_worker.py`)
- **Асинхронная публикация** - обработка очереди сообщений
- **Error handling** - управление ошибками и повторными попытками
- **Batch processing** - групповая обработка постов
- **Status tracking** - отслеживание статусов публикации

### 5. **🗄️ Database Layer** (`database/`)
- **PostgreSQL** - надежная реляционная СУБД
- **SQLAlchemy ORM** - современная работа с БД
- **Модели данных** - структурированное хранение
- **Миграции** - управление схемой БД

---

## 🤖 AI сервис с Gemini

### 🚀 Основные возможности

- **🔍 Умная фильтрация контента**
  - Удаление рекламы и промо-материалов
  - Фильтрация спама и низкокачественного контента
  - Очистка от эмоциональных реакций без информации

- **🚫 Интеллектуальная дедупликация**
  - MD5 хеширование нормализованного контента
  - Глобальный кеш между сессиями
  - Сессионная фильтрация в рамках запроса

- **⏰ Автоматическое управление кешем**
  - Автоочистка каждые 24 часа
  - Предотвращение переполнения памяти
  - Актуальность фильтрации (старые новости не блокируют новые)

### 🌐 API Эндпоинты

```bash
# Основная фильтрация постов
POST /gemini/filter
{
  "posts": ["Текст поста 1", "Текст поста 2"],
  "has_image": false
}

# Статистика кеша
GET /gemini/cache_stats

# Ручная очистка кеша
POST /gemini/clear_cache

# Принудительная автоочистка
POST /gemini/force_auto_clear

# Health check
GET /health
```

### 📊 Мониторинг AI сервиса

```bash
# Запуск AI сервиса
uvicorn AIservice.gemini:app --host 0.0.0.0 --port 8000 --reload

# Проверка состояния
curl http://localhost:8000/health

# Статистика кеша
curl http://localhost:8000/gemini/cache_stats
```

---

## 🔧 Установка и настройка

### 1. **Клонирование репозитория**
```bash
git clone <repository-url>
cd autoposting
```

### 2. **Создание виртуального окружения**
```bash
python -m venv venv
source venv/bin/activate  # Linux/macOS
# или
venv\Scripts\activate     # Windows
```

### 3. **Установка зависимостей**
```bash
pip install -r requirements.txt
```

### 4. **Настройка переменных окружения**
Создайте файл `.env` в корне проекта:

```env
# Telegram API (получить на https://my.telegram.org)
TELEGRAM_API_ID=your_api_id
TELEGRAM_API_HASH=your_api_hash

# Telegram Bot Token (получить у @BotFather)
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_BOT_TOKEN_MAIN=your_main_bot_token

# Google Gemini API (получить на https://ai.google.dev)
GEMINI_API_KEY=your_gemini_api_key

# AI Service URL
AI_SERVICE_URL=http://localhost:8000/gemini/filter

# Database (PostgreSQL)
DATABASE_URL=postgresql://user:password@localhost:5432/autoposting

# Phone number для парсера
PHONE_NUMBER=+1234567890
```

### 5. **📢 Настройка рекламного блока**

Система поддерживает автоматическое добавление рекламного блока к каждому сообщению. Добавьте следующие переменные в `.env`:
По нужде, можно просто убрать, поля оставить пустыми.

```env
# Рекламный блок (опционально)
PROMO_ENABLED=true                                    # Включить/выключить блок
PROMO_TITLE=———Подписаться———                        # Заголовок блока
PROMO_CRYPTO_TEXT=Крипто.                           # Текст для крипто-канала
PROMO_CRYPTO_URL=https://t.me/+OWWu9brDBI41Yjgy     # URL крипто-канала
PROMO_FOREX_TEXT=Форекс.                            # Текст для форекс-канала
PROMO_FOREX_URL=https://t.me/+cjGt046qe_1kMzFi      # URL форекс-канала
PROMO_NEWS_TEXT=Новости.                            # Текст для новостного канала
PROMO_NEWS_URL=https://t.me/+T2sxJEJj2343Y2Ji       # URL новостного канала
```

**Пример результата:**
```
Основной контент поста...

———Подписаться———

Крипто.

Форекс.

Новости.
```

> **Примечание:** Слова "Крипто.", "Форекс." и "Новости." будут кликабельными ссылками (URL не видны)
> 
> 📖 **Подробная документация:** [docs/PROMOTIONAL_BLOCK.md](docs/PROMOTIONAL_BLOCK.md)

### 6. **Настройка базы данных**
```bash
# Создание БД и таблиц
python -c "from database.models import engine, Base; Base.metadata.create_all(engine)"
```

---

## 🎮 Команды бота

### 📱 **Управление аккаунтами Telegram**
- `/add_account` - добавить новый аккаунт Telegram
- `/view_accounts` - просмотреть список доступных аккаунтов
- `/activate_account ID` - активировать аккаунт
- `/deactivate_account ID` - деактивировать аккаунт
- `/delete_account ID` - удалить аккаунт

### 📋 **Управление источниками парсинга**
- `/add_source` - добавить новый источник для парсинга
- `/view_all_sources` - просмотреть все источники парсинга
- `/update_source ID` - обновить существующий источник
- `/copy_source` - копировать источник в другой целевой канал
- `/delete_source ID` - удалить источник парсинга

### 🎯 **Управление целевыми каналами**
- `/add_target` - добавить новый целевой канал
- `/all_targets` (или `/t`) - просмотреть список всех целевых каналов
- `/targets_with_sources` (или `/ts`) - просмотреть целевые каналы с их источниками
- `/activate_target ID` - активировать целевой канал
- `/toggle_target ID` - переключить статус целевого канала
- `/deactivate_target ID` - деактивировать целевой канал
- `/update_target ID` - обновить информацию о целевом канале
- `/delete_target ID` - удалить целевой канал

### 🤖 **Управление AI сервисом**
- `/ai_cache_stats` - статистика кеша AI сервиса
- `/clear_ai_cache` - очистить кеш дубликатов AI вручную
- `/force_auto_clear` - принудительная автоочистка кеша

### 🛠️ **Управление сообщениями с ошибками**
- `/errors` - просмотр и управление сообщениями с ошибками
  - `list` - показать список сообщений с ошибками
  - `retry all` - повторить обработку всех сообщений с ошибками
  - `retry ID` - повторить обработку конкретного сообщения
  - `skip ID` - пометить сообщение как окончательно ошибочное

### ⚙️ **Сервисные команды**
- `/help`, `/commands` - показать список всех команд
- `/add_bot_to_channel` - инструкции по добавлению бота в канал
- `/check_channel` - проверить доступность канала
- `/cancel` - отменить текущую операцию

---

## 🚀 Запуск системы

### **Полный запуск (рекомендуется)**
```bash
# Основное приложение (включает все компоненты)
python main.py
```

### **Отдельные компоненты**

#### 1. **AI Service**
```bash
# Development режим
uvicorn AIservice.gemini:app --host 0.0.0.0 --port 8000 --reload

# Production режим
uvicorn AIservice.gemini:app --host 0.0.0.0 --port 8000 --workers 4
```

#### 2. **Parser Service**
```bash
python -m telegram.parser.parser_service
```

#### 3. **Posting Worker**
```bash
python -m telegram.bot.posting_worker
```

#### 4. **Management Bot**
```bash
python -m telegram.bot.main
```

---

## 📊 Мониторинг

### **Статистика AI сервиса**
```bash
# Через curl
curl http://localhost:8000/gemini/cache_stats

# Через бота
/ai_cache_stats
```

**Пример ответа:**
```json
{
  "cache_size": 1250,
  "last_auto_clear": "2024-01-15 14:30:00",
  "hours_since_clear": 12.5,
  "hours_until_next_clear": 11.5,
  "next_auto_clear": "2024-01-16 14:30:00"
}
```

### **Логирование**
Все компоненты системы ведут подробные логи:

```bash
# Основные логи
tail -f bot_log.txt

# Логи парсера
tail -f parser_debug.log

# Логи AI сервиса
# Выводятся в консоль при запуске uvicorn
```

### **Health Checks**
```bash
# AI Service
curl http://localhost:8000/health

# Проверка каналов через бота
/check_channel
```

---

## 🔍 Troubleshooting

### **Частые проблемы**

#### 1. **AI сервис не отвечает**
```bash
# Проверка статуса
curl http://localhost:8000/health

# Перезапуск
uvicorn AIservice.gemini:app --host 0.0.0.0 --port 8000 --reload
```

#### 2. **Проблемы с Telegram аккаунтами**
```bash
# Удаление сессии
rm temp_session_*.session

# Повторное добавление аккаунта
/add_account
```

#### 3. **Ошибки публикации**
```bash
# Управление ошибочными сообщениями
/errors

# Проверка прав бота в канале
/check_channel
```

#### 4. **Кеш AI не очищается**
```bash
# Принудительная очистка
curl -X POST http://localhost:8000/gemini/force_auto_clear

# Через бота
/force_auto_clear
```

---

## 📈 Производительность

### **Оптимизация**
- **Batch processing** - обработка нескольких постов за раз
- **Асинхронность** - все операции неблокирующие
- **Кеширование** - избежание повторной обработки
- **Connection pooling** - эффективное использование соединений

### **Масштабирование**
- **Горизонтальное масштабирование** AI сервиса с uvicorn workers
- **Множественные аккаунты** для парсинга
- **Database pooling** для высоких нагрузок

---

## 📝 Заключение

**AutoPosting** - это комплексная система для автоматизации контент-агрегации с использованием современных технологий AI. Система обеспечивает:

- 🎯 **Высокое качество контента** благодаря Gemini AI
- 🚀 **Автономность работы** с автоматическим управлением
- 📊 **Полную прозрачность** процессов через мониторинг
- 🛡️ **Надежность** с системой обработки ошибок
- ⚡ **Производительность** с асинхронной архитектурой

### 🔗 **Полезные ссылки**
- [Google Gemini AI](https://ai.google.dev)
- [Telegram Bot API](https://core.telegram.org/bots/api)
- [FastAPI Documentation](https://fastapi.tiangolo.com)
- [Aiogram Framework](https://aiogram.dev)

**💡 Кеш AI автоматически очищается каждые 24 часа для поддержания актуальности и производительности системы!** 