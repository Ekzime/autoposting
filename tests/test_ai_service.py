import asyncio
import json
import httpx
import logging

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# URL API сервиса
API_URL = "http://localhost:8000/gemini/filter"

async def test_ai_service():
    """Тестирует работу AI сервиса с обработкой изображений."""
    
    # Тестовые данные
    test_cases = [
        {
            "name": "Сообщение с изображением",
            "payload": {
                "posts": ["Вчера Bitcoin достиг нового максимума! Смотрите график!"],
                "has_image": True
            }
        },
        {
            "name": "Сообщение без изображения",
            "payload": {
                "posts": ["Вчера Bitcoin достиг нового максимума! Цена выросла до $80,000."],
                "has_image": False
            }
        }
    ]
    
    # Выполняем тестовые запросы
    async with httpx.AsyncClient(timeout=60.0) as client:
        for test in test_cases:
            try:
                logging.info(f"Выполняем тест: {test['name']}")
                logging.info(f"Отправляем: {json.dumps(test['payload'], ensure_ascii=False)}")
                
                response = await client.post(API_URL, json=test["payload"])
                response.raise_for_status()
                
                result = response.json()
                logging.info(f"Статус: {response.status_code}")
                logging.info(f"Ответ: {json.dumps(result, indent=2, ensure_ascii=False)}")
                
            except Exception as e:
                logging.error(f"Ошибка при выполнении теста {test['name']}: {e}")

if __name__ == "__main__":
    asyncio.run(test_ai_service()) 