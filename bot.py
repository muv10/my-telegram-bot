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
# قم بتغيير هذا الرقم إلى الأيدي الخاص بك لتلقي الإشعارات والتحكم
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
    cleaned_text = re.sub(r'[\d\s\W_]', '', text)
    if not cleaned_text:
        return True
    return all(char.isalpha() and char.isascii() for char in cleaned_text)

def contains_link(text):
    pattern = r'(https?://[^\s]+)|(www\.[^\s]+)|([a-zA-Z0-9-]+\.[a-zA-Z]{2,})'
    return bool(re.search(pattern, text))

def contains_bad_word(text):
    text_lower = text.lower()
    for word in BAD_WORDS:
        if re.search(rf'\b{word}\b', text_lower):
            return True
    return False

# --- نظام التعامل مع المخالفات (3 تحذيرات ثم كتم 5 دقائق) ---
async def handle_violation(event, violation_type, reason_text):
    chat_id = event.chat_id
    user_id = event.sender_id
    user_name = f"@{event.sender.username}" if (event.sender and event.sender.username) else (event.sender.first_name if event.sender else "User")
    
    await event.delete()
    warnings[chat_id][user_id] += 1
    current_warns = warnings[chat_id][user_id]
    
    if current_warns >= 3:
        warnings[chat_id][user_id] = 0  # تصفير العداد بعد الكتم
        try:
            # كتم العضو لمدة 5 دقائق عبر سحب صلاحية إرسال الرسائل
            await client.edit_permissions(chat_id, user_id, until_date=timedelta(minutes=5), send_messages=False)
            await event.respond(f"🚫 {user_name} has been muted for 5 minutes! Reason: Reached 3 warnings for {reason_text}.")
        except Exception as e:
            await event.respond(f"⚠️ {user_name} violated rules ({reason_text}), but I couldn't mute them (Check Admin Permissions).")
    else:
        await event.respond(f"⚠️ {user_name}, {reason_text} is not allowed here! [Warning: {current_warns}/3]")

# --- دالة ويب وهمية لتجنب نوم السيرفر (Keep Alive) ---
async def keep_alive():
    await asyncio.sleep(10)
    # في حال طلب ويب لنفسه ونحن نستخدم Render نستخدم رابط السيرفر التلقائي من #
    app_name = os.environ.get("RENDER_EXTERNAL_HOSTNAME", "my-bot")
    url = f"https://{app_name}.onrender.com"
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                # نرسل طلب وهمي لنفس السيرفر لإبقائه نشطاً ومستيقظاً #
                async with session.get(url) as response:
                    pass
            except Exception:
                pass
            await asyncio.sleep(45)

# --- أولاً إلى رابعاً وعشرة: فحص ومراقبة الرسائل والمحادثات ---
@client.on(events.NewMessage(incoming=True))
async def monitor_group_messages(event):
    if event.is_private:
        return

    chat_id = event.chat_id
    groups_db.add(chat_id)
    text = event.text or ""

    # الخدمة 13: حذف رسائل انضمام ومغادرة الأعضاء (تم إصلاحها بالكامل هنا)
    if settings['clean_service_msg'] and event.is_group:
        if event.action_message:
            await event.delete()
            return

    # الفحص الأول: الكلمات البذيئة والجنسية #
    if settings['bad_words_filter'] and contains_bad_word(text):
        await handle_violation(event, "bad_word", "using inappropriate words")
        return

    # الفحص الثاني: منع الروابط #
    if settings['link_filter'] and contains_link(text):
        await handle_violation(event, "link", "sending links")
        return

    # الفحص الثالث: منع السباام (أكثر من 4 رسائل في غضون 3 ثوانٍ) #
    if settings['spam_filter']:
        user_id = event.sender_id
        now = datetime.now()
        span_tracker[user_id] = [t for t in span_tracker[user_id] if (now - t).total_seconds() < 3]
        span_tracker[user_id].append(now)
        if len(span_tracker[user_id]) > 4:
            await handle_violation(event, "spam", "flooding/spamming")
            return

    # الفحص الرابع: منع اللغات عدا الإنجليزية #
    if settings['lang_filter'] and not is_english_only(text):
        await handle_violation(event, "language", "using non-English language")
        return

# --- سادساً: أوامر السيطرة الإدارية بالرد (/mute, /unmute, /ban, /unban) ---
@client.on(events.NewMessage(pattern=r'^/(mute|unmute|ban|unban)'))
async def admin_commands(event):
    if event.is_private:
        return
        
    # التحقق من أن المستخدم مشرف أو المطور نفسه #
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
    user_name = f"@{reply_msg.sender.username}" if (reply_msg.sender and reply_msg.sender.username) else "User"

    try:
        if command == "mute":
            await client.edit_permissions(event.chat_id, target_user, send_messages=False)
            await event.respond(f"🚫 {user_name} has been muted by Admin.")
        elif command == "unmute":
            await client.edit_permissions(event.chat_id, target_user, send_messages=True)
            await event.respond(f"✅ {user_name} has been unmuted by Admin.")
        elif command == "ban":
            await client.kick_participant(event.chat_id, target_user)
            await event.respond(f"🚷 {user_name} has been banned and kicked by Admin.")
        elif command == "unban":
            # في التليثون الغاء الحظر يتم باعادة تفعيل الصلاحيات أو دعوته
            await client.edit_permissions(event.chat_id, target_user, send_messages=True)
            await event.respond(f"🔓 {user_name} has been unbanned.")
    except Exception as e:
        await event.respond(f"Failed to execute admin command: {str(e)}")

# --- سابعاً: لوحة التحكم التفاعلية الشاملة للأزرار (للمطور فقط في الخاص) ---
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

# --- ثامناً: معالجة ضغطات أزرار لوحة التحكم التفاعلية ---
@client.on(events.CallbackQuery(data=re.compile(b'toggle_(.*)')))
async def on_toggle_setting(event):
    if event.sender_id != OWNER_ID:
        await event.answer("You are not authorized!", alert=True)
        return
        
    key = event.pattern_match.group(1).decode('utf-8')
    settings[key] = not settings[key] # عكس القيمة التفعيلية
    
    # تحديث اللوحة والأزرار تلقائياً بعد التعديل
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
