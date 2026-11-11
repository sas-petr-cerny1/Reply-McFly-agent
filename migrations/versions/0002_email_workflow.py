"""Persistent email jobs, fenced leases and reply outbox."""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("mailbox_sync_state", sa.Column("lease_token", sa.Uuid(), nullable=True))
    op.create_table(
        "email_jobs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "mailbox_id",
            sa.String(320),
            sa.ForeignKey("mailbox_sync_state.mailbox_id"),
            nullable=False,
        ),
        sa.Column("gmail_message_id", sa.String(255), nullable=False),
        sa.Column("gmail_thread_id", sa.String(255), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("lease_until", sa.DateTime(timezone=True)),
        sa.Column("lease_token", sa.Uuid()),
        sa.Column("error_code", sa.String(64)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("mailbox_id", "gmail_message_id", name="uq_job_mailbox_message"),
        sa.CheckConstraint("attempt_count >= 0", name="ck_job_attempt_count"),
        sa.CheckConstraint(
            "status IN ('RECEIVED','QUEUED','PROCESSING','READY_TO_SEND','SENDING',"
            "'SENT','RETRY_PENDING','REVIEW_REQUIRED','FAILED','DELIVERY_UNKNOWN')",
            name="ck_job_status",
        ),
    )
    for column in ("gmail_thread_id", "status", "lease_until"):
        op.create_index(f"ix_email_jobs_{column}", "email_jobs", [column])
    op.create_table(
        "email_outbox",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("job_id", sa.Uuid(), sa.ForeignKey("email_jobs.id"), unique=True, nullable=False),
        sa.Column("outbound_message_id", sa.String(998), unique=True, nullable=False),
        sa.Column("recipient", sa.String(320), nullable=False),
        sa.Column("subject", sa.String(998), nullable=False),
        sa.Column("draft_body", sa.Text(), nullable=False),
        sa.Column("response_type", sa.String(16), nullable=False),
        sa.Column("fallback_reason", sa.String(64), nullable=True),
        sa.Column("in_reply_to", sa.String(998), nullable=False),
        sa.Column("references", sa.String(2000), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("gmail_sent_message_id", sa.String(255)),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "(response_type = 'GENERATED' AND fallback_reason IS NULL) OR "
            "(response_type = 'FALLBACK' AND fallback_reason IN "
            "('INSUFFICIENT_INFORMATION','UNSUPPORTED_ATTACHMENT'))",
            name="ck_outbox_response_type",
        ),
    )


def downgrade() -> None:
    op.drop_table("email_outbox")
    op.drop_table("email_jobs")
    op.drop_column("mailbox_sync_state", "lease_token")
