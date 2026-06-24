from datetime import datetime, date
from zoneinfo import ZoneInfo
from sqlalchemy import select
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.database.db import AsyncSessionLocal
from app.database.models.user import User
from app.services.lesson_service import create_lesson_for_user
from app.services.srs import count_due_words
from app.bot import bot
from app.keyboards.lesson import lesson_kb
from app.keyboards.srs import srs_reminder_kb
from app.locales import t

TZ = ZoneInfo("Europe/Moscow")

scheduler = AsyncIOScheduler(timezone=TZ)

LESSONS_SENT_TODAY = set()


async def send_daily_lessons():
    now = datetime.now(TZ).strftime("%H:%M")
    today = date.today()

    async with AsyncSessionLocal() as session:
        stmt = select(User).where(User.lesson_time == now)
        result = await session.execute(stmt)
        users = result.scalars().all()

    for user in users:
        if (user.telegram_id, today) in LESSONS_SENT_TODAY:
            continue

        # 1. Генерируем и отправляем урок (общая функция-сервис)
        lesson_data = await create_lesson_for_user(user)
        lang = user.interface_language or "en"

        await bot.send_message(
            user.telegram_id,
            f"{lesson_data['title']}\n\n{lesson_data['text']}",
            reply_markup=lesson_kb(lang)
        )

        LESSONS_SENT_TODAY.add((user.telegram_id, today))

        # 2. Если есть слова на повторение — одно деликатное напоминание.
        #    Никакого ежечасного спама: одно сообщение с кнопкой "Повторить".
        due = await count_due_words(user.telegram_id, user.target_language or "en")
        if due > 0:
            await bot.send_message(
                user.telegram_id,
                t("repeat_reminder", lang).format(count=due),
                reply_markup=srs_reminder_kb(lang)
            )


def start_scheduler():
    # Только ежедневный урок. Ежечасную рассылку карточек убрали —
    # именно она спамила ночью одним словом каждый час.
    scheduler.add_job(send_daily_lessons, "interval", minutes=1)
    scheduler.start()