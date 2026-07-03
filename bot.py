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
        settings = {lang: (lang in ["AR", "EN"]) for lang in LANGUAGES}
        settings.update({'link_filter': True, 'spam_filter': True, 'bad_words_filter': True})
        group_settings[chat_id] = settings
    return group_settings[chat_id]

def build_main_panel(chat_id, user_id):
    settings = get_settings(chat_id)
    builder = InlineKeyboardBuilder()
    
    # الفلاتر الأساسية كما في الصورة
    for key, label in [('link_filter', 'Links'), ('spam_filter', 'Spam'), ('bad_words_filter', 'Bad Words')]:
        status = "✅" if settings[key] else "❌"
        builder.row(InlineKeyboardButton(text=f"{label}: {status}", callback_data=f"toggle_{key}_{chat_id}"))
    
    builder.row(InlineKeyboardButton(text="🌍 Language Control", callback_data=f"lang_menu_{chat_id}"))
    
    if user_id == OWNER_ID:
        builder.row(InlineKeyboardButton(text="📊 Show Stats", callback_data="stats"))
    return builder.as_markup()

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
    msg = await message.answer("🛠 Bot Control Panel:", reply_markup=build_main_panel(message.chat.id, message.from_user.id))
    last_panel_msg[message.chat.id] = msg.message_id

@dp.callback_query(F.data.startswith(("lang_menu_", "main_menu_")))
async def switch_menu(callback: types.CallbackQuery):
    chat_id = int(callback.data.split("_")[-1])
    if callback.data.startswith("lang_menu_"):
        await callback.message.edit_reply_markup(reply_markup=build_lang_panel(chat_id))
    else:
        await callback.message.edit_reply_markup(reply_markup=build_main_panel(chat_id, callback.from_user.id))

@dp.callback_query(F.data.startswith("toggle_"))
async def handle_toggle(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    chat_id = int(parts[-1])
    settings = get_settings(chat_id)
    
    if parts[1] == "lang":
        lang_code = parts[2]
        settings[lang_code] = not settings[lang_code]
        await callback.message.edit_reply_markup(reply_markup=build_lang_panel(chat_id))
    else:
        key = f"{parts[1]}_filter"
        settings[key] = not settings[key]
        await callback.message.edit_reply_markup(reply_markup=build_main_panel(chat_id, callback.from_user.id))
    await callback.answer("Settings updated")

# دالة monitor ستحتاج لتحديث منطق فحص اللغات بناءً على قاموس اللغات الجديد (سأقوم ببرمجتها لاحقاً إذا أردت)
# حالياً الكود يركز على ضبط شكل القائمة كما طلبت في **1000319405.jpg**
