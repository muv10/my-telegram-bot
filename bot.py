import os
import re
import asyncio
import collections
from datetime import datetime, timedelta
import aiohttp
from telethon import TelegramClient, events, Button

API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = 5270790672

client = TelegramClient('bot_session', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

users_db = set()
groups_db = set()
warnings = collections.defaultdict(lambda: collections.defaultdict(int))
span_tracker = collections.defaultdict(list)

settings = {
    'lang_filter': True,
    'link_filter': True,
    'spam_filter': True,
    'bad_words_filter': True,
    'clean_service_msg': True
}

BAD_WORDS = {"fuck", "shit", "sex", "porn"}

def is_english_only(text):
    if not text.strip():
        return True
    arabic_pattern = re.compile(r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]')
    if arabic_pattern.search(text):
        return False
    return True

def contains_link(text):
    pattern = r'(https?://[^\s]+)|(www\.[^\s]+)|(t\.me/[^\s]+)|(@[a-zA-Z0-9_]+)'
    return bool(re.search(pattern, text))

async def handle_violation(event, reason_text):
    try:
        await event.delete() # الحذف الفوري
    except Exception:
        pass

    chat_id = event.chat_id
    user_id = event.sender_id
    
    try:
        sender = await event.get_sender()
        user_name = f"@{sender.username}" if (sender and sender.username) else "User"
    except Exception:
        user_name = "User"

    warnings[chat_id][user_id] += 1
    current_warns = warnings[chat_id][user_id]
    
    if current_warns >= 3:
        warnings[chat_id][user_id] = 0
        try:
            await client.edit_permissions(chat_id, user_id, until_date=timedelta(minutes=5), send_messages=False)
            await event.respond(f"🚫 {user_name} has been muted for 5 minutes for {reason_text}.")
        except Exception:
            await event.respond(f"⚠️ {user_name} violated rules, but I couldn't mute them.")
    else:
        await event.respond(f"⚠️ {user_name}, {reason_text} is not allowed! [Warning: {current_warns}/3]")

# --- مراقبة المجموعات بشكل صارم وبدون استثناءات للأونر لتجربة الفلتر ---
@client.on(events.NewMessage(chats=None)) # None تعني استقبال من كل مكان ومراقبة المجموعات
async def monitor_messages(event):
    if event.is_private:
        return

    text = event.raw_text or ""
    if text.startswith('/'):
        return

    # الفحص الأول: الروابط
    if settings['link_filter'] and (contains_link(text) or event.forward):
        await handle_violation(event, "sending links/forward")
        return

    # الفحص الثاني: اللغة العربية
    if settings['lang_filter'] and not is_english_only(text):
        await handle_violation(event, "using non-English language")
        return

# --- أوامر المشرفين ولوحة التحكم بقيت كما هي دون تغيير لضمان الاستقرار ---
@client.on(events.NewMessage(pattern=r'^/(mute|unmute|ban|unban)'))
async def admin_commands(event):
    if event.is_private:
        return
    command = event.pattern_match.group(1)
    if not event.is_reply:
        return
    reply_msg = await event.get_reply_message()
    target_user = reply_msg.sender_id
    try:
        if command == "mute":
            await client.edit_permissions(event.chat_id, target_user, send_messages=False)
            await event.respond("🚫 Muted.")
            await client.forward_messages(OWNER_ID, reply_msg)
        elif command == "ban":
            await client.kick_participant(event.chat_id, target_user)
            await event.respond("🚷 Banned.")
            await client.forward_messages(OWNER_ID, reply_msg)
    except Exception:
        pass

@client.on(events.NewMessage(pattern='/panel', incoming=True))
async def send_panel(event):
    if event.sender_id != OWNER_ID: return
    buttons = [[Button.inline("English Filter: ✅ ON", data="toggle_lang_filter")]]
    await client.send_message(event.chat_id, "🛠️ Control Panel:", buttons=buttons)

async def main():
    print("Bot is running...")
    await client.run_until_disconnected()

if __name__ == '__main__':
    asyncio.get_event_loop().run_until_complete(main())
