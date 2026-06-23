from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from sqlalchemy import select

from app.database.db import AsyncSessionLocal
from app.database.models.user import User
from app.services.ai import scene_chat
from app.services.scene import (
    BARISTA_OPENING,
    SCENE_HISTORIES,
    build_scene_recap,
    is_scene_active,
    start_scene,
    stop_scene,
)

router = Router()


@router.message(Command("scene"))
async def cmd_scene(message: Message, state: FSMContext):
    await state.clear()
    start_scene(message.from_user.id)
    await message.answer(BARISTA_OPENING)


@router.message(Command("stop"))
async def cmd_stop(message: Message):
    user_id = message.from_user.id
    if not is_scene_active(user_id):
        await message.answer("No active scene. Use /scene to start one.")
        return

    history = SCENE_HISTORIES[user_id]

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == user_id)
        )
        user = result.scalar_one_or_none()
    native = (user.native_language if user else None) or "Russian"

    recap = await build_scene_recap(history, native)
    stop_scene(user_id)

    if recap:
        await message.answer(recap)
    await message.answer("Scene ended. See you next time!")


@router.message(F.text, ~F.text.startswith("/"), lambda m: is_scene_active(m.from_user.id))
async def scene_message(message: Message):
    text = (message.text or "").strip()
    if not text:
        return

    user_id = message.from_user.id
    history = SCENE_HISTORIES[user_id]
    history.append({"role": "user", "content": text})

    reply = await scene_chat(history)
    if reply is None:
        history.pop()
        await message.answer("Sorry, something went wrong. Please try again.")
        return

    history.append({"role": "assistant", "content": reply})
    await message.answer(reply)
