#!/usr/bin/env python3
"""
One-time migration: add missing columns to the users table.

Safe for production PostgreSQL:
  - only ADD COLUMN IF NOT EXISTS
  - no DROP / TRUNCATE / DELETE / CREATE TABLE / create_all
  - idempotent (safe to run more than once)

Usage (from project root, with DATABASE_URL in .env or environment):
    python scripts/migrate_add_columns.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Allow `import app.*` when run as `python scripts/migrate_add_columns.py`
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.config import DATABASE_URL

LIST_COLUMNS_SQL = text("""
    SELECT column_name
    FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'users'
    ORDER BY ordinal_position
""")

COUNT_USERS_SQL = text("SELECT COUNT(*) FROM users")

ADD_COLUMNS_SQL = [
    text("""
        ALTER TABLE users
        ADD COLUMN IF NOT EXISTS target_language VARCHAR NOT NULL DEFAULT 'en'
    """),
    text("""
        ALTER TABLE users
        ADD COLUMN IF NOT EXISTS last_activity_date TIMESTAMP
    """),
    text("""
        ALTER TABLE users
        ADD COLUMN IF NOT EXISTS streak_days INTEGER DEFAULT 0
    """),
    text("""
        ALTER TABLE users
        ADD COLUMN IF NOT EXISTS interface_language VARCHAR DEFAULT 'en'
    """),
    text("""
        ALTER TABLE users
        ADD COLUMN IF NOT EXISTS preferred_topic VARCHAR DEFAULT 'general'
    """),
    text("""
        ALTER TABLE users
        ADD COLUMN IF NOT EXISTS lessons_today INTEGER DEFAULT 0
    """),
    text("""
        ALTER TABLE users
        ADD COLUMN IF NOT EXISTS lessons_date DATE
    """),
    text("""
        ALTER TABLE users
        ADD COLUMN IF NOT EXISTS checks_today INTEGER DEFAULT 0
    """),
    text("""
        ALTER TABLE users
        ADD COLUMN IF NOT EXISTS checks_date DATE
    """),
    text("""
        ALTER TABLE vocab
        ADD COLUMN IF NOT EXISTS target_language VARCHAR NOT NULL DEFAULT 'en'
    """),
]

FILL_NULLS_SQL = [
    text("UPDATE users SET target_language = 'en' WHERE target_language IS NULL"),
    text("UPDATE users SET streak_days = 0 WHERE streak_days IS NULL"),
    text("UPDATE users SET interface_language = 'en' WHERE interface_language IS NULL"),
    text("UPDATE users SET preferred_topic = 'general' WHERE preferred_topic IS NULL"),
    text("UPDATE users SET lessons_today = 0 WHERE lessons_today IS NULL"),
    text("UPDATE users SET checks_today = 0 WHERE checks_today IS NULL"),
    text("UPDATE vocab SET target_language = 'en' WHERE target_language IS NULL"),
]


def _mask_url(url: str) -> str:
    """Hide password in connection URL for logs."""
    if "@" not in url:
        return url
    prefix, rest = url.split("@", 1)
    if "://" in prefix:
        scheme, creds = prefix.split("://", 1)
        if ":" in creds:
            user, _ = creds.split(":", 1)
            return f"{scheme}://{user}:***@{rest}"
    return f"***@{rest}"


async def _fetch_columns(conn) -> list[str]:
    result = await conn.execute(LIST_COLUMNS_SQL)
    return [row[0] for row in result.fetchall()]


async def _fetch_user_count(conn) -> int:
    result = await conn.execute(COUNT_USERS_SQL)
    return int(result.scalar_one())


def _print_columns(title: str, columns: list[str]) -> None:
    print(f"\n{title}")
    print("-" * len(title))
    if columns:
        for name in columns:
            print(f"  • {name}")
    else:
        print("  (no columns found — check that table users exists)")


async def _apply_migration(engine: AsyncEngine) -> None:
    """ALTER + UPDATE in one transaction; rolls back automatically on error."""
    async with engine.begin() as conn:
        for stmt in ADD_COLUMNS_SQL:
            await conn.execute(stmt)
        for stmt in FILL_NULLS_SQL:
            await conn.execute(stmt)


async def migrate() -> int:
    if not DATABASE_URL:
        print("ERROR: DATABASE_URL is not set.")
        return 1

    if "postgresql" not in DATABASE_URL and "postgres" not in DATABASE_URL:
        print("ERROR: This script is intended for PostgreSQL (Amvera production).")
        print(f"       Current DATABASE_URL: {_mask_url(DATABASE_URL)}")
        return 1

    print("One-time migration: add missing columns to users")
    print(f"Database: {_mask_url(DATABASE_URL)}")

    engine = create_async_engine(DATABASE_URL, echo=False)

    try:
        async with engine.connect() as conn:
            before_columns = await _fetch_columns(conn)
        _print_columns("Columns BEFORE migration:", before_columns)

        print("\nApplying changes in a single transaction...")
        await _apply_migration(engine)

        async with engine.connect() as conn:
            after_columns = await _fetch_columns(conn)
            user_count = await _fetch_user_count(conn)

        _print_columns("Columns AFTER migration:", after_columns)
        print(f"\nUser count: {user_count}")
        print("\nMigration completed successfully.")
        return 0

    except Exception as exc:
        print("\nERROR: migration failed — transaction rolled back.")
        print(f"       {type(exc).__name__}: {exc}")
        return 1

    finally:
        await engine.dispose()


def main() -> None:
    exit_code = asyncio.run(migrate())
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
