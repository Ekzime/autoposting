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

# Репозитории для работы с базой данных
from database.repositories import parsing_source_repository as ps_repo
from database.repositories import posting_target_repository as pt_repo

# Настройка логгера
logger = logging.getLogger(__name__)

router = Router()

#######################################################################
#                                                                     #
#                    FSM States                                       #
#                                                                     #
#######################################################################
class AddSourceStates(StatesGroup):
    choosing_target_for_source = State() 
    waiting_for_source_identifier = State()
    waiting_for_source_title = State()

class UpdateSourceStates(StatesGroup):
    waiting_for_source_id = State()
    waiting_for_new_identifier = State()
    waiting_for_new_title = State()
    asking_change_target = State()
    waiting_for_new_target = State()

class DeleteSourceStates(StatesGroup):
    waiting_for_source_id = State()
    confirming_deletion = State()

    
#######################################################################
#                                                                     #
#                    Handlers Add Source                              #
#                                                                     #
#######################################################################

@router.message(Command("add_source"))
async def cmd_add_source_command(message: Message, state: FSMContext):
    """
    Обработчик команды /add_source для добавления нового источника парсинга.
    
    Args:
        message (Message): Объект сообщения от пользователя, содержащий команду
        state (FSMContext): Объект состояния FSM для хранения данных между этапами
    
    Действия:
        1. Получает список всех целевых каналов из базы данных
        2. Проверяет наличие целевых каналов
        3. Формирует и отправляет список доступных целевых каналов
        4. Переводит FSM в состояние ожидания выбора целевого канала
    
    Raises:
        Exception: Логирует ошибку и отправляет сообщение пользователю при возникновении исключения
    """
    # Вспомогательная функция для синхронного получения списка целевых каналов
    def _sync_get_all_targets():
        return pt_repo.get_all_target_channels()
    
    try:
        # Получаем список всех целевых каналов асинхронно
        targets = await asyncio.to_thread(_sync_get_all_targets)
        
        # Если нет целевых каналов - сообщаем об этом
        if not targets:
            await message.answer("❌ <b>Нет доступных целевых каналов</b>\n\nСначала добавьте целевой канал.", parse_mode="HTML")
            return
        
        # Формируем список целевых каналов для отображения пользователю
        targets_list = "\n".join([
            f"📌 <code>{target['id']}</code>: {target['target_title'] or target['target_chat_id']}"
            for target in targets
        ])
        
        # Отправляем сообщение с инструкцией и списком каналов
        await message.answer(
            "🎯 <b>Добавление нового источника</b>\n\n"
            "Выберите ID целевого канала, для которого нужно добавить источник:\n\n"
            f"{targets_list}\n\n"
            "ℹ️ Отправьте ID канала числом.",
            parse_mode="HTML"
        )
        
        # Устанавливаем состояние ожидания выбора целевого канала
        await state.set_state(AddSourceStates.choosing_target_for_source)
        
    except Exception as e:
        # Логируем ошибку и сообщаем пользователю
        logger.error(f"Ошибка в команде add_source: {e}")
        await message.answer("❌ <b>Произошла ошибка при выполнении команды.</b>", parse_mode="HTML")

