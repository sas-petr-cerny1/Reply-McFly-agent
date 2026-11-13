"""Semantic retrieval of approved product knowledge from PostgreSQL + pgvector.

Exact cosine search over a few dozen chunks; no vector index, framework or second store.
The table holds catalog text only. Customer mail and thread history are never written here.
"""

from __future__ import annotations

import re
import time
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import SQLAlchemyError

from reply_mcfly.adapters.markdown_rag_adapter import _tokens
from reply_mcfly.application.product_catalog import ProductChunk
from reply_mcfly.application.rag_query import sanitize_product_question
from reply_mcfly.application.telemetry import emit
from reply_mcfly.domain.email import WorkflowError
from reply_mcfly.ports.capabilities import EmbeddingProvider, SourcePassage

MAX_TOP_K = 3
# The whole approved collection (18 chunks) fits; ranking and filtering happen on all of it.
_CANDIDATE_LIMIT = 24
_MAX_TOTAL_CHARS = 6_000
# Time kept back from the retrieval budget for the two short SQL statements.
_DATABASE_RESERVE_SECONDS = 2.0
_MIN_KEYWORD_OVERLAP = 2
_STEM_LENGTH = 5
_MODEL_TOKEN = re.compile(r"[a-z]?\d+[a-z]?")
_BRANDED_NAME = re.compile(r"\bMcFly\s+([A-Z][\w-]+)")
# Words that say nothing about which product or feature a question is about.
_GENERIC_WORDS = frozenset(
    {"mcfly", "produkt", "produktu", "nazev", "fiktivni", "lze", "nelze", "mozne", "funguje"}
)

_PRODUCTS = text(
    "SELECT DISTINCT product_id, product_name FROM rag_product_chunks "
    "WHERE embedding_model = :model ORDER BY product_id"
)
# One statement is one snapshot: a concurrent catalog sync is seen fully or not at all.
_SEARCH = text(
    "SELECT document_id, product_id, document_version, content, source_id, provenance "
    "FROM rag_product_chunks "
    "WHERE embedding_model = :model AND (:any_product OR product_id = ANY(:products)) "
    "ORDER BY embedding <=> CAST(:vector AS vector), chunk_id LIMIT :limit"
)
_LOOKUP = text(
    "SELECT document_id, product_id, document_version, content, source_id, provenance "
    "FROM rag_product_chunks "
    "WHERE embedding_model = :model AND source_id = ANY(:source_ids) ORDER BY chunk_id"
)
_UPSERT = text(
    """
    INSERT INTO rag_product_chunks (
        chunk_id, document_id, product_id, product_name, section_name, document_version,
        language, content, content_sha256, source_id, provenance, embedding_model, embedding
    ) VALUES (
        :chunk_id, :document_id, :product_id, :product_name, :section_name, :document_version,
        :language, :content, :content_sha256, :source_id, :provenance, :embedding_model,
        CAST(:embedding AS vector)
    )
    ON CONFLICT (chunk_id) DO UPDATE SET
        document_id = EXCLUDED.document_id,
        product_id = EXCLUDED.product_id,
        product_name = EXCLUDED.product_name,
        section_name = EXCLUDED.section_name,
        document_version = EXCLUDED.document_version,
        language = EXCLUDED.language,
        content = EXCLUDED.content,
        content_sha256 = EXCLUDED.content_sha256,
        source_id = EXCLUDED.source_id,
        provenance = EXCLUDED.provenance,
        embedding_model = EXCLUDED.embedding_model,
        embedding = EXCLUDED.embedding,
        updated_at = now()
    """
)


def vector_literal(values: Sequence[float]) -> str:
    return "[" + ",".join(repr(float(value)) for value in values) + "]"


def _words(value: str) -> list[str]:
    plain = unicodedata.normalize("NFKD", value.casefold())
    plain = "".join(ch for ch in plain if not unicodedata.combining(ch))
    return re.findall(r"[a-z0-9]+", plain)


