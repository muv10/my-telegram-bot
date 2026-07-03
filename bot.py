import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, ChatPermissions
from aiogram.utils.keyboard import InlineKeyboardBuilder
import os
import re
from collections import defaultdict

BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = 5270790672
BOT_USERNAME = "N7_Ubot" # <--- ضع يوزر بوتك هنا

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
logging.basicConfig(level=logging.INFO)

group_settings = {}
user_warnings = defaultdict(int)
spam_tracker = defaultdict(list)
last_panel_msg = {}

LANGUAGES = {"AR": "العربية 🇮🇶", "EN": "English 🇺🇸", "FR": "Français 🇫🇷"} 

def get_settings(chat_id):
    if chat_id not in group_settings:
        group_settings[chat_id] = {
            'link_filter': True, 'spam_filter': True, 
            'warn_limit': 3, 'action': 'kick'
        }
    return group_settings[chat_id]

def build_main_panel(chat_id, user_id):
    s = get_settings(chat_id)
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text=f"Links: {'✅' if s['link_filter'] else '❌'}", callback_data=f"toggle_link_{chat_id}"))
    b.row(InlineKeyboardButton(text=f"Spam: {'✅' if s['spam_filter'] else '❌'}", callback_data=f"toggle_spam_{chat_id}"))
    b.row(InlineKeyboardButton(text=f"Limit: {s['warn_limit']} | Act: {s['action']}", callback_data=f"warn_menu_{chat_id}"))
    b.row(InlineKeyboardButton(text="🌍 Language Control", callback_data=f"lang_menu_{chat_id}"))
    return b.as_markup()

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    # الحل للمشكلة: التحقق من نوع المحادثة أولاً
    if message.chat.type in ['group', 'supergroup']:
        msg = await message.answer("🛠 Bot Control Panel:", reply_markup=build_main_panel(message.chat.id, message.from_user.id))
        last_panel_msg[message.chat.id] = msg.message_id
    else:
        b = InlineKeyboardBuilder()
        b.row(InlineKeyboardButton(text="➕ Add to Group", url=f"https://t.me/{BOT_USERNAME}?startgroup=true"))
        await message.answer("👋 Welcome! Use this button to add me to your group:", reply_markup=b.as_markup())

@dp.callback_query(F.data.startswith("toggle_"))
async def handle_toggle(callback: types.CallbackQuery):
    _, key, chat_id = callback.data.split("_")
    s = get_settings(int(chat_id))
    if key in ['link', 'spam']:
        s[f"{key}_filter"] = not s.get(f"{key}_filter", False)
    await callback.message.edit_reply_markup(reply_markup=build_main_panel(int(chat_id), callback.from_user.id))
    await callback.answer("Updated!")

@dp.message()
async def monitor(message: types.Message):
    if message.chat.type == 'private' or message.from_user.id == OWNER_ID: return
    
    chat_id = message.chat.id
    s = get_settings(chat_id)
    user_id = message.from_user.id
    
    # منطق الفلترة (سبام وروابط)
    violation = False
    if s['spam_filter']:
        now = asyncio.get_event_loop().time()
        spam_tracker[user_id] = [t for t in spam_tracker[user_id] if now - t < 3]
        spam_tracker[user_id].append(now)
        if len(spam_tracker[user_id]) > 3: violation = True
    
    if s['link_filter'] and re.search(r'https?://[^\s]+', message.text or message.caption or ""):
        violation = True
    
    # منطق التحذيرات والعقوبات
    if violation:
        user_warnings[user_id] += 1
        if user_warnings[user_id] >= s['warn_limit']:
            try:
                if s['action'] == 'kick': await bot.ban_chat_member(chat_id, user_id)
                elif s['action'] == 'mute': await bot.restrict_chat_member(chat_id, user_id, permissions=ChatPermissions(can_send_messages=False))
                user_warnings[user_id] = 0
            except: pass
        else:
            await message.delete()
            await message.answer(f"⚠️ Warning {user_warnings[user_id]}/{s['warn_limit']} for user.")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
