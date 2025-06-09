from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from aiogram.types.base import TelegramObject
from aiogram.fsm.context import FSMContext
from typing import Callable, Dict, Any, Awaitable, Union
from telegram.bot.auth.auth_service import AuthService
import logging

logger = logging.getLogger(__name__)

class AuthMiddleware(BaseMiddleware):
    """Middleware для проверки аутентификации"""
    
    # Команды, доступные без аутентификации
    PUBLIC_COMMANDS = ['/start', '/login', '/help']
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: Union[Message, CallbackQuery],
        data: Dict[str, Any]
    ) -> Any:
        
        # Получаем user_id
        if isinstance(event, Message):
            user_id = event.from_user.id
            username = event.from_user.username
            command = event.text.split()[0] if event.text else ""
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id
            username = event.from_user.username
            command = ""
        else:
            # Для других типов событий пропускаем проверку
            return await handler(event, data)
        
        # Проверяем, разрешен ли пользователь как админ
        if not AuthService.is_admin_allowed(user_id):
            if isinstance(event, Message):
                await event.answer(
                    "❌ <b>Доступ запрещен</b>\n\n"
                    "У вас нет прав для использования этого бота.",
                    parse_mode="HTML"
                )
            return  # Блокируем выполнение
        
        # Проверяем публичные команды
        if command in self.PUBLIC_COMMANDS:
            return await handler(event, data)
        
        # Проверяем FSM состояние - если пользователь в процессе логина, пропускаем
        if 'state' in data:
            state: FSMContext = data['state']
            current_state = await state.get_state()
            if current_state and 'waiting_for_password' in current_state:
                return await handler(event, data)
        
        # Проверяем аутентификацию
        if not AuthService.verify_session(user_id):
            if isinstance(event, Message):
                await event.answer(
                    "🔐 <b>Требуется аутентификация</b>\n\n"
                    "Ваша сессия истекла или вы не авторизованы.\n"
                    "Используйте команду /login для входа в систему.",
                    parse_mode="HTML"
                )
            return  # Блокируем выполнение
        
        # Если все проверки пройдены, выполняем обработчик
        return await handler(event, data)