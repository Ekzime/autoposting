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

    
#######################################################################
#                                                                     #
#                    Handlers                                         #
#                                                                     #
#######################################################################

@router.message(Command("add_source"))
async def add_source_command(message: Message, state: FSMContext):
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
            "(или отправьте '<code>пропустить</code>')",
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
        2. Обрабатывает название источника (None если пользователь отправил 'пропустить')
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
        if message.text.lower() != 'пропустить':
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

