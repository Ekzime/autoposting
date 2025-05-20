import logging
import asyncio

# Библиотеки для работы с ботом
from aiogram import Router, F, Bot
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

# Импорт настроек
from config import settings

# Тексты для сообщений
from telegram.bot.texts.text_for_messages import (
    text_for_set_new_target,
    bot_dont_can_send_message_to_channel_text
)

# Библиотеки для работы с базой данных
from database.repositories import posting_target_repository as pt_repo

# Настройка логгера
logger = logging.getLogger(__name__)

router = Router()

#######################################################################
#                                                                     #
#                    FSM States                                       #
#                                                                     #
#######################################################################
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
        """
        return pt_repo.set_active_target(target_id, title)

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
    def _get_sync():
        """
        Returns:
            list: Список словарей с информацией о каналах.
        """
        return pt_repo.get_all_target_channels()
    
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
    
#######################################################################
#                                                                     #
#              Handle Target Channel Activation Status                #
#                                                                     #
#######################################################################
@router.message(Command("view_targets"))
async def cmd_view_targets(message: Message):
    def _get_target_sync():
        return pt_repo.get_active_target_info()
        
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
    """
    try:
        # Получаем список всех целевых каналов
        def _get_all_targets_sync():
            return pt_repo.get_all_target_channels()
            
        targets = await asyncio.to_thread(_get_all_targets_sync)
        
        if not targets:
            await message.answer("❌ <b>Нет доступных целевых каналов</b>\n\nСначала добавьте целевой канал.", parse_mode="HTML")
            return
        
        # Формируем список целевых каналов для выбора
        targets_list = "\n".join([
            f"📌 <code>{target['id']}</code>: {target['target_title'] or target['target_chat_id']} - "
            f"{'✅ Активен' if target['is_active'] else '❌ Неактивен'}"
            for target in targets
        ])
        
        await message.answer(
            "🔴 <b>Деактивация целевого канала</b>\n\n"
            "Выберите ID канала для деактивации:\n\n"
            f"{targets_list}\n\n"
            "ℹ️ Отправьте ID канала числом.",
            parse_mode="HTML"
        )
        
        await state.set_state(DeactivateTargetState.waiting_for_target_id_str)
    except Exception as e:
        logger.error(f"Ошибка при запросе списка каналов для деактивации: {e}")
        await message.answer("❌ <b>Произошла ошибка при выполнении команды.</b>", parse_mode="HTML")


