import asyncio
import re
import os

from bot_logging import write_log, view_logs, everyday_logs
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
        [InlineKeyboardButton(text="👑 Aдминские команды", callback_data="commands_for_admins")],
        [InlineKeyboardButton(text="🚪 Выйти", callback_data="leave_menu")]
    ])

def protected(func):
    async def wrapper(callback: CallbackQuery):
        if not is_admin(callback.from_user.id):
            await callback.answer(f'⛔ Извини {callback.from_user.first_name}, эта команда тебе недоступна',show_alert=True)
            await write_log(callback.from_user.id,
                            f'Попытка нажать на кнопку для админов без прав в функции "{func.__name__}"')
            return None
        else:
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
    await write_log(message.from_user.id, "Старт или команда меню")

@dp.callback_query(F.data == "register")
async def register(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(id=callback.from_user.id)
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
    await write_log(message.from_user.id, "Успешная отправка заявки")
    buttons=[]
    for member in return_from('Requests'):
        buttons.append([
            InlineKeyboardButton(text=f'👤 {member["nick"]}, {member["age"]}', url=f'tg://user/?id={member["id"]}')])
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
    await write_log(callback.from_user.id, 'Использован список участников')

@dp.callback_query(F.data == "requests")
@protected
async def show_requests(callback: CallbackQuery) -> None:
    buttons = []
    for request in return_from('Requests'):
        buttons.append([
            InlineKeyboardButton(text=f'👤 {request["nick"]}, {request["age"]}', url=f'tg://user/?id={request["id"]}')])
        buttons.append([
            InlineKeyboardButton(text="✅ Принять", callback_data=f"Принять{request['id']}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"Отклонить{request['id']}")
        ])
    if buttons:
        await callback.answer()
        buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="go_back")])
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        await change_message('📨 Вот список заявок на вступление:', callback, keyboard)
    else:
        await callback.answer('❌ Заявок нет',show_alert=True)
    await write_log(callback.from_user.id, "Использование списка заявок")

@dp.callback_query(F.data.startswith('Принять'))
@protected
async def accept_request(callback: CallbackQuery) -> None:
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
    await show_requests(callback)
    nick="Неизвестен"
    for member in return_from('Members'):
        if member['id']==user_id:
            nick = member['nick']
    await write_log(callback.from_user.id,f"Принятие заявки игрока {nick} ({user_id})")

@dp.callback_query(F.data.startswith('Отклонить'))
@protected
async def decline_request(callback: CallbackQuery) -> None:
    user_id = callback.data[9:]
    nick = "Неизвестен"
    for member in return_from('Requests'):
        if member['id']==user_id:
            nick = member['nick']
    remove_member(user_id)
    await bot.send_message(chat_id=user_id, text="😕 К сожалению, твоя заявка была отклонена")
    await callback.answer("❌ Заявка была отклонена",show_alert=True)
    await show_requests()
    await write_log(callback.from_user.id,f"Принятие заявки игрока {nick} ({user_id})")

@dp.callback_query(F.data == "commands_for_admins")
@protected
async def commands_for_admins(callback : CallbackQuery) -> None:
    keyboard=InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="📨 Заявки на вступление", callback_data="requests")],
    [InlineKeyboardButton(text="⚙️ Управление участниками", callback_data="manage_members")],
    [InlineKeyboardButton(text="👑 Управление админами", callback_data="manage_admins")],
    [InlineKeyboardButton(text="📋 Логи", callback_data="menu_logs")],
    [InlineKeyboardButton(text="◀️ Назад", callback_data="go_back")]])
    await change_message('Админские команды:', callback, keyboard)
    await write_log(callback.from_user.id, 'Использование панели админских команд')

@dp.callback_query(F.data == "menu_logs")
@protected
async def menu_logs(callback : CallbackQuery) -> None:
    await callback.answer()
    buttons = []
    for member in return_from('Members'):
        buttons.append([InlineKeyboardButton(text=f"👤 {member['nick']}", callback_data=f'view{member["id"]}')])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="go_back")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await change_message('Выбери учасника, чьи логи хочешь посмотреть:', callback, keyboard)
    await write_log(callback.from_user.id, 'Использование панели логов')

