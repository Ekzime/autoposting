# 🚀 AI Service - Quick Start

## Быстрый запуск

### 1. Установка зависимостей
```bash
pip install fastapi uvicorn google-generativeai httpx
```

### 2. Настройка переменных окружения
```bash
export GEMINI_API_KEY="your_gemini_api_key_here"
```

### 3. Запуск сервиса
```bash
# Development режим
uvicorn AIservice.gemini:app --host 0.0.0.0 --port 8000 --reload

# Production режим  
uvicorn AIservice.gemini:app --host 0.0.0.0 --port 8000 --workers 4
```

### 4. Проверка работы
```bash
# Health check
curl http://localhost:8000/health

# Тестовый запрос
curl -X POST http://localhost:8000/gemini/filter \
  -H "Content-Type: application/json" \
  -d '{"posts": ["Тестовый пост"], "has_image": false}'
```

## Основные команды

### API эндпоинты
- `POST /gemini/filter` - фильтрация постов
- `GET /gemini/cache_stats` - статистика кеша
- `POST /gemini/clear_cache` - очистка кеша
- `POST /gemini/force_auto_clear` - принудительная автоочистка
- `GET /health` - проверка состояния

### Команды бота
- `/ai_cache_stats` - статистика кеша
- `/clear_ai_cache` - ручная очистка
- `/force_auto_clear` - принудительная автоочистка

## Ключевые особенности

✅ **Автоматическая очистка кеша каждые 24 часа**
✅ **Интеллектуальная фильтрация дубликатов** 
✅ **Обработка батчей постов**
✅ **Подробная статистика и мониторинг**
✅ **RESTful API с CORS поддержкой**

## Пример использования

```python
import httpx

async def process_posts(posts):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/gemini/filter",
            json={"posts": posts, "has_image": False}
        )
        return response.json()

# Использование
result = await process_posts(["Bitcoin достиг $100k", "Новости о Ethereum"])
```

📖 **Полная документация:** [AI_SERVICE_DOCUMENTATION.md](AI_SERVICE_DOCUMENTATION.md) 