"""initial_schema

Revision ID: 24912d9fd3a7
Revises:
Create Date: 2026-04-09 16:41:45.274620

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON


revision: str = '24912d9fd3a7'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "workspaces",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("trust_level", sa.String(16), nullable=False, server_default="MEDIUM"),
        sa.Column("policy_yaml", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )

    op.create_table(
        "sessions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("workspace_id", sa.String(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("backend_used", sa.String(64), nullable=False, server_default="unknown"),
        sa.Column("model_used", sa.String(128), nullable=False, server_default="unknown"),
        sa.Column("messages", JSON(), nullable=False, server_default="[]"),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("trust_level", sa.String(16), nullable=False, server_default="MEDIUM"),
        sa.Column("channel", sa.String(64), nullable=False, server_default="web"),
        sa.Column("dry_run", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )

    op.create_table(
        "memory_records",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("workspace_id", sa.String(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("memory_class", sa.String(32), nullable=False),
        sa.Column("key", sa.String(256), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("trust_level", sa.String(16), nullable=False, server_default="MEDIUM"),
        sa.Column("retention_class", sa.String(32), nullable=False, server_default="persistent"),
        sa.Column("provenance", JSON(), nullable=False, server_default="{}"),
        sa.Column("is_secret", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("created_by", sa.String(128), nullable=False, server_default="system"),
        sa.Column("session_id", sa.String(), nullable=True),
        sa.Column("embedding", sa.Text(), nullable=True, comment="pgvector column; type changed to vector(1536) by init_db()"),
    )

    op.execute(
        "ALTER TABLE memory_records ALTER COLUMN embedding TYPE vector(1536) "
        "USING NULL"
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("workspace_id", sa.String(), sa.ForeignKey("workspaces.id"), nullable=True),
        sa.Column("actor", sa.String(128), nullable=False),
        sa.Column("action", sa.String(256), nullable=False),
        sa.Column("tool_name", sa.String(128), nullable=True),
        sa.Column("input_hash", sa.String(64), nullable=True),
        sa.Column("policy_decision", sa.String(32), nullable=False, server_default="unknown"),
        sa.Column("approval_status", sa.String(32), nullable=False, server_default="not_required"),
        sa.Column("dry_run", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("result_summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("correlation_id", sa.String(64), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )

    op.create_table(
        "policy_configs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("workspace_id", sa.String(), sa.ForeignKey("workspaces.id"), nullable=False, unique=True),
        sa.Column("config_yaml", sa.Text(), nullable=False, server_default=""),
        sa.Column("kill_switch", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )

    op.create_index("ix_memory_records_workspace_class", "memory_records", ["workspace_id", "memory_class"])
    op.create_index("ix_audit_logs_workspace_timestamp", "audit_logs", ["workspace_id", "timestamp"])
    op.create_index("ix_sessions_workspace", "sessions", ["workspace_id"])


def downgrade() -> None:
    op.drop_index("ix_sessions_workspace", table_name="sessions")
    op.drop_index("ix_audit_logs_workspace_timestamp", table_name="audit_logs")
    op.drop_index("ix_memory_records_workspace_class", table_name="memory_records")
    op.drop_table("policy_configs")
    op.drop_table("audit_logs")
    op.drop_table("memory_records")
    op.drop_table("sessions")
    op.drop_table("workspaces")