# Обработчик выбора целевого канала
@router.message(AddSourceStates.choosing_target_for_source)
async def process_target_choice(message: Message, state: FSMContext):
    """
    Обработчик выбора целевого канала для добавления источника парсинга.
    
    Args:
        message (Message): Объект сообщения от пользователя, содержащий ID целевого канала
        state (FSMContext): Объект состояния FSM для хранения данных между этапами
    
    Действия:
        1. Проверяет корректность введенного ID (должно быть числом)
        2. Сохраняет выбранный ID в состояние FSM
        3. Запрашивает у пользователя идентификатор источника
        4. Переводит FSM в состояние ожидания идентификатора источника
    
    Raises:
        ValueError: Если введенный ID не является числом
        Exception: Логирует ошибку и отправляет сообщение пользователю при возникновении проблем
    """
    try:
        # Преобразуем введенный ID в число
        target_id = int(message.text)
        
        # Сохраняем выбранный ID в состояние
        await state.update_data(chosen_target_id=target_id)
        
        # Запрашиваем идентификатор источника
        await message.answer(
            "📝 <b>Укажите источник</b>\n\n"
            "Отправьте идентификатор источника.\n"
            "Это может быть:\n"
            "• username канала (например: <code>@channel</code>)\n"
            "• ID канала (например: <code>-100123456789</code>)",
            parse_mode="HTML"
        )
        
        # Переходим к следующему состоянию
        await state.set_state(AddSourceStates.waiting_for_source_identifier)
        
    except ValueError:
        # Если введено не число - сообщаем об ошибке
        await message.answer("❌ <b>Ошибка!</b>\n\nПожалуйста, отправьте корректный ID целевого канала (число).", parse_mode="HTML")
    except Exception as e:
        # Логируем другие ошибки
        logger.error(f"Ошибка при выборе целевого канала: {e}")
        await message.answer("❌ <b>Произошла ошибка при обработке выбора.</b>", parse_mode="HTML")

# Обработчик получения идентификатора источника
@router.message(AddSourceStates.waiting_for_source_identifier)
async def process_source_identifier(message: Message, state: FSMContext):
    """
    Обработчик получения идентификатора источника для парсинга.
    
    Args:
        message (Message): Объект сообщения от пользователя, содержащий идентификатор источника
        state (FSMContext): Объект состояния FSM для хранения данных между этапами
    
    Действия:
        1. Получает ID целевого канала из состояния
        2. Сохраняет полученный идентификатор источника
        3. Запрашивает название источника
        4. Переводит FSM в состояние ожидания названия источника
    
    Raises:
        Exception: Логирует ошибку и отправляет сообщение пользователю при возникновении проблем
    """
    try:
        # Получаем сохраненные данные из состояния
        data = await state.get_data()
        target_id = data['chosen_target_id']
        
        # Очищаем и сохраняем идентификатор источника
        source_identifier = message.text.strip()
        await state.update_data(source_identifier=source_identifier)
        
        # Запрашиваем название источника
        await message.answer(
            "📋 <b>Название источника</b>\n\n"
            "Введите название источника для отображения\n"
            "(или отправьте '<code>skip</code>')",
            parse_mode="HTML"
        )
        
        # Переходим к ожиданию названия источника
        await state.set_state(AddSourceStates.waiting_for_source_title)
        
    except Exception as e:
        # Обработка ошибок
        logger.error(f"Ошибка при добавлении источника: {e}")
        await message.answer("❌ <b>Произошла ошибка при добавлении источника.</b>", parse_mode="HTML")
        await state.clear()

# Обработчик получения названия источника и завершения добавления
@router.message(AddSourceStates.waiting_for_source_title)
async def process_source_title(message: Message, state: FSMContext):
    """
    Обработчик получения названия источника и завершения процесса добавления источника.
    
    Args:
        message (Message): Объект сообщения от пользователя, содержащий название источника
        state (FSMContext): Объект состояния FSM для хранения данных между этапами
    
    Действия:
        1. Получает сохраненные данные (ID целевого канала и идентификатор источника)
        2. Обрабатывает название источника (None если пользователь отправил 'skip')
        3. Добавляет источник в базу данных через репозиторий
        4. Отправляет пользователю результат операции:
           - Уведомление если источник уже существует
           - Подтверждение успешного добавления
           - Сообщение об ошибке при неудаче
        5. Очищает состояние FSM
    
    Raises:
        Exception: Логирует ошибку и отправляет сообщение пользователю при возникновении проблем
    """
    try:
        # Получаем все сохраненные данные
        data = await state.get_data()
        target_id = data['chosen_target_id']
        source_identifier = data['source_identifier']
        
        # Определяем название источника (None если пропущено)
        source_title = None
        if message.text.lower() != 'skip':
            source_title = message.text.strip()
        
        # Вспомогательная функция для синхронного добавления источника
        def _add_source_sync():
            return ps_repo.add_source_to_target(
                posting_target_db_id=target_id,
                source_identifier=source_identifier,
                source_title=source_title
            )
        
        # Добавляем источник в базу данных
        result = await asyncio.to_thread(_add_source_sync)
        
        # Обрабатываем результат добавления
        if result == "exists":
            # Если источник уже существует
            await message.answer(
                "⚠️ <b>Источник уже существует</b>\n\n"
                f"Источник с идентификатором <code>{source_identifier}</code> "
                f"уже привязан к целевому каналу с ID <code>{target_id}</code>.\n\n"
                "Для обновления существующего источника используйте команду /update_source",
                parse_mode="HTML"
            )
        elif result:
            # Если источник успешно добавлен
            await message.answer(
                "✅ <b>Источник успешно добавлен!</b>\n\n"
                f"📌 Целевой канал ID: <code>{target_id}</code>\n"
                f"🔍 Идентификатор источника: <code>{source_identifier}</code>\n"
                f"📝 Название источника: <code>{source_title or 'не задано'}</code>",
                parse_mode="HTML"
            )
        else:
            # Если произошла ошибка при добавлении
            await message.answer(
                "❌ <b>Не удалось добавить источник</b>\n\n"
                "Возможно, целевой канал не существует или произошла ошибка в базе данных.",
                parse_mode="HTML"
            )
        
        # Очищаем состояние FSM
        await state.clear()
    except Exception as e:
        # Обработка неожиданных ошибок
        logger.error(f"Ошибка при добавлении источника: {e}")
        await message.answer("❌ <b>Произошла ошибка при добавлении источника.</b>", parse_mode="HTML")
        await state.clear()

