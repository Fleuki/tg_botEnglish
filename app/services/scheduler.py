from datetime import datetime, date
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

scheduler = AsyncIOScheduler()

# Track which users have received lessons today
LESSONS_SENT_TODAY = set()


# -------------------------
# 1. DAILY LESSON
# -------------------------

async def send_daily_lessons():
    now = datetime.now().strftime("%H:%M")
    today = date.today()

    async with AsyncSessionLocal() as session:
        stmt = select(User).where(User.lesson_time == now)
        result = await session.execute(stmt)
        users = result.scalars().all()

        for user in users:
            # Skip if already sent today
            if (user.telegram_id, today) in LESSONS_SENT_TODAY:
                continue

            lesson = await generate_ai_lesson(user)

            # 🔥 фиксируем структуру урока
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

            # Mark as sent today
            LESSONS_SENT_TODAY.add((user.telegram_id, today))

            # сохраняем слова в БД
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
                            next_review=datetime.utcnow()
                        )
                    )

            await session.commit()


# -------------------------
# 2. REPEAT LESSONS
# -------------------------
async def send_repeat_lessons():

    now = datetime.utcnow()

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
