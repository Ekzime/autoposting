import logging
import asyncio

# Библиотеки для работы с ботом
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

# Библиотеки для работы с базой данных
from database.channels import (
    set_active_target, 
    get_active_target_chat_id_str,
    deactivate_target_by_id,
    get_active_target_info,
    get_all_target_channels,
    delete_target_channel,
    activate_target_by_id
)

# Настройка логгера
logger = logging.getLogger(__name__)

router = Router()

########## FSM States ##########
class SetChannelState(StatesGroup):
    """Состояния для процесса установки нового целевого канала"""
    waiting_for_channel_id_str = State()
    waiting_for_title = State()

class DeactivateTargetState(StatesGroup):
    """Состояния для процесса деактивации целевого канала"""
    waiting_for_target_id_str = State()

class DeleteTargetState(StatesGroup):
    """Состояния для процесса удаления целевого канала"""
    waiting_for_target_id_str = State()

class ActivateTargetState(StatesGroup):
    """Состояния для процесса активации целевого канала"""
    waiting_for_target_id_str = State()



########## Set New Target Channel ##########
@router.message(Command("set_new_target"))
async def cmd_set_channel(message: Message, state: FSMContext):
    """
    Обработчик команды /set_new_target для добавления нового канала.
    
    Args:
        message (Message): Объект сообщения от пользователя
        state (FSMContext): Контекст состояния FSM для хранения данных
    
    Действия:
    1. Логирует получение команды
    2. Отправляет инструкцию пользователю
    3. Запрашивает ID канала или username
    4. Устанавливает состояние ожидания ID канала
    """
    logger.info(f"Получена команда /set_new_target от пользователя {message.from_user.id}")
    
    # Отправляем инструкцию пользователю
    text = """Для добавления таргетного канала в бота, вам нужно отправить:

    1️⃣ Для публичного канала:
       Юзернейм канала, например: <code>@channel_name</code>
        (без @ в начале, только имя канала)
    2️⃣ Для приватного канала:
       ID канала с префиксом -100, например: <code>-1001234567890</code>

    ❗️ Убедитесь, что бот добавлен в канал как администратор."""
    await message.answer(text, parse_mode="HTML")
    await message.answer("Введите ID канала или @username:")
    await state.set_state(SetChannelState.waiting_for_channel_id_str)


@router.message(SetChannelState.waiting_for_channel_id_str)
async def cmd_process_channel_id(message: Message, state: FSMContext):
    """
    Обработчик для получения ID канала или username.
    
    Args:
        message (Message): Объект сообщения от пользователя, содержащий ID/username канала
        state (FSMContext): Контекст состояния FSM для хранения данных
        
    Действия:
    1. Проверяет корректность введенного ID/username
    2. Преобразует числовой ID или форматирует username
    3. Сохраняет данные в состоянии FSM
    4. Переходит к запросу названия канала
    
    Raises:
        ValueError: Если ID канала не удается преобразовать в число
        Exception: При других ошибках обработки
    """
    try:
        if not message.text:
            await message.answer("Вы отправили пустое сообщение. Пожалуйста, введите ID канала или @username.", parse_mode="HTML")
            await state.clear()
            return

        channel_id = message.text.strip().replace("@", "")
        if channel_id.isnumeric():
            logger.info(f"Получен числовой ID канала: {channel_id}")
            target_id = int(channel_id)

        else:
            logger.info(f"Получен username канала: @{channel_id}")
            target_id = str(channel_id)
            
        await state.update_data(target_id=target_id)
        await message.answer(f"Теперь введите название для канала для отображения в боте {target_id}:")
        await state.set_state(SetChannelState.waiting_for_title)

    except Exception:
        await message.answer("Произошла ошибка при обработке ID канала. Пожалуйста, попробуйте еще раз.")
        await state.clear()    

    
