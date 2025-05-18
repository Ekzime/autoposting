import logging
import asyncio

# Библиотеки для работы с ботом
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

# Тексты для сообщений
from telegram.texts.text_for_messages import text_for_set_new_target

# Библиотеки для работы с базой данных
from database.channels import (
    set_active_target, 
    get_active_target_chat_id_str,
    deactivate_target_by_id,
    get_active_target_info,
    get_all_target_channels,
    delete_target_channel
)

# Настройка логгера
logger = logging.getLogger(__name__)

router = Router()


class SetChannelState(StatesGroup):
    """Состояния для процесса установки нового целевого канала"""
    # Состояние ожидания ID канала или username
    waiting_for_channel_id = State()
    # Состояние ожидания названия канала
    waiting_for_title = State() 


class DeactivateTargetState(StatesGroup):
    """Состояния для процесса деактивации целевого канала"""
    waiting_for_target_id = State()

class DeleteTargetState(StatesGroup):
    """Состояния для процесса удаления целевого канала"""
    waiting_for_target_id = State()


#######################################################################
#                                                                     #
#                    Set New Target Channel                           #
#                                                                     #
#######################################################################
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
    await message.answer(text_for_set_new_target, parse_mode="HTML")
    await message.answer("Введите ID канала или @username:")
    await state.set_state(SetChannelState.waiting_for_channel_id)


@router.message(SetChannelState.waiting_for_channel_id)
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
    channel_id = message.text.strip()
    
    # Проверка на пустой ввод
    if not channel_id:
        await message.answer("Вы отправили пустое сообщение. Пожалуйста, введите ID канала или @username.", parse_mode="HTML")
        return
    
    try:
        # Пробуем преобразовать в число для случая с ID канала
        try:
            numeric_id = int(channel_id)
            logger.info(f"Получен числовой ID канала: {numeric_id}")
            target_id = str(numeric_id)
            # Предлагаем базовое название для числового ID
            suggested_title = f"Channel {numeric_id}"
        except ValueError:
            # Если не получилось преобразовать в число, значит это username
            if channel_id.startswith('@'):
                target_id = channel_id
            else:
                target_id = f"@{channel_id}"
            # Предлагаем юзернейм как базовое название
            suggested_title = channel_id
            logger.info(f"Получен username канала: {target_id}")
        
        # Сохраняем ID в состоянии FSM
        await state.update_data(target_id=target_id, suggested_title=suggested_title)
        
        # Переходим к вводу названия
        await message.answer(f"Теперь введите название для канала для отображения в боте {target_id}:")
        await state.set_state(SetChannelState.waiting_for_title)

    except Exception as e:
        await message.answer(f"Произошла ошибка при обработке ID канала: {str(e)}")
        logger.error(f"Ошибка при обработке ID канала: {e}")
        await state.clear()


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
    4. Сохраняет канал в базу данных
    5. Очищает состояние FSM
    
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
        logger.info("Состояние очищено")

#######################################################################
#                                                                     #
#                    View All Target Channels                         #
#                                                                     #
#######################################################################
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
    all_target_channels = get_all_target_channels()
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
    
#######################################################################
#                                                                     #
#              Handle Target Channel Activation Status                #
#                                                                     #
#######################################################################
@router.message(Command("view_targets"))
async def cmd_view_targets(message: Message):
    """
    Обработчик команды /get_active_target для получения информации о целевых каналов.
    
    Args:
        message (Message): Объект сообщения от пользователя
        
    Действия:
    1. Получает информацию об активном канале из БД
    2. Если активный канал найден - отправляет информацию о нем
    3. Если активного канала нет - отправляет соответствующее сообщение
    """
    active_target = get_active_target_info()
    if active_target:
        await message.answer(
            f"📌 <b>Активный целевой канал:</b>\n\n"
            f"<b>🆔 ID канала:</b> <code>{active_target.target_chat_id}</code>\n"
            f"<b>📝 Название:</b> {active_target.target_title}",
            parse_mode="HTML"
        )
    else:
        await message.answer("❌ Активный целевой канал не установлен.")

#######################################################################
#                                                                     #
#              Handle Target Channel Deactivation                     #
#                                                                     #
#######################################################################
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
    await state.set_state(DeactivateTargetState.waiting_for_target_id)


@router.message(DeactivateTargetState.waiting_for_target_id)
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
    # Проверяем, что введенный ID не пустой
    if not target_chat_id_str:
        await message.answer("❌ Вы не ввели ID канала.")
        await state.clear()
        return
    
    # Пытаемся деактивировать канал в БД
    try:
        # Вызываем функцию деактивации из модуля database.channels
        success = deactivate_target_by_id(target_chat_id_str)
        
        if success:
            await message.answer(f"✅ Целевой канал с ID {target_chat_id_str} успешно деактивирован.")
        else:
            await message.answer(f"❌ Канал с указанным ID не найден или уже деактивирован.")
    except Exception as e:
        await message.answer(f"❌ Произошла ошибка при деактивации канала: {str(e)}")
    
    # Очищаем состояние FSM
    await state.clear()
    

#######################################################################
#                                                                     #
#                    Delete Target Channel                            #
#                                                                     #
#######################################################################
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
    await state.set_state(DeleteTargetState.waiting_for_target_id)


@router.message(DeleteTargetState.waiting_for_target_id)
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

    if not target_chat_id_str:
        await message.answer("❌ Вы не ввели ID канала.")
        await state.clear()
        return

    try:
        success = delete_target_channel(target_chat_id_str)

        if success:
            await message.answer(f"✅ Целевой канал с ID {target_chat_id_str} успешно удален.")
        else:
            await message.answer(f"❌ Канал с указанным ID не найден или уже удален.")
    except Exception as e:
        await message.answer(f"❌ Произошла ошибка при удалении канала: {str(e)}")
    
    await state.clear()


# TODO:
# - Добавить проверку на наличие канала в базе данных перед установкой нового целевого канала.
# - Добавить проверку на наличие канала в базе данных перед деактивацией целевого канала.
# - Добавить проверку на наличие канала в базе данных перед удалением целевого канала.
# - Добавить проверку на наличие канала в базе данных перед получением информации о целевом канале.
# - Добавить проверку на наличие канала в базе данных перед получением списка всех целевых каналов.
# - Добавить проверку на наличие канала в базе данных перед получением информации о целевом канале.


