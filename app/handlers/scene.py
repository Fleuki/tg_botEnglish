from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy import select

from app.database.db import AsyncSessionLocal
from app.database.models.user import User
from app.keyboards.scene import scenes_menu_kb
from app.locales import t
from app.services.ai import scene_chat
from app.services.scene import (
    SCENES,
    SCENE_HISTORIES,
    SCENE_TARGET_LANG,
    build_scene_recap,
    get_scene_opening,
    is_scene_active,
    start_scene,
    stop_scene,
)

router = Router()


async def _user_target_language(telegram_id: int) -> str:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
    return (user.target_language if user else None) or "en"


@router.message(Command("scene"))
async def cmd_scene(message: Message, state: FSMContext, lang: str):
    await state.clear()
    await message.answer(
        t("choose_scene", lang),
        reply_markup=scenes_menu_kb(lang),
    )


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

    await call.message.edit_text(opening)


@router.message(Command("stop"))
async def cmd_stop(message: Message, lang: str):
    user_id = message.from_user.id
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


@router.message(F.text, ~F.text.startswith("/"), lambda m: is_scene_active(m.from_user.id))
async def scene_message(message: Message, lang: str):
    text = (message.text or "").strip()
    if not text:
        return

    user_id = message.from_user.id
    history = SCENE_HISTORIES[user_id]
    history.append({"role": "user", "content": text})

    reply = await scene_chat(history)
    if reply is None:
        history.pop()
        await message.answer(t("scene_error", lang))
        return

    history.append({"role": "assistant", "content": reply})
    await message.answer(reply)
