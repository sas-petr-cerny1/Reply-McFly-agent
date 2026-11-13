"""Selects the RAG backend from configuration for every composition root."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy.engine import Engine

from reply_mcfly.adapters.markdown_rag_adapter import MarkdownRAGProvider
from reply_mcfly.adapters.pgvector_rag_adapter import PgVectorRAGProvider
from reply_mcfly.adapters.vertex_embedding_adapter import VertexEmbeddingAdapter
from reply_mcfly.application.rag_query import build_product_question, build_rag_retrieval_query
from reply_mcfly.config.settings import Settings
from reply_mcfly.domain.email import IncomingEmail
from reply_mcfly.ports.capabilities import RAGProvider


@dataclass(frozen=True)
class RagComponents:
    provider: RAGProvider | None
    query_builder: Callable[[IncomingEmail], str]
    # Seconds the Worker must still have before it may start a retrieval; 0 = local, instant.
    timeout: float


def build_embedder(settings: Settings) -> VertexEmbeddingAdapter:
    return VertexEmbeddingAdapter(
        settings.gcp_project_id,
        settings.rag_embedding_location or settings.gcp_region,
        settings.rag_embedding_model,
        settings.rag_embedding_dims,
    )


def build_rag(settings: Settings, engine: Engine) -> RagComponents:
    if not settings.enable_rag:
        return RagComponents(None, build_rag_retrieval_query, 0.0)
    if settings.rag_backend == "markdown":
        return RagComponents(MarkdownRAGProvider(), build_rag_retrieval_query, 0.0)
    provider = PgVectorRAGProvider(
        engine,
        build_embedder(settings),
        embedding_model=settings.rag_embedding_model,
        top_k=settings.rag_top_k,
        timeout=settings.rag_timeout_seconds,
    )
    # The embedding API is external: it gets a minimised question, never attachment text.
    return RagComponents(provider, build_product_question, settings.rag_timeout_seconds)
