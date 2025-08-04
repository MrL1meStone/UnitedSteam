import asyncio
import re
import os

from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database import *

load_dotenv('.gitignore/token.env')

BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

class States(StatesGroup):
    none = State()
    nick = State()
    age = State()
    make_request = State()

def get_main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Заполнить анкету", callback_data="register")],
        [InlineKeyboardButton(text="👥 Список участников", callback_data="members")],
        [InlineKeyboardButton(text="📨 Заявки на вступление", callback_data="requests")],
        [InlineKeyboardButton(text="⚙️ Управление участниками", callback_data="manage_members")],
        [InlineKeyboardButton(text="👑 Управление админами", callback_data="manage_admins")],
        [InlineKeyboardButton(text="🚪 Выйти", callback_data="leave")]
    ])

def protected(func):
    async def wrapper(callback: CallbackQuery):
        if not is_admin(callback.from_user.id):
            await callback.answer(f'⛔ Извини {callback.from_user.first_name}, эта команда тебе недоступна',show_alert=True)
            return None
        else:
            await callback.answer()
            return await func(callback)
    return wrapper

async def change_message(text :str, callback: CallbackQuery, keyboard: InlineKeyboardMarkup) -> None:
    await bot.edit_message_text(text=text, message_id=callback.message.message_id,
                                chat_id=callback.message.chat.id)
    await bot.edit_message_reply_markup(chat_id=callback.message.chat.id, message_id=callback.message.message_id,
                                        reply_markup=keyboard)

@dp.message(CommandStart())
@dp.message(Command("menu"))
async def command_start_handler(message: Message, state: FSMContext) -> None:
    await state.set_state(States.none)
    await message.answer(
        "👋 Привет! Я бот для вступления в *Паровой Союз* 🌁☁️\n\n"
        "Здесь ты можешь подать заявку на вступление и управлять кланом!",
        reply_markup=get_main_menu(),parse_mode="Markdown"
    )

@dp.callback_query(F.data == "register")
async def register(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(id=callback.from_user.id)
    await callback.answer()
    if is_member(callback.from_user.id):
        await callback.answer(
            "⚠️ Ты уже подавал заявку! Подожди пока ее одобрят или ее уже одобрили",show_alert=True)
        return
    if is_banned(callback.from_user.id):
        await callback.answer('⚠️ Извините, вы находитесь в черном списке клана',show_alert=True)
        return

    await state.set_state(States.nick)
    await callback.message.answer("✏️ Напиши свой ник в Minecraft:")

@dp.message(States.nick)
async def write_nick(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    if data['id'] != message.from_user.id:
        await message.answer(f"⚠️ {message.from_user.first_name}, ты не тот, кто использовал команду")
        return
    await state.update_data(nick=message.text)
    await message.answer("✅ Отлично! Теперь введи свой возраст:")
    await state.set_state(States.age)

@dp.message(States.age)
async def write_age(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    if data['id'] != message.from_user.id:
        await message.answer(f"⚠️ {message.from_user.first_name}, ты не тот, кто использовал команду")
        return
    if re.fullmatch(r'^(7|8|9|1\d|2\d|3\d)$', message.text):
        await state.update_data(age=message.text)
        await state.set_state(States.make_request)
        await make_request(message, state)
    else:
        await message.answer("❌ Не верю что тебе меньше 7 или больше 39! Напиши реальный возраст:")

@dp.message(States.make_request)
async def make_request(message: Message, state: FSMContext):
    data = await state.get_data()
    new_user(data['id'], data['nick'], data['age'])
    await message.answer(
        "📩 Отлично, заявка отправлена! Когда она будет принята, тебе придет уведомление 🎉",
        reply_markup=get_main_menu())
    buttons=[]
    for member in return_from('Requests'):
        buttons.append([
            InlineKeyboardButton(text=f'👤 {member["name"]}, {member["age"]}', url=f'tg://user/?id={member["id"]}')])
        buttons.append([
            InlineKeyboardButton(text="✅ Принять", callback_data=f"Принять{member['id']}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"Отклонить{member['id']}")
        ])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="go_back")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    for admin in return_from('Admins'):
        await bot.send_message(chat_id=admin['id'],text="📨 Поступила новая заявка, вот список текущих: ",reply_markup=keyboard)
    await state.set_state('none')

@dp.callback_query(F.data == "members")
async def show_members(callback: CallbackQuery) -> None:
    await callback.answer()
    buttons = []
    for member in return_from('Members'):
        buttons.append([InlineKeyboardButton(text=f"👤 {member['nick']}", url=f'tg://user/?id={member["id"]}')])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="go_back")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await change_message('📋 Вот список игроков клана:',callback, keyboard)

@dp.callback_query(F.data == "requests")
@protected
async def show_requests(callback: CallbackQuery) -> None:
    await callback.answer()
    buttons = []
    for request in return_from('Requests'):
        buttons.append([
            InlineKeyboardButton(text=f'👤 {request["nick"]}, {request["age"]}', url=f'tg://user/?id={request["id"]}')])
        buttons.append([
            InlineKeyboardButton(text="✅ Принять", callback_data=f"Принять{request['id']}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"Отклонить{request['id']}")
        ])
    if buttons:
        buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="go_back")])
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        await change_message('📨 Вот список заявок на вступление:', callback, keyboard)
    else:
        buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="go_back")])
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        await change_message('❌ Заявок нет', callback, keyboard)

