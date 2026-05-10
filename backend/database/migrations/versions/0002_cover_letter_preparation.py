"""cover letter preparation fields

Revision ID: 0002_cover_letter_preparation
Revises: 0001_initial_schema
Create Date: 2026-05-09
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0002_cover_letter_preparation"
down_revision: str | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE company_cache ADD COLUMN IF NOT EXISTS known BOOLEAN DEFAULT true")
    op.execute("ALTER TABLE company_cache ADD COLUMN IF NOT EXISTS industry TEXT")
    op.execute("ALTER TABLE company_cache ADD COLUMN IF NOT EXISTS what_they_do TEXT")
    op.execute("ALTER TABLE company_cache ADD COLUMN IF NOT EXISTS why_interesting TEXT")


def downgrade() -> None:
    op.execute("ALTER TABLE company_cache DROP COLUMN IF EXISTS why_interesting")
    op.execute("ALTER TABLE company_cache DROP COLUMN IF EXISTS what_they_do")
    op.execute("ALTER TABLE company_cache DROP COLUMN IF EXISTS industry")
    op.execute("ALTER TABLE company_cache DROP COLUMN IF EXISTS known")
