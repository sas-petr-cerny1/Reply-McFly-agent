"""Store verifiable source evidence and enforce fallback metadata."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "email_outbox", sa.Column("evidence", JSONB(), server_default="[]", nullable=False)
    )
    op.drop_constraint("ck_outbox_response_type", "email_outbox", type_="check")
    op.create_check_constraint(
        "ck_outbox_response_type",
        "email_outbox",
        "(response_type = 'GENERATED' AND fallback_reason IS NULL) OR "
        "(response_type = 'FALLBACK' AND fallback_reason IN "
        "('INSUFFICIENT_INFORMATION','UNSUPPORTED_ATTACHMENT') AND fallback_reason IS NOT NULL)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_outbox_response_type", "email_outbox", type_="check")
    op.create_check_constraint(
        "ck_outbox_response_type",
        "email_outbox",
        "(response_type = 'GENERATED' AND fallback_reason IS NULL) OR "
        "(response_type = 'FALLBACK' AND fallback_reason IN "
        "('INSUFFICIENT_INFORMATION','UNSUPPORTED_ATTACHMENT'))",
    )
    op.drop_column("email_outbox", "evidence")
