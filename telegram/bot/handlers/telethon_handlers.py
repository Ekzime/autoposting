import logging
import asyncio
import re

# Библиотеки для работы с ботом
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

# Импорт Telethon для работы с Telegram API
from telethon import TelegramClient
from telethon.errors import PhoneNumberInvalidError, SessionPasswordNeededError, PhoneCodeInvalidError, PhoneCodeExpiredError, SessionExpiredError
from telethon.sessions import StringSession

# Импорт настроек
from config import settings

# Репозитории для работы с базой данных
from database.repositories import parsing_telegram_acc_repository as pt_repo
from database.dao.pars_telegram_acc_repository import ParsingTelegramAccRepository

# Импорт функции обновления парсера
from telegram.parser.parser_service import trigger_update

# Настройка логгера
logger = logging.getLogger(__name__)

router = Router()

#######################################################################
#                       FSM States                                    #
#######################################################################
class AddAccountStates(StatesGroup):
    waiting_for_phone = State()
    waiting_for_code = State()
    waiting_for_password = State()

#######################################################################
#                   Account Management Commands                       #
#######################################################################
@router.message(Command("add_account"))
async def cmd_add_account(message: Message, state: FSMContext):
    """Начинает процесс добавления нового аккаунта Telegram."""
    await message.answer(
        "📱 <b>Добавление нового аккаунта</b>\n\n"
        "⚠️ <b>Важно!</b> Используйте другой аккаунт Telegram, а не тот, с которого вы сейчас общаетесь с ботом. Это связано с особенностями работы Telegram API.\n\n"
        "Введите номер телефона в международном формате (включая код страны):\n"
        "Например: <code>+79123456789</code>",
        parse_mode="HTML"
    )
    await state.set_state(AddAccountStates.waiting_for_phone)

@router.message(AddAccountStates.waiting_for_phone)
async def process_phone_number(message: Message, state: FSMContext):
    """Обрабатывает ввод номера телефона и запускает процесс авторизации."""
    phone_number = message.text.strip()
    
    # Проверка формата номера телефона
    if not re.match(r'^\+\d{10,15}$', phone_number):
        await message.answer(
            "❌ <b>Некорректный формат номера</b>\n\n"
            "Номер телефона должен начинаться с '+' и содержать от 10 до 15 цифр.\n"
            "Попробуйте еще раз или отмените операцию командой /cancel",
            parse_mode="HTML"
        )
        return
    
    # Сохраняем номер телефона в состояние FSM
    await state.update_data(phone_number=phone_number)
    
    # Проверяем, существует ли аккаунт с таким номером
    existing_account = await asyncio.to_thread(
        lambda: pt_repo.get_account_by_phone(phone_number)
    )
    
    if existing_account:
        await message.answer(
            "⚠️ <b>Аккаунт уже существует</b>\n\n"
            f"Аккаунт с номером {phone_number} уже зарегистрирован в системе.\n"
            "Используйте другой номер или удалите существующий аккаунт через /delete_account",
            parse_mode="HTML"
        )
        await state.clear()
        return
    
    try:
        # Создаем временный клиент для авторизации
        client = TelegramClient(
            StringSession(), 
            settings.telegram_api.api_id,
            settings.telegram_api.api_hash
        )
        
        await client.connect()
        
        # Отправляем код авторизации
        await client.send_code_request(phone_number)
        
        # Сохраняем клиент в FSM для дальнейшего использования
        await state.update_data(client=client)
        
        await message.answer(
            "✅ <b>Код авторизации отправлен</b>\n\n"
            "На указанный номер отправлен код подтверждения.\n"
            "Введите полученный код (только цифры):",
            parse_mode="HTML"
        )
        
        # Переходим к следующему состоянию - ожидание кода
        await state.set_state(AddAccountStates.waiting_for_code)
        
    except PhoneNumberInvalidError:
        await message.answer(
            "❌ <b>Недействительный номер телефона</b>\n\n"
            "Telegram сервер отклонил этот номер как недействительный.\n"
            "Проверьте номер и попробуйте еще раз, или используйте другой номер.",
            parse_mode="HTML"
        )
        await state.clear()
    except Exception as e:
        logger.error(f"Ошибка при отправке кода авторизации: {e}")
        await message.answer(
            "❌ <b>Произошла ошибка</b>\n\n"
            f"Не удалось отправить код авторизации: {str(e)}\n"
            "Попробуйте позже или используйте другой номер.",
            parse_mode="HTML"
        )
        await state.clear()

