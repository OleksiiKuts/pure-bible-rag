import os
import asyncio
import aiohttp
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
API_URL = "http://127.0.0.1:8000/api/v1/search"

bot = Bot(token=TOKEN)
dp = Dispatcher()

@dp.message(CommandStart())
async def command_start_handler(message: types.Message) -> None:
    welcome_text = (
        "Вітаю! Я — Біблійний Асистент.\n\n"
        "Напиши мені своє запитання, і я знайду найбільш релевантні біблійні "
        "уривки, використовуючи наш семантичний фільтр."
    )
    await message.answer(welcome_text)

@dp.message()
async def handle_search_query(message: types.Message) -> None:
    user_query = message.text
    await message.answer("🔍 Шукаю відповідь у базі... Це може зайняти кілька секунд.")
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(API_URL, json={"query": user_query}) as response:
                if response.status == 200:
                    data = await response.json()
                    approved = data.get("approved_verses", [])
                    
                    if not approved:
                        await message.answer("На жаль, я не знайшов релевантних уривків за вашим запитом.")
                        return
                        
                    reply_text = "✅ **Знайдені уривки:**\n\n"
                    for verse in approved:
                        reply_text += f"📖 **{verse['reference']}**\n{verse['text']}\n\n"
                        
                    # Запобіжник: повідомлення в Telegram не може бути довшим за 4096 символів
                    if len(reply_text) > 4000:
                        reply_text = reply_text[:4000] + "...\n(Текст обрізано)"
                        
                    await message.answer(reply_text, parse_mode="Markdown")
                else:
                    await message.answer("⚠️ Помилка на стороні сервера API.")
    except Exception as e:
        await message.answer(f"❌ Виникла помилка при підключенні до API: {str(e)}")

async def main() -> None:
    print("🤖 Бот запущений і готовий до роботи!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())