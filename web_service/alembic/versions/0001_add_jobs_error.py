"""add jobs.error column

Revision ID: 0001_add_jobs_error
Revises:
Create Date: 2026-10-20
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_add_jobs_error"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("error", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("jobs", "error")