async def check_posting_bot_can_send(target_id_str: str) -> bool:
    """
    Проверяет, может ли постинг-бот отправлять сообщения в указанный канал.
    
    Args:
        target_id_str (str): ID канала или username для проверки
        
    Returns:
        bool: True если бот может отправлять сообщения, False в противном случае
        
    Действия:
    1. Создает временный инстанс бота с токеном из .env
    2. Пытается получить информацию о чате через get_chat
    3. Возвращает результат проверки
    """
    from aiogram import Bot
    from os import getenv
    from dotenv import load_dotenv
    
    try:
        # Загружаем токен постинг-бота из .env
        load_dotenv()
        posting_bot_token = getenv("TELEGRAM_BOT_TOKEN")
        
        if not posting_bot_token:
            logger.error("Не найден токен постинг-бота в .env")
            return False
        
        # Создаем временный инстанс бота
        temp_bot = Bot(token=posting_bot_token)
        
        # Пытаемся получить информацию о чате
        chat = await temp_bot.get_chat(target_id_str)
        # Если дошли до этой точки, значит бот имеет доступ к чату

        await temp_bot.session.close()
        return True
        
    except Exception as e:
        logger.error(f"Ошибка при проверке доступа бота к каналу {target_id_str}: {e}")
        return False


@router.message(SetChannelState.waiting_for_title)
async def cmd_process_channel_title(message: Message, state: FSMContext):
    """
    Обработчик для получения названия канала.
    
    Args:
        message (Message): Объект сообщения от пользователя
        state (FSMContext): Контекст состояния FSM
        
    Действия:
    1. Получает название канала из сообщения
    2. Проверяет корректность названия
    3. Получает сохраненный ID канала из состояния FSM
    4. Проверяет, может ли постинг-бот отправлять сообщения в канал
    5. Сохраняет канал в базу данных
    6. Очищает состояние FSM
    
    Raises:
        Exception: При ошибках сохранения в БД или других проблемах
    """
    title = message.text.strip()
    
    # Проверка на пустой ввод
    if not title:
        await message.answer("Вы отправили пустое название. Пожалуйста, введите понятное название для канала:")
        return
    
    def _db_call_sync():
        """
        Обертка для синхронного вызова set_active_target в отдельном потоке.
        Нужна что бы не блокировать основной асинхронный поток бота при вызове set_active_target.
        Предполагается, что set_active_target сама управляет сессией БД через with session_scope().
        """
        return set_active_target(target_id, title)

    try:
        # Получаем данные из состояния
        data = await state.get_data()
        target_id = data.get("target_id")
        
        if not target_id:
            await message.answer("Произошла ошибка: не найден ID канала. Пожалуйста, начните заново.")
            await state.clear()
            return
        
        # Проверяем, может ли постинг-бот отправлять сообщения в канал
        await message.answer("Проверяем доступ бота к каналу...")
        can_send = await check_posting_bot_can_send(target_id)
        
        if not can_send:
            await message.answer(
                "❌ Бот не может отправлять сообщения в указанный канал.\n\n"
                "Пожалуйста, убедитесь, что:\n"
                "1. Вы добавили бота в канал\n"
                "2. Бот имеет права администратора для отправки сообщений\n"
                "3. ID или username канала указан правильно"
            )
            await state.clear()
            return
        
        # Сохраняем в БД
        # Выполняем синхронную функцию _db_call_sync в отдельном потоке через asyncio.to_thread,
        # чтобы не блокировать основной поток бота во время работы с БД
        result = await asyncio.to_thread(_db_call_sync)
        if result:
            await message.answer(f"Канал <b>{title}</b> ({target_id}) успешно установлен как целевой для публикации.", parse_mode="HTML")
            logger.info(f"Канал {title} ({target_id}) успешно установлен")
        else:
            await message.answer("Не удалось установить канал. Попробуйте позже.")
            
    except Exception as e:
        await message.answer(f"Произошла ошибка при установке канала: {str(e)}")

    finally:
        await state.clear()



