"""add streak tracking to users

Revision ID: add_streak_tracking
Revises: 3c6ca2f88387
Create Date: 2026-06-17 17:02:55.434438

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_streak_tracking'
down_revision: Union[str, Sequence[str], None] = '3c6ca2f88387'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add new columns to users table
    op.add_column('users', sa.Column('last_activity_date', sa.DateTime(), nullable=True))
    op.add_column('users', sa.Column('streak_days', sa.Integer(), nullable=True, server_default='0'))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'streak_days')
    op.drop_column('users', 'last_activity_date')
