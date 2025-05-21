import logging
from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command

# Настройка логгера
logger = logging.getLogger(__name__)

router = Router()

@router.message(Command("help", "commands"))
async def cmd_help(message: Message):
    """
    Обработчик команд /help и /commands для вывода списка всех доступных команд бота
    
    Args:
        message (Message): Сообщение от пользователя
    """
    commands_text = """
🔍 <b>Доступные команды бота</b>

<b>📱 Управление аккаунтами Telegram:</b>
/add_account - добавить новый аккаунт Telegram
/view_accounts - просмотреть список доступных аккаунтов
/activate_account ID - активировать аккаунт с указанным ID
/deactivate_account ID - деактивировать аккаунт
/delete_account ID - удалить аккаунт

<b>📋 Управление источниками парсинга:</b>
/add_source - добавить новый источник для парсинга
/view_all_sources - просмотреть все источники парсинга
/update_source ID - обновить существующий источник
/delete_source ID - удалить источник

<b>🎯 Управление целевыми каналами:</b>
/add_target - добавить новый целевой канал для постинга
/view_targets - просмотреть список целевых каналов
/all_targets - просмотреть все целевые каналы
/update_target ID - обновить целевой канал
/delete_target ID - удалить целевой канал

<b>⚙️ Сервисные команды:</b>
/help, /commands - показать этот список команд
/cancel - отменить текущую операцию

<i>Используйте ID, указанные в списках при просмотре аккаунтов, источников и целевых каналов.</i>
"""
    await message.answer(commands_text, parse_mode="HTML")
    logger.info(f"Показан список команд пользователю {message.from_user.id}") 