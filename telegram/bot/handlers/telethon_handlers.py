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
    """Начинает процесс добавления нового аккаунта для парсинга."""
    try:
        await message.answer(
            "📱 <b>Добавление аккаунта для парсинга</b>\n\n"
            "Пожалуйста, отправьте номер телефона в международном формате, например: <code>+79123456789</code>\n\n"
            "<i>Этот номер будет использоваться для авторизации в Telegram API и получения данных из каналов.</i>\n\n"
            "Для отмены операции введите <code>skip</code>",
            parse_mode="HTML"
        )
        
        await state.set_state(AddAccountStates.waiting_for_phone)
    except Exception as e:
        logger.error(f"Ошибка при запуске добавления аккаунта: {e}")
        await message.answer(
            "❌ <b>Произошла ошибка</b>\n\n"
            "Не удалось запустить процесс добавления аккаунта. Пожалуйста, попробуйте позже.",
            parse_mode="HTML"
        )
        await state.clear()


@router.message(AddAccountStates.waiting_for_phone, F.text.lower() == "skip")
async def cancel_add_account(message: Message, state: FSMContext):
    """Отменяет процесс добавления аккаунта."""
    # Получаем данные, на случай если аккаунт уже был создан
    data = await state.get_data()
    account_id = data.get("account_id")
    
    # Если аккаунт уже создан, удаляем его
    if account_id:
        await asyncio.to_thread(lambda: pt_repo.delete_account(account_id))
        logger.info(f"Удален недоактивированный аккаунт с ID {account_id}")
    
    await message.answer(
        "❌ <b>Операция отменена</b>\n\n"
        "Добавление аккаунта было отменено.",
        parse_mode="HTML"
    )
    await state.clear()


@router.message(AddAccountStates.waiting_for_phone)
async def process_phone_text(message: Message, state: FSMContext):
    """Обрабатывает ввод номера телефона."""
    raw_phone = message.text.strip()
    
    # Очищаем номер от всех нецифровых символов
    digits_only = re.sub(r'[^0-9]', '', raw_phone)
    
    # Добавляем + в начало
    phone_number = '+' + digits_only
    
    # Проверяем длину номера (должно быть от 10 до 15 цифр после +)
    if len(digits_only) < 10 or len(digits_only) > 15:
        await message.answer(
            "⚠️ <b>Неверный формат номера</b>\n\n"
            "Пожалуйста, введите номер телефона в международном формате, например: <code>+79123456789</code>\n\n"
            "Количество цифр должно быть от 10 до 15 (не считая +).\n\n"
            "Для отмены операции введите <code>skip</code>",
            parse_mode="HTML"
        )
        return
    
    logger.info(f"Распознан номер телефона: {phone_number} из ввода: {raw_phone}")
    await process_phone_number(message, state, phone_number)


