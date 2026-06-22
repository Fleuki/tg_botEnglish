from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select, func

from app.database.db import AsyncSessionLocal
from app.database.models.vocab import Vocab
from app.bot import bot
from app.keyboards.srs import srs_card_kb
from app.locales import t

REVIEW_STAGES = [1, 3, 7, 14, 30]

# Единое время для всего бота — Москва.
# Раньше тут смешивались utcnow() и now(TZ), из-за чего слова
# то "не находились", то "находились" — отсюда баг с карточками.
TZ = ZoneInfo("Europe/Moscow")


def now_msk():
    """Текущее московское время без tzinfo (naive) — в одной шкале с next_review."""
    return datetime.now(TZ).replace(tzinfo=None)


async def get_next_vocab(telegram_id: int):
    async with AsyncSessionLocal() as session:
        stmt = (
            select(Vocab)
            .where(Vocab.telegram_id == telegram_id)
            .where(
                (Vocab.next_review == None) |
                (Vocab.next_review <= now_msk())
            )
            .order_by(Vocab.next_review.asc().nullsfirst())
            .limit(1)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()


async def get_vocab(vocab_id: int):
    async with AsyncSessionLocal() as session:
        return await session.get(Vocab, vocab_id)


async def update_srs(vocab_id: int, correct: bool):
    async with AsyncSessionLocal() as session:
        vocab = await session.get(Vocab, vocab_id)
        if not vocab:
            return

        if correct:
            vocab.stage += 1
            if vocab.stage < len(REVIEW_STAGES):
                vocab.next_review = now_msk() + timedelta(
                    days=REVIEW_STAGES[vocab.stage]
                )
            else:
                vocab.next_review = None  # слово выучено
        else:
            vocab.stage = 0
            vocab.next_review = now_msk() + timedelta(days=1)

        await session.commit()


async def send_next_card(telegram_id: int, lang: str = "en"):
    vocab = await get_next_vocab(telegram_id)

    if not vocab:
        await bot.send_message(telegram_id, t("cards_done", lang))
        return

    await bot.send_message(
        telegram_id,
        f"🧠 {vocab.word}",
        reply_markup=srs_card_kb(vocab.id, lang)
    )


async def count_due_words(telegram_id: int) -> int:
    """Сколько слов готово к повторению прямо сейчас (по московскому времени)."""
    async with AsyncSessionLocal() as session:
        stmt = (
            select(func.count())
            .select_from(Vocab)
            .where(Vocab.telegram_id == telegram_id)
            .where(
                (Vocab.next_review == None) |
                (Vocab.next_review <= now_msk())
            )
        )
        result = await session.execute(stmt)
        return result.scalar() or 0