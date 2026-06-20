from datetime import datetime, date
from zoneinfo import ZoneInfo
from sqlalchemy import select
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.database.db import AsyncSessionLocal
from app.database.models.user import User
from app.database.models.vocab import Vocab
from app.services.ai import generate_ai_lesson
from app.bot import bot
from app.services.srs import send_next_card
from app.keyboards.lesson import lesson_kb
from app.services.memory import LESSONS

# Часовой пояс по которому пользователи задают время урока.
# Сервер может жить по UTC, но мы всегда считаем по Москве —
# тогда поведение одинаковое и локально, и на сервере.
TZ = ZoneInfo("Europe/Moscow")

scheduler = AsyncIOScheduler(timezone=TZ)

# Защита от повторной отправки в течение дня.
LESSONS_SENT_TODAY = set()


# -------------------------
# 1. DAILY LESSON
# -------------------------
async def send_daily_lessons():
    # Текущее время ИМЕННО по Москве, а не по часовому поясу сервера.
    now = datetime.now(TZ).strftime("%H:%M")
    today = date.today()

    async with AsyncSessionLocal() as session:
        stmt = select(User).where(User.lesson_time == now)
        result = await session.execute(stmt)
        users = result.scalars().all()

        for user in users:
            if (user.telegram_id, today) in LESSONS_SENT_TODAY:
                continue

            lesson = await generate_ai_lesson(user)

            lesson_data = {
                "title": lesson.get("title", "📖 Daily English"),
                "text": lesson["text"],
                "translation": lesson["translation"],
                "questions": lesson.get("questions", []),
                "vocab": lesson.get("vocab", [])[:7],
            }

            LESSONS[user.telegram_id] = lesson_data

            await bot.send_message(
                user.telegram_id,
                f"{lesson_data['title']}\n\n{lesson_data['text']}",
                reply_markup=lesson_kb(user.interface_language or "en")
            )

            LESSONS_SENT_TODAY.add((user.telegram_id, today))

            for v in lesson_data["vocab"]:
                existing = await session.execute(
                    select(Vocab).where(
                        Vocab.telegram_id == user.telegram_id,
                        Vocab.word == v["word"]
                    )
                )
                if not existing.scalar_one_or_none():
                    session.add(
                        Vocab(
                            telegram_id=user.telegram_id,
                            word=v["word"],
                            translation=v["translation"],
                            stage=0,
                            # next_review тоже по Москве, чтобы всё было в одной шкале
                            next_review=datetime.now(TZ).replace(tzinfo=None)
                        )
                    )

            await session.commit()


# -------------------------
# 2. REPEAT LESSONS
# -------------------------
async def send_repeat_lessons():
    # Сравниваем по той же шкале (Москва, без tzinfo — naive),
    # чтобы согласовать с next_review выше.
    now = datetime.now(TZ).replace(tzinfo=None)

    async with AsyncSessionLocal() as session:
        stmt = select(Vocab).where(Vocab.next_review <= now)
        result = await session.execute(stmt)
        words = result.scalars().all()

        users = set(w.telegram_id for w in words)

        for telegram_id in users:
            user_lang = "en"
            async with AsyncSessionLocal() as user_session:
                user_result = await user_session.execute(
                    select(User).where(User.telegram_id == telegram_id)
                )
                user = user_result.scalar_one_or_none()
                if user and user.interface_language:
                    user_lang = user.interface_language

            await send_next_card(telegram_id, user_lang)

        await session.commit()


# -------------------------
# 3. START SCHEDULER
# -------------------------
def start_scheduler():
    scheduler.add_job(send_daily_lessons, "interval", minutes=1)
    scheduler.add_job(send_repeat_lessons, "interval", minutes=60)
    scheduler.start()