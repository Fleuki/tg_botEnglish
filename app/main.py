import asyncio
from aiogram import Dispatcher
from aiogram.types import BotCommand

from app.bot import bot
from app.database.db import init_db
from app.services.scheduler import start_scheduler

from app.handlers.start import router as start_router
from app.handlers.register import router as register_router
from app.handlers.lesson import router as lesson_router
from app.handlers.srs import router as srs_router
from app.handlers.menu import router as menu_router
from app.middlewares.i18n import I18nMiddleware
from app.handlers import settings
from app.handlers import check_text

dp = Dispatcher()

dp.update.middleware(I18nMiddleware())

# Порядок роутеров важен: сначала start и register (регистрация),
# потом settings, menu и остальные.
dp.include_router(start_router)
dp.include_router(register_router)
dp.include_router(settings.router)
dp.include_router(menu_router)
dp.include_router(lesson_router)
dp.include_router(srs_router)
dp.include_router(check_text.router)

async def set_commands():
    """Меню команд, которое видно в кнопке слева от поля ввода."""
    commands = [
        BotCommand(command="start", description="Регистрация / перезапуск"),
        BotCommand(command="menu", description="Главное меню"),
        BotCommand(command="settings", description="Настройки профиля"),
    ]
    await bot.set_my_commands(commands)


async def main():
    await init_db()
    await set_commands()      # устанавливаем меню команд при запуске
    start_scheduler()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())