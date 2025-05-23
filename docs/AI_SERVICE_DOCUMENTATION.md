# 🤖 AI Service Documentation

## Оглавление
1. [Общее описание](#общее-описание)
2. [Архитектура системы](#архитектура-системы)
3. [API Эндпоинты](#api-эндпоинты)
4. [Система кеширования](#система-кеширования)
5. [Автоматическая очистка кеша](#автоматическая-очистка-кеша)
6. [Настройка и конфигурация](#настройка-и-конфигурация)
7. [Использование через бота](#использование-через-бота)
8. [Примеры использования](#примеры-использования)
9. [Мониторинг и отладка](#мониторинг-и-отладка)
10. [Troubleshooting](#troubleshooting)

---

## Общее описание

AI Service - это микросервис на базе **Google Gemini API** и **FastAPI**, предназначенный для:

- 🔍 **Фильтрации постов** - удаление рекламы, спама и низкокачественного контента
- 🚫 **Предотвращения дубликатов** - система кеширования для избежания повторяющегося контента
- ✨ **Улучшения качества** - обработка и очистка текста постов
- 🔄 **Автоматического управления** - автоочистка кеша каждые 24 часа

### Ключевые возможности
- Обработка одиночных постов и батчей
- Интеллектуальная фильтрация дубликатов
- Поддержка изображений
- RESTful API с подробной статистикой
- Автономное управление кешем

---

## Архитектура системы

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Telegram Bot  │───▶│   AI Service    │───▶│  Google Gemini  │
│                 │    │   (FastAPI)     │    │      API        │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │
         │              ┌─────────────────┐
         └─────────────▶│ Cache System    │
                        │ (In-Memory)     │
                        └─────────────────┘
```

### Компоненты

#### 1. **FastAPI Application** (`AIservice/gemini.py`)
- Основное приложение с REST API
- CORS middleware для кросс-доменных запросов
- Валидация данных через Pydantic

#### 2. **Google Gemini Integration**
- Модель: `gemini-1.5-flash`
- Обработка текста через prompt engineering
- Парсинг ответов в JSON формате

#### 3. **Cache System**
- In-memory кеш для отслеживания обработанных постов
- MD5 хеширование нормализованного контента
- Автоматическая очистка каждые 24 часа

#### 4. **Prompt System** (`AIservice/prompts.py`)
- Специализированные промпты для фильтрации
- Инструкции по предотвращению дубликатов
- Правила обработки различных типов контента

---

## API Эндпоинты

### 1. **POST** `/gemini/filter`
Основной эндпоинт для фильтрации постов.

**Request Body:**
```json
{
  "posts": ["Текст поста 1", "Текст поста 2"],
  "has_image": false
}
```

**Response:**
```json
{
  "status": "success",
  "result": [
    {"text": "Обработанный текст поста 1"},
    {"text": "Обработанный текст поста 2"}
  ]
}
```

**Параметры:**
- `posts` (array[string], required) - Массив текстов постов для обработки
- `has_image` (boolean, optional) - Указывает, есть ли изображения в постах

### 2. **POST** `/gemini/clear_cache`
Ручная очистка кеша дубликатов.

**Response:**
```json
{
  "status": "success",
  "message": "Кеш очищен вручную. Удалено 150 записей."
}
```

### 3. **GET** `/gemini/cache_stats`
Получение статистики кеша.

**Response:**
```json
{
  "status": "success",
  "cache_size": 1250,
  "recent_hashes": ["abc123...", "def456..."],
  "last_auto_clear": "2024-01-15 14:30:00",
  "hours_since_clear": 12.5,
  "hours_until_next_clear": 11.5,
  "next_auto_clear": "2024-01-16 14:30:00"
}
```

### 4. **POST** `/gemini/force_auto_clear`
Принудительный запуск автоочистки кеша.

**Response:**
```json
{
  "status": "success",
  "message": "Автоочистка кеша выполнена принудительно"
}
```

---

## Система кеширования

### Принцип работы

1. **Генерация хеша** - каждый пост нормализуется и хешируется:
   ```python
   # Убираем пунктуацию, приводим к нижнему регистру
   normalized = re.sub(r'[^\w\s]', '', text.lower())
   hash = hashlib.md5(normalized.encode()).hexdigest()
   ```

2. **Проверка дубликатов** - новые посты сравниваются с кешем:
   - Глобальные дубликаты (между сессиями)
   - Сессионные дубликаты (в рамках одного запроса)

3. **Фильтрация результатов** - AI результаты также проверяются на дубликаты

### Структура кеша

```python
# Глобальные переменные
processed_content_hashes = set()  # Множество хешей обработанных постов
last_cache_clear = datetime.now()  # Время последней очистки
```

### Примеры дубликатов

**Обнаруживаются как дубликаты:**
- "Bitcoin достиг $100k" → "bitcoin достиг 100k"
- "🚀 BTC новый максимум!!!" → "btc новый максимум"
- "Биткоин - $100,000" → "биткоин 100000"

---

## Автоматическая очистка кеша

### Логика автоочистки

```python
def check_and_auto_clear_cache():
    current_time = datetime.now()
    hours_passed = (current_time - last_cache_clear).total_seconds() / 3600
    
    if hours_passed >= 24:
        cache_size_before = len(processed_content_hashes)
        processed_content_hashes.clear()
        last_cache_clear = current_time
        return True
    return False
```

### Когда происходит проверка
- При каждом вызове `process_posts()`
- При каждом вызове `filter_duplicate_results()`
- При запросе статистики кеша
- При принудительной очистке

### Преимущества автоочистки
- ✅ Предотвращает переполнение памяти
- ✅ Старые новости не блокируют новые события
- ✅ Автономность работы
- ✅ Актуальность фильтрации

---

## Настройка и конфигурация

### 1. Переменные окружения
```bash
# Google Gemini API
GEMINI_API_KEY=your_gemini_api_key_here

# AI Service URL
AI_SERVICE_URL=http://localhost:8000/gemini/filter
```

### 2. Конфигурация в `config/settings.py`
```python
class AIServiceSettings(BaseModel):
    gemini_key: str
    api_url: str = "http://localhost:8000/gemini/filter"
```

### 3. Запуск сервиса
```bash
# Установка зависимостей
pip install fastapi uvicorn google-generativeai

# Запуск в development режиме
uvicorn AIservice.gemini:app --host 0.0.0.0 --port 8000 --reload

# Запуск в production режиме
uvicorn AIservice.gemini:app --host 0.0.0.0 --port 8000 --workers 4
```

### 4. Docker конфигурация
```dockerfile
FROM python:3.10-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY AIservice/ ./AIservice/
COPY config/ ./config/

EXPOSE 8000
CMD ["uvicorn", "AIservice.gemini:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## Использование через бота

### Команды бота

#### `/ai_cache_stats` - Статистика кеша
```
📊 Статистика кеша AI сервиса

🗃️ Размер кеша: 1250 записей
📝 Это количество уникальных постов, которые уже были обработаны

⏰ Автоматическая очистка:
• Последняя очистка: 2024-01-15 14:30:00
• Прошло часов: 12.5
• До следующей очистки: 11.5 ч.
• Следующая очистка: 2024-01-16 14:30:00
```

#### `/clear_ai_cache` - Ручная очистка
```
✅ Кеш очищен вручную. Удалено 1250 записей.
```

#### `/force_auto_clear` - Принудительная автоочистка
```
✅ Автоочистка кеша выполнена принудительно
```

### Интеграция в `posting_worker.py`

```python
async def process_with_ai(posts, has_image=False):
    ai_service_url = settings.ai_service.api_url
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        payload = {
            "posts": posts,
            "has_image": has_image
        }
        
        response = await client.post(ai_service_url, json=payload)
        
        if response.status_code == 200:
            result = response.json()
            return result.get('result', [])
        else:
            logger.error(f"AI service error: {response.status_code}")
            return []
```

---

## Примеры использования

### 1. Обработка одного поста

**Request:**
```bash
curl -X POST http://localhost:8000/gemini/filter \
  -H "Content-Type: application/json" \
  -d '{
    "posts": ["🚀 Bitcoin достиг исторического максимума в $100,000! 📈"],
    "has_image": false
  }'
```

**Response:**
```json
{
  "status": "success",
  "result": [
    {
      "text": "Bitcoin достиг исторического максимума в $100,000, установив новый рекорд на криптовалютном рынке."
    }
  ]
}
```

### 2. Batch обработка с дубликатами

**Request:**
```json
{
  "posts": [
    "Bitcoin достиг $100k",
    "Биткоин установил рекорд на отметке $100,000",
    "Ethereum запустил новое обновление",
    "📈 BTC = $100000 🚀🚀🚀"
  ],
  "has_image": false
}
```

**Response:**
```json
{
  "status": "success",
  "result": [
    {
      "text": "Bitcoin достиг исторического максимума в $100,000"
    },
    {
      "text": "Ethereum успешно запустил новое обновление протокола"
    }
  ]
}
```

### 3. Проверка статистики кеша

**Request:**
```bash
curl -X GET http://localhost:8000/gemini/cache_stats
```

### 4. Очистка кеша

**Request:**
```bash
curl -X POST http://localhost:8000/gemini/clear_cache
```

---

## Мониторинг и отладка

### Логирование

AI сервис выводит подробные логи:

```
🔄 Входной пост уже обработан ранее: Bitcoin достиг нового максимума...
✅ Добавлен уникальный контент: Ethereum запустил новое обновление...
❌ Дубликат отфильтрован: Биткоин установил рекорд...
📊 Результат: 4 -> 2 (после фильтрации дубликатов)
🔄 Автоматическая очистка кеша: удалено 1250 записей
⏰ Следующая очистка через 24 часа: 2024-01-16 14:30:00
```

### Мониторинг производительности

```python
# Отслеживание времени обработки
import time

start_time = time.time()
result = process_posts(posts)
processing_time = time.time() - start_time
print(f"⏱️ Время обработки: {processing_time:.2f} секунд")
```

### Health Check эндпоинт

```python
@app.get('/health')
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "cache_size": len(processed_content_hashes),
        "gemini_model": "gemini-1.5-flash"
    }
```

---

## Troubleshooting

### Частые проблемы и решения

#### 1. **AI сервис не отвечает**

**Проблема:** `Connection refused` или timeout
**Решения:**
- Проверить, запущен ли сервис: `curl http://localhost:8000/health`
- Проверить logs сервиса
- Перезапустить сервис

#### 2. **Gemini API ошибки**

**Проблема:** `❌ Gemini Error: 403 Forbidden`
**Решения:**
- Проверить API ключ в переменных окружения
- Проверить квоты Gemini API
- Проверить формат запросов

#### 3. **Кеш не очищается автоматически**

**Проблема:** Кеш растет бесконечно
**Решения:**
- Проверить логи автоочистки
- Запустить принудительную очистку: `/force_auto_clear`
- Проверить системное время

#### 4. **Дубликаты не фильтруются**

**Проблема:** Одинаковые посты проходят фильтрацию
**Решения:**
- Проверить функцию нормализации текста
- Очистить кеш и протестировать заново
- Проверить логи обработки

#### 5. **Медленная обработка**

**Проблема:** Запросы выполняются долго
**Решения:**
- Уменьшить размер батчей
- Увеличить timeout в клиенте
- Мониторить нагрузку на Gemini API

### Диагностические команды

```bash
# Проверка статуса сервиса
curl -X GET http://localhost:8000/health

# Проверка статистики кеша
curl -X GET http://localhost:8000/gemini/cache_stats

# Тестовый запрос
curl -X POST http://localhost:8000/gemini/filter \
  -H "Content-Type: application/json" \
  -d '{"posts": ["Test post"], "has_image": false}'

# Очистка кеша для отладки
curl -X POST http://localhost:8000/gemini/clear_cache
```

### Настройка логирования

```python
import logging

# Настройка подробного логирования
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('ai_service.log'),
        logging.StreamHandler()
    ]
)
```

---

## Заключение

AI Service обеспечивает надежную и эффективную обработку постов с автоматическим управлением дубликатами. Система спроектирована для автономной работы с минимальным вмешательством администратора.

### Ключевые особенности:
- 🤖 **Умная фильтрация** через Gemini AI
- 🔄 **Автоматическое управление кешем**
- 📊 **Подробная статистика и мониторинг**
- 🛡️ **Надежная система предотвращения дубликатов**
- ⚡ **Высокая производительность** с поддержкой батчей

Для дополнительной информации или вопросов, обратитесь к логам сервиса или используйте встроенные команды мониторинга. 