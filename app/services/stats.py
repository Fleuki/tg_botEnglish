from datetime import datetime, timedelta
from sqlalchemy import select
from app.database.db import AsyncSessionLocal
from app.database.models.user import User
from app.database.models.vocab import Vocab


async def update_user_activity(telegram_id: int):
    """Обновляет последнюю дату активности и расчитывает дни подряд"""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            return 0
        
        now = datetime.utcnow()
        today = now.date()
        
        # Если последняя активность была вчера
        if user.last_activity_date:
            last_date = user.last_activity_date.date()
            yesterday = today - timedelta(days=1)
            
            if last_date == today:
                # Уже был активен сегодня
                streak = user.streak_days
            elif last_date == yesterday:
                # Был активен вчера - увеличиваем полосу
                streak = user.streak_days + 1
            else:
                # Был неактивен > 1 дня - сбрасываем полосу
                streak = 1
        else:
            streak = 1
        
        user.last_activity_date = now
        user.streak_days = streak
        await session.commit()
        
        return streak


async def get_learned_words_count(telegram_id: int):
    """Получает количество выученных слов"""
    async with AsyncSessionLocal() as session:
        stmt = select(Vocab).where(
            Vocab.telegram_id == telegram_id,
            Vocab.next_review == None
        )
        result = await session.execute(stmt)
        return len(result.scalars().all())


async def get_user_stats(telegram_id: int):
    """Получает полную статистику пользователя"""
    async with AsyncSessionLocal() as session:
        user_result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = user_result.scalar_one_or_none()
        
        if not user:
            return {
                "learned_words": 0,
                "streak_days": 0,
                "level": "A1",
                "lesson_time": "Not set"
            }
        
        # Подсчитаем выученные слова
        vocab_stmt = select(Vocab).where(
            Vocab.telegram_id == telegram_id,
            Vocab.next_review == None
        )
        vocab_result = await session.execute(vocab_stmt)
        learned_words = len(vocab_result.scalars().all())
        
        return {
            "learned_words": learned_words,
            "streak_days": user.streak_days or 0,
            "level": user.level or "A1",
            "lesson_time": user.lesson_time or "Not set"
        }
