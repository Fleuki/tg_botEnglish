from aiogram.utils.keyboard import InlineKeyboardBuilder
from app.locales import t


def lesson_kb(lang: str = "en", show_translation: bool = True):
    kb = InlineKeyboardBuilder()

    if show_translation:
        kb.button(
            text=t("show_translation_button", lang),
            callback_data="lesson:show_translation"
        )

    kb.button(
        text=t("listen_button", lang),
        callback_data="lesson:listen"
    )

    kb.button(
        text=t("questions_button", lang),
        callback_data="lesson:start_questions"
    )

    kb.button(
        text=t("words_button", lang),
        callback_data="lesson:start_cards"
    )

    kb.adjust(1)
    return kb.as_markup()