#######################################################################
#                                                                     #
#                    Handlers Update Source                           #
#                                                                     #
#######################################################################
@router.message(Command("update_source"))
async def cmd_update_source(message: Message, state: FSMContext):
    """
    Обработчик команды /update_source для обновления существующего источника парсинга.
    
    Args:
        message (Message): Объект сообщения от пользователя, содержащий команду
        state (FSMContext): Объект состояния FSM для хранения данных между этапами
    """
    try:
        # Получаем все источники из базы данных
        def _get_all_sources_sync():
            return ps_repo.get_all_sources()
            
        def _get_all_targets_sync():
            return pt_repo.get_all_target_channels()
        
        sources = await asyncio.to_thread(_get_all_sources_sync)
        targets = await asyncio.to_thread(_get_all_targets_sync)
        
        if not sources:
            await message.answer(
                "❌ <b>Нет доступных источников для обновления</b>\n\n"
                "Сначала добавьте источник с помощью команды /add_source",
                parse_mode="HTML"
            )
            return
        
        # Создаем словарь для быстрого поиска названий каналов по их ID
        target_names = {}
        for target in targets:
            target_names[target['id']] = target['target_title'] or target['target_chat_id']
        
        # Формируем список источников для отображения
        sources_list = []
        for source in sources:
            target_id = source['posting_target_id']
            target_name = target_names.get(target_id, f"ID: {target_id}")
            
            sources_list.append(
                f"📌 <code>{source['id']}</code>: {source['source_title'] or source['source_identifier']} "
                f"(для канала: <b>{target_name}</b>)"
            )
        
        # Отправляем сообщение с инструкцией и списком источников
        await message.answer(
            "🔄 <b>Обновление источника парсинга</b>\n\n"
            "Выберите ID источника, который нужно обновить:\n\n"
            f"{chr(10).join(sources_list)}\n\n"
            "ℹ️ Отправьте ID источника числом.",
            parse_mode="HTML"
        )
        
        # Устанавливаем состояние ожидания выбора источника
        await state.set_state(UpdateSourceStates.waiting_for_source_id)
    except Exception as e:
        logger.error(f"Ошибка при запросе списка источников: {e}")
        await message.answer(
            "❌ <b>Произошла ошибка при получении списка источников</b>",
            parse_mode="HTML"
        )

