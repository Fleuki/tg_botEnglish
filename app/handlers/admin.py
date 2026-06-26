from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy import select

from app.config import ADMIN_IDS
from app.database.db import AsyncSessionLocal
from app.database.models.user import User

router = Router()

TZ = ZoneInfo("Europe/Moscow")


@router.message(Command("stats_admin"))
async def stats_admin(message: Message):
    # доступ только для админов
    if message.from_user.id not in ADMIN_IDS:
        return

    # читаем всех пользователей (только SELECT, ничего не меняем)
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User))
        users = result.scalars().all()

    total = len(users)
    today = datetime.now(TZ).replace(tzinfo=None).date()

    active_today = 0
    active_week = 0
    inactive = 0
    never = 0
    lines = []

    for u in users:
        if not u.last_activity_date:
            never += 1
            status = "никогда не занимался"
            days_ago_str = "—"
        else:
            last = u.last_activity_date.date()
            days_ago = (today - last).days
            if days_ago <= 0:
                active_today += 1
                status = "сегодня"
            elif days_ago <= 7:
                active_week += 1
                status = f"{days_ago} дн. назад"
            else:
                inactive += 1
                status = f"{days_ago} дн. назад (пропал)"
            days_ago_str = status

        lines.append(
            f"• id {u.telegram_id} | учит {u.target_language or '—'} | "
            f"стрик {u.streak_days or 0} | {days_ago_str}"
        )

    summary = (
        f"📊 Сводка по пользователям\n\n"
        f"Всего: {total}\n"
        f"🟢 Активны сегодня: {active_today}\n"
        f"🟡 На этой неделе: {active_week}\n"
        f"🔴 Пропали (>7 дн.): {inactive}\n"
        f"⚪ Ни разу: {never}\n\n"
        f"Детали:\n" + "\n".join(lines)
    )

    await message.answer(summary)