###############################
#           system libs
#------------------------------
import re
import json
import hashlib
from typing import List, Optional, Dict, Any, Union
###############################
#           my moduls
#------------------------------
from .prompts import prompt
from config import settings
###############################
#            FAST API
#------------------------------
from fastapi import FastAPI, APIRouter
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
###############################
#       other libs/frameworks
#------------------------------
import google.generativeai as genai

# Configure Gemini API
genai.configure(api_key=settings.ai_service.gemini_key)
model = genai.GenerativeModel("gemini-1.5-flash")

# Глобальный кеш для отслеживания уже обработанных постов
processed_content_hashes = set()

# Модель для валидации входных данных
class PostBatch(BaseModel):
    posts: List[str]
    has_image: Optional[bool] = False

# Инициализация FastAPI приложения
app = FastAPI()
# Настройка CORS для разрешения кросс-доменных запросов
app.add_middleware(
    CORSMiddleware,
    allow_origins=    ["*"],  # Разрешаем запросы с любых доменов
    allow_methods=    ["*"],  # Разрешаем все HTTP методы
    allow_headers=    ["*"],  # Разрешаем все заголовки
    allow_credentials=True,   # Разрешаем передачу учетных данных
)


def generate_content_hash(text: str) -> str:
    """Генерирует хеш для текста, игнорируя пунктуацию и регистр"""
    # Приводим к нижнему регистру и удаляем лишние символы
    normalized = re.sub(r'[^\w\s]', '', text.lower())
    # Удаляем лишние пробелы
    normalized = ' '.join(normalized.split())
    return hashlib.md5(normalized.encode()).hexdigest()


def check_content_similarity(new_text: str, existing_hashes: set) -> bool:
    """Проверяет, похож ли новый текст на уже обработанные"""
    new_hash = generate_content_hash(new_text)
    return new_hash in existing_hashes


def filter_duplicate_results(results: List[Dict]) -> List[Dict]:
    """Фильтрует дубликаты из результатов AI"""
    if not results:
        return results
    
    filtered_results = []
    session_hashes = set()
    
    for result in results:
        text = result.get('text', '')
        if not text:
            continue
            
        content_hash = generate_content_hash(text)
        
        # Проверяем как на глобальные, так и на сессионные дубликаты
        if content_hash not in processed_content_hashes and content_hash not in session_hashes:
            filtered_results.append(result)
            session_hashes.add(content_hash)
            processed_content_hashes.add(content_hash)
            print(f"✅ Добавлен уникальный контент: {text[:50]}...")
        else:
            print(f"❌ Дубликат отфильтрован: {text[:50]}...")
    
    return filtered_results


# Функция обработки постов через Gemini API
def process_posts(posts: list[str], has_image: bool = False, prompt_template: str = prompt) -> list[str]:
    # Проверяем на дубликаты на входе
    unique_posts = []
    for post in posts:
        if not check_content_similarity(post, processed_content_hashes):
            unique_posts.append(post)
        else:
            print(f"🔄 Входной пост уже обработан ранее: {post[:50]}...")
    
    if not unique_posts:
        print("🚫 Все входные посты являются дубликатами")
        return []
    
    # Формируем промпт, добавляя посты в виде списка
    content = prompt_template + "\n\n"
    
    # Добавляем информацию о наличии изображения
    if has_image:
        content += "ВАЖНО: К сообщению прикреплено изображение, которое будет автоматически добавлено в пост.\n\n"
    
    # Добавляем инструкцию для уникальности с учетом количества постов
    if len(unique_posts) > 1:
        content += f"ВНИМАНИЕ: Обрабатывается {len(unique_posts)} постов. Убедись, что каждый выходной пост уникален и не повторяет смысл других.\n\n"
    
    content += "\n".join(f"- {p}" for p in unique_posts)

    try:
        # Отправляем запрос к Gemini API
        response = model.generate_content(content)
        raw = response.text.strip()

        # Выводим сырой ответ для отладки
        print("📥 GEMINI RAW RESPONSE:")
        print(raw)

        # Парсим ответ
        parsed_results = []
        
        # 1. Если markdown-обёртка ```json ... ```, вырезаем содержимое
        match = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", raw, re.DOTALL)
        if match:
            parsed_results = json.loads(match.group(1))
        # 2. Если просто массив без markdown
        elif raw.startswith("[") and raw.endswith("]"):
            parsed_results = json.loads(raw)
        # 3. Не получилось — распарсим как строки
        else:
            lines = raw.splitlines()
            parsed_results = [{"text": line.strip("-• ").strip()} for line in lines if line and not line.startswith("Вот")]

        # Фильтруем дубликаты
        filtered_results = filter_duplicate_results(parsed_results)
        
        print(f"📊 Результат: {len(parsed_results)} -> {len(filtered_results)} (после фильтрации дубликатов)")
        
        return filtered_results

    except Exception as e:
        # Логируем ошибку и возвращаем пустой список
        print(f"❌ Gemini Error: {e}")
        return []


# Эндпоинт для фильтрации постов
@app.post('/gemini/filter')
async def multi_filter(data: PostBatch):
    # Обрабатываем посты и возвращаем результат
    result = process_posts(posts=data.posts, has_image=data.has_image)
    return {
        'status': 'success',
        'result': result,
    }


# Эндпоинт для очистки кеша дубликатов (для административных целей)
@app.post('/gemini/clear_cache')
async def clear_duplicate_cache():
    """Очищает кеш дубликатов"""
    global processed_content_hashes
    cache_size = len(processed_content_hashes)
    processed_content_hashes.clear()
    return {
        'status': 'success',
        'message': f'Кеш очищен. Удалено {cache_size} записей.'
    }


# Эндпоинт для получения статистики кеша
@app.get('/gemini/cache_stats')
async def get_cache_stats():
    """Возвращает статистику кеша"""
    return {
        'status': 'success',
        'cache_size': len(processed_content_hashes),
        'recent_hashes': list(processed_content_hashes)[-10:] if processed_content_hashes else []
    }