@router.message(UpdateSourceStates.waiting_for_source_id)
async def process_source_id_selection(message: Message, state: FSMContext):
    """
    Обработчик выбора ID источника для обновления.
    
    Args:
        message (Message): Сообщение с ID источника
        state (FSMContext): Состояние FSM
    """
    try:
        # Проверяем, что введено число
        if not message.text.isdigit():
            await message.answer(
                "⚠️ <b>Ошибка ввода</b>\n\n"
                "ID источника должен быть числом. Пожалуйста, введите корректный ID.",
                parse_mode="HTML"
            )
            return
        
        source_id = int(message.text)
        
        # Сохраняем ID источника в состоянии
        await state.update_data(source_id=source_id)
        
        # Запрашиваем новый идентификатор источника
        await message.answer(
            "🔤 <b>Введите новый идентификатор источника</b>\n\n"
            "Например, имя пользователя канала без символа @\n"
            "Или отправьте <code>skip</code>, чтобы оставить текущий идентификатор.",
            parse_mode="HTML"
        )
        
        # Переходим к следующему состоянию
        await state.set_state(UpdateSourceStates.waiting_for_new_identifier)
    except Exception as e:
        logger.error(f"Ошибка при обработке выбора ID источника: {e}")
        await message.answer(
            "❌ <b>Произошла ошибка при обработке выбора</b>",
            parse_mode="HTML"
        )
        await state.clear()

@router.message(UpdateSourceStates.waiting_for_new_identifier)
async def process_new_identifier(message: Message, state: FSMContext):
    """
    Обработчик ввода нового идентификатора источника.
    
    Args:
        message (Message): Сообщение с новым идентификатором
        state (FSMContext): Состояние FSM
    """
    try:
        # Получаем данные из состояния
        data = await state.get_data()
        source_id = data.get("source_id")
        
        # Проверяем, хочет ли пользователь пропустить этот шаг
        if message.text.lower() == "skip":
            new_identifier = None
        else:
            new_identifier = message.text.strip()
        
        # Сохраняем новый идентификатор в состоянии
        await state.update_data(new_identifier=new_identifier)
        
        # Запрашиваем новое название источника
        await message.answer(
            "📝 <b>Введите новое название источника</b>\n\n"
            "Или отправьте <code>skip</code>, чтобы оставить текущее название.",
            parse_mode="HTML"
        )
        
        # Переходим к следующему состоянию
        await state.set_state(UpdateSourceStates.waiting_for_new_title)
    except Exception as e:
        logger.error(f"Ошибка при обработке нового идентификатора: {e}")
        await message.answer(
            "❌ <b>Произошла ошибка при обработке идентификатора</b>",
            parse_mode="HTML"
        )
        await state.clear()

@router.message(UpdateSourceStates.waiting_for_new_title)
async def process_new_title_and_ask_target(message: Message, state: FSMContext):
    """
    Обработчик ввода нового названия источника и запроса о смене целевого канала.
    
    Args:
        message (Message): Сообщение с новым названием
        state (FSMContext): Состояние FSM
    """
    try:
        # Получаем данные из состояния
        data = await state.get_data()
        source_id = data.get("source_id")
        new_identifier = data.get("new_identifier")
        
        # Проверяем, хочет ли пользователь пропустить этот шаг
        if message.text.lower() == "skip":
            new_title = None
        else:
            new_title = message.text.strip()
        
        # Сохраняем новое название в состоянии
        await state.update_data(new_title=new_title)
        
        # Спрашиваем, хочет ли пользователь изменить целевой канал
        await message.answer(
            "🔄 <b>Изменение целевого канала</b>\n\n"
            "Хотите изменить целевой канал для этого источника?\n\n"
            "Отправьте <code>yes</code>, чтобы изменить канал\n"
            "Отправьте <code>no</code>, чтобы оставить текущий канал",
            parse_mode="HTML"
        )
        
        # Переходим к следующему состоянию
        await state.set_state(UpdateSourceStates.asking_change_target)
    except Exception as e:
        logger.error(f"Ошибка при обработке нового названия: {e}")
        await message.answer(
            "❌ <b>Произошла ошибка при обработке названия</b>",
            parse_mode="HTML"
        )
        await state.clear()