@router.message(AddAccountStates.waiting_for_code)
async def process_verification_code(message: Message, state: FSMContext):
    """Обрабатывает ввод кода подтверждения."""
    code = message.text.strip()
    
    # Проверка формата кода
    if not re.match(r'^\d{5}$', code):
        await message.answer(
            "❌ <b>Некорректный формат кода</b>\n\n"
            "Код подтверждения должен состоять из 5 цифр.\n"
            "Попробуйте еще раз или отмените операцию командой /cancel",
            parse_mode="HTML"
        )
        return
    
    # Получаем данные из FSM состояния
    state_data = await state.get_data()
    phone_number = state_data.get("phone_number")
    client = state_data.get("client")
    
    if not client:
        logger.error("Клиент Telethon не найден в FSM состоянии")
        await message.answer(
            "❌ <b>Произошла ошибка</b>\n\n"
            "Сессия авторизации устарела или была прервана.\n"
            "Начните процесс заново с команды /add_account",
            parse_mode="HTML"
        )
        await state.clear()
        return
    
    try:
        # Пытаемся войти с полученным кодом
        await message.answer(
            "⏳ <b>Авторизация...</b>\n\n"
            "Пожалуйста, подождите, идет подключение к API Telegram.",
            parse_mode="HTML"
        )
        
        try:
            # Пытаемся авторизоваться с полученным кодом
            await client.sign_in(phone_number, code)
            
            # Если авторизация прошла успешно, сохраняем сессию
            string_session = StringSession.save(client.session)
            
            # Добавляем аккаунт в базу данных
            account_info = await asyncio.to_thread(
                lambda: pt_repo.add_account(phone_number, string_session)
            )
            
            if account_info == "exists":
                await message.answer(
                    "⚠️ <b>Аккаунт уже существует</b>\n\n"
                    f"Аккаунт с номером {phone_number} уже зарегистрирован в системе.",
                    parse_mode="HTML"
                )
            elif account_info:
                await message.answer(
                    "✅ <b>Аккаунт успешно добавлен</b>\n\n"
                    f"Аккаунт с номером {phone_number} успешно добавлен в систему.\n"
                    f"ID аккаунта: {account_info['id']}",
                    parse_mode="HTML"
                )
                
                # Если это единственный аккаунт, автоматически активируем его
                all_accounts = await asyncio.to_thread(pt_repo.get_all_accounts)
                if len(all_accounts) == 1:
                    await asyncio.to_thread(lambda: pt_repo.set_active_status(account_info['id'], True))
                    await message.answer(
                        "✅ <b>Аккаунт автоматически активирован</b>\n\n"
                        "Так как это единственный аккаунт в системе, он был автоматически установлен как активный.",
                        parse_mode="HTML"
                    )
                    
                    # Вызываем обновление парсера
                    trigger_update()
                    logger.info(f"Запущено обновление парсера после добавления аккаунта {phone_number}")
            else:
                await message.answer(
                    "❌ <b>Ошибка при сохранении аккаунта</b>\n\n"
                    "Аккаунт был авторизован, но произошла ошибка при сохранении в базу данных.",
                    parse_mode="HTML"
                )
                
            # Очищаем состояние FSM
            await state.clear()
            
        except SessionPasswordNeededError:
            # Если требуется 2FA, переходим к следующему состоянию
            await message.answer(
                "🔐 <b>Требуется двухфакторная аутентификация</b>\n\n"
                "На этом аккаунте включена двухфакторная аутентификация.\n"
                "Введите ваш пароль двухфакторной аутентификации:",
                parse_mode="HTML"
            )
            await state.set_state(AddAccountStates.waiting_for_password)
            
    except PhoneCodeInvalidError:
        await message.answer(
            "❌ <b>Неверный код подтверждения</b>\n\n"
            "Введенный код неверен. Пожалуйста, проверьте код и введите его снова.",
            parse_mode="HTML"
        )
    except PhoneCodeExpiredError:
        await message.answer(
            "❌ <b>Код подтверждения истек</b>\n\n"
            "Время действия кода истекло. Начните процесс заново с команды /add_account",
            parse_mode="HTML"
        )
        await state.clear()
    except Exception as e:
        logger.error(f"Ошибка при вводе кода подтверждения: {e}")
        await message.answer(
            "❌ <b>Произошла ошибка</b>\n\n"
            f"Ошибка при авторизации: {str(e)}\n"
            "Попробуйте позже или используйте другой номер.",
            parse_mode="HTML"
        )
        await state.clear()

