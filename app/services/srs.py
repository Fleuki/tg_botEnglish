from datetime import datetime, timedelta

from sqlalchemy import select

from app.database.db import AsyncSessionLocal
from app.database.models.vocab import Vocab
from app.bot import bot
from app.keyboards.srs import srs_card_kb
from app.locales import t

REVIEW_STAGES = [1, 3, 7, 14, 30]


async def get_next_vocab(telegram_id: int):
    async with AsyncSessionLocal() as session:
        stmt = (
            select(Vocab)
            .where(Vocab.telegram_id == telegram_id)
            .where(
                (Vocab.next_review == None) |
                (Vocab.next_review <= datetime.utcnow())
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
                vocab.next_review = datetime.utcnow() + timedelta(
                    days=REVIEW_STAGES[vocab.stage]
                )
            else:
                vocab.next_review = None
        else:
            vocab.stage = 0
            vocab.next_review = datetime.utcnow() + timedelta(days=1)

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