def _stems(value: str) -> frozenset[str]:
    return frozenset(
        token[:_STEM_LENGTH] for token in _tokens(value) if token not in _GENERIC_WORDS
    )


@dataclass(frozen=True)
class _Product:
    product_id: str
    family: str
    designator: str


def _product(product_id: str, product_name: str) -> _Product:
    # "McFly AirDock 8 — dokovací stanice" -> family "airdock", model designator "8".
    words = _words(product_name.split("—")[0])
    names = [word for word in words if word != "mcfly" and not _MODEL_TOKEN.fullmatch(word)]
    designator = words[-1] if words and _MODEL_TOKEN.fullmatch(words[-1]) else ""
    return _Product(product_id, max(names, key=len, default=""), designator)


def identify_products(question: str, products: Sequence[_Product]) -> tuple[tuple[str, ...], bool]:
    """Return the catalog products the question names and whether it names an unknown one.

    An unknown product is a known family with a different model ("AirDock 9") or another
    "McFly <Name>". Such a question must not be answered with a sibling product's facts.
    """
    words = _words(question)
    compact = "".join(words)
    named: list[str] = []
    unknown = False
    for product in products:
        if "".join(_words(product.product_id)) in compact:
            named.append(product.product_id)
            continue
        for index, word in enumerate(words):
            if not product.family or not word.startswith(product.family):
                continue
            following = words[index + 1] if index + 1 < len(words) else ""
            if product.designator and _MODEL_TOKEN.fullmatch(following):
                if following != product.designator:
                    unknown = True
                    continue
            named.append(product.product_id)
            break
    families = [product.family for product in products if product.family]
    for name in _BRANDED_NAME.findall(question):
        candidate = "".join(_words(name))
        if candidate and not any(candidate.startswith(family) for family in families):
            unknown = True
    return tuple(dict.fromkeys(named)), unknown


def _select(
    rows: Sequence[Mapping[str, Any]], named: Sequence[str], question: str, top_k: int
) -> list[Mapping[str, Any]]:
    """Pick the passages to return; ``rows`` are already ordered by cosine distance."""
    if len(named) == 1:
        return list(rows[:top_k])
    if named:
        # Two products in one question: the best passage of each first, then by rank.
        first = [next((row for row in rows if row["product_id"] == item), None) for item in named]
        leaders = [row for row in first if row is not None]
        rest = [row for row in rows if row not in leaders]
        return (leaders + rest)[:top_k]
    # No product named: trust the vector order, but only for passages that share real
    # vocabulary with the question, and only for the product ranked first. A fixed
    # similarity threshold would need calibration on live embeddings first.
    wanted = _stems(question)
    relevant = [row for row in rows if len(wanted & _stems(row["content"])) >= _MIN_KEYWORD_OVERLAP]
    if not relevant:
        return []
    return [row for row in relevant if row["product_id"] == relevant[0]["product_id"]][:top_k]


def _passages(rows: Sequence[Mapping[str, Any]]) -> tuple[SourcePassage, ...]:
    versions: dict[str, str] = {}
    for row in rows:
        if (
            versions.setdefault(row["document_id"], row["document_version"])
            != (row["document_version"])
        ):
            # Never hand the model two versions of one document as a single truth.
            raise WorkflowError("RAG_VERSION_CONFLICT")
    return tuple(
        SourcePassage(row["source_id"], "RAG", row["content"], row["provenance"]) for row in rows
    )