@router.message(UpdateSourceStates.asking_change_target)
async def process_change_target_answer(message: Message, state: FSMContext):
    """
    Обработчик ответа на вопрос о смене целевого канала.
    
    Args:
        message (Message): Сообщение с ответом (yes/no)
        state (FSMContext): Состояние FSM
    """
    try:
        answer = message.text.lower().strip()
        
        if answer == "yes":
            # Получаем список всех целевых каналов
            def _get_all_targets_sync():
                return pt_repo.get_all_target_channels()
                
            targets = await asyncio.to_thread(_get_all_targets_sync)
            
            if not targets:
                await message.answer(
                    "❌ <b>Нет доступных целевых каналов</b>\n\n"
                    "Невозможно изменить целевой канал. Продолжаем без изменения канала.",
                    parse_mode="HTML"
                )
                # Переходим к обновлению без изменения канала
                await process_update_source(message, state)
                return
            
            # Формируем список целевых каналов для выбора
            targets_list = "\n".join([
                f"📌 <code>{target['id']}</code>: {target['target_title'] or target['target_chat_id']}"
                for target in targets
            ])
            
            await message.answer(
                "🎯 <b>Выбор нового целевого канала</b>\n\n"
                "Выберите ID нового целевого канала:\n\n"
                f"{targets_list}\n\n"
                "ℹ️ Отправьте ID канала числом.",
                parse_mode="HTML"
            )
            
            # Переходим к состоянию ожидания выбора нового целевого канала
            await state.set_state(UpdateSourceStates.waiting_for_new_target)
        elif answer == "no":
            # Пользователь не хочет менять целевой канал, продолжаем обновление
            await process_update_source(message, state)
        else:
            # Неверный ввод
            await message.answer(
                "⚠️ <b>Неверный ввод</b>\n\n"
                "Пожалуйста, отправьте <code>yes</code> или <code>no</code>.",
                parse_mode="HTML"
            )
    except Exception as e:
        logger.error(f"Ошибка при обработке ответа о смене канала: {e}")
        await message.answer(
            "❌ <b>Произошла ошибка при обработке ответа</b>",
            parse_mode="HTML"
        )
        await state.clear()

@router.message(UpdateSourceStates.waiting_for_new_target)
async def process_new_target_selection(message: Message, state: FSMContext):
    """
    Обработчик выбора нового целевого канала.
    
    Args:
        message (Message): Сообщение с ID нового целевого канала
        state (FSMContext): Состояние FSM
    """
    try:
        # Проверяем, что введено число
        if not message.text.isdigit():
            await message.answer(
                "⚠️ <b>Ошибка ввода</b>\n\n"
                "ID канала должен быть числом. Пожалуйста, введите корректный ID.",
                parse_mode="HTML"
            )
            return
        
        new_target_id = int(message.text)
        
        # Сохраняем ID нового целевого канала в состоянии
        await state.update_data(new_target_id=new_target_id)
        
        # Переходим к обновлению источника
        await process_update_source(message, state)
    except Exception as e:
        logger.error(f"Ошибка при выборе нового целевого канала: {e}")
        await message.answer(
            "❌ <b>Произошла ошибка при выборе нового целевого канала</b>",
            parse_mode="HTML"
        )
        await state.clear()

