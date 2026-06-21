from aiogram.utils.keyboard import InlineKeyboardBuilder
from app.locales import t


def srs_card_kb(vocab_id: int, lang: str = "en"):
    kb = InlineKeyboardBuilder()

    kb.button(
        text=t("show_word_button", lang),
        callback_data=f"srs:show:{vocab_id}"
    )

    kb.adjust(1)
    return kb.as_markup()


def srs_answer_kb(vocab_id: int, lang: str = "en"):
    kb = InlineKeyboardBuilder()

    kb.button(text=t("know_button", lang), callback_data=f"srs:know:{vocab_id}")
    kb.button(text=t("dont_know_button", lang), callback_data=f"srs:dont:{vocab_id}")

    kb.adjust(2)
    return kb.as_markup()

# Добавь в конец app/keyboards/srs.py

def srs_reminder_kb(lang: str = "en"):
    """Кнопка под напоминанием о повторении — запускает карточки."""
    kb = InlineKeyboardBuilder()
    kb.button(text=t("repeat_button", lang), callback_data="menu:cards")
    kb.adjust(1)
    return kb.as_markup()