from aiogram.utils.keyboard import InlineKeyboardBuilder


def quiz_kb():
    kb = InlineKeyboardBuilder()

    for i in range(1, 4):
        kb.button(
            text=str(i),
            callback_data=f"quiz:answer:{i}"
        )

    kb.adjust(3)

    return kb.as_markup()
