#!/bin/bash

# AUTOPOSTING BOT - РАЗВЕРТЫВАНИЕ
set -e

echo "🚀 Запуск Autoposting Bot..."

# Проверка Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker не установлен!"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose не установлен!"
    exit 1
fi

cd "$(dirname "$0")"

# Создание .env из шаблона
if [ ! -f .env ]; then
    echo "📝 Создание .env файла..."
    cp env.example .env
    echo "⚠️  Отредактируйте файл .env с вашими настройками!"
    echo "   Файл: $(pwd)/.env"
    read -p "Нажмите Enter когда заполните .env..."
fi

# Проверка session файла
if [ ! -f ../temp_session_380956341569.session ]; then
    echo "⚠️  Session файл не найден - парсер потребует авторизации"
fi

echo "🔧 Остановка старых контейнеров..."
docker-compose down

echo "🏗️  Сборка образов..."
docker-compose build --no-cache

echo "🚀 Запуск сервисов..."
docker-compose up -d

echo "⏳ Ожидание запуска..."
sleep 10

echo "📊 Статус:"
docker-compose ps

echo ""
echo "✅ Готово!"
echo ""
echo "🌐 Сервисы:"
echo "   - AI сервис: http://localhost:8000"
echo "   - База данных: localhost:3306"
echo "   - Бот: работает в Telegram"
echo ""
echo "📋 Команды:"
echo "   docker-compose logs -f     # Логи"
echo "   docker-compose restart     # Перезапуск"
echo "   docker-compose down        # Остановка" 