########## View All Target Channels ##########
@router.message(Command("get_all_targets"))
async def cmd_all_channels(message: Message):
    """
    Обработчик команды /get_all_targets для получения списка всех целевых каналов.
    
    Args:
        message (Message): Объект сообщения от пользователя
        
    Действия:
    1. Получает список всех целевых каналов из БД
    2. Если список пустой - отправляет сообщение об отсутствии каналов
    3. Формирует текстовый список с информацией о каждом канале:
       - ID канала
       - Название
       - Статус активности (✅ или ❌)
    4. Отправляет сформированный список пользователю
    """
    def _get_sync():
        """
        Returns:
            list: Список словарей с информацией о каналах.
                  Каждый словарь содержит:
                  - target_chat_id: ID канала
                  - target_title: Название канала  
                  - is_active: Статус активности
                  
        Note:
            Функция выполняется в отдельном потоке через asyncio.to_thread,
            чтобы не блокировать основной поток бота во время работы с БД.
        """
        return get_all_target_channels()
    
    all_target_channels = await asyncio.to_thread(_get_sync)
    if not all_target_channels:
        await message.answer("Целевых каналов нет.")
        return
    
    channels_list = ["<b>📋 Список всех целевых каналов:</b>"]
    for channel in all_target_channels:
        status = "✅ <b>Активен</b>" if channel['is_active'] else "❌ <b>Неактивен</b>"
        channels_list.append(f"<b>🆔 ID канала:</b> <code>{channel['target_chat_id']}</code>\n"
                           f"<b>📝 Название:</b> {channel['target_title']}\n"
                           f"<b>📊 Статус:</b> {status}\n")
    
    await message.answer("\n\n".join(channels_list), parse_mode="HTML")
    

########## Handle Target Channel Activation Status ##########
@router.message(Command("view_targets"))
async def cmd_view_targets(message: Message):
    def _get_target_sync():
        return get_active_target_info()
        
    active_target = await asyncio.to_thread(_get_target_sync)
    if active_target:
        await message.answer(
            f"📌 <b>Активный целевой канал:</b>\n\n"
            f"<b>🆔 ID канала:</b> <code>{active_target['target_chat_id']}</code>\n"
            f"<b>📝 Название:</b> {active_target['target_title']}",
            parse_mode="HTML"
        )
    else:
        await message.answer("❌ Активный целевой канал не установлен.")


########## Handle Target Channel Deactivation ##########
@router.message(Command("deactivate_target"))
async def cmd_deactivate_target(message: Message, state: FSMContext):
    """
    Обработчик команды /deactivate_target для деактивации целевого канала.
    
    Args:
        message (Message): Объект сообщения от пользователя
        state (FSMContext): Объект состояния FSM для хранения данных между этапами
        
    Действия:
    1. Отправляет пользователю запрос на ввод ID или @username канала
    2. Устанавливает состояние DeactivateTargetState.waiting_for_target_id
       для ожидания ввода идентификатора канала
    """
    await message.answer("Введите ID или @username канала для деактивации:")
    await state.set_state(DeactivateTargetState.waiting_for_target_id_str)


@router.message(DeactivateTargetState.waiting_for_target_id_str)
async def process_deactivate_target(message: Message, state: FSMContext):
    """
    Обработчик для получения ID или @username канала для деактивации.

    Args:
        message (Message): Объект сообщения от пользователя
        state (FSMContext): Объект состояния FSM для хранения данных между этапами

    Действия:
    1. Получает ID канала из сообщения
    2. Проверяет корректность введенного ID
    3. Деактивирует целевой канал в БД
    4. Отправляет пользователю сообщение об успешной деактивации
    5. Очищает состояние FSM
    """
    target_chat_id_str = message.text.strip()

    def _deactivate_sync():
        return deactivate_target_by_id(target_chat_id_str)

    # Проверяем, что введенный ID не пустой
    if not target_chat_id_str:
        await message.answer("❌ Вы не ввели ID канала.")
        await state.clear()
        return
    
    # Пытаемся деактивировать канал в БД
    try:
        # Вызываем функцию деактивации из модуля database.channels
        success = await asyncio.to_thread(_deactivate_sync)
        
        if success:
            await message.answer(f"✅ Целевой канал с ID {target_chat_id_str} успешно деактивирован.")
        else:
            await message.answer(f"❌ Канал с указанным ID не найден или уже деактивирован.")
    except Exception as e:
        await message.answer(f"❌ Произошла ошибка при деактивации канала: {str(e)}")
    
    # Очищаем состояние FSM
    await state.clear()
    

