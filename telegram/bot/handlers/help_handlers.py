import logging
import httpx
from aiogram import Router, Bot
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from sqlalchemy import select
from database.models import SessionLocal, Messages, NewsStatus
from config import settings

# Настройка логгера
logger = logging.getLogger(__name__)

router = Router()


class ErrorMessagesStates(StatesGroup):
    """Состояния для обработки сообщений с ошибками"""
    waiting_for_action = State()  # Ожидание действия (retry/skip/list)
    waiting_for_message_id = State()  # Ожидание ID сообщения


class CheckChannelState(StatesGroup):
    """Состояния для обработки команды /check_channel"""
    waiting_for_id = State()  # Ожидание ввода ID канала


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

<b>🤖 Управление AI сервисом:</b>
/clear_ai_cache - очистить кеш дубликатов AI вручную
/ai_cache_stats - статистика кеша AI сервиса
/force_auto_clear - принудительная автоочистка кеша

<b>⚙️ Сервисные команды:</b>
/help, /commands - показать этот список команд
/add_bot_to_channel - инструкции по добавлению бота в канал
/check_channel - проверить доступность канала
/cancel - отменить текущую операцию

Используйте ID, указанные в списках при просмотре аккаунтов, источников и целевых каналов.

💡 <b>Кеш AI автоматически очищается каждые 24 часа</b>
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

<b>⚠️ ВАЖНО: Правильный формат ID канала</b>

При добавлении канала в бота, используйте:

• Для <b>публичных каналов</b>: @username 
  Пример: <code>@mychannel</code>

• Для <b>приватных каналов</b>: ID с префиксом -100
  Пример: <code>-1001234567890</code>

<b>Как узнать ID приватного канала:</b>
1. Перешлите любое сообщение из канала боту @getidsbot
2. Бот покажет ID канала, который начинается с "-100..."
3. Скопируйте полный ID вместе с -100
4. Используйте этот ID при добавлении канала через /add_target

<b>Распространенные ошибки:</b>
• Использование имени канала вместо ID для приватных каналов
• Указание ID без префикса -100
• Недостаточные права бота в канале
• Бот не добавлен как администратор

