from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select

from app.keyboards.menu import main_menu_kb
from app.keyboards.lesson import lesson_kb
from app.locales import t
from app.services.stats import get_user_stats
from app.services.lesson_service import check_and_increment_limit, create_lesson_for_user
from app.database.db import AsyncSessionLocal
from app.database.models.user import User

router = Router()


def back_to_menu_kb(lang: str = "en"):
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ " + t("main_menu", lang), callback_data="menu:back")
    kb.adjust(1)
    return kb.as_markup()


@router.message(Command("menu"))
async def show_menu(message: Message, lang: str):
    await message.answer(t("main_menu", lang), reply_markup=main_menu_kb(lang))


@router.callback_query(F.data == "menu:lesson")
async def menu_lesson(call: CallbackQuery, lang: str):
    await call.answer()
    telegram_id = call.from_user.id

    # 1. Проверка дневного лимита (для админов — безлимит, см. lesson_service)
    allowed = await check_and_increment_limit(telegram_id)
    if not allowed:
        await call.message.answer(t("lesson_limit_reached", lang))
        return

    # 2. Сообщаем что генерируем
    await call.message.answer(t("generating_lesson", lang))

    # 3. Берём пользователя
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()

    if not user:
        await call.message.answer(t("lesson_not_found", lang))
        return

    # 4. Генерируем урок
    lesson_data = await create_lesson_for_user(user)

    # 5. Показываем урок
    await call.message.answer(
        f"{lesson_data['title']}\n\n{lesson_data['text']}",
        reply_markup=lesson_kb(user.interface_language or "en")
    )


@router.callback_query(F.data == "menu:cards")
async def menu_cards(call: CallbackQuery, lang: str, user: User):
    await call.answer()
    from app.services.srs import send_next_card
    await send_next_card(
        call.from_user.id,
        lang,
        target_language=(user.target_language if user else None) or "en",
    )


@router.callback_query(F.data == "menu:stats")
async def menu_stats(call: CallbackQuery, lang: str):
    telegram_id = call.from_user.id

    # Только читаем статистику. Стрик здесь НЕ засчитываем
    # (день засчитывается за реальную учёбу, а не за открытие статистики).
    stats = await get_user_stats(telegram_id)

    stats_text = (
        f"{t('stats_title', lang)}\n\n"
        f"📚 {t('learned_words', lang)}: {stats['learned_words']}\n"
        f"📖 {t('in_progress', lang)}: {stats['in_progress']}\n"
        f"🔥 {t('daily_streak', lang)}: {stats['streak_days']} {t('days', lang)}\n"
        f"🎯 {t('current_level', lang)}: {stats['level']}\n"
        f"⏰ {t('lesson_time_setting', lang)}: {stats['lesson_time']}\n"
    )
 
    await call.message.edit_text(stats_text, reply_markup=back_to_menu_kb(lang))
    await call.answer()


@router.callback_query(F.data == "menu:back")
async def menu_back(call: CallbackQuery, lang: str):
    await call.message.edit_text(t("main_menu", lang), reply_markup=main_menu_kb(lang))
    await call.answer()