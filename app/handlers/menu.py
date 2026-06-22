from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.keyboards.menu import main_menu_kb
from app.locales import t
from app.services.stats import update_user_activity, get_user_stats
from app.services.lesson_service import check_and_increment_limit, create_lesson_for_user
from app.keyboards.lesson import lesson_kb

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


"""
Общая логика урока: генерация + сохранение слов + проверка лимита.
Используется и планировщиком, и кнопкой "Начать урок" — чтобы не дублировать код.
"""
from datetime import date
from zoneinfo import ZoneInfo
from datetime import datetime
from sqlalchemy import select

from app.database.db import AsyncSessionLocal
from app.database.models.user import User
from app.database.models.vocab import Vocab
from app.services.ai import generate_ai_lesson
from app.services.memory import LESSONS
from app.database.db import AsyncSessionLocal
from sqlalchemy import select
from app.services.lesson_service import check_and_increment_limit, create_lesson_for_user
from app.keyboards.lesson import lesson_kb
TZ = ZoneInfo("Europe/Moscow")
DAILY_LIMIT = 3  # сколько уроков в день можно сгенерировать вручную

@router.callback_query(F.data == "menu:lesson")
async def menu_lesson(call: CallbackQuery, lang: str):
    await call.answer()
    telegram_id = call.from_user.id
 
    # 1. Проверяем дневной лимит
    allowed = await check_and_increment_limit(telegram_id)
    if not allowed:
        await call.message.answer(t("lesson_limit_reached", lang))
        return
 
    # 2. Сообщаем что генерируем (это занимает пару секунд)
    await call.message.answer(t("generating_lesson", lang))
 
    # 3. Берём пользователя из БД
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
 
    if not user:
        await call.message.answer(t("lesson_not_found", lang))
        return
 
    # 4. Генерируем урок (та же функция что у планировщика)
    lesson_data = await create_lesson_for_user(user)
 
    # 5. Показываем урок с кнопками (перевод / вопросы / карточки)
    await call.message.answer(
        f"{lesson_data['title']}\n\n{lesson_data['text']}",
        reply_markup=lesson_kb(user.interface_language or "en")
    )

async def check_and_increment_limit(telegram_id: int) -> bool:
    """
    Проверяет дневной лимит уроков.
    Возвращает True если можно делать урок (и увеличивает счётчик),
    False если лимит исчерпан.
    """
    today = datetime.now(TZ).date()

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        if not user:
            return False

        # Новый день — сбрасываем счётчик.
        if user.lessons_date != today:
            user.lessons_today = 0
            user.lessons_date = today

        if user.lessons_today >= DAILY_LIMIT:
            await session.commit()  # сохраним сброс даты если он был
            return False

        user.lessons_today += 1
        await session.commit()
        return True


async def create_lesson_for_user(user: User) -> dict:
    """
    Генерирует урок, кладёт в LESSONS (RAM) и сохраняет новые слова в БД.
    Возвращает данные урока. Эту же функцию использует планировщик.
    """
    lesson = await generate_ai_lesson(user)

    lesson_data = {
        "title": lesson.get("title", "📖 Daily English"),
        "text": lesson["text"],
        "translation": lesson["translation"],
        "questions": lesson.get("questions", []),
        "vocab": lesson.get("vocab", [])[:7],
    }

    LESSONS[user.telegram_id] = lesson_data

    # Сохраняем новые слова в словарь пользователя.
    async with AsyncSessionLocal() as session:
        for v in lesson_data["vocab"]:
            existing = await session.execute(
                select(Vocab).where(
                    Vocab.telegram_id == user.telegram_id,
                    Vocab.word == v["word"]
                )
            )
            if not existing.scalar_one_or_none():
                session.add(
                    Vocab(
                        telegram_id=user.telegram_id,
                        word=v["word"],
                        translation=v["translation"],
                        stage=0,
                        next_review=datetime.now(TZ).replace(tzinfo=None)
                    )
                )
        await session.commit()

    return lesson_data

@router.callback_query(F.data == "menu:cards")
async def menu_cards(call: CallbackQuery, lang: str):
    await call.answer()
    # Переходим к SRS картам
    from app.services.srs import send_next_card
    await send_next_card(call.from_user.id, lang)


@router.callback_query(F.data == "menu:stats")
async def menu_stats(call: CallbackQuery, lang: str):
    telegram_id = call.from_user.id
    
    
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



@router.callback_query(F.data == "menu:back")
async def menu_back(call: CallbackQuery, lang: str):
    await call.message.edit_text(
        t("main_menu", lang),
        reply_markup=main_menu_kb(lang)
    )
    await call.answer()
