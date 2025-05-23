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
FORCE_AUTO_CLEAR_URL = "http://localhost:8000/gemini/force_auto_clear"


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


async def test_auto_clear_functionality():
    """Тестирует функциональность автоматической очистки кеша."""
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        logging.info("\n=== ТЕСТ АВТООЧИСТКИ КЕША ===")
        
        # 1. Очищаем кеш и добавляем тестовые данные
        await client.post(CLEAR_CACHE_URL)
        
        # Добавляем несколько записей в кеш
        test_posts = [
            "Тестовая новость 1",
            "Тестовая новость 2", 
            "Тестовая новость 3"
        ]
        
        for post in test_posts:
            payload = {"posts": [post], "has_image": False}
            await client.post(API_URL, json=payload)
        
        # 2. Проверяем статистику до автоочистки
        stats_before = await client.get(STATS_URL)
        stats_before_data = stats_before.json()
        cache_size_before = stats_before_data.get('cache_size', 0)
        
        logging.info(f"Размер кеша до автоочистки: {cache_size_before}")
        logging.info(f"Часов до следующей очистки: {stats_before_data.get('hours_until_next_clear', 0)}")
        
        # 3. Принудительно запускаем автоочистку
        logging.info("Запускаем принудительную автоочистку...")
        force_clear_response = await client.post(FORCE_AUTO_CLEAR_URL)
        
        if force_clear_response.status_code == 200:
            result = force_clear_response.json()
            logging.info(f"✅ Автоочистка: {result.get('message', 'Выполнена')}")
        else:
            logging.error(f"❌ Ошибка автоочистки: HTTP {force_clear_response.status_code}")
            return
        
        # 4. Проверяем статистику после автоочистки
        stats_after = await client.get(STATS_URL)
        stats_after_data = stats_after.json()
        cache_size_after = stats_after_data.get('cache_size', 0)
        
        logging.info(f"Размер кеша после автоочистки: {cache_size_after}")
        logging.info(f"Часов до следующей очистки: {stats_after_data.get('hours_until_next_clear', 0)}")
        
        # 5. Анализируем результат
        if cache_size_before > 0 and cache_size_after == 0:
            logging.info("✅ АВТООЧИСТКА РАБОТАЕТ: Кеш был очищен")
        else:
            logging.error(f"❌ АВТООЧИСТКА НЕ РАБОТАЕТ: До {cache_size_before}, После {cache_size_after}")
        
        # 6. Проверяем, что новые записи добавляются после очистки
        test_post_after_clear = "Новая запись после очистки кеша"
        payload = {"posts": [test_post_after_clear], "has_image": False}
        await client.post(API_URL, json=payload)
        
        final_stats = await client.get(STATS_URL)
        final_stats_data = final_stats.json()
        final_cache_size = final_stats_data.get('cache_size', 0)
        
        if final_cache_size > 0:
            logging.info("✅ После очистки кеш снова работает корректно")
        else:
            logging.error("❌ После очистки кеш не работает")


if __name__ == "__main__":
    logging.info("Запуск тестов предотвращения дубликатов...")
    asyncio.run(test_duplicate_prevention())
    
    logging.info("\nЗапуск теста batch обработки...")
    asyncio.run(test_batch_processing())
    
    logging.info("\nЗапуск теста автоочистки кеша...")
    asyncio.run(test_auto_clear_functionality()) 