########## Delete Target Channel ##########
@router.message(Command("delete_target"))
async def cmd_delete_target(message:Message, state:FSMContext):
    """
    Обработчик команды /delete_target для удаления целевого канала.
    
    Args:
        message (Message): Объект сообщения от пользователя
        state (FSMContext): Контекст состояния FSM для хранения данных
    
    Действия:
    1. Отправляет пользователю запрос на ввод ID канала для удаления
    2. Устанавливает состояние DeleteTargetState.waiting_for_target_id
       для ожидания ввода идентификатора канала
    """
    await message.answer("Введите ID канала для удаления:")
    await state.set_state(DeleteTargetState.waiting_for_target_id_str)


@router.message(DeleteTargetState.waiting_for_target_id_str)
async def process_delete_target(message:Message, state:FSMContext):
    """
    Обработчик для получения ID канала и его удаления.

    Args:
        message (Message): Объект сообщения от пользователя
        state (FSMContext): Объект состояния FSM для хранения данных между этапами

    Действия:
    1. Получает ID канала из сообщения
    2. Проверяет корректность введенного ID
    3. Удаляет целевой канал из БД
    4. Отправляет пользователю сообщение о результате операции
    5. Очищает состояние FSM
    """
    target_chat_id_str = message.text.strip()

    def _delete_sync():
            return delete_target_channel(target_chat_id_str)

    if not target_chat_id_str:
        await message.answer("❌ Вы не ввели ID канала.")
        await state.clear()
        return

    try:
        success = await asyncio.to_thread(_delete_sync)

        if success:
            await message.answer(f"✅ Целевой канал с ID {target_chat_id_str} успешно удален.")
        else:
            await message.answer(f"❌ Канал с указанным ID не найден или уже удален.")
    except Exception as e:
        await message.answer(f"❌ Произошла ошибка при удалении канала: {str(e)}")
    
    await state.clear()


########## Activate Target Channel ##########
@router.message(Command("activate_target"))
async def cmd_activate_target(message:Message, state:FSMContext):
    """
    Обработчик команды /activate_target для активации целевого канала.
    """
    await message.answer("Сейчас может быть только один активный целевой канал. Мульти-задачность пока не поддерживается.")
    await message.answer("Введите ID канала для активации:")
    await state.set_state(ActivateTargetState.waiting_for_target_id_str)


@router.message(ActivateTargetState.waiting_for_target_id_str)
async def process_activate_target(message:Message, state:FSMContext):
    """
    Обработчик для получения ID канала и его активации.

    Args:
        message (Message): Объект сообщения от пользователя
        state (FSMContext): Объект состояния FSM для хранения данных между этапами

    Действия:
    1. Получает ID канала из сообщения
    2. Проверяет корректность введенного ID
    3. Активирует целевой канал в БД
    4. Отправляет пользователю сообщение о результате операции
    5. Очищает состояние FSM
    """
    target_chat_id_str = message.text.strip()

    def _activate_sync():
        return activate_target_by_id(target_chat_id_str)
    
    if not target_chat_id_str:
        await message.answer("❌ Вы не ввели ID канала.")
        await state.clear()
        return

    try:
        success = await asyncio.to_thread(_activate_sync)

        if success:
            await message.answer(f"✅ Целевой канал с ID {target_chat_id_str} успешно активирован.")
        else:
            await message.answer(f"❌ Канал с указанным ID не найден или уже активирован.")
    except Exception as e:
        await message.answer(f"❌ Произошла ошибка при активации канала: {str(e)}")


# TODO:
# - Добавить проверку на наличие канала в базе данных перед деактивацией целевого канала.
# - Добавить проверку на наличие канала в базе данных перед удалением целевого канала.
# - Добавить проверку на наличие канала в базе данных перед получением информации о целевом канале.
# - Добавить проверку на наличие канала в базе данных перед получением списка всех целевых каналов.
# - Добавить проверку на наличие канала в базе данных перед получением информации о целевом канале.

