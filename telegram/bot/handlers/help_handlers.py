import logging
from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from sqlalchemy import select
from database.models import SessionLocal, Messages, NewsStatus

# Настройка логгера
logger = logging.getLogger(__name__)

router = Router()


class ErrorMessagesStates(StatesGroup):
    """Состояния для обработки сообщений с ошибками"""
    waiting_for_action = State()  # Ожидание действия (retry/skip/list)
    waiting_for_message_id = State()  # Ожидание ID сообщения


@router.message(Command("help", "commands"))
async def cmd_help(message: Message):
    """
    Обработчик команд /help и /commands для вывода списка всех доступных команд бота
    
    Args:
        message (Message): Сообщение от пользователя
    """
    commands_text = """
🔍 <b>Доступные команды бота</b>

<b>📱 Управление аккаунтами Telegram:</b>
/add_account - добавить новый аккаунт Telegram
/view_accounts - просмотреть список доступных аккаунтов
/activate_account ID - активировать аккаунт с указанным ID
/deactivate_account ID - деактивировать аккаунт
/delete_account ID - удалить аккаунт

<b>📋 Управление источниками парсинга:</b>
/add_source - добавить новый источник для парсинга
/view_all_sources - просмотреть все источники парсинга
/update_source ID - обновить существующий источник
/copy_source - копировать источник в другой целевой канал
/delete_source ID - удалить источник парсинга

<b>🎯 Управление целевыми каналами:</b>
/add_target - добавить новый целевой канал
/all_targets (или /t) - просмотреть список всех целевых каналов
/targets_with_sources (или /ts) - просмотреть целевые каналы с их источниками
/activate_target ID - активировать целевой канал (можно указать несколько ID через запятую)
/toggle_target ID - переключить статус целевого канала
/deactivate_target ID - деактивировать целевой канал
/update_target ID - обновить информацию о целевом канале
/delete_target ID - удалить целевой канал

<b>🛠️ Управление сообщениями с ошибками:</b>
/errors - просмотр и управление сообщениями с ошибками

<b>⚙️ Сервисные команды:</b>
/help, /commands - показать этот список команд
/cancel - отменить текущую операцию

Используйте ID, указанные в списках при просмотре аккаунтов, источников и целевых каналов.
"""
    await message.answer(commands_text, parse_mode="HTML")
    logger.info(f"Показан список команд пользователю {message.from_user.id}")


@router.message(Command("errors"))
async def cmd_errors(message: Message, state: FSMContext):
    """
    Обработчик команды /errors для управления сообщениями с ошибками
    
    Args:
        message (Message): Сообщение от пользователя
        state (FSMContext): Контекст состояния FSM для отслеживания диалога
    """
    # Получаем количество сообщений с ошибками
    error_messages = await get_error_messages_count()
    
    # Формируем сообщение с инструкциями
    instructions_text = f"""
<b>🔧 Управление сообщениями с ошибками</b>

Сейчас в системе:
- {error_messages["ai_errors"]} сообщений с ошибками обработки AI
- {error_messages["posting_errors"]} сообщений с ошибками постинга
- {error_messages["permanent_errors"]} сообщений с постоянными ошибками

<b>Доступные команды:</b>
- <code>list</code> - показать список сообщений с ошибками
- <code>retry all</code> - повторить обработку всех сообщений с ошибками
- <code>retry ID</code> - повторить обработку конкретного сообщения
- <code>skip ID</code> - пометить сообщение как окончательно ошибочное
- <code>cancel</code> - выйти из режима управления ошибками

Что вы хотите сделать?
"""
    await message.answer(instructions_text, parse_mode="HTML")
    await state.set_state(ErrorMessagesStates.waiting_for_action)


