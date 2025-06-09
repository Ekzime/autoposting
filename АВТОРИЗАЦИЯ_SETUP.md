# 🔐 Настройка системы авторизации для Telegram Bot

## Обзор

Реализована система авторизации администраторов с использованием JWT-токенов и сессий в базе данных.

## 🚀 Быстрая настройка

### 1. Обновите файл `.env`

В вашем существующем файле `.env` добавьте следующие переменные для авторизации:

```env
# ==============================================
# НАСТРОЙКИ АВТОРИЗАЦИИ
# ==============================================

# Пароль для входа администраторов
TELEGRAM_BOT__ADMIN_PASSWORD=your_secure_password_here

# Длительность сессии в часах
TELEGRAM_BOT__SESSION_DURATION_HOURS=12

# Секретный ключ для JWT (уже есть в вашем .env)
TELEGRAM_BOT__JWT_SECRET=fTmTUkHINr4XJYu8AowQct6EwuktYQQRleXR0wYDiig

# Список разрешенных админов (Telegram ID через запятую)
# В данный момент: 778354651
TELEGRAM_BOT__ALLOWED_ADMINS=778354651

# ==============================================
# ОСТАЛЬНЫЕ НАСТРОЙКИ
# ==============================================

# Токены ботов
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_BOT_TOKEN_MAIN=your_main_bot_token_here

# Telegram API
API_ID=your_api_id
API_HASH=your_api_hash

# База данных
DB_CONNECT_STRING=your_database_connection_string
```

**ВАЖНО**: Переменные должны иметь префикс `TELEGRAM_BOT__` (с двойным подчеркиванием)!

### 2. Настройте пароль администратора

В `.env` файле замените:
```env
TELEGRAM_BOT__ADMIN_PASSWORD=your_secure_password_here
```

На надежный пароль, например:
```env
TELEGRAM_BOT__ADMIN_PASSWORD=MySecurePassword123!
```

### 3. Проверьте ваш Telegram ID

Ваш текущий ID в настройках: `778354651`

Если хотите добавить других администраторов:
1. Узнайте их ID через [@userinfobot](https://t.me/userinfobot)
2. Добавьте через запятую: `TELEGRAM_BOT__ALLOWED_ADMINS=778354651,123456789`

## 📋 Доступные команды

### Для авторизации:
- `/login` - Вход в систему (запросит пароль)
- `/logout` - Выход из системы
- `/session_status` - Проверка статуса текущей сессии

### Общие команды:
- `/help` - Справка по командам
- `/start` - Приветствие

## 🔒 Как работает авторизация

1. **Проверка доступа**: Бот проверяет, есть ли ваш Telegram ID в списке `TELEGRAM_BOT__ALLOWED_ADMINS`
2. **Аутентификация**: При вводе `/login` запрашивается пароль
3. **Создание сессии**: После успешной аутентификации создается JWT-токен и запись в БД
4. **Middleware**: Все команды (кроме публичных) проверяются через AuthMiddleware
5. **Автообновление**: При каждом действии обновляется время последней активности

## ⚙️ Технические детали

### Структура файлов:
- `telegram/bot/auth/auth_service.py` - Основная логика авторизации
- `telegram/bot/middleware/auth_middleware.py` - Middleware для проверки доступа
- `telegram/bot/handlers/auth_handlers.py` - Обработчики команд авторизации
- `database/models.py` - Модель AdminSession для хранения сессий

### Публичные команды (доступны без авторизации):
- `/start`
- `/login` 
- `/help`

### Безопасность:
- Пароли не логируются
- Сообщения с паролями автоматически удаляются
- JWT токены имеют ограниченный срок действия
- Автоматическая очистка истекших сессий

## 🔧 Устранение неполадок

### Ошибка: "Bot token not found"
- Проверьте, что `TELEGRAM_BOT_TOKEN` указан в `.env`

### Ошибка: "Database connection"
- Убедитесь, что `DB_CONNECT_STRING` корректен
- Проверьте, что база данных запущена

### Ошибка: "Доступ запрещен"
- Проверьте, что ваш Telegram ID `778354651` добавлен в `TELEGRAM_BOT__ALLOWED_ADMINS`
- Убедитесь, что переменная имеет префикс `TELEGRAM_BOT__`

### Ошибка: "Сессия неактивна"
- Выполните `/login` для повторной авторизации
- Проверьте `TELEGRAM_BOT__SESSION_DURATION_HOURS` в настройках

## 📝 Изменения в коде

### main.py:
```python
# Добавлены импорты
from telegram.bot.middleware.auth_middleware import AuthMiddleware
from telegram.bot.handlers.auth_handlers import router as auth_router

# В функции main():
# Подключение middleware
dp.middleware.setup(AuthMiddleware())

# Регистрация auth_router ПЕРВЫМ
dp.include_router(auth_router)
```

### Новые файлы:
- ✅ `telegram/bot/auth/__init__.py`
- ✅ `telegram/bot/auth/auth_service.py`
- ✅ `telegram/bot/middleware/__init__.py`
- ✅ `telegram/bot/middleware/auth_middleware.py`
- ✅ `telegram/bot/handlers/auth_handlers.py`

### Обновлены:
- ✅ `requirements.txt` (добавлен PyJWT==2.9.0)
- ✅ `database/models.py` (модель AdminSession уже существовала)
- ✅ `config/settings.py` (настройки авторизации с правильными префиксами)

## 🚀 Запуск

После настройки переменных в `.env` запустите:

```bash
python main.py
```

Бот автоматически подключит систему авторизации!

## 🔄 Следующие шаги

1. ✅ Установите надежный пароль в `TELEGRAM_BOT__ADMIN_PASSWORD`
2. ✅ Ваш ID `778354651` уже настроен в `TELEGRAM_BOT__ALLOWED_ADMINS`
3. ✅ JWT секрет уже настроен
4. 🚀 Запустите бота и протестируйте авторизацию командой `/login`

## 📤 Пример правильного .env

```env
# Ваши существующие настройки...
TELEGRAM_BOT_TOKEN=7809653490:AAEkMjJnSCdzePbFVvm0qX8APJ86JJsOauU

# Добавьте эти строки для авторизации:
TELEGRAM_BOT__ADMIN_PASSWORD=MySecurePassword123!
TELEGRAM_BOT__SESSION_DURATION_HOURS=12
TELEGRAM_BOT__JWT_SECRET=fTmTUkHINr4XJYu8AowQct6EwuktYQQRleXR0wYDiig
TELEGRAM_BOT__ALLOWED_ADMINS=778354651
``` 