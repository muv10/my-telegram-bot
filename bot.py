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
BOT_USERNAME = "N7_Ubot"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
logging.basicConfig(level=logging.INFO)

group_settings = {}
user_warnings = defaultdict(int)
spam_tracker = defaultdict(list)

def get_settings(chat_id):
    if chat_id not in group_settings:
        group_settings[chat_id] = {'link_filter': True, 'spam_filter': True, 'warn_limit': 3, 'action': 'kick'}
    return group_settings[chat_id]

# لوحة التحكم تعمل الآن لأي chat_id يتم تمريره
def build_main_panel(chat_id):
    s = get_settings(chat_id)
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text=f"Links: {'✅' if s['link_filter'] else '❌'}", callback_data=f"toggle_link_{chat_id}"))
    b.row(InlineKeyboardButton(text=f"Spam: {'✅' if s['spam_filter'] else '❌'}", callback_data=f"toggle_spam_{chat_id}"))
    b.row(InlineKeyboardButton(text=f"Limit: {s['warn_limit']} | Act: {s['action']}", callback_data=f"warn_menu_{chat_id}"))
    return b.as_markup()

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    if message.chat.type == 'private':
        # في الخاص، نرسل لوحة التحكم مباشرة
        await message.answer("🛠 لوحة التحكم الخاصة بك:", reply_markup=build_main_panel(message.chat.id))
    else:
        # في المجموعة، لا نرسل شيئاً، فقط نقوم بتفعيل البوت داخلياً
        await message.delete() # حذف رسالة الـ /start من المجموعة للحفاظ على النظافة

@dp.callback_query(F.data.startswith("toggle_"))
async def handle_toggle(callback: types.CallbackQuery):
    _, key, chat_id = callback.data.split("_")
    s = get_settings(int(chat_id))
    if key in ['link', 'spam']:
        s[f"{key}_filter"] = not s.get(f"{key}_filter", False)
    await callback.message.edit_reply_markup(reply_markup=build_main_panel(int(chat_id)))
    await callback.answer("تم التحديث!")

@dp.message()
async def monitor(message: types.Message):
    if message.chat.type == 'private': return
    
    chat_id = message.chat.id
    s = get_settings(chat_id)
    user_id = message.from_user.id
    
    # منطق الفلترة (يعمل في الخلفية بدون رسائل)
    violation = False
    # [نفس منطق الفلترة السابق هنا]
    
    if violation:
        user_warnings[user_id] += 1
        if user_warnings[user_id] >= s['warn_limit']:
            # تنفيذ العقوبة
            try:
                if s['action'] == 'kick': await bot.ban_chat_member(chat_id, user_id)
                elif s['action'] == 'mute': await bot.restrict_chat_member(chat_id, user_id, permissions=ChatPermissions(can_send_messages=False))
                user_warnings[user_id] = 0
            except: pass
        else:
            await message.delete() # حذف الرسالة المخالفة فقط

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