@dp.callback_query(F.data.startswith("view"))
@protected
async def menu_logs(callback : CallbackQuery) -> None:
    await callback.answer()
    nick='?'
    user_id=callback.data[4:]
    for member in return_from('Members'):
        if member['id']==user_id: nick = member['nick']
    keyboard=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад", callback_data="go_back")]])
    await write_log(callback.from_user.id, f'Просмотр логов {nick} ({user_id})')
    await change_message(view_logs(user_id), callback, keyboard)

@dp.callback_query(F.data == "manage_members")
@protected
async def manage_members(callback: CallbackQuery) -> None:
    keyboard=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🚪 Выгнать", callback_data='show_members_to_fire')],
        [InlineKeyboardButton(text=f"⛔ Забанить", callback_data='show_members_to_ban')],
        [InlineKeyboardButton(text=f"✅ Разбанить", callback_data='show_members_to_unban')],
        [InlineKeyboardButton(text=f"📋 Список забаненых", callback_data='show_bans')],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="go_back")]])
    await change_message('Что сделать?', callback, keyboard)
    await write_log(callback.from_user.id,"Использование меню управления игроками")

@dp.callback_query(F.data == "show_members_to_fire")
@protected
async def fire_member(callback: CallbackQuery) -> None:
    buttons = []
    for member in return_from('Members'):
        buttons.append([InlineKeyboardButton(text=f"🚪 Выгнать {member['nick']}", callback_data=f'fire{member["id"]}')])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="go_back")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await change_message('❓ Кого выгнать из клана?', callback, keyboard)
    await write_log(callback.from_user.id, "Использование меню кика игроков")

@dp.callback_query(F.data == "show_members_to_ban")
@protected
async def show_members_to_ban(callback: CallbackQuery) -> None:
    buttons = []
    for member in return_from('Members'):
        buttons.append([InlineKeyboardButton(text=f"⛔ Забанить {member['nick']}", callback_data=f'ban{member["id"]}')])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="go_back")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await change_message('❓ Кого забанить?', callback, keyboard)
    await write_log(callback.from_user.id, "Использование мекню бана игроков")

@dp.callback_query(F.data.startswith("ban"))
@protected
async def ban_member(callback: CallbackQuery) -> None:
    user_id = callback.data[4:]
    nick = "Неизвестен"
    for member in return_from('Member'):
        if member['id'] == user_id:
            nick = member['nick']
    remove_member(user_id)
    await bot.send_message(chat_id=user_id, text="😢 К сожалению, вас добавили в ЧС клана")
    await callback.answer("👋 Игрок был забанен",show_alert=True)
    await write_log(callback.from_user.id, f"Бан игрока {nick} ({user_id})")

@dp.callback_query(F.data == "show_members_to_unban")
@protected
async def show_members_to_unban(callback: CallbackQuery) -> None:
    buttons = []
    for member in return_from('Bans'):
        buttons.append([InlineKeyboardButton(text=f"✅ Разбанить {member['nick']}", callback_data=f'unban{member["id"]}')])
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    if buttons:
        await callback.answer()
        buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="go_back")])
        await change_message('❓ Кого разбанить?', callback, keyboard)
    else:
        await callback.answer('❌ Забаненых нет, ура!',show_alert=True)
    await write_log(callback.from_user.id, "Использование меню разбана")

@dp.callback_query(F.data.startswith("unban"))
@protected
async def unban_member(callback: CallbackQuery) -> None:
    user_id = callback.data[4:]
    nick='?'
    for banned in return_from("Bans"):
        if banned['id']==user_id: nick=banned['nick']
    remove_member(user_id)
    await bot.send_message(chat_id=user_id, text="✅ Вас убрали из ЧС клана")
    await callback.answer("✅ Игрок был разбанен",show_alert=True)
    await write_log(callback.from_user.id, f"Разбан игрока {nick} ({user_id})")

