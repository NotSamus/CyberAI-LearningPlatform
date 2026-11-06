"""lesson archived: archiving a lesson instead of deleting it

Revision ID: 4b8e1f2a9c37
Revises: 2e7c9b4d1f58
Create Date: 2026-11-06 12:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '4b8e1f2a9c37'
down_revision: Union[str, Sequence[str], None] = '2e7c9b4d1f58'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """No lesson is archived to begin with."""
    op.add_column('lessons', sa.Column('archived_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('lessons', 'archived_at')
