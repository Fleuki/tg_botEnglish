from dotenv import load_dotenv
import os

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
# Добавь в app/config.py (например после OPENAI_API_KEY):

# ID администраторов через запятую в .env: ADMIN_IDS=785630289
# Для них не действует дневной лимит уроков.
_admin_raw = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = [
    int(x) for x in _admin_raw.replace(" ", "").split(",") if x
]
# ── Логика выбора базы данных ──────────────────────────────
# 1. Если задана переменная DATABASE_URL (так делает Render) — используем её.
# 2. Иначе, если заданы отдельные DB_* переменные — собираем PostgreSQL URL.
# 3. Иначе (локальная разработка) — SQLite-файл.
#
# Это позволяет одному и тому же коду работать и локально, и на сервере.

DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL:
    # Render обычно даёт URL вида "postgresql://..."
    # Нам нужен async-драйвер, поэтому подменяем префикс на asyncpg.
    if DATABASE_URL.startswith("postgresql://"):
        DATABASE_URL = DATABASE_URL.replace(
            "postgresql://", "postgresql+asyncpg://", 1
        )
else:
    DB_HOST = os.getenv("DB_HOST")
    DB_PORT = os.getenv("DB_PORT")
    DB_NAME = os.getenv("DB_NAME")
    DB_USER = os.getenv("DB_USER")
    DB_PASSWORD = os.getenv("DB_PASSWORD")

    if DB_HOST and DB_NAME and DB_USER:
        # Все данные для PostgreSQL заданы — собираем URL.
        DATABASE_URL = (
            f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}"
            f"@{DB_HOST}:{DB_PORT}/{DB_NAME}"
        )
    else:
        # Ничего не задано — локальная разработка на SQLite.
        DATABASE_URL = "sqlite+aiosqlite:///./bot.db"