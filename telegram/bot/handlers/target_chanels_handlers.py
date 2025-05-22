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
from database.dao.parsing_source_repository import ParsingSourceRepository

# Импорт функции для обновления настроек постинга
from telegram.bot.utils.trigger_utils import trigger_posting_settings_update

# Настройка логгера
logger = logging.getLogger(__name__)

router = Router()

# Инициализируем репозиторий источников
ps_repo = ParsingSourceRepository()

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

class ToggleTargetState(StatesGroup):
    """Состояния для процесса включения/выключения целевого канала"""
    waiting_for_target_id_str = State()
    waiting_for_status = State()

class UpdateTargetState(StatesGroup):
    """Состояния для процесса обновления целевого канала"""
    waiting_for_target_id_str = State()
    waiting_for_new_title = State()


#######################################################################
#                                                                     #
#                    Set New Target Channel                           #
#                                                                     #
#######################################################################
@router.message(Command("add_target"))
async def cmd_set_channel(message: Message, state: FSMContext):
    """
    Обработчик команды /add_target для добавления нового канала.
    
    Args:
        message (Message): Объект сообщения от пользователя
        state (FSMContext): Контекст состояния FSM для хранения данных
    
    Действия:
    1. Логирует получение команды
    2. Отправляет инструкцию пользователю
    3. Запрашивает ID канала или username
    4. Устанавливает состояние ожидания ID канала
    """
    logger.info(f"Получена команда /add_target от пользователя {message.from_user.id}")
    
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
            
            # Запускаем обновление настроек постинга
            trigger_posting_settings_update()
            logger.info("Отправлен сигнал обновления настроек постинга")
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
@router.message(Command("all_targets", "targets", "t"))
async def cmd_all_targets(message: Message):
    """
    Обработчик команды /all_targets (/targets, /t) для получения списка всех целевых каналов.
    Добавлена возможность фильтрации по активности.
    
    Args:
        message (Message): Объект сообщения от пользователя
    """
    # Определяем, показывать ли только активные каналы
    show_only_active = False
    if message.text.lower().strip() in ["/active", "/active_targets"]:
        show_only_active = True
    
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
    
    # Фильтруем каналы по активности, если нужно
    if show_only_active:
        all_target_channels = [channel for channel in all_target_channels if channel['is_active']]
        if not all_target_channels:
            await message.answer("Активных целевых каналов нет.")
            return
        channels_list = ["<b>📋 Список активных целевых каналов:</b>"]
    else:
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
@router.message(Command("activate_target", "activate"))
async def cmd_activate_target(message: Message, state: FSMContext):
    """
    Обработчик команды /activate_target (/activate) для активации целевого канала или нескольких каналов.
    Объединяет функциональность команд activate_target и activate_multiple.
    
    Args:
        message (Message): Объект сообщения от пользователя
        state (FSMContext): Контекст состояния FSM
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
            "Выберите ID канала для активации:\n\n"
            f"{targets_list}\n\n"
            "ℹ️ Отправьте ID канала числом или через запятую для активации нескольких каналов.",
            parse_mode="HTML"
        )
        
        await state.set_state(ActivateTargetState.waiting_for_target_id_str)
    except Exception as e:
        logger.error(f"Ошибка при запросе списка каналов для активации: {e}")
        await message.answer("❌ <b>Произошла ошибка при выполнении команды.</b>", parse_mode="HTML")


@router.message(ActivateTargetState.waiting_for_target_id_str)
async def process_activate_target(message:Message, state:FSMContext):
    """
    Обработчик для активации целевого канала или нескольких каналов.
    
    Args:
        message (Message): Объект сообщения от пользователя с ID канала(ов) для активации
        state (FSMContext): Контекст состояния FSM
    """
    # Проверяем, есть ли запятые в сообщении (несколько ID)
    if "," in message.text:
        # Несколько ID каналов через запятую
        target_ids = [target_id.strip() for target_id in message.text.split(",")]
        activated_channels = []
        failed_channels = []
        
        for target_id in target_ids:
            try:
                # Получаем информацию о каналах
                def _activate_sync(tid):
                    # Получаем сначала информацию о канале, чтобы узнать его chat_id
                    def _get_all_targets_sync():
                        return pt_repo.get_all_target_channels()
                        
                    all_targets = _get_all_targets_sync()
                    target_info = None
                    
                    # Проверяем, существует ли канал с таким ID
                    for target in all_targets:
                        if str(target['id']) == tid:
                            target_info = target
                            break
                            
                    if not target_info:
                        return False, f"Не найден канал с ID {tid}"
                        
                    # Активируем канал - теперь метод позволяет активировать без деактивации других
                    success = pt_repo.toggle_target_active_status(target_info['target_chat_id'], True)
                    
                    if not success:
                        return False, f"Не удалось активировать канал {target_info['target_title']}"
                        
                    return True, target_info
                
                # Выполняем синхронную функцию через asyncio.to_thread
                success, result = await asyncio.to_thread(lambda: _activate_sync(target_id))
                
                if success:
                    activated_channels.append(f"{result['target_title']} ({result['target_chat_id']})")
                else:
                    failed_channels.append(f"{target_id}: {result}")
                    
            except Exception as e:
                failed_channels.append(f"{target_id}: {str(e)}")
        
        # Формируем сообщение с результатами
        result_message = []
        if activated_channels:
            result_message.append(f"✅ <b>Успешно активированы каналы:</b>\n{', '.join(activated_channels)}")
        if failed_channels:
            result_message.append(f"❌ <b>Не удалось активировать:</b>\n{', '.join(failed_channels)}")
            
        await message.answer("\n\n".join(result_message), parse_mode="HTML")
        logger.info(f"Активировано несколько каналов: {', '.join(activated_channels)}")
        
        # Запускаем обновление настроек постинга
        trigger_posting_settings_update()
        logger.info("Отправлен сигнал обновления настроек постинга после активации нескольких каналов")
    else:
        # Одиночный ID канала - используем существующую логику
        target_id = message.text.strip()
        
        try:
            # Получаем информацию о каналах
            def _activate_sync():
                # Получаем сначала информацию о канале, чтобы узнать его chat_id
                def _get_all_targets_sync():
                    return pt_repo.get_all_target_channels()
                    
                all_targets = _get_all_targets_sync()
                target_info = None
                
                # Проверяем, существует ли канал с таким ID
                for target in all_targets:
                    if str(target['id']) == target_id:
                        target_info = target
                        break
                        
                if not target_info:
                    return False, f"Не найден канал с ID {target_id}"
                    
                # Активируем канал - теперь этот метод не деактивирует другие каналы
                success = pt_repo.activate_target_by_id(target_info['target_chat_id'])
                
                if not success:
                    return False, f"Не удалось активировать канал {target_info['target_title']}"
                    
                return True, target_info
            
            # Выполняем синхронную функцию через asyncio.to_thread
            success, result = await asyncio.to_thread(_activate_sync)
            
            if success:
                await message.answer(f"Канал <b>{result['target_title']}</b> успешно активирован.", parse_mode="HTML")
                logger.info(f"Канал {result['target_title']} ({result['target_chat_id']}) активирован")
                
                # Запускаем обновление настроек постинга
                trigger_posting_settings_update()
                logger.info("Отправлен сигнал обновления настроек постинга после активации канала")
            else:
                await message.answer(result)
                
        except Exception as e:
            await message.answer(f"Произошла ошибка при активации канала: {str(e)}")
            logger.error(f"Ошибка при активации канала: {e}")
        
        finally:
            await state.clear()

#######################################################################
#                                                                     #
#                    Toggle Target Channel                            #
#                                                                     #
#######################################################################
@router.message(Command("toggle_target"))
async def cmd_toggle_target(message: Message, state: FSMContext):
    """
    Обработчик команды /toggle_target для включения/выключения целевого канала.
    
    Args:
        message (Message): Объект сообщения от пользователя
        state (FSMContext): Контекст состояния FSM
        
    Действия:
    1. Получает список всех целевых каналов из БД
    2. Если список пустой - отправляет сообщение об отсутствии каналов
    3. Формирует сообщение с запросом выбора канала для переключения статуса
    4. Устанавливает состояние ожидания ID канала
    """
    def _get_all_targets_sync():
        return pt_repo.get_all_target_channels()
    
    all_target_channels = await asyncio.to_thread(_get_all_targets_sync)
    if not all_target_channels:
        await message.answer("Целевых каналов нет. Используйте /add_target, чтобы добавить канал.")
        return
    
    channels_list = ["<b>Выберите канал для включения/выключения:</b>"]
    for channel in all_target_channels:
        status = "✅ Активен" if channel['is_active'] else "❌ Неактивен"
        channels_list.append(f"ID: <code>{channel['id']}</code> - {channel['target_title']} ({status})")
    
    await message.answer("\n".join(channels_list), parse_mode="HTML")
    await message.answer("Введите ID канала для переключения статуса:")
    await state.set_state(ToggleTargetState.waiting_for_target_id_str)


@router.message(ToggleTargetState.waiting_for_target_id_str)
async def process_toggle_target_id(message: Message, state: FSMContext):
    """
    Обработчик для получения ID канала для переключения статуса.
    
    Args:
        message (Message): Объект сообщения от пользователя
        state (FSMContext): Контекст состояния FSM
        
    Действия:
    1. Проверяет корректность введенного ID канала
    2. Сохраняет ID канала в состоянии FSM
    3. Запрашивает новый статус канала (включить/выключить)
    """
    target_id = message.text.strip()
    
    if not target_id.isdigit():
        await message.answer("ID канала должен быть числом. Пожалуйста, введите корректный ID:")
        return
    
    # Проверяем существование канала
    def _check_target_exists():
        all_targets = pt_repo.get_all_target_channels()
        for target in all_targets:
            if str(target['id']) == target_id:
                return True, target
        return False, None
    
    exists, target_info = await asyncio.to_thread(_check_target_exists)
    
    if not exists:
        await message.answer(f"Канал с ID {target_id} не найден. Пожалуйста, введите корректный ID:")
        return
    
    # Сохраняем информацию о канале
    await state.update_data(target_id=target_id, target_info=target_info)
    
    current_status = "активен" if target_info['is_active'] else "неактивен"
    new_status = "деактивировать" if target_info['is_active'] else "активировать"
    
    await message.answer(
        f"Канал <b>{target_info['target_title']}</b> сейчас {current_status}.\n"
        f"Хотите {new_status} этот канал? (да/нет)",
        parse_mode="HTML"
    )
    await state.set_state(ToggleTargetState.waiting_for_status)


@router.message(ToggleTargetState.waiting_for_status)
async def process_toggle_target_status(message: Message, state: FSMContext):
    """
    Обработчик для получения подтверждения изменения статуса канала.
    
    Args:
        message (Message): Объект сообщения от пользователя
        state (FSMContext): Контекст состояния FSM
        
    Действия:
    1. Проверяет ответ пользователя (да/нет)
    2. Если ответ положительный - переключает статус канала
    3. Отправляет результат операции
    4. Очищает состояние FSM
    """
    response = message.text.strip().lower()
    
    if response not in ["да", "нет", "yes", "no"]:
        await message.answer("Пожалуйста, ответьте 'да' или 'нет':")
        return
    
    # Если ответ отрицательный, прекращаем операцию
    if response in ["нет", "no"]:
        await message.answer("Операция отменена.")
        await state.clear()
        return
    
    # Получаем данные из состояния
    data = await state.get_data()
    target_id = data.get("target_id")
    target_info = data.get("target_info")
    
    if not target_id or not target_info:
        await message.answer("Произошла ошибка: данные о канале потеряны. Пожалуйста, начните заново.")
        await state.clear()
        return
    
    # Определяем новый статус (инвертируем текущий)
    new_status = not target_info['is_active']
    status_text = "активирован" if new_status else "деактивирован"
    
    def _toggle_status():
        return pt_repo.toggle_target_active_status(
            target_info['target_chat_id'], 
            new_status
        )
    
    try:
        success = await asyncio.to_thread(_toggle_status)
        
        if success:
            await message.answer(
                f"Канал <b>{target_info['target_title']}</b> успешно {status_text}.",
                parse_mode="HTML"
            )
            logger.info(f"Канал {target_info['target_title']} ({target_info['target_chat_id']}) {status_text}")
            
            # Запускаем обновление настроек постинга
            trigger_posting_settings_update()
            logger.info(f"Отправлен сигнал обновления настроек постинга после изменения статуса канала")
        else:
            await message.answer(f"Не удалось изменить статус канала {target_info['target_title']}.")
    
    except Exception as e:
        await message.answer(f"Произошла ошибка при изменении статуса канала: {str(e)}")
        logger.error(f"Ошибка при изменении статуса канала: {e}")
    
    finally:
        await state.clear()

#######################################################################
#                                                                     #
#                    Update Target Channel                            #
#                                                                     #
#######################################################################
@router.message(Command("update_target"))
async def cmd_update_target(message: Message, state: FSMContext):
    """
    Обработчик команды /update_target для обновления информации о целевом канале.
    
    Args:
        message (Message): Объект сообщения от пользователя
        state (FSMContext): Контекст состояния FSM
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
            "✏️ <b>Обновление целевого канала</b>\n\n"
            "Выберите ID канала для обновления:\n\n"
            f"{targets_list}\n\n"
            "ℹ️ Отправьте ID канала числом.",
            parse_mode="HTML"
        )
        
        await state.set_state(UpdateTargetState.waiting_for_target_id_str)
    except Exception as e:
        logger.error(f"Ошибка при запросе списка каналов для обновления: {e}")
        await message.answer("❌ <b>Произошла ошибка при выполнении команды.</b>", parse_mode="HTML")


