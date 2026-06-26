"""add return tracking to users

Revision ID: add_return_tracking
Revises: add_vocab_target_language
Create Date: 2026-06-26

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "add_return_tracking"
down_revision: Union[str, Sequence[str], None] = "add_vocab_target_language"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Разделение органических возвратов и возвратов по уведомлению.
    # Только ADD COLUMN — существующие данные не трогаем.
    op.add_column(
        "users",
        sa.Column("last_notified_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("organic_returns", sa.Integer(), nullable=True, server_default="0"),
    )
    op.add_column(
        "users",
        sa.Column("notified_returns", sa.Integer(), nullable=True, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("users", "notified_returns")
    op.drop_column("users", "organic_returns")
    op.drop_column("users", "last_notified_at")
