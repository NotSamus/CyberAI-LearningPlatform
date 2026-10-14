"""account theme: how the site looks for each account

Revision ID: 3b7e5c1d9a24
Revises: 96f8b8967047
Create Date: 2026-10-14 00:10:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '3b7e5c1d9a24'
down_revision: Union[str, Sequence[str], None] = '96f8b8967047'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Every account starts with the standard look."""
    op.add_column('users', sa.Column('theme', sa.String(length=16), server_default='standard', nullable=False))


def downgrade() -> None:
    op.drop_column('users', 'theme')
