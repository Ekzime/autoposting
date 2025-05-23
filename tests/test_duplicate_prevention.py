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
CLEAR_CACHE_URL = "http://localhost:8000/gemini/clear_cache"
STATS_URL = "http://localhost:8000/gemini/cache_stats"


async def test_duplicate_prevention():
    """Тестирует систему предотвращения дубликатов."""
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        # 1. Очищаем кеш перед тестом
        logging.info("Очищаем кеш перед тестом...")
        try:
            response = await client.post(CLEAR_CACHE_URL)
            if response.status_code == 200:
                logging.info("✅ Кеш очищен")
            else:
                logging.warning(f"⚠️ Не удалось очистить кеш: {response.status_code}")
        except Exception as e:
            logging.warning(f"⚠️ Ошибка при очистке кеша: {e}")
        
        # 2. Отправляем первый пост о биткоине
        test_post_1 = "Bitcoin достиг нового максимума в $100,000"
        payload_1 = {"posts": [test_post_1], "has_image": False}
        
        logging.info("Отправляем первый пост о биткоине...")
        response_1 = await client.post(API_URL, json=payload_1)
        result_1 = response_1.json()
        
        logging.info(f"Результат 1: {json.dumps(result_1, ensure_ascii=False, indent=2)}")
        
        # 3. Отправляем похожий пост (должен быть отфильтрован)
        test_post_2 = "Биткоин установил новый рекорд на отметке $100k"
        payload_2 = {"posts": [test_post_2], "has_image": False}
        
        logging.info("Отправляем похожий пост (должен быть отфильтрован)...")
        response_2 = await client.post(API_URL, json=payload_2)
        result_2 = response_2.json()
        
        logging.info(f"Результат 2: {json.dumps(result_2, ensure_ascii=False, indent=2)}")
        
        # 4. Отправляем совершенно другой пост
        test_post_3 = "Ethereum обновил свой протокол консенсуса"
        payload_3 = {"posts": [test_post_3], "has_image": False}
        
        logging.info("Отправляем другой пост о Ethereum...")
        response_3 = await client.post(API_URL, json=payload_3)
        result_3 = response_3.json()
        
        logging.info(f"Результат 3: {json.dumps(result_3, ensure_ascii=False, indent=2)}")
        
        # 5. Проверяем статистику кеша
        logging.info("Получаем статистику кеша...")
        try:
            stats_response = await client.get(STATS_URL)
            if stats_response.status_code == 200:
                stats = stats_response.json()
                logging.info(f"Статистика кеша: {json.dumps(stats, ensure_ascii=False, indent=2)}")
            else:
                logging.warning(f"Не удалось получить статистику: {stats_response.status_code}")
        except Exception as e:
            logging.warning(f"Ошибка при получении статистики: {e}")
        
        # 6. Анализируем результаты
        logging.info("\n=== АНАЛИЗ РЕЗУЛЬТАТОВ ===")
        
        result_1_count = len(result_1.get('result', []))
        result_2_count = len(result_2.get('result', []))
        result_3_count = len(result_3.get('result', []))
        
        logging.info(f"Первый пост (биткоин): {result_1_count} результатов")
        logging.info(f"Похожий пост (биткоин): {result_2_count} результатов")
        logging.info(f"Другой пост (ethereum): {result_3_count} результатов")
        
        if result_1_count > 0 and result_2_count == 0 and result_3_count > 0:
            logging.info("✅ ТЕСТ ПРОЙДЕН: Система корректно фильтрует дубликаты")
        else:
            logging.error("❌ ТЕСТ НЕ ПРОЙДЕН: Система работает некорректно")


async def test_batch_processing():
    """Тестирует обработку нескольких постов одновременно."""
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        # Очищаем кеш
        await client.post(CLEAR_CACHE_URL)
        
        # Отправляем несколько постов одновременно, включая дубликаты
        batch_posts = [
            "Tesla принимает биткоин как способ оплаты",
            "Тесла начала принимать BTC в качестве платежного средства",  # дубликат
            "Ethereum запустил новое обновление сети",
            "Dogecoin вырос на 20% за день"
        ]
        
        payload = {"posts": batch_posts, "has_image": False}
        
        logging.info("Тестируем batch обработку с дубликатами...")
        response = await client.post(API_URL, json=payload)
        result = response.json()
        
        logging.info(f"Batch результат: {json.dumps(result, ensure_ascii=False, indent=2)}")
        
        result_count = len(result.get('result', []))
        logging.info(f"Из {len(batch_posts)} постов получили {result_count} уникальных")


if __name__ == "__main__":
    logging.info("Запуск тестов предотвращения дубликатов...")
    asyncio.run(test_duplicate_prevention())
    
    logging.info("\nЗапуск теста batch обработки...")
    asyncio.run(test_batch_processing()) 