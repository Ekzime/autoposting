import aiogram
from aiogram.filters import Command
from aiogram.types import BotCommand
import os
from dotenv import load_dotenv
from enum import Enum
# from autoposting.telegram.bot.core.handlers import start
# from autoposting.database.channels import add_channel


commands = [
    BotCommand(command="start",            description="main menu"),
    BotCommand(command="add_channel",       description="add new channel to autoposting list"),
    BotCommand(command="remove_channel",    description="remove channel from autoposting list"),
    BotCommand(command="channels",          description="get list of channels via inline keyboard"),
    BotCommand(command="togle_autoposting", description="togle autoposting for specific channel")
]

# load_dotenv()

bot = aiogram.Bot(token=os.getenv("TELEGRAM_BOT_TOKEN"))
bot.set_my_commands(commands)
# dispatcher = aiogram.Dispatcher()

# dispatcher.include_router()
