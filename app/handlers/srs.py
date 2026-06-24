from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext
from app.database.models.user import User
from app.keyboards.srs import srs_answer_kb, srs_card_with_undo_kb
from app.services.srs import (
    send_next_card, get_vocab, update_srs, restore_srs, get_next_vocab
)
from app.services.stats import update_user_activity
from app.locales import t

router = Router()


def _target_language(user: User | None) -> str:
    return (user.target_language if user else None) or "en"


@router.callback_query(F.data == "lesson:start_cards")
async def start_cards(call: CallbackQuery, state: FSMContext, lang: str, user: User):
    await update_user_activity(call.from_user.id)
    await send_next_card(
        call.from_user.id,
        lang,
        target_language=_target_language(user),
    )
    await call.answer()


@router.callback_query(F.data.startswith("srs:show:"))
async def show_word(call: CallbackQuery, lang: str):
    vocab_id = int(call.data.split(":")[2])
    vocab = await get_vocab(vocab_id)
    if not vocab:
        await call.answer(t("not_found", lang))
        return
    await call.message.edit_text(
        f"🧠 {vocab.word}\n\n🌍 {vocab.translation}",
        reply_markup=srs_answer_kb(vocab.id, lang)
    )
    await call.answer()


async def _answer_and_next(
    call, state, lang, user, vocab_id, correct, toast_key,
):
    """Общая логика для 'знаю'/'не знаю': применяем, запоминаем для отмены,
    показываем следующую карточку с кнопкой отмены."""
    target = _target_language(user)
    prev = await update_srs(vocab_id, correct=correct)

    # запоминаем в FSM, что можно откатить
    if prev is not None:
        await state.update_data(
            undo_vocab_id=vocab_id,
            undo_stage=prev["stage"],
            undo_next_review=prev["next_review"],
        )

    # следующая карточка
    next_vocab = await get_next_vocab(call.from_user.id, target)
    if not next_vocab:
        await call.message.answer(t("cards_done", lang))
        await call.answer(t(toast_key, lang))
        return

    await call.message.answer(
        f"🧠 {next_vocab.word}",
        reply_markup=srs_card_with_undo_kb(next_vocab.id, vocab_id, lang)
    )
    await call.answer(t(toast_key, lang))


@router.callback_query(F.data.startswith("srs:know:"))
async def know(call: CallbackQuery, state: FSMContext, lang: str, user: User):
    vocab_id = int(call.data.split(":")[2])
    await _answer_and_next(call, state, lang, user, vocab_id, True, "correct")


@router.callback_query(F.data.startswith("srs:dont:"))
async def dont(call: CallbackQuery, state: FSMContext, lang: str, user: User):
    vocab_id = int(call.data.split(":")[2])
    await _answer_and_next(call, state, lang, user, vocab_id, False, "repeat_tomorrow")


@router.callback_query(F.data.startswith("srs:undo:"))
async def undo(call: CallbackQuery, state: FSMContext, lang: str):
    vocab_id = int(call.data.split(":")[2])
    data = await state.get_data()

    # проверяем, что есть что откатывать и это то же слово
    if data.get("undo_vocab_id") != vocab_id:
        await call.answer(t("undo_nothing", lang))
        return

    await restore_srs(
        vocab_id,
        data["undo_stage"],
        data["undo_next_review"],
    )
    # чистим, чтобы нельзя было откатить дважды
    await state.update_data(undo_vocab_id=None)

    # показываем восстановленное слово снова
    vocab = await get_vocab(vocab_id)
    if vocab:
        await call.message.answer(
            f"🧠 {vocab.word}",
            reply_markup=srs_answer_kb(vocab.id, lang)
        )
    await call.answer(t("undo_done", lang))