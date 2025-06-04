from database.models import SessionLocal, Channels, Messages
import json
from datetime import datetime

def create_backup():
    session = SessionLocal()
    try:
        # Получаем все каналы
        channels = session.query(Channels).all()
        
        # Получаем образец сообщений (первые 1000)
        messages = session.query(Messages).limit(1000).all()
        
        backup_data = {
            'created_at': datetime.now().isoformat(),
            'channels': [
                {
                    'id': c.id, 
                    'peer_id': c.peer_id, 
                    'username': c.username, 
                    'title': c.title
                } for c in channels
            ],
            'messages_sample': [
                {
                    'id': m.id, 
                    'channel_id': m.channel_id, 
                    'message_id': m.message_id, 
                    'text': m.text[:100] if m.text else None  # Первые 100 символов
                } for m in messages
            ]
        }
        
        # Сохраняем backup
        with open('backup_before_bigint_migration.json', 'w', encoding='utf-8') as f:
            json.dump(backup_data, f, ensure_ascii=False, indent=2, default=str)
        
        print(f"✅ Backup создан успешно!")
        print(f"📊 Каналов: {len(backup_data['channels'])}")
        print(f"📧 Сообщений (образец): {len(backup_data['messages_sample'])}")
        
    except Exception as e:
        print(f"❌ Ошибка создания backup: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    create_backup() 