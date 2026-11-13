"""Isolated product knowledge chunks with pgvector embeddings."""

import sqlalchemy as sa
from alembic import op

from reply_mcfly.adapters.postgres_adapter import EMBEDDING_DIMENSIONS, Vector

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "rag_product_chunks",
        sa.Column("chunk_id", sa.String(255), primary_key=True),
        sa.Column("document_id", sa.String(255), nullable=False),
        sa.Column("product_id", sa.String(64), nullable=False),
        sa.Column("product_name", sa.String(255), nullable=False),
        sa.Column("section_name", sa.String(255), nullable=False),
        sa.Column("document_version", sa.String(64), nullable=False),
        sa.Column("language", sa.String(8), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_sha256", sa.String(64), nullable=False),
        sa.Column("source_id", sa.String(512), nullable=False),
        sa.Column("provenance", sa.String(512), nullable=False),
        sa.Column("embedding_model", sa.String(128), nullable=False),
        sa.Column("embedding", Vector(EMBEDDING_DIMENSIONS), nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("source_id", name="uq_rag_product_chunks_source_id"),
    )
    # 18 chunks are searched exactly; no HNSW/IVFFlat index without a benchmark.
    op.create_index("ix_rag_product_chunks_product_id", "rag_product_chunks", ["product_id"])


def downgrade() -> None:
    op.drop_table("rag_product_chunks")
