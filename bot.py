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
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
logging.basicConfig(level=logging.INFO)

# Language Dictionary
LANGUAGES = {
    "AR": "Arabic 🇮🇶", "EN": "English 🇺🇸", "FR": "Français 🇫🇷", "ES": "Español 🇪🇸",
    "PT": "Português 🇵🇹", "DE": "Deutsch 🇩🇪", "IT": "Italiano 🇮🇹", "RU": "Русский 🇷🇺",
    "ZH": "Chinese 🇨🇳", "JA": "Japanese 🇯🇵", "KO": "Korean 🇰🇷", "HI": "Hindi 🇮🇳",
    "UR": "Urdu 🇵🇰", "TR": "Turkish 🇹🇷", "FA": "Persian 🇮🇷", "ID": "Indonesian 🇮🇩",
    "MS": "Malay 🇲🇾", "TH": "Thai 🇹🇭", "VI": "Vietnamese 🇻🇳", "NL": "Dutch 🇳🇱",
    "SV": "Swedish 🇸🇪", "NO": "Norwegian 🇳🇴", "DA": "Danish 🇩🇰", "FI": "Finnish 🇫🇮",
    "EL": "Greek 🇬🇷", "HE": "Hebrew 🇮🇱", "UK": "Ukrainian 🇺🇦", "PL": "Polish 🇵🇱",
    "CS": "Czech 🇨🇿", "RO": "Romanian 🇷🇴"
}

# Settings Database
group_settings = defaultdict(lambda: {
    'link_filter': True, 'spam_filter': True, 
    'langs': {code: True for code in LANGUAGES}
})

# --- Main Panel Builder ---
def build_main_panel(chat_id):
    s = group_settings[chat_id]
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text=f"Links: {'✅' if s['link_filter'] else '❌'}", callback_data=f"toggle_link_{chat_id}"))
    b.row(InlineKeyboardButton(text=f"Spam: {'✅' if s['spam_filter'] else '❌'}", callback_data=f"toggle_spam_{chat_id}"))
    b.row(InlineKeyboardButton(text="🌍 Language Gate", callback_data=f"lang_menu_{chat_id}"))
    return b.as_markup()

# --- Language Panel Builder ---
def build_lang_panel(chat_id):
    s = group_settings[chat_id]
    b = InlineKeyboardBuilder()
    items = list(LANGUAGES.items())
    for i in range(0, len(items), 2):
        row = []
        for code, name in items[i:i+2]:
            text = f"{name} {'✅' if s['langs'][code] else '❌'}"
            row.append(InlineKeyboardButton(text=text, callback_data=f"toggle_lang_{code}_{chat_id}"))
        b.row(*row)
    b.row(InlineKeyboardButton(text="🔙 Back", callback_data=f"main_{chat_id}"))
    return b.as_markup()

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    if message.chat.type in ['group', 'supergroup']:
        await message.answer("✅ Activated! Control panel has been sent to your private chat.")
        await bot.send_message(message.from_user.id, "🛠 Bot Control Panel:", reply_markup=build_main_panel(message.chat.id))
    else:
        await message.answer("👋 Welcome! Please add me to your group, then send /start inside the group.")

# --- Button Logic ---
@dp.callback_query(F.data.startswith("toggle_"))
async def handle_toggle(callback: types.CallbackQuery):
    data = callback.data.split("_")
    chat_id = int(data[-1])
    s = group_settings[chat_id]
    
    if data[1] == "lang":
        lang_code = data[2]
        s['langs'][lang_code] = not s['langs'][lang_code]
        await callback.message.edit_reply_markup(reply_markup=build_lang_panel(chat_id))
    else:
        key = f"{data[1]}_filter"
        s[key] = not s[key]
        await callback.message.edit_reply_markup(reply_markup=build_main_panel(chat_id))
    await callback.answer("Updated!")

@dp.callback_query(F.data.startswith("lang_menu_"))
async def open_lang_menu(callback: types.CallbackQuery):
    chat_id = int(callback.data.split("_")[-1])
    await callback.message.edit_text("🌍 Select forbidden languages:", reply_markup=build_lang_panel(chat_id))

@dp.callback_query(F.data.startswith("main_"))
async def back_to_main(callback: types.CallbackQuery):
    chat_id = int(callback.data.split("_")[-1])
    await callback.message.edit_text("🛠 Bot Control Panel:", reply_markup=build_main_panel(chat_id))

# --- Filter Logic ---
@dp.message()
async def monitor(message: types.Message):
    if message.chat.type == 'private' or not message.text: return
    chat_id = message.chat.id
    s = group_settings[chat_id]
    
    violation = False
    if s['link_filter'] and re.search(r'https?://[^\s]+', message.text): violation = True
    if s['spam_filter'] and len(message.text) > 200: violation = True 

    if violation:
        await message.delete()

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
