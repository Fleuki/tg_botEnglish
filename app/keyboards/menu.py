from aiogram.utils.keyboard import InlineKeyboardBuilder
from app.locales import t


# (добавлена кнопка "Проверить текст")


def main_menu_kb(lang: str = "en"):
    kb = InlineKeyboardBuilder()
    kb.button(text=t("lesson_button", lang), callback_data="menu:lesson")
    kb.button(text=t("cards_button", lang), callback_data="menu:cards")
    kb.button(text=t("check_button", lang), callback_data="menu:check")
    kb.button(text=t("stats_button", lang), callback_data="menu:stats")
    kb.button(text=t("settings_button", lang), callback_data="menu:settings")
    kb.adjust(2)
    return kb.as_markup()
