import os
import tempfile

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.fsm.context import FSMContext
from sqlalchemy import select

from app.bot import bot
from app.database.db import AsyncSessionLocal
from app.database.models.user import User
from app.keyboards.scene import scenes_menu_kb, scene_active_kb, scene_voice_kb
from app.locales import t
from app.services.ai import scene_chat, speech_to_text, text_to_speech
from app.services.scene import (
    SCENES,
    SCENE_HISTORIES,
    SCENE_TARGET_LANG,
    apply_scene_opening,
    build_scene_recap,
    get_scene_opening,
    is_scene_active,
    start_scene,
    stop_scene,
)
from app.services.prompts import language_name

router = Router()

MAX_VOICE_DURATION = 60  # секунд; длиннее — отказываем до скачивания и whisper

async def _user_target_language(telegram_id: int) -> str:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
    return (user.target_language if user else None) or "en"


async def finish_scene(message: Message, user_id: int, lang: str) -> None:
    if not is_scene_active(user_id):
        await message.answer(t("scene_not_active", lang))
        return

    history = SCENE_HISTORIES[user_id]

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == user_id)
        )
        user = result.scalar_one_or_none()
    native = (user.native_language if user else None) or "Russian"
    target = SCENE_TARGET_LANG.get(user_id) or (
        (user.target_language if user else None) or "en"
    )

    recap = await build_scene_recap(history, native, target, lang)
    stop_scene(user_id)

    if recap:
        await message.answer(recap)
    await message.answer(t("scene_ended", lang))


async def handle_scene_reply(message: Message, user_id: int, text: str, lang: str) -> None:
    history = SCENE_HISTORIES[user_id]
    history.append({"role": "user", "content": text})

    reply = await scene_chat(history)
    if reply is None:
        history.pop()
        await message.answer(t("scene_error", lang))
        return

    history.append({"role": "assistant", "content": reply})
    audio = await text_to_speech(reply)
    if audio:
        voice_file = BufferedInputFile(audio, filename="reply.mp3")
        await message.answer_voice(voice_file, reply_markup=scene_voice_kb(lang))
    else:
        # озвучка не удалась — показываем текст, чтобы диалог не прервался
        await message.answer(reply, reply_markup=scene_active_kb(lang))


@router.message(Command("scene"))
async def cmd_scene(message: Message, state: FSMContext, lang: str):
    await state.clear()
    await message.answer(
        t("choose_scene", lang),
        reply_markup=scenes_menu_kb(lang),
    )


@router.callback_query(F.data == "menu:scene")
async def menu_scene(call: CallbackQuery, state: FSMContext, lang: str):
    await call.answer()
    await state.clear()
    await call.message.answer(t("choose_scene", lang), reply_markup=scenes_menu_kb(lang))


async def _generate_scene_opening(user_id: int, target_language: str) -> str | None:
    """Первая реплика персонажа на изучаемом языке, если нет готового шаблона."""
    history = SCENE_HISTORIES.get(user_id)
    if not history:
        return None

    lang = language_name(target_language or "en")
    messages = history + [
        {
            "role": "user",
            "content": (
                f"[Scene start — internal instruction, not shown to the learner. "
                f"Say your opening line in {lang} only, 1-2 short sentences, stay in character.]"
            ),
        }
    ]
    opening = await scene_chat(messages)
    if opening:
        apply_scene_opening(user_id, opening)
    return opening


@router.callback_query(F.data.startswith("scene:pick:"))
async def pick_scene(call: CallbackQuery, state: FSMContext, lang: str):
    scene_id = call.data.split(":")[2]
    if scene_id not in SCENES:
        await call.answer(t("scene_not_found", lang))
        return

    await state.clear()
    await call.answer()

    target = await _user_target_language(call.from_user.id)
    start_scene(call.from_user.id, target, scene_id)

    opening = get_scene_opening(scene_id, target)
    if not opening:
        opening = await _generate_scene_opening(call.from_user.id, target)
    if not opening:
        await call.message.edit_text(t("scene_error", lang))
        return

    try:
        await call.message.delete()
    except Exception:
        pass
    audio = await text_to_speech(opening)
    if audio:
        voice_file = BufferedInputFile(audio, filename="opening.mp3")
        await call.message.answer_voice(voice_file, reply_markup=scene_voice_kb(lang))
    else:
        await call.message.answer(opening, reply_markup=scene_active_kb(lang))


@router.callback_query(F.data == "scene:showtext")
async def scene_show_text(call: CallbackQuery, lang: str):
    await call.answer()
    user_id = call.from_user.id
    history = SCENE_HISTORIES.get(user_id) or []
    last_reply = next(
        (m["content"] for m in reversed(history) if m["role"] == "assistant"),
        None,
    )
    if last_reply:
        await call.message.answer(last_reply)
    else:
        await call.answer(t("scene_not_active", lang))


@router.callback_query(F.data == "scene:stop")
async def scene_stop_btn(call: CallbackQuery, lang: str):
    await call.answer()
    await finish_scene(call.message, call.from_user.id, lang)


@router.message(Command("stop"))
async def cmd_stop(message: Message, lang: str):
    await finish_scene(message, message.from_user.id, lang)


@router.message(F.text, ~F.text.startswith("/"), lambda m: is_scene_active(m.from_user.id))
async def scene_message(message: Message, lang: str):
    text = (message.text or "").strip()
    if not text:
        return
    await handle_scene_reply(message, message.from_user.id, text, lang)


@router.message(F.voice, lambda m: is_scene_active(m.from_user.id))
async def scene_voice(message: Message, lang: str):
    user_id = message.from_user.id
    if message.voice.duration and message.voice.duration > MAX_VOICE_DURATION:
        await message.answer(t("voice_too_long", lang).format(sec=MAX_VOICE_DURATION))
        return
    tg_file = await bot.get_file(message.voice.file_id)
    fd, tmp_path = tempfile.mkstemp(suffix=".ogg")
    os.close(fd)
    try:
        await bot.download_file(tg_file.file_path, tmp_path)
        text = await speech_to_text(tmp_path)
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
    if not text:
        await message.answer(t("voice_not_recognized", lang))
        return
    await message.answer(t("voice_recognized", lang).format(text=text))
    await handle_scene_reply(message, user_id, text, lang)
