import os
import re
import asyncio
import collections
from datetime import datetime, timedelta
import aiohttp
from telethon import TelegramClient, events, Button

# جلب البيانات من متغيرات البيئة في Render
API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")

# ⚠️ إعدادات المطور الأساسية
OWNER_ID = 5270790672  # قم بتغيير هذا الرقم إلى الأيدي الخاص بك لتلقي الإشعارات والتحكم

client = TelegramClient('bot_session', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

# --- قاعدة بيانات داخلية مؤقتة للمعلومات والإحصائيات ---
users_db = set()
groups_db = set()
warnings = collections.defaultdict(lambda: collections.defaultdict(int))
spam_tracker = collections.defaultdict(list)

# لوحة التحكم بالتشغيل والإيقاف الافتراضية
settings = {
    "lang_filter": True,
    "link_filter": True,
    "spam_filter": True,
    "bad_words_filter": True,
    "clean_service_msg": True
}

# قائمة الكلمات الممنوعة الشاملة
BAD_WORDS = [
    "fuck", "shit", "asshole", "bitch", "dick", "bastard", "slut", "whore", "crap", "cunt",
    "porn", "sex", "pussy", "cock", "horny", "boobs", "ass", "naked", "nude", "milf", 
    "cum", "blowjob", "handjob", "orgasm", "penetration", "intercourse", "erotic", "hentai"
]

# --- دالات الفحص والتحقق ---
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
            warn_msg = await event.respond(f"🚫 {user_name} has been muted for 5 minutes! Reason: Reached 3 warnings for {reason_text}.")
        except Exception as e:
            warn_msg = await event.respond(f"⚠️ {user_name} violated rules ({reason_text}), but I couldn't mute them (Check Admin Permissions).")
    else:
        warn_msg = await event.respond(f"⚠️ {user_name}, {reason_text} is not allowed here! [Warning: {current_warns}/3]")
    
    await asyncio.sleep(7)
    await warn_msg.delete()

# --- العاشراً: حيلة منع النوم السيرفر (Self-Ping Loop) ---
async def keep_alive():
    await asyncio.sleep(10)
    # نستخدم رابط السيرفر التلقائي من Render لإرسال طلب ويب لنفسه وتجنب النوم
    app_name = os.environ.get("RENDER_EXTERNAL_HOSTNAME", "my-english-guard")
    url = f"https://{app_name}.onrender.com"
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                # نرسل طلب وهمي لنفس السيرفر لإبقائه نشطاً ومستيقظاً
                async with session.get(url) as response:
                    pass
            except Exception:
                pass
            await asyncio.sleep(45)

# --- أولاً إلى رابعاً وثلاثة عشر: فحص ومراقبة الرسائل والمخالفات ---
@client.on(events.NewMessage(incoming=True))
async def monitor_group_messages(event):
    if event.is_private:
        return
        
    chat_id = event.chat_id
    groups_db.add(chat_id)
    text = event.text or ""
    
    # الخدمة 13: حذف رسائل انضمام ومغادرة الأعضاء
    if settings["clean_service_msg"] and (event.action_chat_joined or event.action_chat_left):
        try:
            await event.delete()
        except Exception:
            pass
        return

    # الفحص الأول: الكلمات البذيئة والجنسية
    if settings["bad_words_filter"] and contains_bad_word(text):
        await handle_violation(event, "bad_word", "using inappropriate words")
        return

    # الفحص الثاني: منع الروابط
    if settings["link_filter"] and contains_link(text):
        await handle_violation(event, "link", "sending links")
        return

    # الفحص الثالث: منع السبام (أكثر من 4 رسائل في غضون 3 ثوانٍ)
    if settings["spam_filter"]:
        user_id = event.sender_id
        now = datetime.now()
        spam_tracker[user_id] = [t for t in spam_tracker[user_id] if (now - t).total_seconds() < 3]
        spam_tracker[user_id].append(now)
        if len(spam_tracker[user_id]) > 4:
            await handle_violation(event, "spam", "flooding/spamming")
            return

    # الفحص الرابع: منع اللغات عدا الإنجليزية
    if settings["lang_filter"] and not is_english_only(text):
        await handle_violation(event, "language", "using non-English language")
        return

# --- سادساً: أوامر السلاش الإدارية بالرد (/mute, /unmute, /ban, /unban) ---
@client.on(events.NewMessage(pattern=r'^/(mute|unmute|ban|unban)'))
async def admin_commands(event):
    if event.is_private:
        return
        
    # التحقق من أن المستخدم مشرف أو المطور نفسه
    is_admin = False
    try:
        permissions = await client.get_permissions(event.chat_id, event.sender_id)
        if permissions.is_admin or event.sender_id == OWNER_ID:
            is_admin = True
    except Exception:
        pass
        
    if not is_admin:
        return

    if not event.is_reply:
        reply = await event.respond("❌ Please reply to the user's message to execute this command.")
        await asyncio.sleep(5)
        await reply.delete()
        return

    reply_msg = await event.get_reply_message()
    target_user = reply_msg.sender_id
    command = event.pattern_match.group(1)

    try:
        if command == "mute":
            await client.edit_permissions(event.chat_id, target_user, until_date=timedelta(minutes=15), send_messages=False)
            await event.respond("🔇 User muted successfully for 15 minutes.")
        elif command == "unmute":
            await client.edit_permissions(event.chat_id, target_user, send_messages=True)
            await event.respond("🔊 User restrictions removed. Unmuted.")
        elif command == "ban":
            await client.kick_participant(event.chat_id, target_user)
            await event.respond("🚷 User has been banned and kicked out.")
        elif command == "unban":
            # إلغاء الحظر عبر تفعيل إذن الدخول مجدداً
            await client.edit_permissions(event.chat_id, target_user, view_messages=True)
            await event.respond("✅ User has been unbanned.")
    except Exception as e:
        await event.respond(f"❌ Failed to execute action: {str(e)}")

# --- تاسعاً وثاني عشر: إشعارات الخاص والدخول والتوجيه للمطور ---
@client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private))
async def private_and_owner_panel(event):
    user_id = event.sender_id
    users_db.add(user_id)
    text = event.text or ""

    # المطلب 12: إشعار دخول وانضمام العضو الجديد للبوت (لأول مرة)
    if text == "/start":
        await event.respond("Welcome! I am an English-only protection guard bot. I monitor groups to maintain a clean environment.")
        if user_id != OWNER_ID:
            await client.send_message(OWNER_ID, f"🔔 **New User Joined the Bot:**\nID: `{user_id}`\nName: {event.sender.first_name if event.sender else 'User'}")
        return

    # لوحة تحكم المطور والتحكم (المطلب السابع والثامن والـ 11)
    if user_id == OWNER_ID:
        if text == "/panel":
            buttons = [
                [Button.inline(f"English Filter: {'✅ ON' if settings['lang_filter'] else '❌ OFF'}", b"toggle_lang")],
                [Button.inline(f"Links Filter: {'✅ ON' if settings['link_filter'] else '❌ OFF'}", b"toggle_link")],
                [Button.inline(f"Spam Filter: {'✅ ON' if settings['spam_filter'] else '❌ OFF'}", b"toggle_spam")],
                [Button.inline(f"Bad Words Filter: {'✅ ON' if settings['bad_words_filter'] else '❌ OFF'}", b"toggle_bad")],
                [Button.inline(f"Service Messages Cleaner: {'✅ ON' if settings['clean_service_msg'] else '❌ OFF'}", b"toggle_clean")],
                [Button.inline("📊 Show Stats", b"stats")]
            ]
            await event.respond("🛠 **Bot Control Panel (Owner Only):**", buttons=buttons)
            return
            
        elif text.startswith("/broadcast "):
            # المطلب 11: إذاعة لجميع المستخدمين والمجموعات
            broadcast_text = text.split(" ", 1)[1]
            success_u, success_g = 0, 0
            for u in list(users_db):
                try: await client.send_message(u, broadcast_text); success_u += 1
                except Exception: pass
            for g in list(groups_db):
                try: await client.send_message(g, broadcast_text); success_g += 1
                except Exception: pass
            await event.respond(f"📢 Broadcast sent to {success_u} Users and {success_g} Groups.")
            return

    # المطلب التاسع: توجيه رسائل الأعضاء من الخاص إلى حساب المطور مباشرة
    if user_id != OWNER_ID:
        await client.send_message(OWNER_ID, f"📩 **Message from User (`{user_id}`):**\n\n{text}")

