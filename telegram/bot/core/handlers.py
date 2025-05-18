# autoposting/telegram/bot/core/handlers.py

from aiogram import Router, Bot
from aiogram.filters import Command
from aiogram.types import (
    Message, 
    CallbackQuery,
    InlineKeyboardButton as Button, 
    InlineKeyboardMarkup as InlineKb
)
from aiogram.fsm import StatesGroup, State
from aiogram.fsm.context import FSMContext
from autoposting.telegram.bot.core.bot_instance import bot
from aiogram.utils.keyboard import InlineKeyboardBuilder as  KbBuilder



# TODO подумать как можно оптимизировать этот код для состояний (probably redunant classes defining)
class ChannelAddingState(StatesGroup):
    channel_id = State()

class ChannelRemovingState(StatesGroup):
    channel_id = State()

class AddParsingChannelState(StatesGroup):
    channel_id = State()

class RemoveParsingChannelState(StatesGroup):
    channel_id = State()


main_router = Router()


def resolve_id(tgid: int | str | None) -> int | str | None:
    channel_id = tgid.strip().replace("@", "")
    if channel_id:
        if channel_id.isnumeric():
            return int(channel_id)
        else:
            return str(channel_id)
    return None


@main_router.message(Command('start'))
async def start(message: Message):
    """
    Это самый главный обработчик он будет показывать главное меню бота.
    Главное меню будет содержать такие кнопки как:
    - мои каналы
    - Добавить мой канал
    - Удалить мой канал
    
    - Добавить канал для парсинга
    - Получить список каналов для парсинга
    - удалить канал для парсинга

    - Включить/выключить автопостинг для конкретного канала
    """
    # user = database.get_user(message.from_user.id)
    # if user is None:
    #     database.add_user(message.from_user.id, message.from_user.username)
    #     await message.answer("новый юзер зарегистрирован")
    # else:
    #     await message.answer("юзер уже зарегистрирован")

    main_menu = InlineKb(
        inline_keyboard=[
            [Button(text="Мои каналы",                              callback_data="my_channels")],
            [Button(text="Добавить мой канал",                      callback_data="add_my_channel")],
            [Button(text="Удалить мой канал",                       callback_data="remove_my_channel")],
            
            [Button(text="Добавить канал для парсинга",             callback_data="add_parsing_channel")],
            [Button(text="Получить список каналов для парсинга",    callback_data="get_parsing_channels")],
            [Button(text="Удалить канал для парсинга",              callback_data="remove_parsing_channel")],

            [Button(text="Включить/выключить автопостинг",          callback_data="toggle_autoposting")]
        ]
    )
    await message.answer("выберите опцию из списка", reply_markup=main_menu)


# GET USER MANAGING CHANNELS #############
@main_router.callback_query("my_channels")
async def get_user_managing_channels(callback: CallbackQuery, bot: Bot):
    channels = ... # database.get_user_channels(callback.from_user.id) ?

    if not channels:
        await callback.answer("У вас нет каналов для постинга")
        return

    builder = KbBuilder()

    for channel in channels:
        builder.add(
            Button(channel.title, callback_data=f"channel_{channel.id}")
        )

    await bot.send_message(
        "Это все ваши каналы для постинга", 
        reply_markup=builder.as_markup()
    )
##########################################



# ADD POST CHANNEL ##########################
@main_router.callback_query("add_my_channel")
async def add_to_user_channels_callback_handler(state: FSMContext, callback: CallbackQuery, bot: Bot):
    # await bot.send_message(
    #     callback.from_user.id,
    #     "чтобы добавить канал для автоведения вам нужно сначала добавить бота в канал и дать ему права"
    # )
    await callback.answer(show_alert=False)
    await bot.send_message(callback.from_user.id, "Введите ID канала для добавления")
    await state.set_state(ChannelAddingState.channel_id)


