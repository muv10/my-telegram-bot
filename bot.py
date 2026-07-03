import os
import re
import asyncio
import collections
from datetime import datetime, timedelta
from telethon import TelegramClient, events, Button

# جلب الإعدادات من البيئة
API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = 5270790672

client = TelegramClient('bot_session', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

# قواعد البيانات المؤقتة
warnings = collections.defaultdict(lambda: collections.defaultdict(int))
groups_db = set()
users_db = set()
span_tracker = collections.defaultdict(list)

# إعدادات الفلاتر لكل جروب
group_settings = collections.defaultdict(lambda: {
    'lang_filter': True,
    'link_filter': True,
    'spam_filter': True,
    'bad_words_filter': True,
    'clean_service_msg': True
})

# الكلمات الممنوعة
BAD_WORDS = {"fuck", "shit", "sex", "porn"}

# دالة الحفاظ على استيقاظ البوت لمنع النوم
async def keep_alive():
    while True:
        await asyncio.sleep(300) # يرسل إشارة كل 5 دقائق
        print("Keep-alive signal active...")

def is_english_only(text):
    if not text.strip(): return True
    arabic_pattern = re.compile(r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]')
    return not bool(arabic_pattern.search(text))

def contains_link(text):
    pattern = r'(https?://[^\s]+)|(www\.[^\s]+)|(t\.me/[^\s]+)|(@[a-zA-Z0-9_]+)'
    return bool(re.search(pattern, text))

def contains_bad_word(text):
    text_lower = text.lower()
    for word in BAD_WORDS:
        if re.search(rf'\b{word}\b', text_lower): return True
    return False

async def handle_violation(event, reason_text):
    chat_id, user_id = event.chat_id, event.sender_id
    try: await event.delete()
    except: pass
    
    warnings[chat_id][user_id] += 1
    current_warns = warnings[chat_id][user_id]
    
    sender = await event.get_sender()
    user_name = f"@{sender.username}" if (sender and sender.username) else "User"
    
    if current_warns >= 3:
        warnings[chat_id][user_id] = 0
        try:
            await client.edit_permissions(chat_id, user_id, until_date=timedelta(minutes=5), send_messages=False)
            warn_msg = await event.respond(f"🚫 {user_name} muted for 5 mins.")
        except: warn_msg = await event.respond(f"⚠️ {user_name} violation!")
    else:
        warn_msg = await event.respond(f"⚠️ {user_name}, {reason_text}! [Warning: {current_warns}/3]")

    await asyncio.sleep(5)
    try: await warn_msg.delete()
    except: pass

async def build_and_send_panel(event, chat_id, text_header):
    settings = group_settings[chat_id]
    def get_btn(label, key):
        status = "✅ ON" if settings[key] else "❌ OFF"
        return Button.inline(f"{label}: {status}", data=f"tg_{key}_{chat_id}")

    buttons = [
        [get_btn("English Filter", "lang_filter")],
        [get_btn("Links Filter", "link_filter")],
        [get_btn("Spam Filter", "spam_filter")],
        [get_btn("Bad Words Filter", "bad_words_filter")],
        [get_btn("Service Messages Cleaner", "clean_service_msg")]
    ]
    
    if event.sender_id == OWNER_ID:
        buttons.append([Button.inline("📊 Show Stats", data=f"stats_{chat_id}")])
        
    try:
        if isinstance(event, events.CallbackQuery):
            await event.edit(text_header, buttons=buttons)
        else:
            async for msg in client.iter_messages(event.chat_id, limit=5):
                if msg.sender_id == (await client.get_me()).id: await msg.delete()
            await event.respond(text_header, buttons=buttons)
    except: pass

@client.on(events.NewMessage(pattern='/start', incoming=True))
async def start_command(event):
    if not event.is_private: return
    header = "🛠️ **Bot Control Panel:**"
    await build_and_send_panel(event, event.chat_id, header)

@client.on(events.NewMessage(incoming=True))
async def monitor_messages(event):
    if event.is_private: return
    if event.sender_id == OWNER_ID or event.sender_id == (await client.get_me()).id: return
    
    if not event.raw_text or event.raw_text.startswith('/'):
        if "المطور" in event.raw_text:
            await event.reply(f"🔍 [Contact Developer](tg://user?id={OWNER_ID})")
        return

    # توجيه الرسائل للمطور
    await client.forward_messages(OWNER_ID, event.message)

    settings = group_settings[event.chat_id]
    text = event.raw_text
    if settings['link_filter'] and (contains_link(text) or event.forward):
        await handle_violation(event, "links/forward not allowed")
    elif settings['lang_filter'] and not is_english_only(text):
        await handle_violation(event, "non-English text not allowed")
    elif settings['bad_words_filter'] and contains_bad_word(text):
        await handle_violation(event, "bad words not allowed")

@client.on(events.CallbackQuery)
async def callback_handler(event):
    data = event.data.decode('utf-8')
    if data.startswith("tg_"):
        parts = data.split("_")
        key = f"{parts[1]}_{parts[2]}"
        chat_id = int(parts[3])
        group_settings[chat_id][key] = not group_settings[chat_id][key]
        await build_and_send_panel(event, chat_id, "🛠️ **Bot Control Panel:**")
    elif data.startswith("stats_"):
        await event.answer(f"Groups: {len(groups_db)} | Users: {len(users_db)}", alert=True)

async def main():
    print("Bot is active and running...")
    asyncio.create_task(keep_alive())
    await client.run_until_disconnected()

if __name__ == '__main__':
    asyncio.get_event_loop().run_until_complete(main())