async def process_phone_number(message: Message, state: FSMContext, phone_number: str):
    """Основной обработчик номера телефона."""
    try:
        # Проверяем, существует ли уже аккаунт с таким номером
        account_exists = await asyncio.to_thread(
            lambda: any(account['phone_number'] == phone_number for account in pt_repo.get_all_accounts())
        )
        
        if account_exists:
            await message.answer(
                "⚠️ <b>Аккаунт уже существует</b>\n\n"
                f"Аккаунт с номером {phone_number} уже зарегистрирован в системе.",
                parse_mode="HTML"
            )
            await state.clear()
            return
        
        # Отправляем сообщение о подготовке к отправке кода
        await message.answer(
            "⏳ <b>Подготовка к отправке кода...</b>\n\n"
            f"Номер телефона: <code>{phone_number}</code>",
            parse_mode="HTML"
        )
        
        # Создаем клиент Telegram и отправляем код
        client = TelegramClient(StringSession(), settings.telegram_api.api_id, settings.telegram_api.api_hash)
        
        try:
            await client.connect()
            
            # Проверяем, авторизован ли клиент
            if await client.is_user_authorized():
                await handle_already_authorized_client(client, message, state, phone_number)
                return
            
            # Отправляем код авторизации
            send_code_result = await client.send_code_request(phone_number)
            phone_code_hash = send_code_result.phone_code_hash
            temp_session_string = await client.export_session_string()
            
            logger.info(f"Код успешно отправлен на номер {phone_number}")
            
            # Сохраняем информацию об аккаунте в состоянии
            await state.update_data(
                phone_number=phone_number,
                phone_code_hash=phone_code_hash,
                temp_session_string=temp_session_string
            )
            
            await message.answer(
                "✅ <b>Код отправлен</b>\n\n"
                f"На номер {phone_number} был отправлен код подтверждения.\n"
                "Пожалуйста, введите его в формате <code>12345</code>.\n\n"
                "<i>⚠️ ВАЖНО: Не выходите из чата бота! Ждите код и сразу введите его здесь.</i>",
                parse_mode="HTML"
            )
            
            # Переходим к ожиданию кода
            await state.set_state(AddAccountStates.waiting_for_code)
            
        except PhoneNumberInvalidError:
            await message.answer(
                "❌ <b>Неверный формат номера</b>\n\n"
                "Telegram API не может распознать этот номер телефона. Пожалуйста, убедитесь, что номер введен корректно, включая код страны.",
                parse_mode="HTML"
            )
            await state.clear()
            
        except Exception as e:
            logger.error(f"Ошибка при подключении к Telegram API для номера {phone_number}: {e}")
            await message.answer(
                "❌ <b>Ошибка подключения к Telegram API</b>\n\n"
                f"Не удалось отправить код на номер {phone_number}.\n"
                f"Ошибка: {str(e)[:100]}...\n\n"
                "Пожалуйста, проверьте правильность номера и попробуйте позже.",
                parse_mode="HTML"
            )
            await state.clear()
            
        finally:
            if client:
                await client.disconnect()
            
    except Exception as e:
        logger.error(f"Общая ошибка при обработке номера телефона {phone_number}: {e}")
        await message.answer(
            "❌ <b>Произошла ошибка</b>\n\n"
            f"Не удалось обработать номер {phone_number}. Пожалуйста, попробуйте позже.",
            parse_mode="HTML"
        )
        await state.clear()


async def handle_already_authorized_client(client: TelegramClient, message: Message, state: FSMContext, phone_number: str):
    """Обрабатывает случай, когда клиент уже авторизован."""
    try:
        # Получаем информацию о пользователе и сохраняем сессию
        me = await client.get_me()
        session_string = await client.export_session_string()
        
        # Добавляем аккаунт в БД
        account_id = await asyncio.to_thread(
            lambda: add_account_to_db(phone_number, session_string)
        )
        
        if account_id:
            await message.answer(
                "✅ <b>Аккаунт уже авторизован</b>\n\n"
                f"Аккаунт {phone_number} уже авторизован в системе и добавлен в базу данных.\n\n"
                f"✅ ID аккаунта: <code>{account_id}</code>\n"
                f"✅ Telegram ID: <code>{me.id}</code>\n"
                f"✅ Статус: <code>активен</code>",
                parse_mode="HTML"
            )
        else:
            await message.answer(
                "⚠️ <b>Аккаунт уже авторизован, но не удалось добавить в БД</b>\n\n"
                "Пожалуйста, попробуйте ещё раз.",
                parse_mode="HTML"
            )
    except Exception as e:
        logger.error(f"Ошибка при обработке авторизованного клиента: {e}")
        await message.answer(
            "❌ <b>Произошла ошибка</b>\n\n"
            "Не удалось сохранить данные авторизованного аккаунта.",
            parse_mode="HTML"
        )
    finally:
        await state.clear()
        if client:
            await client.disconnect()


@router.message(AddAccountStates.waiting_for_code, F.text.lower() == "skip")
async def cancel_add_code(message: Message, state: FSMContext):
    """Отменяет процесс добавления аккаунта на этапе ввода кода."""
    await message.answer(
        "❌ <b>Операция отменена</b>\n\n"
        "Добавление аккаунта было отменено.",
        parse_mode="HTML"
    )
    await state.clear()


