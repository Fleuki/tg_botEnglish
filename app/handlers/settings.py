"""
Меню настроек: позволяет менять параметры профиля по одному,
без полной перерегистрации через /start.
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from sqlalchemy import select
from app.database.db import AsyncSessionLocal
from app.database.models.user import User
from app.states.register import SettingsState
from app.keyboards.settings import (
    settings_menu_kb,
    interface_lang_inline_kb,
    level_inline_kb,
)
from app.locales import t

router = Router()

from aiogram.filters import Command
from aiogram.types import Message

@router.message(Command("settings"))
async def settings_command(message: Message, lang: str):
    await message.answer(
        t("settings_button", lang),
        reply_markup=settings_menu_kb(lang),
    )
# ── Вспомогательная функция: сохранить одно поле пользователя ──
async def update_user_field(telegram_id: int, field: str, value: str):
    """Обновляет одно поле профиля в БД."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        if user:
            setattr(user, field, value)  # user.<field> = value
            await session.commit()
            return True
        return False


# ── Открыть меню настроек ──
@router.callback_query(F.data == "menu:settings")
async def open_settings(call: CallbackQuery, lang: str):
    await call.message.edit_text(
        t("settings_button", lang),
        reply_markup=settings_menu_kb(lang),
    )
    await call.answer()


# ── Вернуться в меню настроек (с кнопок "назад") ──
@router.callback_query(F.data == "set:back")
async def back_to_settings(call: CallbackQuery, state: FSMContext, lang: str):
    await state.clear()  # на случай если был режим ввода текста
    await call.message.edit_text(
        t("settings_button", lang),
        reply_markup=settings_menu_kb(lang),
    )
    await call.answer()


# ────────────────────────────────────────────────
# ЯЗЫК ИНТЕРФЕЙСА — выбор кнопкой, меняется сразу
# ────────────────────────────────────────────────
@router.callback_query(F.data == "set:interface")
async def choose_interface(call: CallbackQuery, lang: str):
    await call.message.edit_text(
        t("choose_interface_language", lang),
        reply_markup=interface_lang_inline_kb(),
    )
    await call.answer()


@router.callback_query(F.data.startswith("setlang:"))
async def save_interface(call: CallbackQuery):
    new_lang = call.data.split(":")[1]  # из "setlang:ru" берём "ru"
    await update_user_field(call.from_user.id, "interface_language", new_lang)
    # Дальше интерфейс уже на новом языке
    await call.message.edit_text(
        t("saved", new_lang),
        reply_markup=settings_menu_kb(new_lang),
    )
    await call.answer("✅")


# ────────────────────────────────────────────────
# УРОВЕНЬ — выбор кнопкой, меняется сразу
# ────────────────────────────────────────────────
@router.callback_query(F.data == "set:level")
async def choose_level(call: CallbackQuery, lang: str):
    await call.message.edit_text(
        t("level", lang),
        reply_markup=level_inline_kb(),
    )
    await call.answer()


@router.callback_query(F.data.startswith("setlevel:"))
async def save_level(call: CallbackQuery, lang: str):
    new_level = call.data.split(":")[1]
    await update_user_field(call.from_user.id, "level", new_level)
    await call.message.edit_text(
        t("saved", lang),
        reply_markup=settings_menu_kb(lang),
    )
    await call.answer("✅")


# ────────────────────────────────────────────────
# РОДНОЙ ЯЗЫК — ввод текстом (нужно состояние)
# ────────────────────────────────────────────────
@router.callback_query(F.data == "set:native")
async def ask_native(call: CallbackQuery, state: FSMContext, lang: str):
    await state.set_state(SettingsState.edit_native_language)
    await call.message.edit_text(t("native_language", lang))
    await call.answer()


@router.message(SettingsState.edit_native_language)
async def save_native(message: Message, state: FSMContext, lang: str):
    await update_user_field(message.from_user.id, "native_language", message.text)
    await state.clear()
    await message.answer(
        t("saved", lang),
        reply_markup=settings_menu_kb(lang),
    )


# ────────────────────────────────────────────────
# ВРЕМЯ УРОКА — ввод текстом (нужно состояние)
# ────────────────────────────────────────────────
@router.callback_query(F.data == "set:time")
async def ask_time(call: CallbackQuery, state: FSMContext, lang: str):
    await state.set_state(SettingsState.edit_lesson_time)
    await call.message.edit_text(t("lesson_time", lang))
    await call.answer()


@router.message(SettingsState.edit_lesson_time)
async def save_time(message: Message, state: FSMContext, lang: str):
    # TODO: добавить проверку формата времени (ЧЧ:ММ)
    await update_user_field(message.from_user.id, "lesson_time", message.text)
    await state.clear()
    await message.answer(
        t("saved", lang),
        reply_markup=settings_menu_kb(lang),
    )