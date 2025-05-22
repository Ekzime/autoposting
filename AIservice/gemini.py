###############################
#           system libs
#------------------------------
import re
import json
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


# Функция обработки постов через Gemini API
def process_posts(posts: list[str], has_image: bool = False, prompt_template: str = prompt) -> list[str]:
    # Формируем промпт, добавляя посты в виде списка
    content = prompt_template + "\n\n"
    
    # Добавляем информацию о наличии изображения
    if has_image:
        content += "ВАЖНО: К сообщению прикреплено изображение, которое будет автоматически добавлено в пост.\n\n"
    
    content += "\n".join(f"- {p}" for p in posts)

    try:
        # Отправляем запрос к Gemini API
        response = model.generate_content(content)
        raw = response.text.strip()

        # Выводим сырой ответ для отладки
        print("📥 GEMINI RAW RESPONSE:")
        print(raw)

        # 1. Если markdown-обёртка ```json ... ```, вырезаем содержимое
        match = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", raw, re.DOTALL)
        if match:
            return json.loads(match.group(1))

        # 2. Если просто массив без markdown
        if raw.startswith("[") and raw.endswith("]"):
            return json.loads(raw)

        # 3. Не получилось — распарсим как строки
        lines = raw.splitlines()
        return [line.strip("-• ").strip() for line in lines if line and not line.startswith("Вот")]

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
