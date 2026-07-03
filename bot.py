from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
import asyncio
import os

# قراءة التوكن من المتغيرات البيئية
BOT_TOKEN = os.environ.get('BOT_TOKEN')

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer("أهلاً بك! البوت يعمل الآن بنجاح باستخدام Aiogram.")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