async def process_update_source(message: Message, state: FSMContext):
    """
    Функция для выполнения обновления источника.
    
    Args:
        message (Message): Сообщение пользователя
        state (FSMContext): Состояние FSM
    """
    try:
        # Получаем все данные из состояния
        data = await state.get_data()
        source_id = data.get("source_id")
        new_identifier = data.get("new_identifier")
        new_title = data.get("new_title")
        new_target_id = data.get("new_target_id")  # Может быть None, если канал не меняется
        
        # Если все параметры пропущены, сообщаем об этом
        if new_identifier is None and new_title is None and new_target_id is None:
            await message.answer(
                "ℹ️ <b>Обновление отменено</b>\n\n"
                "Вы не указали новых данных для обновления.",
                parse_mode="HTML"
            )
            await state.clear()
            return
        
        # Функция для синхронного обновления источника
        def _update_source_sync():
            # Если нужно изменить целевой канал
            if new_target_id is not None:
                # Сначала меняем целевой канал
                target_change_result = ps_repo.change_target_for_source(
                    source_db_id=source_id,
                    new_target_db_id=new_target_id
                )
                
                if not target_change_result:
                    return False, None, None
            
            # Если нужно обновить идентификатор или название
            if new_identifier is not None or new_title is not None:
                update_result = ps_repo.update_source(
                    source_db_id=source_id,
                    new_source_identifier=new_identifier,
                    new_source_title=new_title
                )
                
                if not update_result:
                    return False, None, None
            
            # Получаем информацию о новом целевом канале, если он был изменен
            target_name = None
            if new_target_id is not None:
                targets = pt_repo.get_all_target_channels()
                for target in targets:
                    if target['id'] == new_target_id:
                        target_name = target['target_title'] or target['target_chat_id']
                        break
            
            return True, new_target_id, target_name
        
        # Выполняем обновление источника
        result = await asyncio.to_thread(_update_source_sync)
        success, updated_target_id, target_name = result
        
        # Обрабатываем результат обновления
        if success:
            # Формируем сообщение об успешном обновлении
            update_details = []
            if new_identifier:
                update_details.append(f"🔍 Новый идентификатор: <code>{new_identifier}</code>")
            if new_title:
                update_details.append(f"📝 Новое название: <code>{new_title}</code>")
            if updated_target_id:
                update_details.append(f"🎯 Новый целевой канал: <code>{target_name}</code> (ID: {updated_target_id})")
            
            update_info = "\n".join(update_details)
            
            await message.answer(
                f"✅ <b>Источник успешно обновлен!</b>\n\n"
                f"📌 ID источника: <code>{source_id}</code>\n"
                f"{update_info}",
                parse_mode="HTML"
            )
        else:
            await message.answer(
                "❌ <b>Не удалось обновить источник</b>\n\n"
                "Возможно, источник или целевой канал не существуют, или новый идентификатор уже используется для выбранного целевого канала.",
                parse_mode="HTML"
            )
        
        # Очищаем состояние FSM
        await state.clear()
    except Exception as e:
        logger.error(f"Ошибка при обновлении источника: {e}")
        await message.answer(
            "❌ <b>Произошла ошибка при обновлении источника</b>",
            parse_mode="HTML"
        )
        await state.clear()


#######################################################################
#                                                                     #
#                    Handlers Delete Source                           #
#                                                                     #
#######################################################################
@router.message(Command("delete_source"))
async def cmd_delete_source(message: Message, state: FSMContext):
    """
    Обработчик команды /delete_source для удаления источника парсинга.
    
    Args:
        message (Message): Объект сообщения от пользователя
        state (FSMContext): Объект состояния FSM для хранения данных между этапами
    """
    try:
        # Получаем все источники из базы данных
        def _get_all_sources_sync():
            return ps_repo.get_all_sources()
            
        def _get_all_targets_sync():
            return pt_repo.get_all_target_channels()
        
        sources = await asyncio.to_thread(_get_all_sources_sync)
        targets = await asyncio.to_thread(_get_all_targets_sync)
        
        if not sources:
            await message.answer(
                "❌ <b>Нет доступных источников для удаления</b>\n\n"
                "Сначала добавьте источник с помощью команды /add_source",
                parse_mode="HTML"
            )
            return
        
        # Создаем словарь для быстрого поиска названий каналов по их ID
        target_names = {}
        for target in targets:
            target_names[target['id']] = target['target_title'] or target['target_chat_id']
        
        # Формируем список источников для отображения
        sources_list = []
        for source in sources:
            target_id = source['posting_target_id']
            target_name = target_names.get(target_id, f"ID: {target_id}")
            
            sources_list.append(
                f"📌 <code>{source['id']}</code>: {source['source_title'] or source['source_identifier']} "
                f"(для канала: <b>{target_name}</b>)"
            )
        
        # Отправляем сообщение с инструкцией и списком источников
        await message.answer(
            "🗑️ <b>Удаление источника парсинга</b>\n\n"
            "Выберите ID источника, который нужно удалить:\n\n"
            f"{chr(10).join(sources_list)}\n\n"
            "⚠️ <b>Внимание!</b> Удаление источника необратимо!\n"
            "ℹ️ Отправьте ID источника числом.",
            parse_mode="HTML"
        )
        
        # Устанавливаем состояние ожидания выбора источника
        await state.set_state(DeleteSourceStates.waiting_for_source_id)
    except Exception as e:
        logger.error(f"Ошибка при запросе списка источников для удаления: {e}")
        await message.answer(
            "❌ <b>Произошла ошибка при получении списка источников</b>",
            parse_mode="HTML"
        )

