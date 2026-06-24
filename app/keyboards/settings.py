from aiogram.utils.keyboard import InlineKeyboardBuilder
from app.locales import t


def settings_menu_kb(lang: str = "en"):
    """Меню настроек: список параметров которые можно изменить."""
    kb = InlineKeyboardBuilder()
    kb.button(text="🌍 " + t("set_interface_lang", lang), callback_data="set:interface")
    kb.button(text="🗣 " + t("set_native_lang", lang), callback_data="set:native")
    kb.button(text="🎯 " + t("set_target_lang", lang), callback_data="set:target")
    kb.button(text="📊 " + t("set_level", lang), callback_data="set:level")
    kb.button(text="⏰ " + t("set_time", lang), callback_data="set:time")
    kb.button(text="⬅️ " + t("main_menu", lang), callback_data="menu:back")
    kb.adjust(1)  # каждая кнопка на своей строке
    return kb.as_markup()


# Языки интерфейса как inline-кнопки (callback несёт код языка: setlang:ru и т.д.)
INTERFACE_LANGS = [
    ("🇷🇺 Русский", "ru"),
    ("🇺🇸 English", "en"),
    ("🇩🇪 Deutsch", "de"),
    ("🇪🇸 Español", "es"),
    ("🇫🇷 Français", "fr"),
    ("🇮🇩 Indonesia", "id"),
    ("🇧🇷 Português", "pt_br"),
]

# Изучаемые языки (target_language): код → ключ локали для подписи кнопки
TARGET_LANGS = [
    ("en", "target_lang_button_en"),
    ("ru", "target_lang_button_ru"),
    ("de", "target_lang_button_de"),
    ("es", "target_lang_button_es"),
    ("fr", "target_lang_button_fr"),
    ("id", "target_lang_button_id"),
    ("pt_br", "target_lang_button_pt_br"),
]


def interface_lang_inline_kb():
    kb = InlineKeyboardBuilder()
    for label, code in INTERFACE_LANGS:
        kb.button(text=label, callback_data=f"setlang:{code}")
    kb.button(text="⬅️", callback_data="set:back")
    kb.adjust(2)  # по две кнопки в ряд
    return kb.as_markup()


def level_inline_kb():
    kb = InlineKeyboardBuilder()
    for level in ["A1", "A2", "B1", "B2", "C1"]:
        kb.button(text=level, callback_data=f"setlevel:{level}")
    kb.button(text="⬅️", callback_data="set:back")
    kb.adjust(3)
    return kb.as_markup()


def interface_lang_register_kb():
    """Клавиатура выбора языка при ПЕРВОЙ регистрации.
    Отличается от настроек префиксом callback: reglang: вместо setlang:"""
    kb = InlineKeyboardBuilder()
    for label, code in INTERFACE_LANGS:
        kb.button(text=label, callback_data=f"reglang:{code}")
    kb.adjust(2)
    return kb.as_markup()

def level_register_kb():
    """Выбор уровня при регистрации. Префикс reglevel: (в настройках setlevel:)"""
    kb = InlineKeyboardBuilder()
    for level in ["A1", "A2", "B1", "B2", "C1"]:
        kb.button(text=level, callback_data=f"reglevel:{level}")
    kb.adjust(3)
    return kb.as_markup()


def target_language_kb(lang: str, callback_prefix: str, *, with_back: bool = False):
    """Выбор изучаемого языка. Префикс callback: regtarget: или settarget:"""
    kb = InlineKeyboardBuilder()
    for code, label_key in TARGET_LANGS:
        kb.button(text=t(label_key, lang), callback_data=f"{callback_prefix}:{code}")
    if with_back:
        kb.button(text="⬅️", callback_data="set:back")
    kb.adjust(2)
    return kb.as_markup()


def target_language_register_kb(lang: str):
    return target_language_kb(lang, "regtarget")


def target_language_settings_kb(lang: str):
    return target_language_kb(lang, "settarget", with_back=True)
 