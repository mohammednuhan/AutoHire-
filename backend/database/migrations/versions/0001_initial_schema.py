"""initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-05-08
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from alembic import op

revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    schema_path = Path(__file__).resolve().parents[2] / "schema.sql"
    statements = [statement.strip() for statement in schema_path.read_text().split(";")]
    for statement in statements:
        if statement:
            op.execute(statement)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS tasks CASCADE")
    op.execute("DROP TABLE IF EXISTS company_cache CASCADE")
    op.execute("DROP TABLE IF EXISTS form_template_cache CASCADE")
    op.execute("DROP TABLE IF EXISTS qa_memory CASCADE")
    op.execute("DROP TABLE IF EXISTS application_events CASCADE")
    op.execute("DROP TABLE IF EXISTS agent_logs CASCADE")
    op.execute("DROP TABLE IF EXISTS cover_letters CASCADE")
    op.execute("DROP TABLE IF EXISTS applications CASCADE")
    op.execute("DROP TABLE IF EXISTS job_scores CASCADE")
    op.execute("DROP TABLE IF EXISTS jobs CASCADE")
    op.execute("DROP TABLE IF EXISTS user_preferences CASCADE")
    op.execute("DROP TABLE IF EXISTS resumes CASCADE")
    op.execute("DROP TABLE IF EXISTS users CASCADE")
