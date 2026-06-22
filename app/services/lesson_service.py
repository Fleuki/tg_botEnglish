"""
Общая логика урока: генерация + сохранение слов + проверка лимита.
Используется и планировщиком, и кнопкой "Начать урок" — чтобы не дублировать код.
"""
from datetime import date
from zoneinfo import ZoneInfo
from datetime import datetime
from sqlalchemy import select

from app.database.db import AsyncSessionLocal
from app.database.models.user import User
from app.database.models.vocab import Vocab
from app.services.ai import generate_ai_lesson
from app.services.memory import LESSONS
from app.config import ADMIN_IDS

TZ = ZoneInfo("Europe/Moscow")
DAILY_LIMIT = 3  # сколько уроков в день можно сгенерировать вручную


async def check_and_increment_limit(telegram_id: int) -> bool:
    """
    Проверяет дневной лимит уроков.
    Админы (ADMIN_IDS) — без ограничений.
    Возвращает True если можно делать урок.
    """
    # Безлимит для админов (для тестирования / премиум в будущем).
    if telegram_id in ADMIN_IDS:
        return True
 
    today = datetime.now(TZ).date()
 
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        if not user:
            return False
 
        if user.lessons_date != today:
            user.lessons_today = 0
            user.lessons_date = today
 
        if user.lessons_today >= DAILY_LIMIT:
            await session.commit()
            return False
 
        user.lessons_today += 1
        await session.commit()
        return True
 

async def create_lesson_for_user(user: User) -> dict:
    """
    Генерирует урок, кладёт в LESSONS (RAM) и сохраняет новые слова в БД.
    Возвращает данные урока. Эту же функцию использует планировщик.
    """
    lesson = await generate_ai_lesson(user)

    lesson_data = {
        "title": lesson.get("title", "📖 Daily English"),
        "text": lesson["text"],
        "translation": lesson["translation"],
        "questions": lesson.get("questions", []),
        "vocab": lesson.get("vocab", [])[:7],
    }

    LESSONS[user.telegram_id] = lesson_data

    # Сохраняем новые слова в словарь пользователя.
    async with AsyncSessionLocal() as session:
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
                        next_review=datetime.now(TZ).replace(tzinfo=None)
                    )
                )
        await session.commit()

    return lesson_data