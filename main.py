import asyncio, os
from aiohttp import web
from aiogram import Bot, Dispatcher
import db
from handlers import router

async def health(request):
    return web.Response(text="Chef-bot is alive 🍽")

async def run_web():
    app = web.Application()
    app.router.add_get("/", health)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", 10000)))
    await site.start()

async def main():
    db.init()
    bot = Bot(os.environ["BOT_TOKEN"])
    dp = Dispatcher()
    dp.include_router(router)
    await run_web()                 # Render требует открытый порт
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
