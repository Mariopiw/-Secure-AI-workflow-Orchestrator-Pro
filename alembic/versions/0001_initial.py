"""initial workflow schema

Revision ID: 0001
Revises:
Create Date: 2026-10-06
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

userrole = sa.Enum("SUBMITTER", "APPROVER", "OPERATOR", "ADMIN", name="userrole")
workflowstatus = sa.Enum(
    "RECEIVED", "VALIDATING", "AI_REVIEW", "WAITING_APPROVAL", "APPROVED",
    "EXECUTING", "COMPLETED", "REJECTED", "FAILED", "NEEDS_RECONCILIATION",
    name="workflowstatus",
)
decision = sa.Enum("APPROVE", "REJECT", name="decision")
deliverystatus = sa.Enum("PENDING", "DELIVERING", "DELIVERED", "FAILED", name="deliverystatus")


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(120), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", userrole, nullable=False),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("username"),
    )
    op.create_index("ix_users_tenant_id", "users", ["tenant_id"])
    op.create_index("ix_users_role", "users", ["role"])

    op.create_table(
        "workflows",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_id", sa.String(36), nullable=False),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("workflow_type", sa.String(80), nullable=False, server_default="regulated_case_review"),
        sa.Column("case_reference", sa.String(120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("input_payload", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("callback_url", sa.String(500), nullable=True),
        sa.Column("status", workflowstatus, nullable=False, server_default="RECEIVED"),
        sa.Column("risk_score", sa.Integer(), nullable=True),
        sa.Column("ai_reason", sa.Text(), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("public_id"),
        sa.UniqueConstraint("tenant_id", "idempotency_key", name="uq_workflow_tenant_idem"),
    )
    op.create_index("ix_workflow_tenant_status", "workflows", ["tenant_id", "status"])
    op.create_index("ix_workflows_updated_at", "workflows", ["updated_at"])
    op.create_index("ix_workflows_case_reference", "workflows", ["case_reference"])

    op.create_table(
        "workflow_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workflow_id", sa.Integer(), sa.ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("actor", sa.String(160), nullable=False),
        sa.Column("detail", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_workflow_events_workflow_id", "workflow_events", ["workflow_id"])
    op.create_index("ix_workflow_events_tenant_id", "workflow_events", ["tenant_id"])

    op.create_table(
        "approvals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workflow_id", sa.Integer(), sa.ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("decision", decision, nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("workflow_id", name="uq_approval_workflow"),
    )

    op.create_table(
        "execution_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workflow_id", sa.Integer(), sa.ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("effect_key", sa.String(120), nullable=False),
        sa.Column("result", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("workflow_id", name="uq_execution_workflow"),
        sa.UniqueConstraint("effect_key"),
    )

    op.create_table(
        "outbox_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_id", sa.String(36), nullable=False),
        sa.Column("workflow_id", sa.Integer(), sa.ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("callback_url", sa.String(500), nullable=False),
        sa.Column("enqueued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dead_lettered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("event_id"),
    )
    op.create_index("ix_outbox_pending", "outbox_events", ["delivered_at", "dead_lettered_at", "enqueued_at"])

    op.create_table(
        "webhook_deliveries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("outbox_event_id", sa.Integer(), sa.ForeignKey("outbox_events.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_id", sa.String(36), nullable=False),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("status", deliverystatus, nullable=False, server_default="PENDING"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_status_code", sa.Integer(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("outbox_event_id"),
        sa.UniqueConstraint("event_id"),
    )

    op.create_table(
        "inbound_webhooks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("provider", sa.String(80), nullable=False),
        sa.Column("external_event_id", sa.String(200), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("provider", "external_event_id", name="uq_inbound_provider_event"),
    )

    op.create_table(
        "dead_letters",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("kind", sa.String(80), nullable=False),
        sa.Column("object_id", sa.String(200), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade():
    for table in [
        "dead_letters", "inbound_webhooks", "webhook_deliveries", "outbox_events",
        "execution_records", "approvals", "workflow_events", "workflows", "users",
    ]:
        op.drop_table(table)
    deliverystatus.drop(op.get_bind(), checkfirst=True)
    decision.drop(op.get_bind(), checkfirst=True)
    workflowstatus.drop(op.get_bind(), checkfirst=True)
    userrole.drop(op.get_bind(), checkfirst=True)
