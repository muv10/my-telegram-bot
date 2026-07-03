import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
import os
import re

# إعدادات البوت
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = 5270790672

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
logging.basicConfig(level=logging.INFO)

# إعدادات الفلاتر (في الذاكرة)
group_settings = {}

def get_settings(chat_id):
    if chat_id not in group_settings:
        group_settings[chat_id] = {
            'lang_filter': True, 'link_filter': True,
            'spam_filter': True, 'bad_words_filter': True
        }
    return group_settings[chat_id]

# دوال الفلترة
def contains_link(text):
    return bool(re.search(r'(https?://[^\s]+)|(www\.[^\s]+)|(t\.me/[^\s]+)|(@[a-zA-Z0-9_]+)', text))

def is_english_only(text):
    return not bool(re.search(r'[\u0600-\u06FF]', text))

# بناء لوحة التحكم
def build_panel(chat_id):
    settings = get_settings(chat_id)
    builder = InlineKeyboardBuilder()
    for key, label in [('lang_filter', 'English'), ('link_filter', 'Links'), 
                       ('spam_filter', 'Spam'), ('bad_words_filter', 'Bad Words')]:
        status = "✅" if settings[key] else "❌"
        builder.row(InlineKeyboardButton(text=f"{label}: {status}", callback_data=f"toggle_{key}_{chat_id}"))
    return builder.as_markup()

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    if message.chat.type == 'private':
        await message.answer("🛠 **Bot Control Panel:**", reply_markup=build_panel(message.chat.id))

@dp.callback_query(F.data.startswith("toggle_"))
async def handle_toggle(callback: types.CallbackQuery):
    _, key, chat_id = callback.data.split("_")
    settings = get_settings(int(chat_id))
    settings[key] = not settings[key]
    await callback.message.edit_reply_markup(reply_markup=build_panel(int(chat_id)))
    await callback.answer("تم تحديث الإعدادات")

@dp.message()
async def monitor(message: types.Message):
    if message.chat.type == 'private' or message.from_user.id == OWNER_ID:
        return
    
    chat_id = message.chat.id
    settings = get_settings(chat_id)
    text = message.text or message.caption or ""

    if settings['link_filter'] and contains_link(text):
        await message.delete()
        await message.answer("🚫 الروابط ممنوعة في هذه المجموعة!")
    elif settings['lang_filter'] and not is_english_only(text):
        await message.delete()
        await message.answer("🚫 يمنع استخدام لغة غير الإنجليزية!")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
