import logging
import asyncio
from os import getenv

# Библиотеки для работы с ботом
from aiogram import Router, F, Bot
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from dotenv import load_dotenv


# Библиотеки для работы с базой данных
from database.repositories import parsing_source_repository as ps_repo
from database.repositories import posting_target_repository as pt_repo

# Настройка логгера
logger = logging.getLogger(__name__)

load_dotenv()

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
        
        sources = await asyncio.to_thread(_get_all_sources_sync)
        
        if not sources:
            await message.answer(
                "❌ <b>Нет доступных источников для обновления</b>\n\n"
                "Сначала добавьте источник с помощью команды /add_source",
                parse_mode="HTML"
            )
            return
        
        # Формируем список источников для отображения
        sources_list = "\n".join([
            f"📌 <code>{source['id']}</code>: {source['source_title'] or source['source_identifier']} "
            f"(для канала ID: <code>{source['posting_target_id']}</code>)"
            for source in sources
        ])
        
        # Отправляем сообщение с инструкцией и списком источников
        await message.answer(
            "🔄 <b>Обновление источника парсинга</b>\n\n"
            "Выберите ID источника, который нужно обновить:\n\n"
            f"{sources_list}\n\n"
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
async def process_new_title_and_update(message: Message, state: FSMContext):
    """
    Обработчик ввода нового названия источника и выполнения обновления.
    
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
        
        # Если оба параметра пропущены, сообщаем об этом
        if new_identifier is None and new_title is None:
            await message.answer(
                "ℹ️ <b>Обновление отменено</b>\n\n"
                "Вы не указали новых данных для обновления.",
                parse_mode="HTML"
            )
            await state.clear()
            return
        
        # Функция для синхронного обновления источника
        def _update_source_sync():
            return ps_repo.update_source(
                source_db_id=source_id,
                new_source_identifier=new_identifier,
                new_source_title=new_title
            )
        
        # Выполняем обновление источника
        result = await asyncio.to_thread(_update_source_sync)
        
        # Обрабатываем результат обновления
        if result:
            # Формируем сообщение об успешном обновлении
            update_details = []
            if new_identifier:
                update_details.append(f"🔍 Новый идентификатор: <code>{new_identifier}</code>")
            if new_title:
                update_details.append(f"📝 Новое название: <code>{new_title}</code>")
            
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
                "Возможно, источник не существует или новый идентификатор уже используется для этого целевого канала.",
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
    