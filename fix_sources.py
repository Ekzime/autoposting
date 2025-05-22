import logging
import sys
from sqlalchemy import select, update
from database.models import SessionLocal, ParsingSourceChannel

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

def fix_source_identifiers():
    """Исправляет идентификаторы источников, добавляя символ @ для usernames"""
    with SessionLocal() as session:
        # Получаем все источники
        sources = session.execute(select(ParsingSourceChannel)).scalars().all()
        logging.info(f"Найдено {len(sources)} источников:")
        
        fixed_count = 0
        for source in sources:
            logging.info(f"Источник: ID {source.id}, identifier={source.source_identifier}, title={source.source_title}")
            
            # Проверяем, является ли идентификатор числом
            try:
                int(source.source_identifier)
                logging.info(f"  Идентификатор {source.source_identifier} является числом, пропускаем")
                continue
            except ValueError:
                # Если это не число и не начинается с @, добавляем @
                if not source.source_identifier.startswith('@'):
                    old_identifier = source.source_identifier
                    new_identifier = f"@{source.source_identifier}"
                    
                    # Обновляем идентификатор в БД
                    session.execute(
                        update(ParsingSourceChannel)
                        .where(ParsingSourceChannel.id == source.id)
                        .values(source_identifier=new_identifier)
                    )
                    
                    fixed_count += 1
                    logging.info(f"  ИСПРАВЛЕНО: {old_identifier} -> {new_identifier}")
                else:
                    logging.info(f"  Идентификатор {source.source_identifier} уже начинается с @, пропускаем")
        
        # Если были исправления, сохраняем изменения
        if fixed_count > 0:
            session.commit()
            logging.info(f"Исправлено {fixed_count} источников. Изменения сохранены.")
        else:
            logging.info("Исправления не требуются.")

if __name__ == "__main__":
    try:
        from config import settings  # Инициализация настроек
        fix_source_identifiers()
    except KeyboardInterrupt:
        logging.info("Программа прервана пользователем.")
    except Exception as e:
        logging.critical(f"Критическая ошибка: {e}", exc_info=True) 