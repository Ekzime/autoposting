import logging
from datetime import datetime
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from sqlalchemy import select
from database.models import AdminSession, SessionLocal
from telegram.bot.auth.auth_service import AuthService
from config.settings import settings

logger = logging.getLogger(__name__)
router = Router()

class LoginStates(StatesGroup):
    waiting_for_password = State()

@router.message(Command("login"))
async def cmd_login(message: Message, state: FSMContext):
    """Команда для входа в систему"""
    user_id = message.from_user.id
    username = message.from_user.username
    
    # Проверяем, разрешен ли пользователь
    if not AuthService.is_admin_allowed(user_id):
        await message.answer(
            "❌ <b>Доступ запрещен</b>\n\n"
            "У вас нет прав для использования этого бота.",
            parse_mode="HTML"
        )
        return
    
    # Проверяем, уже авторизован ли пользователь
    if AuthService.verify_session(user_id):
        await message.answer(
            "✅ <b>Вы уже авторизованы</b>\n\n"
            f"Ваша сессия активна еще {settings.telegram_bot.session_duration_hours} часов с момента последней активности.",
            parse_mode="HTML"
        )
        return
    
    await message.answer(
        "🔐 <b>Аутентификация администратора</b>\n\n"
        "Введите пароль для доступа к системе управления:",
        parse_mode="HTML"
    )
    await state.set_state(LoginStates.waiting_for_password)

@router.message(LoginStates.waiting_for_password)
async def process_password(message: Message, state: FSMContext):
    """Обработка ввода пароля"""
    user_id = message.from_user.id
    username = message.from_user.username
    password = message.text.strip()
    
    # Удаляем сообщение с паролем для безопасности
    try:
        await message.delete()
    except Exception:
        pass
    
    # Проверяем пароль
    if not AuthService.verify_password(password):
        await message.answer(
            "❌ <b>Неверный пароль</b>\n\n"
            "Доступ запрещен. Попробуйте еще раз с командой /login",
            parse_mode="HTML"
        )
        await state.clear()
        return
    
    # Создаем сессию
    token = AuthService.create_session(user_id, username)
    
    if token:
        await message.answer(
            "✅ <b>Успешная аутентификация</b>\n\n"
            f"Добро пожаловать, {username or 'администратор'}!\n"
            f"Сессия активна на {settings.telegram_bot.session_duration_hours} часов.\n\n"
            "Теперь вы можете использовать все команды бота.\n"
            "Используйте /help для просмотра доступных команд.",
            parse_mode="HTML"
        )
        logger.info(f"Пользователь {user_id} ({username}) успешно авторизован")
    else:
        await message.answer(
            "❌ <b>Ошибка создания сессии</b>\n\n"
            "Произошла техническая ошибка. Попробуйте позже.",
            parse_mode="HTML"
        )
    
    await state.clear()

@router.message(Command("logout"))
async def cmd_logout(message: Message):
    """Команда для выхода из системы"""
    user_id = message.from_user.id
    
    if AuthService.logout_session(user_id):
        await message.answer(
            "✅ <b>Выход выполнен</b>\n\n"
            "Ваша сессия завершена. Для повторного входа используйте /login",
            parse_mode="HTML"
        )
        logger.info(f"Пользователь {user_id} вышел из системы")
    else:
        await message.answer(
            "ℹ️ <b>Вы не были авторизованы</b>",
            parse_mode="HTML"
        )

@router.message(Command("session_status"))
async def cmd_session_status(message: Message):
    """Проверка статуса сессии"""
    user_id = message.from_user.id
    
    try:
        with SessionLocal() as session:
            admin_session = session.execute(
                select(AdminSession).where(
                    AdminSession.user_id == user_id,
                    AdminSession.is_active == True
                )
            ).scalar_one_or_none()
            
            if admin_session and admin_session.expires_at > datetime.utcnow():
                time_left = admin_session.expires_at - datetime.utcnow()
                hours_left = int(time_left.total_seconds() // 3600)
                minutes_left = int((time_left.total_seconds() % 3600) // 60)
                
                await message.answer(
                    f"✅ <b>Сессия активна</b>\n\n"
                    f"Время до истечения: {hours_left}ч {minutes_left}м\n"
                    f"Последняя активность: {admin_session.last_activity.strftime('%d.%m.%Y %H:%M')}",
                    parse_mode="HTML"
                )
            else:
                await message.answer(
                    "❌ <b>Сессия неактивна</b>\n\n"
                    "Используйте /login для входа в систему.",
                    parse_mode="HTML"
                )
                
    except Exception as e:
        logger.error(f"Ошибка при проверке статуса сессии: {e}")
        await message.answer(
            "❌ <b>Ошибка проверки сессии</b>",
            parse_mode="HTML"
        )

@router.message(Command("whoami"))
async def cmd_whoami(message: Message):
    """Показывает информацию о текущем пользователе"""
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    last_name = message.from_user.last_name
    
    await message.answer(
        f"👤 <b>Информация о пользователе</b>\n\n"
        f"🆔 <b>Telegram ID:</b> <code>{user_id}</code>\n"
        f"👤 <b>Username:</b> @{username or 'не установлен'}\n"
        f"📛 <b>Имя:</b> {first_name or 'не указано'}\n"
        f"📛 <b>Фамилия:</b> {last_name or 'не указана'}\n\n"
        f"🔐 <b>Статус доступа:</b> {'✅ Разрешен' if AuthService.is_admin_allowed(user_id) else '❌ Не разрешен'}\n"
        f"🔑 <b>Статус сессии:</b> {'✅ Авторизован' if AuthService.verify_session(user_id) else '❌ Не авторизован'}",
        parse_mode="HTML"
    )

@router.message(Command("start"))
async def cmd_start(message: Message):
    """Команда приветствия"""
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    
    # Проверяем, разрешен ли пользователь
    if not AuthService.is_admin_allowed(user_id):
        await message.answer(
            "👋 <b>Добро пожаловать!</b>\n\n"
            "❌ К сожалению, у вас нет доступа к этому боту.\n"
            "Данный бот предназначен только для авторизованных администраторов.\n\n"
            "📧 Если вы считаете, что это ошибка, обратитесь к разработчику.",
            parse_mode="HTML"
        )
        return
    
    # Проверяем, уже авторизован ли пользователь
    if AuthService.verify_session(user_id):
        await message.answer(
            f"👋 <b>С возвращением, {first_name or username or 'администратор'}!</b>\n\n"
            "✅ Вы уже авторизованы в системе.\n\n"
            "📋 Используйте /commands для просмотра доступных команд.\n"
            "❓ Или /help для быстрой справки.",
            parse_mode="HTML"
        )
    else:
        await message.answer(
            f"👋 <b>Добро пожаловать, {first_name or username or 'администратор'}!</b>\n\n"
            "🤖 <b>AIPosting Bot</b> - система управления контентом\n\n"
            "🔐 Для начала работы необходимо авторизоваться:\n"
            "Используйте команду /login\n\n"
            "❓ Нужна помощь? Используйте /help",
            parse_mode="HTML"
        )