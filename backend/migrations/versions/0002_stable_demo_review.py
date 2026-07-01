"""stable demo review and soft delete

Revision ID: 0002_stable_demo_review
Revises: 0001_initial
Create Date: 2026-07-01
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0002_stable_demo_review"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "verification_results",
        sa.Column("review_status", sa.Text(), nullable=False, server_default="unreviewed"),
    )
    op.add_column("verification_results", sa.Column("review_note", sa.Text(), nullable=True))
    op.add_column("verification_results", sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_documents_deleted_at", "documents", ["deleted_at"])


def downgrade() -> None:
    op.drop_index("ix_documents_deleted_at", table_name="documents")
    op.drop_column("verification_results", "reviewed_at")
    op.drop_column("verification_results", "review_note")
    op.drop_column("verification_results", "review_status")
    op.drop_column("documents", "deleted_at")