from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from sqlalchemy import select
from app.database.db import AsyncSessionLocal
from app.database.models.user import User
from app.database.models.vocab import Vocab

TZ = ZoneInfo("Europe/Moscow")


async def update_user_activity(telegram_id: int):
    """Засчитывает учебный день и считает стрик.
    Вызывать ТОЛЬКО при реальном учебном действии
    (ответ на вопрос / ответ на карточку), не при открытии меню."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        if not user:
            return 0

        now = datetime.now(TZ).replace(tzinfo=None)
        today = now.date()

        if user.last_activity_date:
            last_date = user.last_activity_date.date()
            yesterday = today - timedelta(days=1)

            if last_date == today:
                streak = user.streak_days          # уже занимался сегодня
            elif last_date == yesterday:
                streak = user.streak_days + 1      # занимался вчера — +1
            else:
                streak = 1                          # был перерыв — сброс
        else:
            streak = 1

        user.last_activity_date = now
        user.streak_days = streak
        await session.commit()
        return streak


async def get_learned_words_count(telegram_id: int):
    async with AsyncSessionLocal() as session:
        stmt = select(Vocab).where(
            Vocab.telegram_id == telegram_id,
            Vocab.next_review == None
        )
        result = await session.execute(stmt)
        return len(result.scalars().all())


async def get_user_stats(telegram_id: int):
    async with AsyncSessionLocal() as session:
        user_result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = user_result.scalar_one_or_none()

        if not user:
            return {
                "learned_words": 0,
                "in_progress": 0,
                "streak_days": 0,
                "level": "A1",
                "lesson_time": "Not set"
            }

        vocab_stmt = select(Vocab).where(
            Vocab.telegram_id == telegram_id,
            Vocab.next_review == None
        )
        vocab_result = await session.execute(vocab_stmt)
        learned_words = len(vocab_result.scalars().all())

        in_progress_stmt = select(Vocab).where(
            Vocab.telegram_id == telegram_id,
            Vocab.next_review != None
        )
        in_progress_result = await session.execute(in_progress_stmt)
        in_progress = len(in_progress_result.scalars().all())

        return {
            "learned_words": learned_words,
            "in_progress": in_progress,
            "streak_days": user.streak_days or 0,
            "level": user.level or "A1",
            "lesson_time": user.lesson_time or "Not set"
        }

async def get_in_progress_count(telegram_id: int):
    """Слова, которые ещё изучаются: есть в базе, но не выучены."""
    async with AsyncSessionLocal() as session:
        stmt = select(Vocab).where(
            Vocab.telegram_id == telegram_id,
            Vocab.next_review != None
        )
        result = await session.execute(stmt)
        return len(result.scalars().all())