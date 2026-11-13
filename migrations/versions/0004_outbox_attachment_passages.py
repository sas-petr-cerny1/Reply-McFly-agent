"""Persist extracted attachment passages so retries reuse the verified extraction."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "email_outbox",
        sa.Column("attachment_passages", JSONB(), server_default="[]", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("email_outbox", "attachment_passages")
