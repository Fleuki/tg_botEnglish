"""add target_language to users

Revision ID: add_target_language
Revises: add_streak_tracking
Create Date: 2026-06-23

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "add_target_language"
down_revision: Union[str, Sequence[str], None] = "add_streak_tracking"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("target_language", sa.String(), server_default="en", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("users", "target_language")
