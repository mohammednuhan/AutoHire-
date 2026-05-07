"""foundation schema

Revision ID: 0001_foundation_schema
Revises:
Create Date: 2026-05-08
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_foundation_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


application_status = postgresql.ENUM(
    "DISCOVERED",
    "SCORED",
    "QUEUED",
    "NEEDS_HUMAN",
    "SUBMITTED",
    "SKIPPED",
    "FAILED",
    name="application_status",
)
job_source = postgresql.ENUM(
    "WELLFOUND",
    "NAUKRI",
    "INSTAHYRE",
    "COMPANY_SITE",
    "LINKEDIN",
    "MANUAL",
    name="job_source",
)
decision_reason = postgresql.ENUM(
    "SCORE_AUTO_QUEUE",
    "LOW_CONFIDENCE",
    "DREAM_COMPANY",
    "DAILY_CAP_REACHED",
    "USER_REQUESTED",
    "LINKEDIN_SEMI_AUTOMATIC",
    name="decision_reason",
)
audit_event_type = postgresql.ENUM(
    "JOB_DISCOVERED",
    "JOB_SCORED",
    "STATUS_CHANGED",
    "SCREENSHOT_CAPTURED",
    "HUMAN_REVIEW_REQUESTED",
    name="audit_event_type",
)


def upgrade() -> None:
    bind = op.get_bind()
    application_status.create(bind, checkfirst=True)
    job_source.create(bind, checkfirst=True)
    decision_reason.create(bind, checkfirst=True)
    audit_event_type.create(bind, checkfirst=True)

    op.create_table(
        "user_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("full_name", sa.String(length=160), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("location", sa.String(length=160), nullable=True),
        sa.Column("education", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("skills", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("links", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("preferences", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_table(
        "companies",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("website", sa.String(length=500), nullable=True),
        sa.Column("is_dream_company", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "resumes",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("user_profile_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("content_text", sa.Text(), nullable=False),
        sa.Column("format", sa.String(length=64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_profile_id"], ["user_profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "job_postings",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("source", job_source, nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("url", sa.String(length=1000), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("required_skills", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source", "external_id", name="uq_job_posting_source_external_id"),
    )
    op.create_table(
        "applications",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("job_posting_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("status", application_status, nullable=False),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("confidence", sa.Numeric(precision=3, scale=2), nullable=True),
        sa.Column("decision_reason", decision_reason, nullable=True),
        sa.Column("daily_cap_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["job_posting_id"], ["job_postings.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_posting_id"),
    )
    op.create_table(
        "cover_letters",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("application_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("word_count", sa.Integer(), nullable=False),
        sa.Column("paragraph_count", sa.Integer(), nullable=False),
        sa.Column("model_provider", sa.String(length=80), nullable=False),
        sa.Column("model_name", sa.String(length=160), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("application_id"),
    )
    op.create_table(
        "screening_answers",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("application_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Numeric(precision=3, scale=2), nullable=False),
        sa.Column("model_provider", sa.String(length=80), nullable=False),
        sa.Column("model_name", sa.String(length=160), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "screenshot_audits",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("application_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("field_name", sa.String(length=160), nullable=True),
        sa.Column("path", sa.String(length=1000), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("application_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("event_type", audit_event_type, nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("screenshot_audits")
    op.drop_table("screening_answers")
    op.drop_table("cover_letters")
    op.drop_table("applications")
    op.drop_table("job_postings")
    op.drop_table("resumes")
    op.drop_table("companies")
    op.drop_table("user_profiles")

    audit_event_type.drop(op.get_bind(), checkfirst=True)
    decision_reason.drop(op.get_bind(), checkfirst=True)
    job_source.drop(op.get_bind(), checkfirst=True)
    application_status.drop(op.get_bind(), checkfirst=True)
