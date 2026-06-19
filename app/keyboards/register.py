from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def interface_language_keyboard():

    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🇷🇺 Русский"),
                KeyboardButton(text="🇺🇸 English")
            ],
            [
                KeyboardButton(text="🇩🇪 Deutsch"),
                KeyboardButton(text="🇪🇸 Español")
            ],
            [
                KeyboardButton(text="🇫🇷 Français"),
                KeyboardButton(text="🇮🇩 Indonesia")
            ],
            [
                KeyboardButton(text="🇧🇷 Português")
            ]
        ],
        resize_keyboard=True
    )


def english_level_keyboard():

    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="A1"),
                KeyboardButton(text="A2")
            ],
            [
                KeyboardButton(text="B1"),
                KeyboardButton(text="B2")
            ],
            [
                KeyboardButton(text="C1")
            ]
        ],
        resize_keyboard=True
    )