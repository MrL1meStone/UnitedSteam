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

@dp.message(CommandStart())
@dp.message(Command("menu"))
async def command_start_handler(message: Message, state: FSMContext) -> None:
    await state.set_state(States.none)
    await state.update_data(id=message.from_user.id)
    await message.answer(
        "👋 Привет! Я бот для вступления в *Паровой Союз* 🌁☁️\n\n"
        "Здесь ты можешь подать заявку на вступление и управлять кланом!",
        reply_markup=get_main_menu(),parse_mode="Markdown"
    )

@dp.callback_query(F.data == "register")
async def register(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    await callback.answer()

    if data['id'] != callback.from_user.id:
        await callback.message.answer(f"⚠️ {callback.from_user.first_name}, ты не тот, кто использовал команду")
        return

    if is_member(data["id"]):
        await callback.message.answer(
            "⚠️ Ты уже подавал заявку! Подожди пока ее одобрят или ее уже одобрили",reply_markup=get_main_menu())
        return

    if is_banned(data["id"]):
        await callback.message.answer('⚠️ Извините, вы находитесь в черном списке клана')
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
    for i in return_from('Requests'):
        buttons.append([
            InlineKeyboardButton(text=f'👤 {i[1]}, {i[2]}', url=f'tg://user/?id={i[0]}')])
        buttons.append([
            InlineKeyboardButton(text="✅ Принять", callback_data=f"Принять{i[0]}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"Отклонить{i[0]}")
        ])
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    for admin in return_from('Admins'):
        await bot.send_message(chat_id=admin,text="📨 Поступила новая заявка, вот список текущих: ",reply_markup=keyboard)
    await state.set_state('none')

@dp.callback_query(F.data == "members")
async def show_members(callback: CallbackQuery) -> None:
    await callback.answer()
    buttons = []
    for member in return_from('Members'):
        buttons.append([InlineKeyboardButton(text=f"👤 {member['nick']}", url=f'tg://user/?id={member['id']}')])
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.answer("📋 Вот список игроков клана:", reply_markup=keyboard)

@dp.callback_query(F.data == "requests")
async def show_requests(callback: CallbackQuery) -> None:
    await callback.answer()
    if not is_admin(callback.from_user.id):
        await callback.message.answer(f'⛔ Извини {callback.from_user.first_name}, эта команда тебе недоступна')
        return
    buttons = []
    for request in return_from('Requests'):
        buttons.append([
            InlineKeyboardButton(text=f'👤 {request['nick']}, {request['age']}', url=f'tg://user/?id={request['id']}')])
        buttons.append([
            InlineKeyboardButton(text="✅ Принять", callback_data=f"Принять{request['id']}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"Отклонить{request['id']}")
        ])
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    if buttons:
        await callback.message.answer("📨 Вот список заявок на вступление:", reply_markup=keyboard)
    else:
        await callback.message.answer("❌ Заявок нет")

@dp.callback_query(F.data.startswith('Принять'))
async def accept_request(callback: CallbackQuery) -> None:
    await callback.answer()
    if not is_admin(callback.from_user.id):
        await callback.message.answer(f'⛔ Извини {callback.from_user.first_name}, эта команда тебе недоступна')
        return
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
    await callback.message.answer("✅ Заявка была принята")

@dp.callback_query(F.data.startswith('Отклонить'))
async def decline_request(callback: CallbackQuery) -> None:
    await callback.answer()
    if not is_admin(callback.from_user.id):
        await callback.message.answer(f'⛔ Извини {callback.from_user.first_name}, эта команда тебе недоступна')
        return
    user_id = callback.data[9:]
    remove_member(user_id)
    await bot.send_message(chat_id=user_id, text="😕 К сожалению, твоя заявка была отклонена")
    await callback.message.answer("❌ Заявка была отклонена")

@dp.callback_query(F.data == "manage_members")
async def manage_members(callback: CallbackQuery) -> None:
    await callback.answer()
    if not is_admin(callback.from_user.id):
        await callback.message.answer(f'⛔ Извини {callback.from_user.first_name}, эта команда тебе недоступна')
        return

    keyboard=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🚪 Выгнать", callback_data='show_members_to_fire')],
        [InlineKeyboardButton(text=f"⛔ Забанить", callback_data='show_members_to_ban')]])

    await callback.message.answer("Что сделать?", reply_markup=keyboard)

@dp.callback_query(F.data == "show_members_to_fire")
async def fire_member(callback: CallbackQuery) -> None:
    buttons = []
    for member in return_from('Members'):
        buttons.append([InlineKeyboardButton(text=f"🚪 Выгнать {member['nick']}", callback_data=f'fire{member['id']}')])
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.answer("❓ Кого выгнать из клана?", reply_markup=keyboard)

@dp.callback_query(F.data.startswith("fire"))
async def fire_member(callback: CallbackQuery) -> None:
    await callback.answer()
    if not is_admin(callback.from_user.id):
        await callback.message.answer(f'⛔ Извини {callback.from_user.first_name}, эта команда тебе недоступна')
        return
    user_id = callback.data[4:]
    remove_member(user_id)
    await bot.send_message(chat_id=user_id, text="😢 К сожалению, вас выгнали из клана")
    await callback.message.answer("👋 Игрок был выгнан")

@dp.callback_query(F.data == "manage_admins")
async def manage_admins(callback: CallbackQuery) -> None:
    await callback.answer()
    if not is_admin(callback.from_user.id):
        await callback.message.answer(f'⛔ Извини {callback.from_user.first_name}, эта команда тебе недоступна')
        return
    buttons = [
        [InlineKeyboardButton(text="➕ Назначить админа", callback_data="add_admin")],
        [InlineKeyboardButton(text="➖ Снять с себя права админа", callback_data="remove_admin")]
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.answer("👑 Управление админами:", reply_markup=keyboard)

@dp.callback_query(F.data == "add_admin")
async def add_admin_menu(callback: CallbackQuery) -> None:
    await callback.answer()
    if not is_admin(callback.from_user.id):
        await callback.message.answer(f'⛔ Извини {callback.from_user.first_name}, эта команда тебе недоступна')
        return

    buttons = []
    for i in return_from('Members'):
        if i[0] not in return_from('Admins'):
            buttons.append([InlineKeyboardButton(text=f"👤 {i[1]}", callback_data=f'admin{i[0]}')])
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.answer("👑 Кому выдать права админа?", reply_markup=keyboard)

@dp.callback_query(F.data.startswith("admin"))
async def op_member(callback: CallbackQuery) -> None:
    await callback.answer()
    if not is_admin(callback.from_user.id):
        await callback.message.answer(f'⛔ Извини {callback.from_user.first_name}, эта команда тебе недоступна')
        return
    user_id = callback.data[5:]
    if int(user_id) not in return_from('Admins'):
        make_admin(user_id)
        await bot.send_message(chat_id=user_id, text="🎩 Поздравляем! Вас повысили до админа!")
        await callback.message.answer("✅ Вы повысили игрока до админа")
    else:
        await callback.message.answer("⚠️ Этот игрок уже является админом")

@dp.callback_query(F.data == "remove_admin")
async def deop(callback: CallbackQuery) -> None:
    await callback.answer()
    if not is_admin(callback.from_user.id):
        await callback.message.answer(f'⛔ Извини {callback.from_user.first_name}, эта команда тебе недоступна')
        return
    remove_admin(callback.from_user.id)
    await callback.message.answer("👋 Вы сняли с себя права админа")

@dp.callback_query(F.data == "leave")
async def leave(callback: CallbackQuery) -> None:
    await callback.answer()
    remove_member(callback.from_user.id)
    await callback.message.answer("👋 Вы вышли из клана")

async def main() -> None:
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())