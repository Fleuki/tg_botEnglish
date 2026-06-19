from app.locales.ru import MESSAGES as RU
from app.locales.en import MESSAGES as EN
from app.locales.de import MESSAGES as DE
from app.locales.es import MESSAGES as ES
from app.locales.fr import MESSAGES as FR
from app.locales.pt_br import MESSAGES as PT_BR
from app.locales.id import MESSAGES as ID

LOCALES = {
    "ru": RU,
    "en": EN,
    "de": DE,
    "es": ES,
    "fr": FR,
    "pt": PT_BR,
    "pt_br": PT_BR,
    "id": ID
}

def t(key: str, lang: str):
    return LOCALES.get(lang, EN).get(key, key)