class PgVectorRAGProvider:
    """``RAGProvider`` backed by ``rag_product_chunks``; read-only at runtime."""

    def __init__(
        self,
        engine: Engine,
        embedder: EmbeddingProvider,
        *,
        embedding_model: str,
        top_k: int = MAX_TOP_K,
        timeout: float = 10.0,
    ) -> None:
        if not 1 <= top_k <= MAX_TOP_K:
            raise ValueError("RAG_TOP_K_INVALID")
        if not embedding_model or timeout <= _DATABASE_RESERVE_SECONDS:
            raise ValueError("RAG_CONFIGURATION_INVALID")
        self.engine, self.embedder = engine, embedder
        self.embedding_model, self.top_k, self.timeout = embedding_model, top_k, timeout

    def retrieve(self, query: str) -> tuple[SourcePassage, ...]:
        started = time.monotonic()
        timings = {"embedding": 0, "query": 0}
        passages: tuple[SourcePassage, ...] = ()
        error_code: str | None = None
        version: str | None = None
        try:
            passages, version = self._retrieve(query, started, timings)
            return passages
        except WorkflowError as error:
            error_code = error.code
            raise
        finally:
            emit(
                "rag_retrieval",
                embedding_latency_ms=timings["embedding"],
                vector_query_latency_ms=timings["query"],
                rag_total_latency_ms=int((time.monotonic() - started) * 1000),
                rag_hit_count=len(passages),
                rag_error_code=error_code,
                embedding_model=self.embedding_model,
                document_version=version,
            )

    def _retrieve(
        self, query: str, started: float, timings: dict[str, int]
    ) -> tuple[tuple[SourcePassage, ...], str | None]:
        question = sanitize_product_question(query)
        if not question:
            return (), None
        try:
            with self.engine.connect() as connection:
                products = self._products(connection)
        except SQLAlchemyError:
            raise WorkflowError("RAG_DATABASE_UNAVAILABLE", retryable=True, status=503) from None
        named, unknown = identify_products(question, products)
        if not products or (unknown and not named):
            return (), None
        remaining = self.timeout - (time.monotonic() - started) - _DATABASE_RESERVE_SECONDS
        embedding_started = time.monotonic()
        vector = self.embedder.embed_query(question, remaining)
        timings["embedding"] = int((time.monotonic() - embedding_started) * 1000)
        query_started = time.monotonic()
        try:
            with self.engine.connect() as connection:
                rows = self._search(connection, vector, named)
        except SQLAlchemyError:
            raise WorkflowError("RAG_DATABASE_UNAVAILABLE", retryable=True, status=503) from None
        timings["query"] = int((time.monotonic() - query_started) * 1000)
        selected: list[Mapping[str, Any]] = []
        for row in _select(rows, named, question, self.top_k):
            total = sum(len(item["content"]) for item in selected) + len(row["content"])
            if selected and total > _MAX_TOTAL_CHARS:
                break
            selected.append(row)
        passages = _passages(selected)
        versions = sorted({row["document_version"] for row in selected})
        return passages, ",".join(versions) or None

    def lookup(self, source_ids: tuple[str, ...]) -> tuple[SourcePassage, ...]:
        """Exact passages by id. A changed document has a new id and is simply not found."""
        if not source_ids:
            return ()
        try:
            with self.engine.connect() as connection:
                rows = [
                    dict(row)
                    for row in connection.execute(
                        _LOOKUP,
                        {"model": self.embedding_model, "source_ids": list(source_ids)},
                    ).mappings()
                ]
        except SQLAlchemyError:
            raise WorkflowError("RAG_DATABASE_UNAVAILABLE", retryable=True, status=503) from None
        return _passages(rows)

    def _products(self, connection: Connection) -> list[_Product]:
        rows = connection.execute(_PRODUCTS, {"model": self.embedding_model}).all()
        return [_product(row.product_id, row.product_name) for row in rows]

    def _search(
        self, connection: Connection, vector: Sequence[float], named: Sequence[str]
    ) -> list[dict[str, Any]]:
        return [
            dict(row)
            for row in connection.execute(
                _SEARCH,
                {
                    "model": self.embedding_model,
                    "vector": vector_literal(vector),
                    "any_product": not named,
                    "products": list(named),
                    "limit": _CANDIDATE_LIMIT,
                },
            ).mappings()
        ]


