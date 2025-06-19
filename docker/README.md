# 🐳 Autoposting Bot - Docker

## 🚀 Быстрый запуск

### 1. Скопируйте проект на сервер
```bash
git clone # вставьте ссылку на репо
```

### 2. Настройте переменные
```bash
cp env.example .env
nano .env  # Заполните ваши ключи!
```

### 3. Запустите
```bash
# выдать права
chmod +x ./deploy.sh
# запустить
./deploy.sh
```

## 📝 Что настроить в .env

**Обязательно:**
- `GEMINI_KEY` - ключ Google Gemini
- `API_ID` и `API_HASH` - с https://my.telegram.org  
- `TELEGRAM_BOT_TOKEN` - от @BotFather
- `PHONE_NUMBER` - номер для парсера

**Остальное по желанию:**
- `ADMIN_PASSWORD` - пароль админки
- `ALLOWED_ADMINS` - ваш Telegram ID
- `PROMO_*` - настройки рекламы

## 🔧 Управление

```bash
# Логи
docker-compose logs -f

# Перезапуск
docker-compose restart

# Остановка  
docker-compose down

# запуск
docker-compose up -d
```

## 📊 Что запускается

- **MySQL** - база данных (порт 3306)
- **AI сервис** - обработка контента (порт 8000) 
- **Основное приложение** - бот + парсер + постинг

## ✅ Готово!

После запуска бот будет работать через Telegram.