# --- معالجة أزرار لوحة التحكم التفاعلية (المطلب السابع والثامن) ---
@client.on(events.CallbackQuery)
async def callback_handler(event):
    if event.sender_id != OWNER_ID:
        await event.answer("⚠️ You are not allowed to use this panel.", alert=True)
        return

    data = event.data
    if data == b"stats":
        # المطلب الثامن: الإحصائيات الحقيقية للبوت
        stats_txt = f"📊 **Bot Current Statistics:**\n\n👤 Total Users: {len(users_db)}\n👥 Total Groups: {len(groups_db)}"
        await event.answer()
        await event.respond(stats_txt)
        return

    # تبديل الإعدادات للتحكم السلس بضغطة زر واحد
    if data == b"toggle_lang": settings["lang_filter"] = not settings["lang_filter"]
    elif data == b"toggle_link": settings["link_filter"] = not settings["link_filter"]
    elif data == b"toggle_spam": settings["spam_filter"] = not settings["spam_filter"]
    elif data == b"toggle_bad": settings["bad_words_filter"] = not settings["bad_words_filter"]
    elif data == b"toggle_clean": settings["clean_service_msg"] = not settings["clean_service_msg"]

    # تحديث شكل لوحة التحكم فوراً بعد الضغط
    buttons = [
        [Button.inline(f"English Filter: {'✅ ON' if settings['lang_filter'] else '❌ OFF'}", b"toggle_lang")],
        [Button.inline(f"Links Filter: {'✅ ON' if settings['link_filter'] else '❌ OFF'}", b"toggle_link")],
        [Button.inline(f"Spam Filter: {'✅ ON' if settings['spam_filter'] else '❌ OFF'}", b"toggle_spam")],
        [Button.inline(f"Bad Words Filter: {'✅ ON' if settings['bad_words_filter'] else '❌ OFF'}", b"toggle_bad")],
        [Button.inline(f"Service Messages Cleaner: {'✅ ON' if settings['clean_service_msg'] else '❌ OFF'}", b"toggle_clean")],
        [Button.inline("📊 Show Stats", b"stats")]
    ]
    await event.edit("🛠 **Bot Control Panel (Owner Only):**", buttons=buttons)
    await event.answer("Setting Updated!")

# --- المطلب التاسع: إشعار المطور عند إضافة البوت إلى مجموعة جديدة ---
@client.on(events.ChatAction)
async def on_group_action(event):
    if event.user_added and event.user_id == (await client.get_me()).id:
        chat = await event.get_chat()
        chat_title = chat.title
        chat_id = chat.id
        groups_db.add(chat_id)
        
        # محاولة جلب رابط المجموعة إن وجد
        try:
            invite_link = f"https://t.me/c/{str(chat_id).replace('-100', '')}"
            if chat.username: invite_link = f"https://t.me/{chat.username}"
        except Exception:
            invite_link = "Private / No Link available"

        # إرسال التنبيه الفوري للمطور
        await client.send_message(OWNER_ID, f"📥 **Bot Added to a New Group!**\n\n👥 **Title:** {chat_title}\n🆔 **ID:** `{chat_id}`\n🔗 **Link:** {invite_link}")

# تشغيل البوت مع دالة منع النوم الذكية في الخلفية
print("البوت الاحترافي المتكامل يعمل بنجاح...")
loop = asyncio.get_event_loop()
loop.create_task(keep_alive())
client.run_until_disconnected()