@router.message(DeleteSourceStates.waiting_for_source_id)
async def process_delete_source_id(message: Message, state: FSMContext):
    """
    Обработчик выбора ID источника для удаления.
    
    Args:
        message (Message): Сообщение с ID источника
        state (FSMContext): Состояние FSM
    """
    try:
        # Проверяем, что введено число
        if not message.text.isdigit():
            await message.answer(
                "⚠️ <b>Ошибка ввода</b>\n\n"
                "ID источника должен быть числом. Пожалуйста, введите корректный ID.",
                parse_mode="HTML"
            )
            return
        
        source_id = int(message.text)
        
        # Сохраняем ID источника в состоянии
        await state.update_data(source_id=source_id)
        
        # Получаем информацию об источнике для подтверждения
        def _get_source_info_sync():
            sources = ps_repo.get_all_sources()
            targets = pt_repo.get_all_target_channels()
            
            source_info = None
            target_name = None
            
            # Находим источник по ID
            for source in sources:
                if source['id'] == source_id:
                    source_info = source
                    break
            
            if source_info:
                # Находим название целевого канала
                for target in targets:
                    if target['id'] == source_info['posting_target_id']:
                        target_name = target['target_title'] or target['target_chat_id']
                        break
            
            return source_info, target_name
        
        result = await asyncio.to_thread(_get_source_info_sync)
        source_info, target_name = result
        
        if not source_info:
            await message.answer(
                f"❌ <b>Источник с ID {source_id} не найден</b>\n\n"
                "Пожалуйста, проверьте ID и попробуйте снова.",
                parse_mode="HTML"
            )
            await state.clear()
            return
        
        # Запрашиваем подтверждение удаления
        source_title = source_info['source_title'] or source_info['source_identifier']
        target_info = f"для канала <b>{target_name}</b>" if target_name else f"для канала с ID {source_info['posting_target_id']}"
        
        await message.answer(
            f"⚠️ <b>Подтверждение удаления</b>\n\n"
            f"Вы собираетесь удалить источник:\n"
            f"📌 ID: <code>{source_id}</code>\n"
            f"🔍 Идентификатор: <code>{source_info['source_identifier']}</code>\n"
            f"📝 Название: <code>{source_title}</code>\n"
            f"🎯 Канал: {target_info}\n\n"
            f"Это действие необратимо! Подтвердите удаление:\n\n"
            f"Отправьте <code>confirm</code> для удаления\n"
            f"Отправьте <code>cancel</code> для отмены",
            parse_mode="HTML"
        )
        
        # Переходим к состоянию подтверждения удаления
        await state.set_state(DeleteSourceStates.confirming_deletion)
    except Exception as e:
        logger.error(f"Ошибка при обработке выбора ID источника для удаления: {e}")
        await message.answer(
            "❌ <b>Произошла ошибка при обработке выбора</b>",
            parse_mode="HTML"
        )
        await state.clear()

