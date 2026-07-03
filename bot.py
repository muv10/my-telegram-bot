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
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
logging.basicConfig(level=logging.INFO)

# قاموس اللغات المحدث
LANGUAGES = {
    "AR": "العربية 🇮🇶", "EN": "English 🇺🇸", "FR": "Français 🇫🇷", "ES": "Español 🇪🇸",
    "PT": "Português 🇵🇹", "DE": "Deutsch 🇩🇪", "IT": "Italiano 🇮🇹", "RU": "Русский 🇷🇺",
    "ZH": "中文 🇨🇳", "JA": "日本語 🇯🇵", "KO": "한국어 🇰🇷", "HI": "हिन्दी 🇮🇳",
    "UR": "اردو 🇵🇰", "TR": "Türkçe 🇹🇷", "FA": "فارسی 🇮🇷", "ID": "Indonesian 🇮🇩",
    "MS": "Bahasa Melayu 🇲🇾", "TH": "ไทย 🇹🇭", "VI": "Tiếng Việt 🇻🇳", "NL": "Nederlands 🇳🇱",
    "SV": "Svenska 🇸🇪", "NO": "Norsk 🇳🇴", "DA": "Dansk 🇩🇰", "FI": "Suomi 🇫🇮",
    "EL": "Ελληνικά 🇬🇷", "HE": "עברית 🇮🇱", "UK": "Українська 🇺🇦", "PL": "Polski 🇵🇱",
    "CS": "Čeština 🇨🇿", "RO": "Română 🇷🇴"
}

# قاعدة بيانات الإعدادات
group_settings = defaultdict(lambda: {
    'link_filter': True, 'spam_filter': True, 'warn_limit': 3, 
    'action': 'kick', 'langs': {code: True for code in LANGUAGES}
})
user_warnings = defaultdict(int)

# --- باني القائمة الرئيسية ---
def build_main_panel(chat_id):
    s = group_settings[chat_id]
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text=f"روابط: {'✅' if s['link_filter'] else '❌'}", callback_data=f"toggle_link_{chat_id}"))
    b.row(InlineKeyboardButton(text=f"سبام: {'✅' if s['spam_filter'] else '❌'}", callback_data=f"toggle_spam_{chat_id}"))
    b.row(InlineKeyboardButton(text="🌍 بوابة اللغات", callback_data=f"lang_menu_{chat_id}"))
    b.row(InlineKeyboardButton(text="⚠️ إعدادات العقوبات", callback_data=f"warn_menu_{chat_id}"))
    return b.as_markup()

# --- باني قائمة اللغات (العدد الكبير) ---
def build_lang_panel(chat_id):
    s = group_settings[chat_id]
    b = InlineKeyboardBuilder()
    # توزيع الأزرار بشكل عرضي (كل زرين في سطر)
    items = list(LANGUAGES.items())
    for i in range(0, len(items), 2):
        row = []
        for code, name in items[i:i+2]:
            text = f"{name} {'✅' if s['langs'][code] else '❌'}"
            row.append(InlineKeyboardButton(text=text, callback_data=f"toggle_lang_{code}_{chat_id}"))
        b.row(*row)
    b.row(InlineKeyboardButton(text="🔙 رجوع", callback_data=f"main_{chat_id}"))
    return b.as_markup()

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    if message.chat.type in ['group', 'supergroup']:
        await message.answer("✅ تم التفعيل بنجاح! تم إرسال لوحة التحكم إلى الخاص.")
        await bot.send_message(message.from_user.id, "🛠 لوحة التحكم الخاصة بك:", reply_markup=build_main_panel(message.chat.id))
    else:
        await message.answer("👋 أهلاً بك! يرجى إضافتي إلى مجموعتك، ثم أرسل /start داخل المجموعة.")

# --- منطق الأزرار ---
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
    await callback.answer("تم التحديث!")

@dp.callback_query(F.data.startswith("lang_menu_"))
async def open_lang_menu(callback: types.CallbackQuery):
    chat_id = int(callback.data.split("_")[-1])
    await callback.message.edit_text("🌍 اختر اللغات الممنوعة:", reply_markup=build_lang_panel(chat_id))

@dp.callback_query(F.data.startswith("main_"))
async def back_to_main(callback: types.CallbackQuery):
    chat_id = int(callback.data.split("_")[-1])
    await callback.message.edit_text("🛠 لوحة التحكم الخاصة بك:", reply_markup=build_main_panel(chat_id))

# --- منطق الفلترة ---
@dp.message()
async def monitor(message: types.Message):
    if message.chat.type == 'private' or not message.text: return
    chat_id = message.chat.id
    s = group_settings[chat_id]
    user_id = message.from_user.id
    
    violation = False
    if s['link_filter'] and re.search(r'https?://[^\s]+', message.text): violation = True
    if s['spam_filter'] and len(message.text) > 200: violation = True 

    if violation:
        user_warnings[user_id] += 1
        if user_warnings[user_id] >= s['warn_limit']:
            try:
                if s['action'] == 'kick': await bot.ban_chat_member(chat_id, user_id)
                else: await bot.restrict_chat_member(chat_id, user_id, permissions=ChatPermissions(can_send_messages=False))
                user_warnings[user_id] = 0
            except: pass
        else:
            await message.delete()
            await message.answer(f"⚠️ تحذير {user_warnings[user_id]}/{s['warn_limit']}")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
