import re
from typing import Optional

_TIME_RE = re.compile(r"^(\d{1,2}):(\d{1,2})(?::(\d{1,2}))?$")


def parse_lesson_time(raw: str) -> Optional[str]:
    """
    Приводит ввод пользователя к 'HH:MM' (24h, ведущий ноль).
    Принимает '7:40', '07:40', '07:40:00'. Возвращает None, если формат неверный.
    """
    text = (raw or "").strip()
    if not text:
        return None

    match = _TIME_RE.match(text)
    if not match:
        return None

    hour = int(match.group(1))
    minute = int(match.group(2))
    if hour > 23 or minute > 59:
        return None

    return f"{hour:02d}:{minute:02d}"
