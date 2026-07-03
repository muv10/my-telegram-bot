import os
import re
import asyncio
import collections
from datetime import datetime, timedelta
import aiohttp
from telethon import TelegramClient, events, Button

# --- طلب البيانات من متغيرات البيئة في Render ---
API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")

# --- إعدادات المطور الأساسية ---
OWNER_ID = 5270790672

client = TelegramClient('bot_session', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

# --- قاعدة بيانات داخلية مؤقتة للمعلومات والإحصائيات ---
users_db = set()
groups_db = set()
warnings = collections.defaultdict(lambda: collections.defaultdict(int))
span_tracker = collections.defaultdict(list)

# --- لوحة التحكم بالتفعيل والإيقاف الافتراضية ---
settings = {
    'lang_filter': True,
    'link_filter': True,
    'spam_filter': True,
    'bad_words_filter': True,
    'clean_service_msg': True
}

# --- قائمة الكلمات الممنوعة الشاملة ---
BAD_WORDS = {
    "fuck", "shit", "asshole", "bitch", "dick", "bastard", "slut", "whore", "crap", "cunt",
    "porn", "sex", "pussy", "cock", "horny", "boobs", "ass", "naked", "nude", "milf",
    "cum", "blowjob", "handjob", "orgasm", "penetration", "intercourse", "erotic", "hentai"
}

# --- دالات الفحص والتدقيق ---

def is_english_only(text):
    if not text.strip():
        return True
    # فحص الحروف العربية بشكل صارم ومباشر
    arabic_pattern = re.compile(r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]')
    if arabic_pattern.search(text):
        return False
    return True

def contains_link(text):
    pattern = r'(https?://[^\s]+)|(www\.[^\s]+)|([a-zA-Z0-9-]+\.[a-zA-Z]{2,4})|(t\.me/[^\s]+)|(@[a-zA-Z0-9_]+)'
    return bool(re.search(pattern, text))

def contains_bad_word(text):
    text_lower = text.lower()
    for word in BAD_WORDS:
        if re.search(rf'\b{word}\b', text_lower):
            return True
    return False

# --- نظام التعامل مع المخالفات الشامل الحذف والتحذير ---
async def handle_violation(event, violation_type, reason_text):
    chat_id = event.chat_id
    user_id = event.sender_id
    
    # الحذف الفوري والمباشر قبل عمل أي شيء آخر لضمان السرعة
    try:
        await event.delete()
    except Exception as e:
        print(f"Error deleting message: {e}")

    try:
        sender = await event.get_sender()
        user_name = f"@{sender.username}" if (sender and sender.username) else (sender.first_name if sender else "User")
    except Exception:
        user_name = "User"

    warnings[chat_id][user_id] += 1
    current_warns = warnings[chat_id][user_id]
    
    if current_warns >= 3:
        warnings[chat_id][user_id] = 0
        try:
            await client.edit_permissions(chat_id, user_id, until_date=timedelta(minutes=5), send_messages=False)
            await event.respond(f"🚫 {user_name} has been muted for 5 minutes! Reason: Reached 3 warnings for {reason_text}.")
        except Exception:
            await event.respond(f"⚠️ {user_name} violated rules ({reason_text}), but I couldn't mute them.")
    else:
        await event.respond(f"⚠️ {user_name}, {reason_text} is not allowed here! [Warning: {current_warns}/3]")

# --- دالة ويب وهمية لتجنب نوم السيرفر (Keep Alive) ---
async def keep_alive():
    await asyncio.sleep(10)
    app_name = os.environ.get("RENDER_EXTERNAL_HOSTNAME", "my-bot")
    url = f"https://{app_name}.onrender.com"
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                async with session.get(url) as response:
                    pass
            except Exception:
                pass
            await asyncio.sleep(45)

# --- فحص ومراقبة الرسائل والمحادثات في المجموعات (تعديل جذري وسلس) ---
@client.on(events.NewMessage(incoming=True))
async def monitor_group_messages(event):
    if event.is_private:
        return

    chat_id = event.chat_id
    groups_db.add(chat_id)
    
    # استخراج النص المباشر من الحدث
    text = event.raw_text or event.text or ""

    # تجنب فحص الرسائل التي تبدأ بأوامر إدارية حتى لا يحدث تضارب
    if text.startswith('/'):
        return

    # 1. منع الروابط والرسائل المحولة
    if settings['link_filter']:
        if contains_link(text) or event.forward:
            await handle_violation(event, "link", "sending links/forwarded messages")
            return

    # 2. منع اللغات عدا الإنجليزية (مثل الحروف العربية)
    if settings['lang_filter']:
        if not is_english_only(text):
            await handle_violation(event, "language", "using non-English language")
            return

    # 3. الكلمات البذيئة
    if settings['bad_words_filter'] and contains_bad_word(text):
        await handle_violation(event, "bad_word", "using inappropriate words")
        return

    # 4. منع السخام (Spam)
    if settings['spam_filter']:
        user_id = event.sender_id
        now = datetime.now()
        span_tracker[user_id] = [t for t in span_tracker[user_id] if (now - t).total_seconds() < 3]
        span_tracker[user_id].append(now)
        if len(span_tracker[user_id]) > 4:
            await handle_violation(event, "spam", "flooding/spamming")
            return

# --- تنظيف رسائل الخدمة بشكل منفصل تماماً لمنع أي تعليق في الكود ---
@client.on(events.ChatAction)
async def action_cleaner(event):
    if settings['clean_service_msg']:
        if event.user_joined or event.user_left or event.user_kicked:
            try:
                await event.delete()
            except Exception:
                pass

# --- أوامر السيطرة الإدارية بالرد مع ميزة التوجيه المباشر والفعلي ---
@client.on(events.NewMessage(pattern=r'^/(mute|unmute|ban|unban)'))
async def admin_commands(event):
    if event.is_private:
        return
        
    is_admin = False
    try:
        permissions = await client.get_permissions(event.chat_id, event.sender_id)
        if permissions.is_admin or event.sender_id == OWNER_ID:
            is_admin = True
    except Exception:
        pass
        
    if not is_admin:
        return

    command = event.pattern_match.group(1)
    if not event.is_reply:
        await event.respond("Please reply to a user's message to use this command.")
        return

    reply_msg = await event.get_reply_message()
    target_user = reply_msg.sender_id
    
    try:
        sender = await reply_msg.get_sender()
        user_name = f"@{sender.username}" if (sender and sender.username) else "User"
    except Exception:
        user_name = "User"

    try:
        if command == "mute":
            await client.edit_permissions(event.chat_id, target_user, send_messages=False)
            await event.respond(f"🚫 {user_name} has been muted by Admin.")
            await client.forward_messages(OWNER_ID, reply_msg)
        elif command == "unmute":
            await client.edit_permissions(event.chat_id, target_user, send_messages=True)
            await event.respond(f"✅ {user_name} has been unmuted by Admin.")
        elif command == "ban":
            await client.kick_participant(event.chat_id, target_user)
            await event.respond(f"🚷 {user_name} has been banned and kicked by Admin.")
            await client.forward_messages(OWNER_ID, reply_msg)
        elif command == "unban":
            await client.edit_permissions(event.chat_id, target_user, send_messages=True)
            await event.respond(f"🔓 {user_name} has been unbanned.")
    except Exception as e:
        await event.respond(f"Failed to execute admin command: {str(e)}")

# --- لوحة التحكم التفاعلية الشاملة للأزرار ---
@client.on(events.NewMessage(pattern='/panel', incoming=True))
async def send_panel(event):
    if event.sender_id != OWNER_ID:
        return
    users_db.add(event.sender_id)
    await build_and_send_panel(event.chat_id, "🛠️ **Bot Control Panel (Owner Only):**")

@client.on(events.NewMessage(pattern='/start', incoming=True))
async def send_start(event):
    if event.is_private:
        users_db.add(event.sender_id)
        if event.sender_id == OWNER_ID:
            await build_and_send_panel(event.chat_id, "👋 Hello Developer! Here is your Control Panel:")
        else:
            await event.respond("Hello! I am English Only Guard Bot. Add me to your group to protect it.")

async def build_and_send_panel(chat_id, text):
    def get_btn(label, key):
        status = "✅ ON" if settings[key] else "❌ OFF"
        return Button.inline(f"{label}: {status}", data=f"toggle_{key}")

    buttons = [
        [get_btn("English Filter", "lang_filter")],
        [get_btn("Links Filter", "link_filter")],
        [get_btn("Spam Filter", "spam_filter")],
        [get_btn("Bad Words Filter", "bad_words_filter")],
        [get_btn("Service Messages Cleaner", "clean_service_msg")],
        [Button.inline("📊 Show Stats", data="show_stats")]
    ]
    await client.send_message(chat_id, text, buttons=buttons)

# --- معالجة ضغطات أزرار لوحة التحكم التفاعلية ---
@client.on(events.CallbackQuery(data=re.compile(b'toggle_(.*)')))
async def on_toggle_setting(event):
    if event.sender_id != OWNER_ID:
        await event.answer("You are not authorized!", alert=True)
        return
        
    key = event.pattern_match.group(1).decode('utf-8')
    settings[key] = not settings[key]
    
    def get_btn(label, key_name):
        status = "✅ ON" if settings[key_name] else "❌ OFF"
        return Button.inline(f"{label}: {status}", data=f"toggle_{key_name}")

    buttons = [
        [get_btn("English Filter", "lang_filter")],
        [get_btn("Links Filter", "link_filter")],
        [get_btn("Spam Filter", "spam_filter")],
        [get_btn("Bad Words Filter", "bad_words_filter")],
        [get_btn("Service Messages Cleaner", "clean_service_msg")],
        [Button.inline("📊 Show Stats", data="show_stats")]
    ]
    await event.edit("🛠️ **Bot Control Panel (Owner Only):**", buttons=buttons)
    await event.answer("Settings updated successfully!")

@client.on(events.CallbackQuery(data=b'show_stats'))
async def on_show_stats(event):
    if event.sender_id != OWNER_ID:
        await event.answer("You are not authorized!", alert=True)
        return
    stats_text = (
        "📊 **Bot Current Statistics:**\n\n"
        f"👥 Active Users in DB: {len(users_db)}\n"
        f"📢 Monitored Groups: {len(groups_db)}"
    )
    await event.respond(stats_text)
    await event.answer()

# --- تشغيل البوت مع نظام تجنب النوم ---
async def main():
    asyncio.create_task(keep_alive())
    print("Bot started successfully...")
    await client.run_until_disconnected()

if __name__ == '__main__':
    import sys
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.get_event_loop().run_until_complete(main())