@main_router.message(ChannelAddingState.channel_id_input)
async def add_to_user_channels_id_message_handler(state: FSMContext, message: Message):
    try:
        target_id = resolve_id(message.text)
        if not target_id:
            await message.answer("Некорректный ID канала. Пожалуйста, введите корректный ID канала или @username.", parse_mode="HTML")
            await state.clear()
            return

        # TODO реализовать логику добавления канала в БД
        # привязать этот канал к юзеру
        # TODO реализовать логику проверки прав бота у в указаном канале
        # pseudo
        # if chat.is_admin(bot):
        #       database.add(channel)
        #       state.clear()

        await message.answer(f"Канал {target_id} добавлен в БД")
        await state.clear()
        
    except Exception:
        await message.answer("Произошла ошибка при обработке ID канала. Пожалуйста, попробуйте еще раз.")
        await state.clear()  




# REMOVE POST CHANNEL ##########################
@main_router.callback_query("remove_my_channel")
async def remove_channel_callback_handler(callback: CallbackQuery, state: FSMContext):
    await callback.answer(show_alert=False)
    await bot.send_message(callback.from_user.id, "Введите ID канала для удаления")
    await state.set_state(ChannelRemovingState.channel_id)


@main_router.message(ChannelRemovingState.channel_id)
async def remove_channel_id_message_handler(state: FSMContext, message: Message):
    channel_id = resolve_id(message.text)
    if not channel_id:
        await message.answer("Некорректный ID канала. Пожалуйста, введите корректный ID канала или @username.", parse_mode="HTML")
        await state.clear()
        return

    # TODO реализовать логику удаления канала из БД

    await message.answer(f"Канал {channel_id} удален из БД")
    await state.clear()




# ADD PARSING CHANNEL ############################
@main_router.callback_query("add_parsing_channel")
async def add_parsing_channel(state: FSMContext, callback: CallbackQuery):
    await callback.answer(show_alert=False)
    await bot.send_message(callback.from_user.id, "Введите ID канала для добавления")
    await state.set_state(AddParsingChannelState.channel_id)


@main_router.message(AddParsingChannelState.channel_id)
async def add_parsing_channel_id_message_handler(state: FSMContext, message: Message):
    channel_id = resolve_id(message.text)
    if not channel_id:
        await message.answer("Некорректный ID канала. Пожалуйста, введите корректный ID канала или @username.", parse_mode="HTML")
        await state.clear()
        return

    # TODO реализовать логику добавления канала в БД
    # привязать этот канал к юзеру
    # TODO реализовать логику проверки прав бота у в указаном канале
    # pseudo
    # if chat.is_admin(bot):
    #       database.add(channel)
    #       state.clear()

    await message.answer(f"Канал {channel_id} добавлен в БД")
    await state.clear()



# GET PARSING CHANNELS ############################
@main_router.callback_query("get_parsing_channels")
async def get_parsing_channels_callback_handler(callback: CallbackQuery, bot: Bot):
    channels = ... 
    # тут нужно достать из бд все каналы которые юзер парсит(слушает)
    # возможно нужно добавить поле listeners в модель Channel
    # для хранения id юезеров которые подписаны на парсинг постов с канала

    if not channels:
        await callback.answer("У вас нет каналов для парсинга")
        return

    builder = KbBuilder()

    for channel in channels:
        builder.add(
            Button(channel.title, callback_data=f"channel_{channel.id}")
        )
    await callback.answer(f"загружено {len(channels)} каналов")
    await bot.send_message("Это все ваши каналы для парсинга", reply_markup=builder.as_markup())


# REMOVE PARSING CHANNEL ############################
@main_router.callback_query("remove_parsing_channel")
async def remove_parsing_channel_callback_handler(callback: CallbackQuery, state: FSMContext):
    await callback.answer(show_alert=False)
    await bot.send_message(callback.from_user.id, "Введите ID канала для удаления")
    await state.set_state(ChannelRemovingState.channel_id)


@main_router.message(ChannelRemovingState.channel_id)
async def remove_parsing_channel_id_message_handler(state: FSMContext, message: Message):
    channel_id = resolve_id(message.text)
    if not channel_id:
        await message.answer("Некорректный ID канала. Пожалуйста, введите корректный ID канала или @username.", parse_mode="HTML")
        await state.clear()
        return

    # TODO реализовать логику удаления канала из БД

    await message.answer(f"Канал {channel_id} удален из БД")
    await state.clear()



# TODO подумать над тем как реализовать логику включения/выключения автопостинга для конкретного канала
# как пример можно не показывать кнопку включения/выключения автопостинга 
# в самом меню, сейчас полагаю логично показывать ее только в меню управления конкретным каналом
