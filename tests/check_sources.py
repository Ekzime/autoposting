import logging
import sys
from sqlalchemy import select
from database.models import SessionLocal, ParsingSourceChannel

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

def check_sources():
    """Проверяет источники в базе данных"""
    with SessionLocal() as session:
        # Получаем все источники
        sources = session.execute(select(ParsingSourceChannel)).scalars().all()
        logging.info(f"Найдено {len(sources)} источников:")
        
        for source in sources:
            logging.info(f"Источник: ID {source.id}, target_id={source.posting_target_id}, identifier={source.source_identifier}, title={source.source_title}")

if __name__ == "__main__":
    try:
        from config import settings  # Инициализация настроек
        check_sources()
    except KeyboardInterrupt:
        logging.info("Программа прервана пользователем.")
    except Exception as e:
        logging.critical(f"Критическая ошибка: {e}", exc_info=True) 