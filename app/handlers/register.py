from aiogram import Router
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from sqlalchemy import select
from app.states.register import RegisterState
from app.database.db import AsyncSessionLocal
from app.database.models.user import User
from app.locales import t
from aiogram.types import ReplyKeyboardRemove
from aiogram import F
from aiogram.types import CallbackQuery
from app.keyboards.settings import level_register_kb

router = Router()
LANGUAGES = {
    "🇷🇺 Русский": "ru",
    "🇺🇸 English": "en",
    "🇩🇪 Deutsch": "de",
    "🇪🇸 Español": "es",
    "🇫🇷 Français": "fr",
    "🇮🇩 Indonesia": "id",
    "🇧🇷 Português": "pt_br"
}

# ----------------------------------
# 1. Язык интерфейса
# ----------------------------------
@router.callback_query(RegisterState.interface_language, F.data.startswith("reglang:"))
async def set_interface_language(call: CallbackQuery, state: FSMContext):
    # из "reglang:ru" берём код "ru"
    lang = call.data.split(":")[1]
 
    await state.update_data(interface_language=lang)
    await state.set_state(RegisterState.native_language)
 
    # редактируем сообщение: убираем кнопки, показываем след. вопрос
    await call.message.edit_text(t("native_language", lang))
    await call.answer()
 


# ----------------------------------
# 2. Родной язык
# ----------------------------------
@router.message(RegisterState.native_language)
async def set_native_language(message: Message, state: FSMContext):
    await state.update_data(native_language=message.text)
    data = await state.get_data()
    await state.set_state(RegisterState.level)
    await message.answer(
        t("level", data["interface_language"]),
        reply_markup=level_register_kb()   # inline вместо Reply
    )

# ----------------------------------
# 3. Уровень английского
# ----------------------------------
@router.callback_query(RegisterState.level, F.data.startswith("reglevel:"))
async def set_level(call: CallbackQuery, state: FSMContext):
    level = call.data.split(":")[1]
    await state.update_data(level=level)
    data = await state.get_data()
    await state.set_state(RegisterState.lesson_time)
    await call.message.edit_text(
        t("lesson_time", data["interface_language"])
    )
    await call.answer()
 
# ----------------------------------
# 4. Время уроков
# ----------------------------------
@router.message(RegisterState.lesson_time)
async def set_time(message: Message, state: FSMContext):

    await state.update_data(
        lesson_time=message.text
    )

    data = await state.get_data()

    async with AsyncSessionLocal() as session:

        result = await session.execute(
            select(User).where(
                User.telegram_id == message.from_user.id
            )
        )

        user = result.scalar_one_or_none()

        if user:

            user.interface_language = data["interface_language"]
            user.native_language = data["native_language"]
            user.level = data["level"]
            user.lesson_time = data["lesson_time"]

        else:

            session.add(
                User(
                    telegram_id=message.from_user.id,
                    interface_language=data["interface_language"],
                    native_language=data["native_language"],
                    level=data["level"],
                    lesson_time=data["lesson_time"]
                )
            )

        await session.commit()

    await state.clear()

    await message.answer(
        t("done", data["interface_language"])
    )