import asyncio
from aiogram import Dispatcher

from app.bot import bot
from app.database.db import init_db
from app.services.scheduler import start_scheduler

from app.handlers.start import router as start_router
from app.handlers.register import router as register_router
from app.handlers.lesson import router as lesson_router
from app.handlers.srs import router as srs_router
from app.handlers.menu import router as menu_router
from app.middlewares.i18n import I18nMiddleware

dp = Dispatcher()


dp.update.middleware(I18nMiddleware())
dp.include_router(start_router)
dp.include_router(register_router)
dp.include_router(menu_router)
dp.include_router(lesson_router)
dp.include_router(srs_router)


async def main():
    await init_db()
    start_scheduler()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())