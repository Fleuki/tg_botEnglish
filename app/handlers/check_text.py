"""
Режим проверки письменного текста: пользователь пишет текст на английском,
бот находит ошибки, исправляет и объясняет правила на родном языке.
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select
from datetime import datetime
from zoneinfo import ZoneInfo

from app.database.db import AsyncSessionLocal
from app.database.models.user import User
from app.services.ai import check_user_text
from app.config import ADMIN_IDS
from app.locales import t

router = Router()

TZ = ZoneInfo("Europe/Moscow")
CHECK_DAILY_LIMIT = 5          # проверок в день для обычных пользователей
MAX_TEXT_LENGTH = 500          # лимит длины текста за раз


class CheckState(StatesGroup):
    waiting_for_text = State()


async def can_check(telegram_id: int) -> bool:
    """Лимит проверок в день. Админам — без ограничений.
    Переиспользуем поля? Нет — заведём отдельные, чтобы не мешать урокам.
    Для простоты считаем в этой же таблице User по дате."""
    if telegram_id in ADMIN_IDS:
        return True

    today = datetime.now(TZ).date()
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        if not user:
            return False

        if user.checks_date != today:
            user.checks_today = 0
            user.checks_date = today

        if user.checks_today >= CHECK_DAILY_LIMIT:
            await session.commit()
            return False

        user.checks_today += 1
        await session.commit()
        return True


# ── Вход в режим проверки ──
@router.callback_query(F.data == "menu:check")
async def start_check(call: CallbackQuery, state: FSMContext, lang: str):
    await call.answer()
    if not await can_check(call.from_user.id):
        await call.message.answer(t("check_limit_reached", lang))
        return
    await state.set_state(CheckState.waiting_for_text)
    await call.message.answer(t("check_prompt", lang))


# ── Приём текста и проверка ──
@router.message(CheckState.waiting_for_text)
async def process_check(message: Message, state: FSMContext, lang: str):
    text = (message.text or "").strip()

    if not text:
        await message.answer(t("check_empty", lang))
        return

    if len(text) > MAX_TEXT_LENGTH:
        await message.answer(t("check_too_long", lang).format(max=MAX_TEXT_LENGTH))
        return

    await state.clear()
    await message.answer(t("check_analyzing", lang))

    # родной язык пользователя для объяснений
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        user = result.scalar_one_or_none()
    native = (user.native_language if user else None) or "Russian"

    result = await check_user_text(text, native)

    if result.get("_error"):
        await message.answer(t("check_failed", lang))
        return

    # Формируем ответ
    if not result["has_errors"]:
        reply = f"✅ {result.get('praise', '')}"
        # если предложили более естественный вариант
        if result["corrected"].strip() != text:
            reply += f"\n\n💡 {result['corrected']}"
    else:
        reply = f"📝 {t('check_corrected', lang)}\n{result['corrected']}\n\n"
        reply += f"🔍 {t('check_mistakes', lang)}\n"
        for i, e in enumerate(result["explanations"], 1):
            reply += (
                f"\n{i}. ❌ {e['wrong']} → ✅ {e['right']}\n"
                f"   📖 {e['rule']}\n"
            )
        if result.get("praise"):
            reply += f"\n{result['praise']}"

    await message.answer(reply)