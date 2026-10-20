"""assignment files: data files (datasets) that go with an assignment's notebook

Revision ID: 2e7c9b4d1f58
Revises: 8d4a2f6c1b90
Create Date: 2026-10-20 16:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '2e7c9b4d1f58'
down_revision: Union[str, Sequence[str], None] = '8d4a2f6c1b90'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'assignment_files',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('assignment_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('size', sa.Integer(), nullable=False),
        sa.Column('data', sa.LargeBinary(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['assignment_id'], ['assignments.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('assignment_id', 'name'),
    )
    op.create_index(op.f('ix_assignment_files_assignment_id'), 'assignment_files', ['assignment_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_assignment_files_assignment_id'), table_name='assignment_files')
    op.drop_table('assignment_files')
