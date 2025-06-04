from database.models import engine
from sqlalchemy import text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate_to_bigint():
    """Миграция полей peer_id и channel_id на BigInteger"""
    
    migration_queries = [
        # Шаг 1: Удаляем foreign key constraint
        "ALTER TABLE messages DROP FOREIGN KEY messages_ibfk_1",
        
        # Шаг 2: Изменяем тип поля peer_id в таблице channels
        "ALTER TABLE channels MODIFY COLUMN peer_id BIGINT",
        
        # Шаг 3: Изменяем тип поля channel_id в таблице messages 
        "ALTER TABLE messages MODIFY COLUMN channel_id BIGINT",
        
        # Шаг 4: Создаем foreign key constraint обратно
        "ALTER TABLE messages ADD CONSTRAINT messages_ibfk_1 FOREIGN KEY (channel_id) REFERENCES channels (peer_id)"
    ]
    
    try:
        with engine.begin() as connection:
            logger.info("🚀 Начинаем миграцию...")
            
            for i, query in enumerate(migration_queries, 1):
                logger.info(f"📝 Выполняем запрос {i}/{len(migration_queries)}: {query}")
                connection.execute(text(query))
                logger.info(f"✅ Запрос {i} выполнен успешно")
            
            logger.info("🎉 Миграция завершена успешно!")
            
    except Exception as e:
        logger.error(f"❌ Ошибка миграции: {e}")
        raise

def test_migration():
    """Тестируем миграцию - пробуем добавить канал с большим peer_id"""
    from database.models import SessionLocal, Channels
    
    session = SessionLocal()
    try:
        # Пробуем добавить канал с большим peer_id
        test_peer_id = 2310347474
        test_channel = Channels(
            peer_id=test_peer_id,
            title="Test Big Peer ID Channel"
        )
        
        session.add(test_channel)
        session.commit()
        
        # Проверяем, что он сохранился правильно
        saved_channel = session.query(Channels).filter(
            Channels.peer_id == test_peer_id
        ).first()
        
        if saved_channel and saved_channel.peer_id == test_peer_id:
            logger.info(f"✅ Тест прошел! Канал с peer_id={test_peer_id} сохранен корректно")
            
            # Удаляем тестовый канал
            session.delete(saved_channel)
            session.commit()
            logger.info("🧹 Тестовый канал удален")
            
        else:
            logger.error("❌ Тест провален! Канал не сохранился или сохранился с неправильным peer_id")
            
    except Exception as e:
        logger.error(f"❌ Ошибка тестирования: {e}")
        session.rollback()
    finally:
        session.close()

if __name__ == "__main__":
    print("🔧 Миграция полей peer_id и channel_id на BigInteger")
    print("⚠️  Убедитесь, что backup создан!")
    
    confirm = input("Продолжить миграцию? (yes/no): ")
    if confirm.lower() in ['yes', 'y', 'да', 'д']:
        migrate_to_bigint()
        print("\n🧪 Тестируем миграцию...")
        test_migration()
    else:
        print("❌ Миграция отменена") 