@router.message(ErrorMessagesStates.waiting_for_action)
async def process_error_action(message: Message, state: FSMContext):
    """
    Обработчик действий с сообщениями, имеющими ошибки
    
    Args:
        message (Message): Сообщение от пользователя
        state (FSMContext): Контекст состояния FSM
    """
    action = message.text.lower().strip()
    
    if action == "cancel":
        await state.clear()
        await message.answer("✅ Вы вышли из режима управления ошибками.")
        return
    
    if action == "list":
        # Получаем список сообщений с ошибками
        error_messages = await get_error_messages_list()
        
        if not error_messages:
            await message.answer("✅ Нет сообщений с ошибками.")
            return
        
        # Формируем сообщение со списком ошибок
        messages_text = "<b>📋 Сообщения с ошибками:</b>\n\n"
        
        for msg in error_messages:
            if msg["status"] == NewsStatus.ERROR_AI_PROCESSING:
                error_type = "❌ Ошибка AI"
            elif msg["status"] == NewsStatus.ERROR_POSTING:
                error_type = "📤 Ошибка постинга"
            elif msg["status"] == NewsStatus.ERROR_PERMANENT:
                error_type = "🚫 Постоянная ошибка"
            else:
                error_type = "⚠️ Ошибка"
                
            text_preview = msg["text"][:50] + "..." if len(msg["text"]) > 50 else msg["text"]
            messages_text += f"ID: {msg['id']} - {error_type}\n"
            messages_text += f"Текст: {text_preview}\n"
            messages_text += f"Попыток: {msg['retry_count']}\n"
            messages_text += f"Причина: {msg['error_info'][:100]}...\n\n"
        
        messages_text += "\nИспользуйте <code>retry ID</code> для повторной обработки или <code>skip ID</code> для пропуска."
        
        # Если сообщение слишком длинное, разбиваем на части
        if len(messages_text) > 4000:
            chunks = [messages_text[i:i+4000] for i in range(0, len(messages_text), 4000)]
            for chunk in chunks:
                await message.answer(chunk, parse_mode="HTML")
        else:
            await message.answer(messages_text, parse_mode="HTML")
        return
    
    if action == "retry all":
        # Помечаем все сообщения с ошибками для повторной обработки
        count = await reset_error_messages_status()
        await message.answer(f"✅ {count} сообщений помечено для повторной обработки. Они будут обработаны в следующем цикле.")
        await state.clear()
        return
    
    if action.startswith("retry "):
        try:
            # Получаем ID сообщения
            message_id = int(action.replace("retry ", ""))
            # Помечаем сообщение для повторной обработки
            success = await reset_message_status(message_id)
            
            if success:
                await message.answer(f"✅ Сообщение с ID {message_id} помечено для повторной обработки.")
            else:
                await message.answer(f"❌ Сообщение с ID {message_id} не найдено или не содержит ошибок.")
                
            await state.clear()
            return
        except ValueError:
            await message.answer("❌ Некорректный ID сообщения. Используйте числовой ID.")
            return
    
    if action.startswith("skip "):
        try:
            # Получаем ID сообщения
            message_id = int(action.replace("skip ", ""))
            # Помечаем сообщение как окончательно ошибочное
            success = await mark_message_permanent(message_id)
            
            if success:
                await message.answer(f"✅ Сообщение с ID {message_id} помечено как окончательно ошибочное.")
            else:
                await message.answer(f"❌ Сообщение с ID {message_id} не найдено или не содержит ошибок.")
                
            await state.clear()
            return
        except ValueError:
            await message.answer("❌ Некорректный ID сообщения. Используйте числовой ID.")
            return
    
    # Если команда не распознана
    await message.answer("❌ Неизвестная команда. Используйте list, retry all, retry ID, skip ID или cancel.")


@router.message(Command("add_bot_to_channel"))
async def cmd_add_bot_to_channel(message: Message):
    """
    Обработчик команды /add_bot_to_channel для вывода инструкций
    по добавлению бота в канал как администратора
    
    Args:
        message (Message): Сообщение от пользователя
    """
    # Получаем имя бота
    from config import settings
    bot_token = settings.telegram_bot.bot_token
    bot_username = "Ваш_бот"  # Значение по умолчанию
    
    try:
        from aiogram import Bot
        bot = Bot(token=bot_token)
        bot_info = await bot.get_me()
        bot_username = f"@{bot_info.username}"
        await bot.session.close()
    except Exception as e:
        logger.error(f"Ошибка при получении информации о боте: {e}")
    
    instructions_text = f"""
<b>📝 Как добавить бота в канал Telegram</b>

Чтобы бот мог публиковать сообщения в канале, его необходимо добавить как администратора с правами на публикацию сообщений. Вот пошаговая инструкция:

1. Откройте свой канал в Telegram
2. Нажмите на название канала вверху экрана
3. Выберите "Администраторы" или "Управление каналом"
4. Нажмите "Добавить администратора"
5. Найдите бота {bot_username} и выберите его
6. Убедитесь, что у бота есть как минимум права:
   - "Публиковать сообщения"
   - "Оставаться анонимным"
7. Нажмите "Сохранить"

<b>Важно:</b> Если вы используете имя канала (например, @mychannel) вместо ID канала в настройках, убедитесь, что канал публичный, а не приватный. Для приватных каналов необходимо использовать ID канала (начинается с -100).

<b>Как узнать ID приватного канала:</b>
1. Перешлите любое сообщение из канала боту @getidsbot
2. Бот покажет информацию о канале, включая его ID
3. Используйте полученный ID при настройке целевого канала для постинга

После добавления бота в канал, проверьте работу отправкой тестового сообщения.
"""
    await message.answer(instructions_text, parse_mode="HTML")
    logger.info(f"Показаны инструкции по добавлению бота в канал пользователю {message.from_user.id}")