@dp.callback_query(F.data.startswith('Принять'))
@protected
async def accept_request(callback: CallbackQuery) -> None:
    await callback.answer()
    user_id = callback.data[7:]
    make_member(user_id)
    await bot.send_message(
        chat_id=user_id,
        text="🎉 Поздравляю, твоя заявка принята!\n\n"
             "Мы строим воздушный город на координатах 🗺️: *-1930 1070*\n"
             "Добро пожаловать в Паровой Союз! 🌁☁️\n"
             "[Ссылка на вступление в чат клана тут](https://t.me/+UkFBTi_5J89lNGNi)",
        parse_mode="Markdown"
    )
    await callback.answer("✅ Заявка была принята",show_alert=True)
    await show_requests()

@dp.callback_query(F.data.startswith('Отклонить'))
@protected
async def decline_request(callback: CallbackQuery) -> None:
    user_id = callback.data[9:]
    remove_member(user_id)
    await bot.send_message(chat_id=user_id, text="😕 К сожалению, твоя заявка была отклонена")
    await callback.answer("❌ Заявка была отклонена",show_alert=True)
    await show_requests()

@dp.callback_query(F.data == "manage_members")
@protected
async def manage_members(callback: CallbackQuery) -> None:
    keyboard=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🚪 Выгнать", callback_data='show_members_to_fire')],
        [InlineKeyboardButton(text=f"⛔ Забанить", callback_data='show_members_to_ban')],
        [InlineKeyboardButton(text=f"✅ Разбанить", callback_data='show_members_to_unban')],
        [InlineKeyboardButton(text=f"📋 Список забаненых", callback_data='show_banned')],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="go_back")]])
    await change_message('Что сделать?', callback, keyboard)

@dp.callback_query(F.data == "show_members_to_fire")
@protected
async def fire_member(callback: CallbackQuery) -> None:
    buttons = []
    for member in return_from('Members'):
        buttons.append([InlineKeyboardButton(text=f"🚪 Выгнать {member['nick']}", callback_data=f'fire{member["id"]}')])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="go_back")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await change_message('❓ Кого выгнать из клана?', callback, keyboard)

@dp.callback_query(F.data == "show_members_to_ban")
@protected
async def ban_member(callback: CallbackQuery) -> None:
    buttons = []
    for member in return_from('Members'):
        buttons.append([InlineKeyboardButton(text=f"⛔ Забанить {member['nick']}", callback_data=f'ban{member["id"]}')])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="go_back")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await bot.edit_message_text(text='❓ Кого забанить?', message_id=callback.message.message_id,
                                chat_id=callback.message.chat.id)
    await bot.edit_message_reply_markup(chat_id=callback.message.chat.id, message_id=callback.message.message_id,
                                        reply_markup=keyboard)

