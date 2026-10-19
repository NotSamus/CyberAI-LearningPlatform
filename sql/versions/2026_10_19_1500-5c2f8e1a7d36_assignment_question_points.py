"""assignment question points: each autograded question's points, from the teacher's own tests

Revision ID: 5c2f8e1a7d36
Revises: 3b7e5c1d9a24
Create Date: 2026-10-19 15:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '5c2f8e1a7d36'
down_revision: Union[str, Sequence[str], None] = '3b7e5c1d9a24'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Empty for assignments uploaded before: their points are worked out when a submission of theirs
    is next graded (app/submissions.py)."""
    op.add_column('assignments', sa.Column('question_points', postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    op.drop_column('assignments', 'question_points')
