"""add target_language to vocab

Revision ID: add_vocab_target_language
Revises: add_target_language
Create Date: 2026-06-23

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "add_vocab_target_language"
down_revision: Union[str, Sequence[str], None] = "add_target_language"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "vocab",
        sa.Column("target_language", sa.String(), server_default="en", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("vocab", "target_language")