@dp.callback_query(F.data == "show_members_to_unban")
@protected
async def ban_member(callback: CallbackQuery) -> None:
    buttons = []
    for member in return_from('Bans'):
        buttons.append([InlineKeyboardButton(text=f"✅ Разбанить {member['nick']}", callback_data=f'unban{member["id"]}')])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="go_back")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await bot.edit_message_text(text='❓ Кого разбанить?', message_id=callback.message.message_id,
                                chat_id=callback.message.chat.id)
    await bot.edit_message_reply_markup(chat_id=callback.message.chat.id, message_id=callback.message.message_id,
                                        reply_markup=keyboard)


@dp.callback_query(F.data.startswith("fire"))
@protected
async def fire_member(callback: CallbackQuery) -> None:
    user_id = callback.data[4:]
    remove_member(user_id)
    await bot.send_message(chat_id=user_id, text="😢 К сожалению, вас выгнали из клана")
    await callback.answer("👋 Игрок был выгнан",show_alert=True)

@dp.callback_query(F.data == "manage_admins")
@protected
async def manage_admins(callback: CallbackQuery) -> None:
    buttons = [
        [InlineKeyboardButton(text="➕ Назначить админа", callback_data="add_admin")],
        [InlineKeyboardButton(text="➖ Снять с себя права админа", callback_data="remove_admin")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="go_back")]]
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await bot.edit_message_text(text='👑 Управление админами:', message_id=callback.message.message_id,
                                chat_id=callback.message.chat.id)
    await bot.edit_message_reply_markup(chat_id=callback.message.chat.id, message_id=callback.message.message_id,
                                        reply_markup=keyboard)

@dp.callback_query(F.data == "add_admin")
@protected
async def add_admin_menu(callback: CallbackQuery) -> None:
    buttons = []
    for member in return_from('Members'):
        if not is_admin(member['id']):
            buttons.append([InlineKeyboardButton(text=f"👤 {member['nick']}", callback_data=f'admin{member["id"]}')])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="go_back")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await bot.edit_message_text(text='👑 Кому выдать права админа?', message_id=callback.message.message_id,
                                chat_id=callback.message.chat.id)
    await bot.edit_message_reply_markup(chat_id=callback.message.chat.id, message_id=callback.message.message_id,
                                        reply_markup=keyboard)

@dp.callback_query(F.data.startswith("admin"))
@protected
async def op_member(callback: CallbackQuery) -> None:
    user_id = callback.data[5:]
    if is_admin(user_id):
        make_admin(user_id)
        await bot.send_message(chat_id=user_id, text="🎩 Поздравляем! Вас повысили до админа!")
        await callback.answer("✅ Вы повысили игрока до админа",show_alert=True)
    else:
        await callback.answer("⚠️ Этот игрок уже является админом",show_alert=True)

@dp.callback_query(F.data == "remove_admin")
@protected
async def deop(callback: CallbackQuery) -> None:
    remove_admin(callback.from_user.id)
    await callback.answer("👋 Вы сняли с себя права админа",show_alert=True)

@dp.callback_query(F.data == "leave")
async def leave(callback: CallbackQuery) -> None:
    remove_member(callback.from_user.id)
    await callback.answer("👋 Вы вышли из клана",show_alert=True)

@dp.callback_query(F.data == "go_back")
async def go_back(callback : CallbackQuery) -> None:
    keyboard=get_main_menu()
    await bot.edit_message_text(chat_id=callback.message.chat.id,message_id=callback.message.message_id,text="Вот меню:")
    await bot.edit_message_reply_markup(chat_id=callback.message.chat.id,message_id=callback.message.message_id,reply_markup=keyboard)

async def main() -> None:
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())