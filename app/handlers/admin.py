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
    total_organic = 0
    total_notified = 0
    lines = []

    for u in users:
        total_organic += u.organic_returns or 0
        total_notified += u.notified_returns or 0

        if not u.last_activity_date:
            never += 1
            days_ago_str = "—"
        else:
            last = u.last_activity_date.date()
            days_ago = (today - last).days
            if days_ago <= 0:
                active_today += 1
                days_ago_str = "сегодня"
            elif days_ago <= 7:
                active_week += 1
                days_ago_str = f"{days_ago} дн. назад"
            else:
                inactive += 1
                days_ago_str = f"{days_ago} дн. назад (пропал)"

        org = u.organic_returns or 0
        push = u.notified_returns or 0
        lines.append(
            f"• id {u.telegram_id} | {u.target_language or '—'} | "
            f"стрик {u.streak_days or 0} | {days_ago_str} | "
            f"орг {org} пуш {push}"
        )

    total_visits = total_organic + total_notified
    if total_visits > 0:
        organic_pct = round(total_organic / total_visits * 100)
        notified_pct = 100 - organic_pct
    else:
        organic_pct = notified_pct = 0

    summary = (
        f"📊 Сводка по пользователям\n\n"
        f"Всего: {total}\n"
        f"🟢 Активны сегодня: {active_today}\n"
        f"🟡 На этой неделе: {active_week}\n"
        f"🔴 Пропали (>7 дн.): {inactive}\n"
        f"⚪ Ни разу: {never}\n\n"
        f"🔁 Возвраты: {total_visits} всего\n"
        f"  органика: {total_organic} ({organic_pct}%)\n"
        f"  по пушу:  {total_notified} ({notified_pct}%)\n\n"
        f"Детали (орг / пуш — счётчики визитов):\n" + "\n".join(lines)
    )

    await message.answer(summary)