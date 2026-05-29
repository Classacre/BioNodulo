"""Create collaboration metadata tables.

Revision ID: 0001_collab_sqlalchemy
Revises:
Create Date: 2026-05-24
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0001_collab_sqlalchemy"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workflow_shares",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("workflow_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("invited_by", sa.String(), nullable=True),
        sa.Column("invited_at", sa.String(), nullable=False),
        sa.Column("accepted_at", sa.String(), nullable=True),
        sa.CheckConstraint("role IN ('owner','editor','viewer','commenter')", name="ck_share_role"),
        sa.UniqueConstraint("workflow_id", "user_id", name="uq_workflow_share_user"),
    )
    op.create_index("idx_shares_workflow", "workflow_shares", ["workflow_id"])

    op.create_table(
        "collab_rooms",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("workflow_id", sa.String(), nullable=False, unique=True),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("last_activity_at", sa.String(), nullable=False),
        sa.Column("active_users", sa.Integer(), nullable=False, server_default="0"),
    )

    op.create_table(
        "collab_audit_log",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("workflow_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("target_type", sa.String(), nullable=True),
        sa.Column("target_id", sa.String(), nullable=True),
        sa.Column("payload", sa.Text(), nullable=True),
        sa.Column("performed_at", sa.String(), nullable=False),
    )
    op.create_index("idx_audit_workflow", "collab_audit_log", ["workflow_id"])

    op.create_table(
        "comments",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("workflow_id", sa.String(), nullable=False),
        sa.Column("node_id", sa.String(), nullable=True),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("user_name", sa.String(), nullable=False),
        sa.Column("user_color", sa.String(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("parent_id", sa.String(), nullable=True),
        sa.Column("resolved", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
    )
    op.create_index("idx_comments_workflow", "comments", ["workflow_id"])
    op.create_index("idx_comments_node", "comments", ["node_id"])

    op.create_table(
        "workflow_versions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("workflow_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("user_name", sa.String(), nullable=True),
        sa.Column("snapshot", sa.LargeBinary(), nullable=False),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("auto_save", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("node_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("edge_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.String(), nullable=False),
    )
    op.create_index("idx_versions_workflow", "workflow_versions", ["workflow_id"])
    op.create_index("idx_versions_created", "workflow_versions", ["created_at"])

    op.create_table(
        "workflow_templates",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("workflow_id", sa.String(), nullable=True),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("tags", sa.Text(), nullable=True),
        sa.Column("snapshot", sa.LargeBinary(), nullable=False),
        sa.Column("is_public", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("fork_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.String(), nullable=False),
    )
    op.create_index("idx_templates_public", "workflow_templates", ["is_public"])


def downgrade() -> None:
    op.drop_index("idx_templates_public", table_name="workflow_templates")
    op.drop_table("workflow_templates")
    op.drop_index("idx_versions_created", table_name="workflow_versions")
    op.drop_index("idx_versions_workflow", table_name="workflow_versions")
    op.drop_table("workflow_versions")
    op.drop_index("idx_comments_node", table_name="comments")
    op.drop_index("idx_comments_workflow", table_name="comments")
    op.drop_table("comments")
    op.drop_index("idx_audit_workflow", table_name="collab_audit_log")
    op.drop_table("collab_audit_log")
    op.drop_table("collab_rooms")
    op.drop_index("idx_shares_workflow", table_name="workflow_shares")
    op.drop_table("workflow_shares")