@router.message(DeactivateTargetState.waiting_for_target_id_str)
async def process_deactivate_target(message: Message, state: FSMContext):
    """
    Обработчик для получения ID или @username канала для деактивации.

    Args:
        message (Message): Объект сообщения от пользователя
        state (FSMContext): Объект состояния FSM для хранения данных между этапами
    """
    try:
        # Проверяем, что введен корректный ID
        if not message.text.isdigit():
            await message.answer(
                "⚠️ <b>Ошибка ввода</b>\n\n"
                "ID канала должен быть числом. Пожалуйста, введите корректный ID.",
                parse_mode="HTML"
            )
            return
            
        target_id = int(message.text.strip())
        
        def _deactivate_sync():
            # Получаем сначала информацию о канале, чтобы узнать его chat_id
            def _get_all_targets_sync():
                return pt_repo.get_all_target_channels()
                
            all_targets = _get_all_targets_sync()
            target_chat_id = None
            
            # Находим chat_id по ID канала
            for target in all_targets:
                if target['id'] == target_id:
                    target_chat_id = target['target_chat_id']
                    break
            
            if not target_chat_id:
                return False
                
            # Деактивируем канал по его chat_id
            return pt_repo.deactivate_target_by_id(target_chat_id)

        # Выполняем деактивацию канала
        success = await asyncio.to_thread(_deactivate_sync)
        
        if success:
            await message.answer(
                f"✅ <b>Канал успешно деактивирован</b>\n\n"
                f"Целевой канал с ID {target_id} больше не является активным.",
                parse_mode="HTML"
            )
        else:
            await message.answer(
                f"❌ <b>Ошибка деактивации</b>\n\n"
                f"Канал с ID {target_id} не найден или уже деактивирован.",
                parse_mode="HTML"
            )
    except Exception as e:
        logger.error(f"Ошибка при деактивации канала: {e}")
        await message.answer(
            "❌ <b>Произошла ошибка при деактивации канала</b>",
            parse_mode="HTML"
        )
    
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
    """
    try:
        # Получаем список всех целевых каналов
        def _get_all_targets_sync():
            return pt_repo.get_all_target_channels()
            
        targets = await asyncio.to_thread(_get_all_targets_sync)
        
        if not targets:
            await message.answer("❌ <b>Нет доступных целевых каналов</b>\n\nНечего удалять.", parse_mode="HTML")
            return
        
        # Формируем список целевых каналов для выбора
        targets_list = "\n".join([
            f"📌 <code>{target['id']}</code>: {target['target_title'] or target['target_chat_id']} - "
            f"{'✅ Активен' if target['is_active'] else '❌ Неактивен'}"
            for target in targets
        ])
        
        await message.answer(
            "🗑️ <b>Удаление целевого канала</b>\n\n"
            "Выберите ID канала для удаления:\n\n"
            f"{targets_list}\n\n"
            "⚠️ <b>Внимание!</b> Это действие необратимо!\n"
            "ℹ️ Отправьте ID канала числом.",
            parse_mode="HTML"
        )
        
        await state.set_state(DeleteTargetState.waiting_for_target_id_str)
    except Exception as e:
        logger.error(f"Ошибка при запросе списка каналов для удаления: {e}")
        await message.answer("❌ <b>Произошла ошибка при выполнении команды.</b>", parse_mode="HTML")


@router.message(DeleteTargetState.waiting_for_target_id_str)
async def process_delete_target(message:Message, state:FSMContext):
    """
    Обработчик для получения ID канала и его удаления.
    """
    try:
        # Проверяем, что введен корректный ID
        if not message.text.isdigit():
            await message.answer(
                "⚠️ <b>Ошибка ввода</b>\n\n"
                "ID канала должен быть числом. Пожалуйста, введите корректный ID.",
                parse_mode="HTML"
            )
            return
            
        target_id = int(message.text.strip())
        
        def _delete_sync():
            # Получаем сначала информацию о канале, чтобы узнать его chat_id
            def _get_all_targets_sync():
                return pt_repo.get_all_target_channels()
                
            all_targets = _get_all_targets_sync()
            target_chat_id = None
            target_title = None
            
            # Находим chat_id по ID канала
            for target in all_targets:
                if target['id'] == target_id:
                    target_chat_id = target['target_chat_id']
                    target_title = target['target_title']
                    break
            
            if not target_chat_id:
                return False, None
                
            # Удаляем канал по его chat_id
            success = pt_repo.delete_target_channel(target_chat_id)
            return success, target_title

        # Выполняем удаление канала
        result = await asyncio.to_thread(_delete_sync)
        success, target_title = result
        
        if success:
            await message.answer(
                f"✅ <b>Канал успешно удален</b>\n\n"
                f"Целевой канал с ID {target_id}"
                + (f" ({target_title})" if target_title else "")
                + " был удален из базы данных.",
                parse_mode="HTML"
            )
        else:
            await message.answer(
                f"❌ <b>Ошибка удаления</b>\n\n"
                f"Канал с ID {target_id} не найден или не может быть удален.",
                parse_mode="HTML"
            )
    except Exception as e:
        logger.error(f"Ошибка при удалении канала: {e}")
        await message.answer(
            "❌ <b>Произошла ошибка при удалении канала</b>",
            parse_mode="HTML"
        )
    
    # Очищаем состояние FSM
    await state.clear()

#######################################################################
#                                                                     #
#                    Activate Target Channel                          #
#                                                                     #
#######################################################################
@router.message(Command("activate_target"))
async def cmd_activate_target(message:Message, state:FSMContext):
    """
    Обработчик команды /activate_target для активации целевого канала.
    """
    try:
        # Получаем список всех целевых каналов
        def _get_all_targets_sync():
            return pt_repo.get_all_target_channels()
            
        targets = await asyncio.to_thread(_get_all_targets_sync)
        
        if not targets:
            await message.answer("❌ <b>Нет доступных целевых каналов</b>\n\nСначала добавьте целевой канал.", parse_mode="HTML")
            return
        
        # Формируем список целевых каналов для выбора
        targets_list = "\n".join([
            f"📌 <code>{target['id']}</code>: {target['target_title'] or target['target_chat_id']} - "
            f"{'✅ Активен' if target['is_active'] else '❌ Неактивен'}"
            for target in targets
        ])
        
        await message.answer(
            "🟢 <b>Активация целевого канала</b>\n\n"
            "Сейчас может быть только один активный целевой канал. Предыдущий активный канал будет деактивирован.\n\n"
            "Выберите ID канала для активации:\n\n"
            f"{targets_list}\n\n"
            "ℹ️ Отправьте ID канала числом.",
            parse_mode="HTML"
        )
        
        await state.set_state(ActivateTargetState.waiting_for_target_id_str)
    except Exception as e:
        logger.error(f"Ошибка при запросе списка каналов для активации: {e}")
        await message.answer("❌ <b>Произошла ошибка при выполнении команды.</b>", parse_mode="HTML")


@router.message(ActivateTargetState.waiting_for_target_id_str)
async def process_activate_target(message:Message, state:FSMContext):
    """
    Обработчик для получения ID канала и его активации.
    """
    try:
        # Проверяем, что введен корректный ID
        if not message.text.isdigit():
            await message.answer(
                "⚠️ <b>Ошибка ввода</b>\n\n"
                "ID канала должен быть числом. Пожалуйста, введите корректный ID.",
                parse_mode="HTML"
            )
            return
            
        target_id = int(message.text.strip())
        
        def _activate_sync():
            # Получаем сначала информацию о канале, чтобы узнать его chat_id
            def _get_all_targets_sync():
                return pt_repo.get_all_target_channels()
                
            all_targets = _get_all_targets_sync()
            target_chat_id = None
            target_title = None
            
            # Находим chat_id по ID канала
            for target in all_targets:
                if target['id'] == target_id:
                    target_chat_id = target['target_chat_id']
                    target_title = target['target_title']
                    break
            
            if not target_chat_id:
                return False, None
                
            # Активируем канал по его chat_id
            success = pt_repo.activate_target_by_id(target_chat_id)
            return success, target_title

        # Выполняем активацию канала
        result = await asyncio.to_thread(_activate_sync)
        success, target_title = result
        
        if success:
            await message.answer(
                f"✅ <b>Канал успешно активирован</b>\n\n"
                f"Целевой канал с ID {target_id}"
                + (f" ({target_title})" if target_title else "")
                + " установлен как активный.\n"
                f"Все остальные каналы деактивированы.",
                parse_mode="HTML"
            )
        else:
            await message.answer(
                f"❌ <b>Ошибка активации</b>\n\n"
                f"Канал с ID {target_id} не найден или не может быть активирован.",
                parse_mode="HTML"
            )
    except Exception as e:
        logger.error(f"Ошибка при активации канала: {e}")
        await message.answer(
            "❌ <b>Произошла ошибка при активации канала</b>",
            parse_mode="HTML"
        )
    
    # Очищаем состояние FSM
    await state.clear()


# TODO:
# - Добавить проверку на наличие канала в базе данных перед деактивацией целевого канала.
# - Добавить проверку на наличие канала в базе данных перед удалением целевого канала.
# - Добавить проверку на наличие канала в базе данных перед получением информации о целевом канале.
# - Добавить проверку на наличие канала в базе данных перед получением списка всех целевых каналов.
# - Добавить проверку на наличие канала в базе данных перед получением информации о целевом канале.

