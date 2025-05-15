import asyncio
import httpx
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, update
from database.models import Messages, NewsStatus, engine, SessionLocal
from dotenv import load_dotenv
import os
from datetime import datetime
import logging

# Настройка базовой конфигурации логгера
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(module)s - %(funcName)s - %(lineno)d - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

load_dotenv()

AI_SERVICE_URL = os.getenv("AI_API_URL")

async def send_message_to_telegram(message_id: int, text: str):
    """
    Отправляет сообщение в Telegram.
    """
    logging.info(f"Отправка сообщения ID {message_id} в Telegram: {text[:30]}...")
    # Здесь должен быть код для отправки сообщения в Telegram
    pass

logging.info("posting_worker.py загружен")

async def get_new_messages(limit: int = 5) -> list[Messages]:
    """
    Извлекает из БД новые сообщения (со статусом NEW и непустым текстом),
    готовые к отправке в AI.
    """
    logging.info("Получение новых сообщений из БД...")
    def _get_new_messages():
        with SessionLocal() as sync_session:
            stmt_sync = (
                select(Messages)
                .where(Messages.status == NewsStatus.NEW, Messages.text != None, Messages.text != "")
                .order_by(Messages.date.asc())
                .limit(limit)
            )
            result_sync = sync_session.execute(stmt_sync)
            return result_sync.scalars().all()
    
    messages_list = await asyncio.to_thread(_get_new_messages)
    if messages_list:
        logging.info(f"Найдено {len(messages_list)} новых сообщений.")
    else:
        logging.info("Новых сообщений не найдено.")
    return messages_list

async def _fetch_ai_response(message_id: int, text_to_process: str, service_url: str) -> str | None:
    """
    Асинхронно отправляет текст на AI сервис и возвращает обработанный результат.
    Выбрасывает исключения httpx при ошибках сети или HTTP.
    """
    logging.info(f"ID {message_id}: Отправка в AI ({service_url}): {text_to_process[:30]}...")
    async with httpx.AsyncClient(timeout=60.0) as client:
        # Сервис AIservice/gemini.py ожидает ключ "posts", который должен быть списком строк (List[str]).
        payload = {"posts": [text_to_process]}
        response = await client.post(service_url, json=payload)
        response.raise_for_status()  # Вызовет исключение для 4xx/5xx ответов

    response_json = response.json() # Ожидаемый формат от FastAPI: {'status': 'success', 'result': [...тут список...]}
    processed_text = None

    if response_json and isinstance(response_json, dict) and response_json.get("status") == "success":
        ai_result_list = response_json.get("result") # ai_result_list может быть List[Dict] или List[str] или []
        
        if ai_result_list and isinstance(ai_result_list, list) and len(ai_result_list) > 0:
            first_item = ai_result_list[0]
            
            if isinstance(first_item, dict) and "text" in first_item:
                # Случай: result = [{"text": "..."}, ...]
                processed_text = first_item.get("text")
            elif isinstance(first_item, str):
                # Случай: result = ["просто строка", ...]
                processed_text = first_item
            
            # Дополнительная проверка: если текст пустой (None или ""), считаем что текста нет
            if not processed_text:
                 processed_text = None 
    
    logging.info(f"ID {message_id}: Ответ от AI: {processed_text[:50] if processed_text else 'Нет текста (или пустой список от AI)'}")
    return processed_text