@router.message(DeleteSourceStates.confirming_deletion)
async def process_delete_confirmation(message: Message, state: FSMContext):
    """
    Обработчик подтверждения удаления источника.
    
    Args:
        message (Message): Сообщение с подтверждением
        state (FSMContext): Состояние FSM
    """
    try:
        answer = message.text.lower().strip()
        
        if answer == "confirm":
            # Получаем ID источника из состояния
            data = await state.get_data()
            source_id = data.get("source_id")
            
            # Удаляем источник
            def _delete_source_sync():
                return ps_repo.delete_source_by_id(source_id)
            
            success = await asyncio.to_thread(_delete_source_sync)
            
            if success:
                await message.answer(
                    "✅ <b>Источник успешно удален!</b>\n\n"
                    f"Источник с ID <code>{source_id}</code> был удален из базы данных.",
                    parse_mode="HTML"
                )
            else:
                await message.answer(
                    "❌ <b>Не удалось удалить источник</b>\n\n"
                    "Возможно, источник уже был удален или произошла ошибка в базе данных.",
                    parse_mode="HTML"
                )
        elif answer == "cancel":
            await message.answer(
                "✅ <b>Удаление отменено</b>\n\n"
                "Источник не был удален.",
                parse_mode="HTML"
            )
        else:
            await message.answer(
                "⚠️ <b>Неверный ввод</b>\n\n"
                "Пожалуйста, отправьте <code>confirm</code> для подтверждения удаления\n"
                "или <code>cancel</code> для отмены.",
                parse_mode="HTML"
            )
            return
        
        # Очищаем состояние FSM
        await state.clear()
    except Exception as e:
        logger.error(f"Ошибка при подтверждении удаления источника: {e}")
        await message.answer(
            "❌ <b>Произошла ошибка при удалении источника</b>",
            parse_mode="HTML"
        )
        await state.clear()


#######################################################################
#                                                                     #
#                    View All Sources                                 #
#                                                                     #
#######################################################################
@router.message(Command("view_all_sources"))
async def cmd_view_all_sources(message: Message):
    """
    Обработчик команды /view_all_sources для просмотра всех источников парсинга.
    
    Args:
        message (Message): Объект сообщения от пользователя
    
    Действия:
        1. Получает список всех источников из базы данных
        2. Получает список всех целевых каналов для отображения их названий
        3. Формирует и отправляет структурированный список всех источников
        4. Группирует источники по целевым каналам для лучшей читаемости
    """
    try:
        # Получаем все источники и целевые каналы из базы данных
        def _get_all_sources_sync():
            return ps_repo.get_all_sources()
            
        def _get_all_targets_sync():
            return pt_repo.get_all_target_channels()
        
        sources = await asyncio.to_thread(_get_all_sources_sync)
        targets = await asyncio.to_thread(_get_all_targets_sync)
        
        if not sources:
            await message.answer(
                "ℹ️ <b>Нет доступных источников</b>\n\n"
                "Добавьте источники с помощью команды /add_source",
                parse_mode="HTML"
            )
            return
        
        # Создаем словарь для быстрого поиска названий каналов по их ID
        target_names = {}
        for target in targets:
            target_names[target['id']] = {
                'name': target['target_title'] or target['target_chat_id'],
                'is_active': target['is_active']
            }
        
        # Группируем источники по целевым каналам
        sources_by_target = {}
        for source in sources:
            target_id = source['posting_target_id']
            if target_id not in sources_by_target:
                sources_by_target[target_id] = []
            sources_by_target[target_id].append(source)
        
        # Формируем сообщение с группировкой по целевым каналам
        message_parts = ["📋 <b>Список всех источников парсинга</b>\n"]
        
        for target_id, target_sources in sources_by_target.items():
            target_info = target_names.get(target_id, {'name': f"ID: {target_id}", 'is_active': False})
            target_name = target_info['name']
            is_active = target_info['is_active']
            
            # Добавляем заголовок целевого канала
            status_emoji = "✅" if is_active else "❌"
            message_parts.append(f"\n🎯 <b>Целевой канал:</b> {target_name} {status_emoji}")
            
            # Добавляем список источников для этого целевого канала
            for source in target_sources:
                source_id = source['id']
                source_identifier = source['source_identifier']
                source_title = source['source_title'] or source_identifier
                
                message_parts.append(
                    f"  📌 <code>{source_id}</code>: <b>{source_title}</b> "
                    f"(<code>{source_identifier}</code>)"
                )
        
        # Добавляем подсказку с доступными командами
        message_parts.append(
            "\n\n<i>Доступные команды:</i>\n"
            "/add_source - добавить новый источник\n"
            "/update_source - изменить существующий источник\n"
            "/delete_source - удалить источник"
        )
        
        # Отправляем сообщение
        await message.answer("\n".join(message_parts), parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"Ошибка при получении списка всех источников: {e}")
        await message.answer(
            "❌ <b>Произошла ошибка при получении списка источников</b>",
            parse_mode="HTML"
        )