Если у вас возникли проблемы, проверьте формат ID канала в базе данных и права бота.
"""
    await message.answer(instructions_text, parse_mode="HTML")
    logger.info(f"Показаны инструкции по добавлению бота в канал пользователю {message.from_user.id}")


@router.message(Command("check_channel"))
async def cmd_check_channel(message: Message, state: FSMContext):
    """
    Обработчик команды /check_channel для проверки доступности канала.
    Инициирует процесс проверки канала по ID.
    
    Args:
        message (Message): Объект сообщения от пользователя
        state (FSMContext): Контекст состояния FSM
    """
    await message.answer(
        "<b>🔍 Проверка доступности канала</b>\n\n"
        "Отправьте ID канала или @username, который вы хотите проверить.\n\n"
        "<b>Поддерживаемые форматы:</b>\n"
        "• Публичные каналы: <code>@username</code>\n"
        "• Приватные каналы: <code>-100XXXXXXXXXX</code>",
        parse_mode="HTML"
    )
    await state.set_state(CheckChannelState.waiting_for_id)


@router.message(CheckChannelState.waiting_for_id)
async def cmd_process_check_channel(message: Message, state: FSMContext, bot: Bot):
    """
    Обработчик для проверки доступности канала по ID.
    
    Args:
        message (Message): Объект сообщения от пользователя с ID канала
        state (FSMContext): Контекст состояния FSM
        bot (Bot): Экземпляр бота для проверки доступа
    """
    channel_id = message.text.strip()
    
    if not channel_id:
        await message.answer("Вы отправили пустое сообщение. Пожалуйста, введите ID канала или @username.")
        return
    
    await message.answer(f"🔄 Проверяю доступность канала <code>{channel_id}</code>...", parse_mode="HTML")
    
    # Если ID не начинается с @ и не является числом, возможно это username без @
    if not (channel_id.startswith('@') or channel_id.lstrip('-').isdigit()):
        await message.answer(
            "⚠️ <b>Обратите внимание:</b> ID не начинается с @ и не является числом.\n"
            "Возможно, вы имели в виду публичный канал? Добавляю префикс @...",
            parse_mode="HTML"
        )
        channel_id = f"@{channel_id}"
    
    # Для числовых ID проверяем формат -100
    if channel_id.lstrip('-').isdigit() and not channel_id.startswith('-100'):
        numeric_id = int(channel_id)
        if numeric_id < 0:
            corrected_id = f"-100{abs(numeric_id)}"
            await message.answer(
                f"⚠️ <b>Внимание!</b> ID канала в неправильном формате.\n\n"
                f"Вы ввели: <code>{channel_id}</code>\n"
                f"Правильный формат: <code>{corrected_id}</code>\n\n"
                f"Пробую проверить с исправленным ID...",
                parse_mode="HTML"
            )
            channel_id = corrected_id
    
    # Проверяем доступность канала
    try:
        # Для публичных каналов (@username)
        if channel_id.startswith('@'):
            try:
                chat = await bot.get_chat(chat_id=channel_id)
                await message.answer(
                    f"✅ <b>Канал найден!</b>\n\n"
                    f"<b>Название:</b> {chat.title}\n"
                    f"<b>Тип:</b> {chat.type}\n"
                    f"<b>ID:</b> <code>{chat.id}</code>\n"
                    f"<b>Username:</b> @{chat.username}\n\n"
                    f"<b>ℹ️ Рекомендуемый формат для использования:</b> <code>@{chat.username}</code>",
                    parse_mode="HTML"
                )
            except Exception as e:
                await message.answer(
                    f"❌ <b>Канал не найден или бот не имеет доступа</b>\n\n"
                    f"<b>Ошибка:</b> {str(e)}\n\n"
                    f"<b>Возможные причины:</b>\n"
                    f"• Канал не существует\n"
                    f"• Бот не добавлен в канал\n"
                    f"• У бота нет прав администратора\n"
                    f"• Неверный формат username",
                    parse_mode="HTML"
                )
        # Для приватных каналов (числовой ID)
        else:
            try:
                numeric_id = int(channel_id)
                chat = await bot.get_chat(chat_id=numeric_id)
                
                # Формируем сообщение в зависимости от типа канала
                if chat.username:  # Публичный канал
                    recommendation = f"<b>ℹ️ Рекомендуемый формат для использования:</b> <code>@{chat.username}</code>"
                else:  # Приватный канал
                    recommendation = f"<b>ℹ️ Рекомендуемый формат для использования:</b> <code>{chat.id}</code>"
                
                await message.answer(
                    f"✅ <b>Канал найден!</b>\n\n"
                    f"<b>Название:</b> {chat.title}\n"
                    f"<b>Тип:</b> {chat.type}\n"
                    f"<b>ID:</b> <code>{chat.id}</code>\n"
                    f"<b>Username:</b> {('@' + chat.username) if chat.username else 'Отсутствует (приватный канал)'}\n\n"
                    f"{recommendation}",
                    parse_mode="HTML"
                )
                
                # Отправляем тестовое сообщение для проверки прав на публикацию
                try:
                    test_message = await bot.send_message(
                        chat_id=numeric_id,
                        text="🔄 Тестовое сообщение для проверки доступа бота. Это сообщение можно удалить."
                    )
                    await message.answer(
                        "✅ <b>Тестовое сообщение успешно отправлено!</b>\n"
                        "Бот имеет права на публикацию сообщений в этом канале.",
                        parse_mode="HTML"
                    )
                    # Удаляем тестовое сообщение
                    await bot.delete_message(chat_id=numeric_id, message_id=test_message.message_id)
                except Exception as e:
                    await message.answer(
                        f"⚠️ <b>Бот не может отправлять сообщения в канал</b>\n\n"
                        f"<b>Ошибка:</b> {str(e)}\n\n"
                        f"<b>Возможные причины:</b>\n"
                        f"• Бот не имеет прав администратора\n"
                        f"• У бота нет прав на публикацию сообщений\n"
                        f"• У бота нет прав на анонимную публикацию\n\n"
                        f"Используйте команду /add_bot_to_channel для получения инструкций.",
                        parse_mode="HTML"
                    )
            except Exception as e:
                await message.answer(
                    f"❌ <b>Канал не найден или бот не имеет доступа</b>\n\n"
                    f"<b>Ошибка:</b> {str(e)}\n\n"
                    f"<b>Возможные причины:</b>\n"
                    f"• Канал не существует\n"
                    f"• Бот не добавлен в канал\n"
                    f"• У бота нет прав администратора\n"
                    f"• Неверный формат ID\n\n"
                    f"<b>Проверьте, что:</b>\n"
                    f"• ID приватного канала начинается с -100\n"
                    f"• Бот добавлен в канал как администратор\n"
                    f"• У бота есть права на публикацию сообщений",
                    parse_mode="HTML"
                )
    except Exception as e:
        await message.answer(
            f"❌ <b>Произошла неожиданная ошибка</b>\n\n"
            f"<b>Ошибка:</b> {str(e)}\n\n"
            f"Пожалуйста, проверьте правильность ID канала и попробуйте снова.",
            parse_mode="HTML"
        )
    
    # Очищаем состояние
    await state.clear()


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


@router.message(Command("clear_ai_cache"))
async def cmd_clear_ai_cache(message: Message):
    """
    Обработчик команды /clear_ai_cache для очистки кеша дубликатов AI сервиса
    
    Args:
        message (Message): Сообщение от пользователя
    """
    try:
        # Отправляем запрос к AI сервису для очистки кеша
        ai_service_url = settings.ai_service.api_url
        if not ai_service_url:
            await message.answer("❌ AI сервис не настроен в конфигурации.")
            return
            
        # Формируем URL для очистки кеша
        clear_cache_url = ai_service_url.replace('/filter', '/clear_cache')
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(clear_cache_url)
            
            if response.status_code == 200:
                result = response.json()
                message_text = f"✅ {result.get('message', 'Кеш AI сервиса успешно очищен')}"
                await message.answer(message_text)
                logger.info(f"Кеш AI сервиса очищен пользователем {message.from_user.id}")
            else:
                await message.answer(f"❌ Ошибка при очистке кеша: HTTP {response.status_code}")
                
    except Exception as e:
        await message.answer(f"❌ Ошибка при подключении к AI сервису: {str(e)}")
        logger.error(f"Ошибка при очистке кеша AI: {e}")


@router.message(Command("ai_cache_stats"))
async def cmd_ai_cache_stats(message: Message):
    """
    Обработчик команды /ai_cache_stats для получения статистики кеша AI сервиса
    
    Args:
        message (Message): Сообщение от пользователя
    """
    try:
        # Отправляем запрос к AI сервису для получения статистики
        ai_service_url = settings.ai_service.api_url
        if not ai_service_url:
            await message.answer("❌ AI сервис не настроен в конфигурации.")
            return
            
        # Формируем URL для получения статистики
        stats_url = ai_service_url.replace('/filter', '/cache_stats')
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(stats_url)
            
            if response.status_code == 200:
                result = response.json()
                cache_size = result.get('cache_size', 0)
                last_clear = result.get('last_auto_clear', 'Неизвестно')
                hours_since = result.get('hours_since_clear', 0)
                hours_until = result.get('hours_until_next_clear', 0)
                next_clear = result.get('next_auto_clear', 'Неизвестно')
                
                stats_text = f"""