async def get_error_messages_count():
    """
    Получает количество сообщений с разными типами ошибок
    
    Returns:
        dict: Словарь с количеством сообщений с ошибками по типам
    """
    def _get_sync():
        with SessionLocal() as session:
            ai_errors = session.query(Messages).filter(Messages.status == NewsStatus.ERROR_AI_PROCESSING).count()
            posting_errors = session.query(Messages).filter(Messages.status == NewsStatus.ERROR_POSTING).count()
            permanent_errors = session.query(Messages).filter(Messages.status == NewsStatus.ERROR_PERMANENT).count()
            
            return {
                "ai_errors": ai_errors,
                "posting_errors": posting_errors,
                "permanent_errors": permanent_errors
            }
    
    import asyncio
    return await asyncio.to_thread(_get_sync)


async def get_error_messages_list():
    """
    Получает список сообщений с ошибками
    
    Returns:
        list: Список словарей с информацией о сообщениях с ошибками
    """
    def _get_sync():
        with SessionLocal() as session:
            query = session.query(Messages).filter(
                (Messages.status == NewsStatus.ERROR_AI_PROCESSING) | 
                (Messages.status == NewsStatus.ERROR_POSTING) |
                (Messages.status == NewsStatus.ERROR_PERMANENT)
            ).order_by(Messages.id.desc()).limit(10)
            
            messages = []
            for msg in query:
                error_info = msg.error_info if hasattr(msg, 'error_info') and msg.error_info else "Нет подробной информации"
                
                messages.append({
                    "id": msg.id,
                    "text": msg.text or "(нет текста)",
                    "status": msg.status,
                    "retry_count": msg.retry_count,
                    "error_info": error_info
                })
            
            return messages
    
    import asyncio
    return await asyncio.to_thread(_get_sync)


async def reset_error_messages_status():
    """
    Сбрасывает статус всех сообщений с ошибками для повторной обработки
    
    Returns:
        int: Количество обновленных сообщений
    """
    def _update_sync():
        with SessionLocal() as session:
            # Сбрасываем статус сообщений с ошибками AI на NEW
            ai_errors = session.query(Messages).filter(Messages.status == NewsStatus.ERROR_AI_PROCESSING)
            ai_count = ai_errors.count()
            ai_errors.update({"status": NewsStatus.NEW})
            
            # Сбрасываем статус сообщений с ошибками постинга на AI_PROCESSED
            posting_errors = session.query(Messages).filter(Messages.status == NewsStatus.ERROR_POSTING)
            posting_count = posting_errors.count()
            posting_errors.update({"status": NewsStatus.AI_PROCESSED})
            
            session.commit()
            return ai_count + posting_count
    
    import asyncio
    return await asyncio.to_thread(_update_sync)


async def reset_message_status(message_id):
    """
    Сбрасывает статус конкретного сообщения для повторной обработки
    
    Args:
        message_id (int): ID сообщения
        
    Returns:
        bool: True, если сообщение найдено и обновлено, иначе False
    """
    def _update_sync():
        with SessionLocal() as session:
            message = session.get(Messages, message_id)
            
            if not message or (message.status != NewsStatus.ERROR_AI_PROCESSING and 
                              message.status != NewsStatus.ERROR_POSTING):
                return False
            
            if message.status == NewsStatus.ERROR_AI_PROCESSING:
                message.status = NewsStatus.NEW
            elif message.status == NewsStatus.ERROR_POSTING:
                message.status = NewsStatus.AI_PROCESSED
                
            session.commit()
            return True
    
    import asyncio
    return await asyncio.to_thread(_update_sync)


async def mark_message_permanent(message_id):
    """
    Помечает сообщение как окончательно ошибочное
    
    Args:
        message_id (int): ID сообщения
        
    Returns:
        bool: True, если сообщение найдено и обновлено, иначе False
    """
    def _update_sync():
        with SessionLocal() as session:
            message = session.get(Messages, message_id)
            
            if not message or (message.status != NewsStatus.ERROR_AI_PROCESSING and 
                              message.status != NewsStatus.ERROR_POSTING):
                return False
            
            message.status = NewsStatus.ERROR_PERMANENT
            session.commit()
            return True
    
    import asyncio
    return await asyncio.to_thread(_update_sync) 