@router.message(AddAccountStates.waiting_for_password)
async def process_2fa_password(message: Message, state: FSMContext):
    """Обрабатывает ввод пароля двухфакторной аутентификации."""
    password = message.text.strip()
    
    # Получаем данные из FSM состояния
    state_data = await state.get_data()
    phone_number = state_data.get("phone_number")
    client = state_data.get("client")
    
    if not client:
        logger.error("Клиент Telethon не найден в FSM состоянии")
        await message.answer(
            "❌ <b>Произошла ошибка</b>\n\n"
            "Сессия авторизации устарела или была прервана.\n"
            "Начните процесс заново с команды /add_account",
            parse_mode="HTML"
        )
        await state.clear()
        return
    
    try:
        # Пытаемся войти с паролем 2FA
        await message.answer(
            "⏳ <b>Авторизация с 2FA...</b>\n\n"
            "Пожалуйста, подождите, идет проверка пароля.",
            parse_mode="HTML"
        )
        
        await client.sign_in(password=password)
        
        # Если авторизация прошла успешно, сохраняем сессию
        string_session = StringSession.save(client.session)
        
        # Добавляем аккаунт в базу данных
        account_info = await asyncio.to_thread(
            lambda: pt_repo.add_account(phone_number, string_session)
        )
        
        if account_info == "exists":
            await message.answer(
                "⚠️ <b>Аккаунт уже существует</b>\n\n"
                f"Аккаунт с номером {phone_number} уже зарегистрирован в системе.\n"
                "Существующий аккаунт был обновлен с новой сессией.",
                parse_mode="HTML"
            )
            
            # Вызываем обновление парсера, так как сессия аккаунта обновилась
            trigger_update()
            logger.info(f"Запущено обновление парсера после обновления сессии аккаунта {phone_number}")
        elif account_info:
            await message.answer(
                "✅ <b>Аккаунт успешно добавлен</b>\n\n"
                f"Аккаунт с номером {phone_number} успешно добавлен в систему.\n"
                f"ID аккаунта: {account_info['id']}",
                parse_mode="HTML"
            )
            
            # Если это единственный аккаунт, автоматически активируем его
            all_accounts = await asyncio.to_thread(pt_repo.get_all_accounts)
            if len(all_accounts) == 1:
                await asyncio.to_thread(lambda: pt_repo.set_active_status(account_info['id'], True))
                await message.answer(
                    "✅ <b>Аккаунт автоматически активирован</b>\n\n"
                    "Так как это единственный аккаунт в системе, он был автоматически установлен как активный.",
                    parse_mode="HTML"
                )
                
                # Вызываем обновление парсера
                trigger_update()
                logger.info(f"Запущено обновление парсера после добавления аккаунта {phone_number}")
        else:
            await message.answer(
                "❌ <b>Ошибка при сохранении аккаунта</b>\n\n"
                "Аккаунт был авторизован, но произошла ошибка при сохранении в базу данных.",
                parse_mode="HTML"
            )
            
    except Exception as e:
        logger.error(f"Ошибка при вводе пароля 2FA: {e}")
        await message.answer(
            "❌ <b>Произошла ошибка</b>\n\n"
            f"Ошибка при авторизации с паролем 2FA: {str(e)}\n"
            "Возможно, введен неверный пароль. Попробуйте снова с команды /add_account",
            parse_mode="HTML"
        )
    finally:
        # Закрываем клиент и очищаем состояние FSM
        await client.disconnect()
        await state.clear()

