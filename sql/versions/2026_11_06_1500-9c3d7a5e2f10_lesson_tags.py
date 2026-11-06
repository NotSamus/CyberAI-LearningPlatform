"""lesson tags: words a teacher puts on a lesson (Cybersecurity, AI, ...)

Revision ID: 9c3d7a5e2f10
Revises: 4b8e1f2a9c37
Create Date: 2026-11-06 15:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '9c3d7a5e2f10'
down_revision: Union[str, Sequence[str], None] = '4b8e1f2a9c37'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Every lesson starts without tags."""
    op.add_column('lessons', sa.Column('tags', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False))


def downgrade() -> None:
    op.drop_column('lessons', 'tags')
