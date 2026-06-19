from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext
from app.keyboards.srs import srs_answer_kb
from app.services.srs import send_next_card
from app.services.srs import get_vocab, update_srs
from app.services.stats import update_user_activity
from app.locales import t

router = Router()


@router.callback_query(F.data == "lesson:start_cards")
async def start_cards(call: CallbackQuery, state: FSMContext, lang: str):
    await update_user_activity(call.from_user.id)
    await send_next_card(call.from_user.id, lang)
    await call.answer()

@router.callback_query(F.data.startswith("srs:show:"))
async def show_word(call: CallbackQuery, lang: str):
    vocab_id = int(call.data.split(":")[2])

    vocab = await get_vocab(vocab_id)

    if not vocab:
        await call.answer(t("not_found", lang))
        return

    await call.message.edit_text(
        f"🧠 {vocab.word}\n\n"
        f"🌍 {vocab.translation}",
        reply_markup=srs_answer_kb(vocab.id, lang)
    )

    await call.answer()

@router.callback_query(F.data.startswith("srs:know:"))
async def know(call: CallbackQuery, lang: str):
    vocab_id = int(call.data.split(":")[2])
    await update_srs(vocab_id, correct=True)
    await send_next_card(call.from_user.id, lang)
    await call.answer(t("correct", lang))

@router.callback_query(F.data.startswith("srs:dont:"))
async def dont(call: CallbackQuery, lang: str):
    vocab_id = int(call.data.split(":")[2])
    await update_srs(vocab_id, correct=False)
    await send_next_card(call.from_user.id, lang)
    await call.answer(t("repeat_tomorrow", lang))