@router.message(UpdateTargetState.waiting_for_target_id_str)
async def process_update_target_id(message: Message, state: FSMContext):
    """
    Обработчик для получения ID канала для обновления.
    
    Args:
        message (Message): Объект сообщения от пользователя с ID канала
        state (FSMContext): Контекст состояния FSM
    """
    target_id = message.text.strip()
    
    if not target_id.isdigit():
        await message.answer("ID канала должен быть числом. Пожалуйста, введите корректный ID:")
        return
    
    # Проверяем существование канала
    def _check_target_exists():
        all_targets = pt_repo.get_all_target_channels()
        for target in all_targets:
            if str(target['id']) == target_id:
                return True, target
        return False, None
    
    exists, target_info = await asyncio.to_thread(_check_target_exists)
    
    if not exists:
        await message.answer(f"Канал с ID {target_id} не найден. Пожалуйста, введите корректный ID:")
        return
    
    # Сохраняем информацию о канале
    await state.update_data(target_id=target_id, target_info=target_info)
    
    await message.answer(
        f"Канал <b>{target_info['target_title']}</b> (ID: {target_id}).\n"
        "Введите новое название для канала:",
        parse_mode="HTML"
    )
    await state.set_state(UpdateTargetState.waiting_for_new_title)


@router.message(UpdateTargetState.waiting_for_new_title)
async def process_update_target_title(message: Message, state: FSMContext):
    """
    Обработчик для получения нового названия канала.
    
    Args:
        message (Message): Объект сообщения от пользователя с новым названием
        state (FSMContext): Контекст состояния FSM
    """
    new_title = message.text.strip()
    
    # Проверка на пустой ввод
    if not new_title:
        await message.answer("Вы отправили пустое название. Пожалуйста, введите понятное название для канала:")
        return
    
    # Получаем данные из состояния
    data = await state.get_data()
    target_info = data.get("target_info")
    
    if not target_info:
        await message.answer("Произошла ошибка: данные о канале потеряны. Пожалуйста, начните заново.")
        await state.clear()
        return
    
    def _update_target():
        return pt_repo.add_or_update_target(
            target_info['target_chat_id'],
            new_title,
            target_info['is_active']
        )
    
    try:
        result = await asyncio.to_thread(_update_target)
        
        if result:
            await message.answer(
                f"✅ Канал <b>{target_info['target_title']}</b> успешно обновлен.\n"
                f"Новое название: <b>{new_title}</b>",
                parse_mode="HTML"
            )
            logger.info(f"Канал {target_info['target_title']} ({target_info['target_chat_id']}) обновлен. Новое название: {new_title}")
            
            # Запускаем обновление настроек постинга
            trigger_posting_settings_update()
            logger.info("Отправлен сигнал обновления настроек постинга после обновления канала")
        else:
            await message.answer("❌ Не удалось обновить канал. Попробуйте позже.")
    
    except Exception as e:
        await message.answer(f"❌ Произошла ошибка при обновлении канала: {str(e)}")
        logger.error(f"Ошибка при обновлении канала: {e}")
    
    finally:
        await state.clear()

