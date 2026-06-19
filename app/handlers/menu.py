from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.keyboards.menu import main_menu_kb
from app.locales import t
from app.services.stats import update_user_activity, get_user_stats

router = Router()


def back_to_menu_kb(lang: str = "en"):
    kb = InlineKeyboardBuilder()
    kb.button(
        text="⬅️ " + t("main_menu", lang),
        callback_data="menu:back"
    )
    kb.adjust(1)
    return kb.as_markup()


@router.message(Command("menu"))
async def show_menu(message: Message, lang: str):
    await message.answer(
        t("main_menu", lang),
        reply_markup=main_menu_kb(lang)
    )


@router.callback_query(F.data == "menu:lesson")
async def menu_lesson(call: CallbackQuery, lang: str):
    await call.answer()
    # Используем существующий callback для урока
    from app.handlers.lesson import start_questions
    # Просто уведомляем пользователя
    await call.message.answer(t("lesson_button", lang) + " 📖")


@router.callback_query(F.data == "menu:cards")
async def menu_cards(call: CallbackQuery, lang: str):
    await call.answer()
    # Переходим к SRS картам
    from app.services.srs import send_next_card
    await send_next_card(call.from_user.id, lang)


@router.callback_query(F.data == "menu:stats")
async def menu_stats(call: CallbackQuery, lang: str):
    telegram_id = call.from_user.id
    
    # Обновляем активность
    streak = await update_user_activity(telegram_id)
    
    # Получаем статистику
    stats = await get_user_stats(telegram_id)
    
    stats_text = (
        f"{t('stats_title', lang)}\n\n"
        f"📚 {t('learned_words', lang)}: {stats['learned_words']}\n"
        f"🔥 {t('daily_streak', lang)}: {stats['streak_days']} {t('days', lang)}\n"
        f"🎯 {t('current_level', lang)}: {stats['level']}\n"
        f"⏰ {t('lesson_time_setting', lang)}: {stats['lesson_time']}\n"
    )
    
    await call.message.edit_text(
        stats_text,
        reply_markup=back_to_menu_kb(lang)
    )
    await call.answer()


@router.callback_query(F.data == "menu:settings")
async def menu_settings(call: CallbackQuery, lang: str):
    settings_text = (
        f"{t('settings_button', lang)} ⚙️\n\n"
        f"🌍 {t('choose_interface_language', lang)}\n"
        f"⏰ {t('lesson_time', lang)}\n\n"
        "Use /start to change settings"
    )
    
    await call.message.edit_text(settings_text)
    await call.answer()


@router.callback_query(F.data == "menu:back")
async def menu_back(call: CallbackQuery, lang: str):
    await call.message.edit_text(
        t("main_menu", lang),
        reply_markup=main_menu_kb(lang)
    )
    await call.answer()