@router.message(AddAccountStates.waiting_for_code)
async def process_code(message: Message, state: FSMContext):
    """Обрабатывает ввод кода подтверждения."""
    code = message.text.strip()
    
    # Проверяем формат кода (обычно 5 цифр)
    if not code.isdigit() or len(code) != 5:
        await message.answer(
            "⚠️ <b>Неверный формат кода</b>\n\n"
            "Код должен состоять из 5 цифр. Пожалуйста, проверьте и введите снова.",
            parse_mode="HTML"
        )
        return
        
    # Получаем сохраненные данные
    data = await state.get_data()
    phone_number = data.get("phone_number")
    phone_code_hash = data.get("phone_code_hash")
    temp_session_string = data.get("temp_session_string")
    
    if not phone_code_hash or not temp_session_string:
        logger.error(f"Не найдены необходимые данные для авторизации для номера {phone_number}")
        await message.answer(
            "❌ <b>Ошибка авторизации</b>\n\n"
            "Не удалось найти данные для подтверждения кода. Пожалуйста, начните процесс заново.",
            parse_mode="HTML"
        )
        await state.clear()
        return
    
    # Проверяем код и добавляем аккаунт
    await verify_code_and_add_account(
        message=message,
        state=state,
        phone_number=phone_number,
        code=code,
        phone_code_hash=phone_code_hash,
        temp_session_string=temp_session_string
    )


async def verify_code_and_add_account(message: Message, state: FSMContext, 
                                     phone_number: str, code: str, 
                                     phone_code_hash: str, temp_session_string: str):
    """Проверяет код подтверждения и добавляет аккаунт в БД."""
    client = None
    try:
        # Восстанавливаем клиент из строки сессии
        client = TelegramClient(
            StringSession(temp_session_string), 
            settings.telegram_api.api_id, 
            settings.telegram_api.api_hash
        )
        
        await client.connect()
        
        # Пытаемся войти с полученным кодом
        await client.sign_in(phone=phone_number, code=code, phone_code_hash=phone_code_hash)
        
        # Успешная авторизация - добавляем аккаунт в БД
        await handle_successful_auth(client, message, state, phone_number)
        
    except SessionPasswordNeededError:
        # Если требуется 2FA
        session_string = await client.export_session_string() if client else temp_session_string
        await handle_2fa_required(message, state, session_string)
        
    except (PhoneCodeInvalidError, PhoneCodeExpiredError, SessionExpiredError) as e:
        # Обработка ошибок кода подтверждения
        await handle_code_error(e, message, state, phone_number)
        
    except Exception as e:
        # Общая обработка ошибок
        logger.error(f"Ошибка при авторизации с кодом для номера {phone_number}: {e}")
        await message.answer(
            "❌ <b>Ошибка авторизации</b>\n\n"
            f"Произошла ошибка при проверке кода: {str(e)[:100]}...\n\n"
            "Пожалуйста, попробуйте еще раз или начните процесс заново с команды /add_account.",
            parse_mode="HTML"
        )
        await state.clear()
        
    finally:
        # Закрываем соединение с клиентом
        if client:
            await client.disconnect()


async def handle_successful_auth(client: TelegramClient, message: Message, 
                                state: FSMContext, phone_number: str):
    """Обрабатывает успешную авторизацию."""
    try:
        # Экспортируем строку сессии и данные пользователя
        session_string = await client.export_session_string()
        me = await client.get_me()
        
        # Добавляем аккаунт в БД
        account_id = await asyncio.to_thread(
            lambda: add_account_to_db(phone_number, session_string)
        )
        
        if not account_id:
            raise Exception("Не удалось добавить аккаунт в базу данных после авторизации")
        
        await message.answer(
            "🎉 <b>Аккаунт успешно добавлен!</b>\n\n"
            f"Аккаунт {phone_number} успешно авторизован и готов к использованию для парсинга.\n\n"
            f"✅ ID аккаунта: <code>{account_id}</code>\n"
            f"✅ Telegram ID: <code>{me.id}</code>\n"
            f"✅ Статус: <code>активен</code>",
            parse_mode="HTML"
        )
            
        await state.clear()
    
    except Exception as e:
        logger.error(f"Ошибка при сохранении данных аккаунта: {e}")
        await message.answer(
            "❌ <b>Ошибка при добавлении аккаунта</b>\n\n"
            "Авторизация прошла успешно, но не удалось сохранить данные аккаунта. Пожалуйста, попробуйте еще раз.",
            parse_mode="HTML"
        )
        await state.clear()


def add_account_to_db(phone_number: str, session_string: str) -> int:
    """Добавляет аккаунт в БД и возвращает его ID."""
    # Добавляем аккаунт
    new_account = pt_repo.add_account(
        phone_number=phone_number,
        session_string=session_string
    )
    
    # Устанавливаем статус активен
    if new_account and new_account != "exists":
        account_id = new_account.id
        pt_repo.set_active_status(account_id, True)
        return account_id
    return None