📊 <b>Статистика кеша AI сервиса</b>

🗃️ <b>Размер кеша:</b> {cache_size} записей
📝 Это количество уникальных постов, которые уже были обработаны

⏰ <b>Автоматическая очистка:</b>
• Последняя очистка: {last_clear}
• Прошло часов: {hours_since}
• До следующей очистки: {hours_until} ч.
• Следующая очистка: {next_clear}

💡 <b>Что это значит:</b>
• Кеш автоматически очищается каждые 24 часа
• Это предотвращает накопление старых записей
• Помогает избежать ложных срабатываний на дубликаты

🧹 <b>Ручное управление:</b>
• /clear_ai_cache - очистить кеш вручную
• /force_auto_clear - запустить автоочистку принудительно
"""
                await message.answer(stats_text, parse_mode="HTML")
                logger.info(f"Статистика кеша AI запрошена пользователем {message.from_user.id}")
            else:
                await message.answer(f"❌ Ошибка при получении статистики: HTTP {response.status_code}")
                
    except Exception as e:
        await message.answer(f"❌ Ошибка при подключении к AI сервису: {str(e)}")
        logger.error(f"Ошибка при получении статистики кеша AI: {e}")


@router.message(Command("force_auto_clear"))
async def cmd_force_auto_clear(message: Message):
    """
    Обработчик команды /force_auto_clear для принудительного запуска автоочистки кеша
    
    Args:
        message (Message): Сообщение от пользователя
    """
    try:
        ai_service_url = settings.ai_service.api_url
        if not ai_service_url:
            await message.answer("❌ AI сервис не настроен в конфигурации.")
            return
            
        # Формируем URL для принудительной автоочистки
        force_clear_url = ai_service_url.replace('/filter', '/force_auto_clear')
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(force_clear_url)
            
            if response.status_code == 200:
                result = response.json()
                message_text = f"✅ {result.get('message', 'Автоочистка выполнена принудительно')}"
                await message.answer(message_text)
                logger.info(f"Принудительная автоочистка кеша AI запущена пользователем {message.from_user.id}")
            else:
                await message.answer(f"❌ Ошибка при запуске автоочистки: HTTP {response.status_code}")
                
    except Exception as e:
        await message.answer(f"❌ Ошибка при подключении к AI сервису: {str(e)}")
        logger.error(f"Ошибка при принудительной автоочистке кеша AI: {e}") 