#######################################################################
#                                                                     #
#                    View Targets With Sources                        #
#                                                                     #
#######################################################################
@router.message(Command("targets_with_sources", "targets_sources", "ts"))
async def cmd_targets_with_sources(message: Message):
    """
    Обработчик команды /targets_with_sources для просмотра целевых каналов с прикрепленными источниками.
    
    Args:
        message (Message): Объект сообщения от пользователя
        
    Действия:
    1. Получает все целевые каналы
    2. Для каждого канала получает его источники
    3. Отображает структурированный список каналов с их источниками
    """
    try:
        # Получаем список всех целевых каналов
        def _get_targets_sync():
            return pt_repo.get_all_target_channels()
        
        all_targets = await asyncio.to_thread(_get_targets_sync)
        
        if not all_targets:
            await message.answer("📋 <b>Целевые каналы не найдены</b>\n\nИспользуйте /add_target, чтобы добавить целевой канал.", parse_mode="HTML")
            return
        
        # Формируем сообщение с каналами и источниками
        message_parts = ["🎯 <b>Целевые каналы и их источники:</b>\n"]
        
        for target in all_targets:
            # Получаем источники для текущего целевого канала
            def _get_sources_sync(target_id):
                return ps_repo.get_sources_for_target(target_id)
            
            sources = await asyncio.to_thread(lambda: _get_sources_sync(target['id']))
            
            # Добавляем информацию о целевом канале
            status = "✅ <b>Активен</b>" if target['is_active'] else "❌ <b>Неактивен</b>"
            target_info = [
                f"📌 <b>{target['target_title']}</b> (<code>{target['target_chat_id']}</code>)",
                f"📊 Статус: {status}"
            ]
            
            # Добавляем информацию об источниках
            if sources:
                target_info.append("\n📥 <b>Источники:</b>")
                for i, source in enumerate(sources, 1):
                    target_info.append(
                        f"  {i}. <code>{source['source_identifier']}</code>"
                        + (f" - {source['source_title']}" if source['source_title'] else "")
                    )
            else:
                target_info.append("\n⚠️ <i>Нет прикрепленных источников</i>")
            
            # Добавляем разделитель между каналами
            message_parts.append("\n".join(target_info) + "\n")
        
        # Добавляем информацию о командах
        message_parts.append(
            "\n<i>Используйте команды:</i>\n"
            "/add_target - добавить новый целевой канал\n"
            "/add_source - добавить источник к каналу\n"
            "/view_all_sources - посмотреть все источники"
        )
        
        await message.answer("\n".join(message_parts), parse_mode="HTML")
    
    except Exception as e:
        logger.error(f"Ошибка при получении целевых каналов с источниками: {e}")
        await message.answer("❌ <b>Произошла ошибка при выполнении команды.</b>", parse_mode="HTML")

