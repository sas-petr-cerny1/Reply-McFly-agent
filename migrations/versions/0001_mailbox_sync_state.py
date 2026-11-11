"""RM-001: initialize pgvector and persistent mailbox state."""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "mailbox_sync_state",
        sa.Column("mailbox_id", sa.String(320), primary_key=True),
        sa.Column("history_id", sa.String(255), nullable=True),
        sa.Column("watch_expiration", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )


def downgrade() -> None:
    op.drop_table("mailbox_sync_state")