async def handle_2fa_required(message: Message, state: FSMContext, session_string: str):
    """Обрабатывает случай, когда требуется двухфакторная аутентификация."""
    logger.info("Требуется 2FA для аккаунта")
    await message.answer(
        "🔐 <b>Требуется пароль двухфакторной аутентификации</b>\n\n"
        "Ваш аккаунт защищен двухфакторной аутентификацией.\n"
        "Пожалуйста, введите пароль от вашего аккаунта.",
        parse_mode="HTML"
    )
    
    # Сохраняем сессию для последующего использования
    await state.update_data(temp_session_string=session_string)
    await state.set_state(AddAccountStates.waiting_for_password)


async def handle_code_error(error: Exception, message: Message, state: FSMContext, phone_number: str):
    """Обрабатывает ошибки кода подтверждения."""
    error_messages = {
        PhoneCodeInvalidError: "Неверный код. Пожалуйста, проверьте и введите снова.",
        PhoneCodeExpiredError: "Срок действия кода истек. Пожалуйста, начните процесс заново с команды /add_account.",
        SessionExpiredError: "Сессия авторизации истекла. Пожалуйста, начните процесс заново с команды /add_account."
    }
    
    error_type = type(error)
    logger.error(f"Ошибка авторизации для номера {phone_number}: {error_type.__name__}")
    
    # Для истекшего кода предлагаем советы
    extra_message = ""
    if error_type == PhoneCodeExpiredError:
        extra_message = "\n\n<i>Совет: При повторной попытке НЕ ВЫХОДИТЕ из чата бота! Дождитесь код и сразу введите его.</i>"
    
    await message.answer(
        f"❌ <b>Ошибка авторизации</b>\n\n{error_messages.get(error_type)}{extra_message}",
        parse_mode="HTML"
    )
    
    # Очищаем состояние для истекших кодов и сессий
    if error_type in (PhoneCodeExpiredError, SessionExpiredError):
        await state.clear()


@router.message(AddAccountStates.waiting_for_password)
async def process_password(message: Message, state: FSMContext):
    """Обрабатывает ввод пароля двухфакторной аутентификации."""
    password = message.text.strip()
    
    # Получаем данные из состояния
    data = await state.get_data()
    phone_number = data.get("phone_number")
    temp_session_string = data.get("temp_session_string")
    
    if not temp_session_string:
        logger.error(f"Не найдена строка сессии для 2FA для номера {phone_number}")
        await message.answer(
            "❌ <b>Ошибка авторизации</b>\n\n"
            "Не удалось найти данные сессии для 2FA. Пожалуйста, начните процесс заново.",
            parse_mode="HTML"
        )
        await state.clear()
        return
    
    client = None
    try:
        # Создаем клиент Telegram для авторизации
        client = TelegramClient(
            StringSession(temp_session_string), 
            settings.telegram_api.api_id, 
            settings.telegram_api.api_hash
        )
        await client.connect()
        
        # Входим с паролем
        await client.sign_in(password=password)
        
        # Получаем данные и сохраняем в БД
        session_string = await client.export_session_string()
        me = await client.get_me()
        
        # Добавляем аккаунт в БД
        account_id = await asyncio.to_thread(
            lambda: add_account_to_db(phone_number, session_string)
        )
        
        if not account_id:
            raise Exception("Не удалось добавить аккаунт в базу данных")
        
        await message.answer(
            "🎉 <b>Аккаунт успешно добавлен!</b>\n\n"
            f"Аккаунт {phone_number} успешно авторизован и готов к использованию для парсинга.\n\n"
            f"✅ ID аккаунта: <code>{account_id}</code>\n"
            f"✅ Telegram ID: <code>{me.id}</code>\n"
            f"✅ Статус: <code>активен</code>",
            parse_mode="HTML"
        )
            
        await state.clear()
        
    except Exception as e:
        logger.error(f"Ошибка при входе с паролем 2FA: {e}")
        await message.answer(
            "❌ <b>Неверный пароль</b>\n\n"
            "Введенный пароль недействителен. Пожалуйста, проверьте и введите снова.",
            parse_mode="HTML"
        )
        
    finally:
        if client:
            await client.disconnect()


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
        
        # Удаляем аккаунт
        success = await asyncio.to_thread(lambda: pt_repo.delete_account(account_id))
        
        if success:
            await message.answer(
                "✅ <b>Аккаунт удален</b>\n\n"
                f"Аккаунт с ID {account_id} успешно удален из системы.",
                parse_mode="HTML"
            )
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

