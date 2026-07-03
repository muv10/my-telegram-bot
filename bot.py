import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
import os
import re
from collections import defaultdict

BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = 5270790672

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
logging.basicConfig(level=logging.INFO)

group_settings = {}
spam_tracker = defaultdict(list)
last_panel_msg = {}

# قاموس اللغات (الرموز: الأعلام والنصوص)
LANGUAGES = {
    "AR": "العربية 🇦🇷", "EN": "English 🇺🇸", "FR": "Français 🇫🇷", "ES": "Español 🇪🇸",
    "PT": "Português 🇵🇹", "DE": "Deutsch 🇩🇪", "IT": "Italiano 🇮🇹", "RU": "Русский 🇷🇺",
    "ZH": "中文 🇨🇳", "JA": "日本語 🇯🇵", "KO": "한국어 🇰🇷", "HI": "हिन्दी 🇮🇳",
    "UR": "اردو 🇵🇰", "TR": "Türkçe 🇹🇷", "FA": "فارسی 🇮🇷", "ID": "Indonesian 🇮🇩",
    "MS": "Bahasa Melayu 🇲🇾", "TH": "ไทย 🇹🇭", "VI": "Tiếng Việt 🇻🇳", "NL": "Nederlands 🇳🇱",
    "SV": "Svenska 🇸🇪", "NO": "Norsk 🇳🇴", "DA": "Dansk 🇩🇰", "FI": "Suomi 🇫🇮",
    "EL": "Ελληνικά 🇬🇷", "HE": "עברית 🇮🇱", "UK": "Українська 🇺🇦", "PL": "Polski 🇵🇱",
    "CS": "Čeština 🇨🇿", "RO": "Română 🇷🇴"
}

def get_settings(chat_id):
    if chat_id not in group_settings:
        # افتراضياً، اللغة الإنجليزية والعربية مفعلتان، والباقي معطل
        settings = {lang: (lang in ["AR", "EN"]) for lang in LANGUAGES}
        settings.update({'link_filter': True, 'spam_filter': True})
        group_settings[chat_id] = settings
    return group_settings[chat_id]

# لوحة التحكم الرئيسية
def build_main_panel(chat_id, user_id):
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🌍 Language Control", callback_data=f"lang_menu_{chat_id}"))
    builder.row(InlineKeyboardButton(text="🔗 Links Filter", callback_data=f"toggle_link_{chat_id}"))
    builder.row(InlineKeyboardButton(text="🚫 Spam Filter", callback_data=f"toggle_spam_{chat_id}"))
    if user_id == OWNER_ID:
        builder.row(InlineKeyboardButton(text="📊 Show Stats", callback_data="stats"))
    return builder.as_markup()

# لوحة اللغات
def build_lang_panel(chat_id):
    settings = get_settings(chat_id)
    builder = InlineKeyboardBuilder()
    for code, label in LANGUAGES.items():
        status = "✅" if settings[code] else "❌"
        builder.add(InlineKeyboardButton(text=f"{label} {status}", callback_data=f"toggle_lang_{code}_{chat_id}"))
    builder.adjust(2)
    builder.row(InlineKeyboardButton(text="🔙 Back", callback_data=f"main_menu_{chat_id}"))
    return builder.as_markup()

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    if message.chat.id in last_panel_msg:
        try: await bot.delete_message(message.chat.id, last_panel_msg[message.chat.id])
        except: pass
    msg = await message.answer("🛠 Main Control Panel:", reply_markup=build_main_panel(message.chat.id, message.from_user.id))
    last_panel_msg[message.chat.id] = msg.message_id

@dp.callback_query(F.data.startswith("lang_menu_"))
async def lang_menu(callback: types.CallbackQuery):
    chat_id = callback.data.split("_")[2]
    await callback.message.edit_reply_markup(reply_markup=build_lang_panel(chat_id))

@dp.callback_query(F.data.startswith("main_menu_"))
async def main_menu(callback: types.CallbackQuery):
    chat_id = callback.data.split("_")[2]
    await callback.message.edit_reply_markup(reply_markup=build_main_panel(int(chat_id), callback.from_user.id))

@dp.callback_query(F.data.startswith("toggle_"))
async def handle_toggle(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    key = parts[1]
    chat_id = int(parts[-1])
    settings = get_settings(chat_id)
    
    if key == "lang":
        lang_code = parts[2]
        settings[lang_code] = not settings[lang_code]
        await callback.message.edit_reply_markup(reply_markup=build_lang_panel(chat_id))
    else:
        settings[f"{key}_filter"] = not settings[f"{key}_filter"]
        await callback.message.edit_reply_markup(reply_markup=build_main_panel(chat_id, callback.from_user.id))
    await callback.answer("Settings updated")

@dp.message()
async def monitor(message: types.Message):
    if message.chat.type == 'private' or message.from_user.id == OWNER_ID: return
    
    chat_id = message.chat.id
    settings = get_settings(chat_id)
    text = message.text or message.caption or ""
    
    # فلترة السبام
    if settings['spam_filter']:
        user_id = message.from_user.id
        now = asyncio.get_event_loop().time()
        spam_tracker[user_id] = [t for t in spam_tracker[user_id] if now - t < 3]
        spam_tracker[user_id].append(now)
        if len(spam_tracker[user_id]) > 3:
            await message.delete()
            return

    # فلترة الروابط
    if settings['link_filter'] and re.search(r'https?://[^\s]+', text):
        await message.delete()
        return

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