@dataclass(frozen=True)
class SyncPlan:
    unchanged: tuple[str, ...]
    to_embed: tuple[str, ...]
    to_delete: tuple[str, ...]

    @property
    def is_noop(self) -> bool:
        return not self.to_embed and not self.to_delete


class ProductCatalogIndex:
    """Administrative writer for the catalog collection; not used by the Worker."""

    def __init__(self, engine: Engine, embedding_model: str) -> None:
        self.engine, self.embedding_model = engine, embedding_model

    def _stored(self, connection: Connection) -> dict[str, tuple[str, ...]]:
        rows = connection.execute(
            text(
                "SELECT chunk_id, content_sha256, source_id, document_version, provenance, "
                "product_name, section_name, embedding_model FROM rag_product_chunks"
            )
        ).all()
        return {row[0]: tuple(row[1:]) for row in rows}

    def _expected(self, chunk: ProductChunk) -> tuple[str, ...]:
        return (
            chunk.content_sha256,
            chunk.source_id,
            chunk.document_version,
            chunk.provenance,
            chunk.product_name,
            chunk.section_name,
            self.embedding_model,
        )

    def _plan(
        self, chunks: Sequence[ProductChunk], stored: Mapping[str, tuple[str, ...]]
    ) -> SyncPlan:
        wanted = {chunk.chunk_id for chunk in chunks}
        changed = [c.chunk_id for c in chunks if stored.get(c.chunk_id) != self._expected(c)]
        return SyncPlan(
            unchanged=tuple(sorted(wanted - set(changed))),
            to_embed=tuple(changed),
            to_delete=tuple(sorted(set(stored) - wanted)),
        )

    def plan(self, chunks: Sequence[ProductChunk]) -> SyncPlan:
        """Read-only comparison of the catalog with the database."""
        with self.engine.connect() as connection:
            return self._plan(chunks, self._stored(connection))

    def apply(
        self, chunks: Sequence[ProductChunk], embedder: EmbeddingProvider, timeout: float = 15.0
    ) -> SyncPlan:
        """Bring the collection to exactly ``chunks`` in one transaction.

        Unchanged chunks are neither re-embedded nor rewritten. A changed embedding model
        re-embeds everything, so one collection never mixes models or document versions.
        """
        plan = self.plan(chunks)
        if plan.is_noop:
            return plan
        by_id = {chunk.chunk_id: chunk for chunk in chunks}
        # Embeddings are network calls; compute them before the transaction opens.
        vectors = {
            chunk_id: embedder.embed_document(
                by_id[chunk_id].product_name, by_id[chunk_id].content, timeout
            )
            for chunk_id in plan.to_embed
        }
        with self.engine.begin() as connection:
            connection.execute(text("LOCK TABLE rag_product_chunks IN SHARE ROW EXCLUSIVE MODE"))
            if self._plan(chunks, self._stored(connection)) != plan:
                raise WorkflowError("RAG_SYNC_CONFLICT", retryable=True, status=503)
            if plan.to_delete:
                connection.execute(
                    text("DELETE FROM rag_product_chunks WHERE chunk_id = ANY(:chunk_ids)"),
                    {"chunk_ids": list(plan.to_delete)},
                )
            for chunk_id, vector in vectors.items():
                chunk = by_id[chunk_id]
                connection.execute(
                    _UPSERT,
                    {
                        "chunk_id": chunk.chunk_id,
                        "document_id": chunk.document_id,
                        "product_id": chunk.product_id,
                        "product_name": chunk.product_name,
                        "section_name": chunk.section_name,
                        "document_version": chunk.document_version,
                        "language": chunk.language,
                        "content": chunk.content,
                        "content_sha256": chunk.content_sha256,
                        "source_id": chunk.source_id,
                        "provenance": chunk.provenance,
                        "embedding_model": self.embedding_model,
                        "embedding": vector_literal(vector),
                    },
                )
        return plan
