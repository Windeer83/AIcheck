"""add run logs

Revision ID: 0003_run_logs
Revises: 0002_stable_demo_review
Create Date: 2026-07-01
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0003_run_logs"
down_revision = "0002_stable_demo_review"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "run_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("runs.id"), nullable=False),
        sa.Column("step", sa.Text(), nullable=False),
        sa.Column("level", sa.Text(), nullable=False, server_default="info"),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_run_logs_run_id", "run_logs", ["run_id"])
    op.create_index("ix_run_logs_created_at", "run_logs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_run_logs_created_at", table_name="run_logs")
    op.drop_index("ix_run_logs_run_id", table_name="run_logs")
    op.drop_table("run_logs")