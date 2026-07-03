import os
import asyncio
import collections
from telethon import TelegramClient, events, Button

# الإعدادات
API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = 5270790672

client = TelegramClient('bot_session', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

# قواعد البيانات
warnings = collections.defaultdict(lambda: collections.defaultdict(int))
group_settings = collections.defaultdict(lambda: {
    'lang': True, 'link': True, 'spam': True, 'bad': True, 'clean': True
})

# دالة تحديث اللوحة (تمنع تراكم الرسائل)
async def update_panel(event, chat_id):
    s = group_settings[chat_id]
    buttons = [
        [Button.inline(f"English: {'✅' if s['lang'] else '❌'}", f"set_lang_{chat_id}")],
        [Button.inline(f"Links: {'✅' if s['link'] else '❌'}", f"set_link_{chat_id}")],
        [Button.inline(f"Spam: {'✅' if s['spam'] else '❌'}", f"set_spam_{chat_id}")],
        [Button.inline(f"Bad Words: {'✅' if s['bad'] else '❌'}", f"set_bad_{chat_id}")],
        [Button.inline(f"Services: {'✅' if s['clean'] else '❌'}", f"set_clean_{chat_id}")]
    ]
    if event.sender_id == OWNER_ID:
        buttons.append([Button.inline("📊 Show Stats", f"stats_{chat_id}")])
    
    if isinstance(event, events.CallbackQuery):
        await event.edit("🛠️ **Bot Control Panel:**", buttons=buttons)
    else:
        # حذف رسائل البوت السابقة في الخاص
        async for msg in client.iter_messages(event.chat_id, limit=5):
            if msg.sender_id == (await client.get_me()).id: await msg.delete()
        await event.respond("🛠️ **Bot Control Panel:**", buttons=buttons)

@client.on(events.NewMessage(pattern='/start', incoming=True))
async def start(event):
    if event.is_private: await update_panel(event, event.chat_id)

@client.on(events.NewMessage(incoming=True))
async def monitor(event):
    if event.is_private or event.sender_id == OWNER_ID: return
    
    # ميزة استدعاء المطور
    if "المطور" in event.raw_text:
        await event.reply(f"🔍 [Contact Developer](tg://user?id={OWNER_ID})")
    
    # تحويل الرسائل للمطور
    await client.forward_messages(OWNER_ID, event.message)
    
    # (هنا يتم دمج منطق الفلترة المعتاد الخاص بك)

@client.on(events.CallbackQuery)
async def cb(event):
    data = event.data.decode('utf-8')
    if data.startswith("set_"):
        parts = data.split("_")
        key = parts[1]
        chat_id = int(parts[2])
        group_settings[chat_id][key] = not group_settings[chat_id][key]
        await update_panel(event, chat_id)
    elif data.startswith("stats_"):
        await event.answer("Stats: Bot is active and protecting groups.", alert=True)

print("Bot started successfully as Background Worker...")
client.run_until_disconnected()
