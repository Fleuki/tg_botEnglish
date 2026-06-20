from aiogram import Router
from aiogram.types import Message
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext

from app.states.register import RegisterState
from app.keyboards.settings import interface_lang_register_kb
from app.locales import t


router = Router()


@router.message(CommandStart())
async def start(message: Message, state: FSMContext, lang: str):
    await state.set_state(RegisterState.interface_language)
    await message.answer(
        t("choose_interface_language", lang),
        reply_markup=interface_lang_register_kb()  # inline-кнопки
    )