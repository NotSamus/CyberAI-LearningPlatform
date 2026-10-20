"""account colour mode: each theme in its light or dark version

Revision ID: 8d4a2f6c1b90
Revises: 5c2f8e1a7d36
Create Date: 2026-10-19 18:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '8d4a2f6c1b90'
down_revision: Union[str, Sequence[str], None] = '5c2f8e1a7d36'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Every account starts as before: light or dark as its device is set."""
    op.add_column('users', sa.Column('color_mode', sa.String(length=8), server_default='device', nullable=False))


def downgrade() -> None:
    op.drop_column('users', 'color_mode')
