import os
import re
import time
import asyncio
from telethon import TelegramClient, events

# جلب البيانات السرية من إعدادات السيرفر للحفاظ على أمان بوتك
API_ID = int(os.environ.get("API_ID", 12345))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

# تشغيل البوت
bot = TelegramClient('bot_session', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

# نظام تعقب السبام (التكرار)
user_messages = {}

def is_spam(user_id):
    now = time.time()
    if user_id not in user_messages:
        user_messages[user_id] = []
    # تنظيف الرسائل الأقدم من 5 ثوانٍ
    user_messages[user_id] = [t for t in user_messages[user_id] if now - t < 5]
    user_messages[user_id].append(now)
    # إذا أرسل أكثر من 4 رسائل في 5 ثوانٍ يعتبر سبام
    if len(user_messages[user_id]) > 4:
        return True
    return False

async def delete_warning(reply_msg):
    """دالة لحذف رسالة التحذير بعد 5 ثوانٍ للحفاظ على نظافة المجموعة"""
    await asyncio.sleep(5)
    try:
        await reply_msg.delete()
    except Exception:
        pass

# فحص الرسائل في المجموعات
@bot.on(events.NewMessage(incoming=True))
async def group_filter(event):
    if not event.is_group:
        return
    
    text = event.raw_text
    user_id = event.sender_id
    
    # 1. منع الروابط والمعرفات
    url_pattern = r'(https?://[^\s]+|t\.me/[^\s]+|@[a-zA-Z0-9_]+)'
    if re.search(url_pattern, text):
        try:
            await event.delete()
            reply = await event.respond("⚠️ **Links and usernames are not allowed here!**")
            bot.loop.create_task(delete_warning(reply))
        except Exception:
            pass
        return

    # 2. منع السبام (التكرار)
    if is_spam(user_id):
        try:
            await event.delete()
            reply = await event.respond("⚠️ **Stop spamming! Multiple messages are not allowed.**")
            bot.loop.create_task(delete_warning(reply))
        except Exception:
            pass
        return

    # 3. السماح باللغة الإنجليزية فقط ومنع بقية اللغات (كالعربية)
    if text.strip():
        # نمط يسمح بالحروف الإنجليزية، الأرقام، المسافات، الرموز، والـ Emojis فقط
        allowed_pattern = r'^[a-zA-Z0-9\s\.,!\?@#\$%\^&\*\(\)_\+=\-\[\]\{\};:\'"<>/\?\\|`~\U00010000-\U0010ffff]*$'
        if not re.match(allowed_pattern, text):
            try:
                await event.delete()
                reply = await event.respond("⚠️ **Only English language is allowed in this group!**")
                bot.loop.create_task(delete_warning(reply))
            except Exception:
                pass
            return

print("🤖 البوت يعمل بنجاح والردود بالإنجليزية فقط...")
bot.run_until_disconnected()