@dp.callback_query(F.data == "show_bans")
@protected
async def show_bans(callback: CallbackQuery) -> None:
    buttons = []
    n=0
    for member in return_from('Bans'):
        n+=1
        buttons.append([InlineKeyboardButton(text=n,url=f'tg://user/?id={member["id"]}')])
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    if buttons:
        await callback.answer()
        buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="go_back")])
        await change_message('⛔ Забаненные игроки: ', callback, keyboard)
    else:
        await callback.answer('❌ Забаненых нет, ура!',show_alert=True)
    await write_log(callback.from_user.id, "Использование меню банов")

@dp.callback_query(F.data.startswith("fire"))
@protected
async def fire_member(callback: CallbackQuery) -> None:
    user_id = callback.data[4:]
    nick='?'
    for member in return_from('Members'):
        if member['id']==user_id: nick = member['nick']
    remove_member(user_id)
    await bot.send_message(chat_id=user_id, text="😢 К сожалению, вас выгнали из клана")
    await callback.answer("👋 Игрок был выгнан",show_alert=True)
    await write_log(callback.from_user.id, f"Кик игрока {nick} ({user_id})")

@dp.callback_query(F.data == "manage_admins")
@protected
async def manage_admins(callback: CallbackQuery) -> None:
    buttons = [
        [InlineKeyboardButton(text="➕ Назначить админа", callback_data="add_admin")],
        [InlineKeyboardButton(text="➖ Снять с себя права админа", callback_data="remove_admin")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="go_back")]]
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await change_message('👑 Управление админами:', callback, keyboard)
    await write_log(callback.from_user.id, "Использование меню управления админами")

@dp.callback_query(F.data == "add_admin")
@protected
async def add_admin_menu(callback: CallbackQuery) -> None:
    buttons = []
    for member in return_from('Members'):
        if not is_admin(member['id']):
            buttons.append([InlineKeyboardButton(text=f"👤 {member['nick']}", callback_data=f'admin{member["id"]}')])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="go_back")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await change_message('👑 Кому выдать права админа?', callback, keyboard)
    await write_log(callback.from_user.id, "Использование панели добавления админов")

@dp.callback_query(F.data.startswith("admin"))
@protected
async def op_member(callback: CallbackQuery) -> None:
    user_id = callback.data[5:]
    nick='?'
    for member in return_from('Members'):
        if member['id']==user_id: nick = member['nick']
    make_admin(user_id)
    await bot.send_message(chat_id=user_id, text="🎩 Поздравляем! Вас повысили до админа!")
    await callback.answer("✅ Вы повысили игрока до админа",show_alert=True)
    await add_admin_menu(callback)
    await write_log(callback.from_user.id, f"Повышение игрока {nick} ({user_id})")

@dp.callback_query(F.data == "remove_admin")
@protected
async def deop(callback: CallbackQuery) -> None:
    remove_admin(callback.from_user.id)
    await callback.answer("👋 Вы сняли с себя права админа",show_alert=True)
    await write_log(callback.from_user.id, "Снятие с себя прав админа")

@dp.callback_query(F.data == "leave_menu")
async def leave_menu(callback: CallbackQuery) -> None:
    keyboard=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚪 Да, я хочу выйти", callback_data="leave")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="go_back")]
    ])
    await change_message('Вы уверенны?', callback, keyboard)

@dp.callback_query(F.data == "leave")
async def leave(callback: CallbackQuery) -> None:
    if is_member(callback.from_user.id):
        remove_member(callback.from_user.id)
        await callback.answer("👋 Вы вышли из клана",show_alert=True)
        await write_log(callback.from_user.id, "Выход из клана")
    else:
        await callback.answer("👋 Вы уже вышли из клана или еще не в нем", show_alert=True)
        await write_log(callback.from_user.id, "Неудачная попытка выхода из клана")

@dp.callback_query(F.data == "go_back")
async def go_back(callback : CallbackQuery) -> None:
    keyboard=get_main_menu()
    await change_message('Вот меню:',callback, keyboard)
    await write_log(callback.from_user.id, 'Нажатие кнопки "назад"')

async def main() -> None:
    await dp.start_polling(bot)
    while True:
        await everyday_logs()

if __name__ == "__main__":
    asyncio.run(main())