from app.locales.en import TEXTS as en
from app.locales.ru import TEXTS as ru
from app.locales.de import TEXTS as de
from app.locales.es import TEXTS as es
from app.locales.fr import TEXTS as fr
from app.locales.id import TEXTS as id_
from app.locales.pt_br import TEXTS as pt_br


LOCALES = {
    "en": en,
    "ru": ru,
    "de": de,
    "es": es,
    "fr": fr,
    "id": id_,
    "pt_br": pt_br
}


def t(key: str, lang: str = "en") -> str:
    language = LOCALES.get(lang, en)

    return language.get(key, en.get(key, key))

UI_TEXTS = {
    "translation": {
        "en": "🌍 Translation",
        "ru": "🌍 Перевод",
        "id": "🌍 Terjemahan"
    }
}

def t_ui(key: str, lang: str):
    return UI_TEXTS[key].get(lang, UI_TEXTS[key]["en"])