# Обработчик отмены операции в любом состоянии
@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    """Отменяет текущую операцию и очищает состояние."""
    current_state = await state.get_state()
    
    if current_state is None:
        await message.answer(
            "🤷‍♂️ <b>Нечего отменять</b>\n\n"
            "В данный момент не выполняется никаких операций.",
            parse_mode="HTML"
        )
        return
    
    # Проверяем, есть ли в состоянии клиент Telethon
    state_data = await state.get_data()
    client = state_data.get("client")
    
    if client:
        # Отключаем клиент, если он существует
        try:
            await client.disconnect()
        except Exception as e:
            logger.error(f"Ошибка при отключении клиента Telethon: {e}")
    
    # Очищаем состояние
    await state.clear()
    
    await message.answer(
        "✅ <b>Операция отменена</b>\n\n"
        "Все текущие операции отменены.",
        parse_mode="HTML"
    )

#######################################################################
#                 Account View Commands                              #
#######################################################################
@router.message(Command("view_accounts"))
async def cmd_view_accounts(message: Message):
    """Показывает список всех аккаунтов."""
    try:
        # Получаем список аккаунтов
        accounts = await asyncio.to_thread(pt_repo.get_all_accounts)
        
        if not accounts:
            await message.answer(
                "ℹ️ <b>Список аккаунтов пуст</b>\n\n"
                "В системе не зарегистрировано ни одного аккаунта для парсинга.\n"
                "Используйте команду /add_account для добавления нового аккаунта.",
                parse_mode="HTML"
            )
            return
            
        # Формируем сообщение со списком аккаунтов
        account_list = "\n\n".join([
            f"📱 <b>Аккаунт #{account['id']}</b>\n"
            f"Номер: <code>{account['phone_number']}</code>\n"
            f"Статус: <code>{'Активен' if account['is_active'] else 'Неактивен'}</code>"
            for account in accounts
        ])
        
        await message.answer(
            f"📋 <b>Список зарегистрированных аккаунтов</b>\n\n{account_list}",
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Ошибка при получении списка аккаунтов: {e}")
        await message.answer(
            "❌ <b>Произошла ошибка</b>\n\n"
            "Не удалось получить список аккаунтов. Пожалуйста, попробуйте позже.",
            parse_mode="HTML"
        )

#######################################################################
#                 Account Delete Commands                             #
#######################################################################
@router.message(Command("delete_account"))
async def cmd_delete_account(message: Message):
    """Удаляет аккаунт по его ID."""
    command_parts = message.text.split()
    
    if len(command_parts) != 2:
        await message.answer(
            "ℹ️ <b>Как использовать команду</b>\n\n"
            "Для удаления аккаунта используйте формат:\n"
            "<code>/delete_account ID</code>\n\n"
            "Где ID - это номер аккаунта из списка /view_accounts",
            parse_mode="HTML"
        )
        return
        
    try:
        account_id = int(command_parts[1])
        
        # Проверяем, активен ли аккаунт перед удалением
        account = await asyncio.to_thread(lambda: pt_repo.get_account_by_id(account_id))
        
        if not account:
            await message.answer(
                "⚠️ <b>Аккаунт не найден</b>\n\n"
                f"Аккаунт с ID {account_id} не найден.",
                parse_mode="HTML"
            )
            return
            
        # Удаляем аккаунт
        success = await asyncio.to_thread(lambda: pt_repo.delete_account(account_id))
        
        if success:
            await message.answer(
                "✅ <b>Аккаунт удален</b>\n\n"
                f"Аккаунт с ID {account_id} успешно удален из системы.",
                parse_mode="HTML"
            )
            
            # Если аккаунт был активен, вызываем обновление парсера
            if account.get('is_active', False):
                trigger_update()
                logger.info(f"Запущено обновление парсера после удаления активного аккаунта {account_id}")
        else:
            await message.answer(
                "⚠️ <b>Аккаунт не найден</b>\n\n"
                f"Аккаунт с ID {account_id} не найден или возникла ошибка при удалении.",
                parse_mode="HTML"
            )
            
    except ValueError:
        await message.answer(
            "❌ <b>Ошибка</b>\n\n"
            "ID аккаунта должен быть числом.",
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Ошибка при удалении аккаунта: {e}")
        await message.answer(
            "❌ <b>Произошла ошибка</b>\n\n"
            "Не удалось удалить аккаунт. Пожалуйста, попробуйте позже.",
            parse_mode="HTML"
        )

# Добавим команды для активации/деактивации аккаунтов
@router.message(Command("activate_account"))
async def cmd_activate_account(message: Message):
    """Активирует аккаунт по его ID."""
    command_parts = message.text.split()
    
    if len(command_parts) != 2:
        await message.answer(
            "ℹ️ <b>Как использовать команду</b>\n\n"
            "Для активации аккаунта используйте формат:\n"
            "<code>/activate_account ID</code>\n\n"
            "Где ID - это номер аккаунта из списка /view_accounts",
            parse_mode="HTML"
        )
        return
        
    try:
        account_id = int(command_parts[1])
        
        # Деактивируем все аккаунты и активируем выбранный
        async def _deactivate_all_and_activate_one():
            # Сначала деактивируем все аккаунты
            all_accounts = pt_repo.get_all_accounts()
            for acc in all_accounts:
                if acc['is_active'] and acc['id'] != account_id:
                    pt_repo.set_active_status(acc['id'], False)
            
            # Затем активируем выбранный аккаунт
            success = pt_repo.set_active_status(account_id, True)
            return success, pt_repo.get_account_by_id(account_id)
            
        success, account = await asyncio.to_thread(_deactivate_all_and_activate_one)
        
        if success and account:
            await message.answer(
                "✅ <b>Аккаунт активирован</b>\n\n"
                f"Аккаунт <code>{account['phone_number']}</code> (ID: {account_id}) успешно активирован.\n"
                "Все остальные аккаунты деактивированы.",
                parse_mode="HTML"
            )
            
            # Вызываем обновление парсера
            trigger_update()
            logger.info(f"Запущено обновление парсера после активации аккаунта {account_id}")
        else:
            await message.answer(
                "⚠️ <b>Аккаунт не найден</b>\n\n"
                f"Аккаунт с ID {account_id} не найден или возникла ошибка при активации.",
                parse_mode="HTML"
            )
            
    except ValueError:
        await message.answer(
            "❌ <b>Ошибка</b>\n\n"
            "ID аккаунта должен быть числом.",
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Ошибка при активации аккаунта: {e}")
        await message.answer(
            "❌ <b>Произошла ошибка</b>\n\n"
            "Не удалось активировать аккаунт. Пожалуйста, попробуйте позже.",
            parse_mode="HTML"
        )

@router.message(Command("deactivate_account"))
async def cmd_deactivate_account(message: Message):
    """Деактивирует аккаунт по его ID."""
    command_parts = message.text.split()
    
    if len(command_parts) != 2:
        await message.answer(
            "ℹ️ <b>Как использовать команду</b>\n\n"
            "Для деактивации аккаунта используйте формат:\n"
            "<code>/deactivate_account ID</code>\n\n"
            "Где ID - это номер аккаунта из списка /view_accounts",
            parse_mode="HTML"
        )
        return
        
    try:
        account_id = int(command_parts[1])
        
        # Деактивируем аккаунт
        async def _deactivate_account():
            success = pt_repo.set_active_status(account_id, False)
            return success, pt_repo.get_account_by_id(account_id)
            
        success, account = await asyncio.to_thread(_deactivate_account)
        
        if success and account:
            await message.answer(
                "✅ <b>Аккаунт деактивирован</b>\n\n"
                f"Аккаунт <code>{account['phone_number']}</code> (ID: {account_id}) успешно деактивирован.",
                parse_mode="HTML"
            )
            
            # Вызываем обновление парсера
            trigger_update()
            logger.info(f"Запущено обновление парсера после деактивации аккаунта {account_id}")
        else:
            await message.answer(
                "⚠️ <b>Аккаунт не найден</b>\n\n"
                f"Аккаунт с ID {account_id} не найден или возникла ошибка при деактивации.",
                parse_mode="HTML"
            )
            
    except ValueError:
        await message.answer(
            "❌ <b>Ошибка</b>\n\n"
            "ID аккаунта должен быть числом.",
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Ошибка при деактивации аккаунта: {e}")
        await message.answer(
            "❌ <b>Произошла ошибка</b>\n\n"
            "Не удалось деактивировать аккаунт. Пожалуйста, попробуйте позже.",
            parse_mode="HTML"
        )