async def simplified_process_message(message_id: int, original_text: str):
    """
    Упрощенная функция: отправляет текст в AI, получает ответ и обновляет запись в БД.

    Args:
        message_id (int): ID сообщения в базе данных, используется для обновления статуса и результата обработки
        original_text (str): Исходный текст сообщения, который будет отправлен в AI сервис для обработки
    """
    logging.info(f"Обработка сообщения ID {message_id} через AI...")
    new_status = NewsStatus.ERROR_AI_PROCESSING # Статус по умолчанию, если что-то пойдет не так
    processed_text_from_ai = None
    
    if not original_text or not AI_SERVICE_URL:
        logging.warning(f"Сообщение ID {message_id} не имеет текста или AI_SERVICE_URL не задан. Пропуск.")
        new_status = NewsStatus.ERROR_AI_PROCESSING 
        # Обновим статус в БД на ошибку
        def _update_db_status_sync_error():
            with SessionLocal() as s:
                stmt = (
                    update(Messages)
                    .where(Messages.id == message_id)
                    .values(status=new_status, ai_processed_text="Нет текста или URL AI")
                )
                s.execute(stmt)
                s.commit()
        await asyncio.to_thread(_update_db_status_sync_error)
        return

    try:
        # Шаг 1: Обновить статус сообщения в БД на "отправляется в AI".
        # Это делается для отслеживания состояния обработки сообщения.
        def _update_db_status_sync_sent():
            with SessionLocal() as s:
                stmt = (
                    update(Messages)
                    .where(Messages.id == message_id)
                    .values(status=NewsStatus.SENT_TO_AI) # Устанавливаем статус "отправлено в AI"
                )
                s.execute(stmt)
                s.commit()
        await asyncio.to_thread(_update_db_status_sync_sent)
        logging.info(f"ID {message_id}: Статус обновлен на SENT_TO_AI.")

        # Шаг 2: Вызов AI сервиса через новый метод
        processed_text_from_ai = await _fetch_ai_response(message_id, original_text, AI_SERVICE_URL)

        # Определение финального статуса в зависимости от ответа AI
        if processed_text_from_ai:
            new_status = NewsStatus.AI_PROCESSED # AI успешно обработал текст
        else:
            # AI вернул успешный ответ, но без текста (processed_text_from_ai is None)
            # или сервис вернул текст, но он пустой (processed_text_from_ai == "")
            new_status = NewsStatus.ERROR_AI_PROCESSING # Или специальный статус для пустого ответа
            processed_text_from_ai = "AI не вернул текст" # Записываем информацию о пустом ответе


    except httpx.RequestError as e:
        # Обработка ошибок сети (например, DNS resolving, connection refused)
        logging.error(f"ID {message_id}: Ошибка сети при обращении к AI: {e}")
        new_status = NewsStatus.ERROR_SENDING_TO_AI # Статус: ошибка отправки
        processed_text_from_ai = f"Ошибка сети: {str(e)}"
    except httpx.HTTPStatusError as e:
        # Обработка HTTP ошибок, возвращенных AI сервисом (например, 400, 500, 503)
        logging.error(f"ID {message_id}: AI сервис вернул HTTP ошибку: {e.response.status_code} - {e.response.text}")
        new_status = NewsStatus.ERROR_AI_PROCESSING # Статус: ошибка при обработке AI
        # Сохраняем код ошибки и часть текста ответа для диагностики
        processed_text_from_ai = f"AI ошибка HTTP: {e.response.status_code} - {e.response.text[:100]}" # Увеличил до 100 символов для тела ответа
    except Exception as e:
        # Обработка любых других непредвиденных ошибок во время процесса
        logging.error(f"ID {message_id}: Непредвиденная ошибка при обработке AI: {e}", exc_info=True) # exc_info=True добавит traceback
        new_status = NewsStatus.ERROR_AI_PROCESSING # Общий статус ошибки
        processed_text_from_ai = f"Ошибка: {str(e)[:100]}" # Сохраняем часть сообщения об ошибке
    finally:
        # Шаг 3: Финальное обновление.
        # Этот блок выполнится всегда, независимо от того, была ошибка или нет.
        # Обновляем сообщение в БД с финальным статусом и результатом (или ошибкой) от AI.
        def _update_db_final_sync():
            with SessionLocal() as s:
                stmt = (
                    update(Messages)
                    .where(Messages.id == message_id)
                    .values(status=new_status, ai_processed_text=processed_text_from_ai)
                )
                s.execute(stmt)
                s.commit()
        await asyncio.to_thread(_update_db_final_sync)
        logging.info(f"ID {message_id}: Финальный статус в БД: {new_status.value}, Результат AI сохранен.")

async def main_logic():
    """
    Основная логика обработки новых сообщений.
    Получает новые сообщения из БД и отправляет их на обработку.
    
    Ограничение в 2 сообщения за раз позволяет не перегружать AI сервис.
    Между обработкой сообщений делается пауза в 2 секунды.
    """
    logging.info("main_logic запущен")
    new_messages = await get_new_messages(limit=2)

    if new_messages:
        logging.info(f"Найдены {len(new_messages)} новых сообщений для обработки.")
        for msg_obj in new_messages:
            # Проверяем, что msg_obj.text не None перед передачей
            if msg_obj.text is not None:
                await simplified_process_message(msg_obj.id, msg_obj.text)
            else:
                logging.warning(f"Сообщение ID {msg_obj.id} имеет пустой текст (None). Пропуск обработки AI.")
                # Опционально: обновить статус в БД на какую-то ошибку или "пропущено"
                def _update_skipped_status_sync():
                    with SessionLocal() as s:
                        stmt = (
                            update(Messages)
                            .where(Messages.id == msg_obj.id)
                            .values(status=NewsStatus.ERROR_AI_PROCESSING, ai_processed_text="Сообщение имеет пустой текст (None)") 
                        )
                        s.execute(stmt)
                        s.commit()
                await asyncio.to_thread(_update_skipped_status_sync)
                logging.info(f"ID {msg_obj.id}: Статус обновлен на ERROR_AI_PROCESSING из-за пустого текста.")

            await asyncio.sleep(2)  # Пауза между обработкой сообщений
    else:
        logging.info("Не найдено новых сообщений для обработки.")

async def run_periodic_tasks():
    """
    Запускает периодическое выполнение основной логики.
    Выполняет main_logic() каждые 10 секунд в бесконечном цикле.
    """
    while True:
        await main_logic()
        await asyncio.sleep(10)  # Пауза между циклами проверки новых сообщений

if __name__ == "__main__":
    try:
        # Запуск периодических задач в асинхронном режиме
        asyncio.run(run_periodic_tasks())
    except KeyboardInterrupt:
        # Обработка прерывания программы пользователем (Ctrl+C)
        logging.info("Программа прервана пользователем.")
    except Exception as e:
        # Логирование любых непредвиденных ошибок
        logging.critical(f"Произошла непредвиденная ошибка в главном цикле: {e}", exc_info=True) # exc_info=True для traceback

