"""Administrative CLI for the product knowledge collection.

    python -m reply_mcfly.rag validate            offline catalog check, no network
    python -m reply_mcfly.rag sync                dry run: what would change (reads the DB)
    python -m reply_mcfly.rag sync --apply        embed changed chunks and write them
    python -m reply_mcfly.rag search --query "…"  one retrieval through the Worker's provider

Only ``sync --apply`` writes, and only ``sync --apply`` and ``search`` call Vertex AI.
Output lists document and chunk identifiers and timings; never credentials.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from reply_mcfly.adapters.pgvector_rag_adapter import (
    PgVectorRAGProvider,
    ProductCatalogIndex,
    SyncPlan,
)
from reply_mcfly.adapters.postgres_adapter import make_engine
from reply_mcfly.adapters.rag_factory import build_embedder
from reply_mcfly.application.product_catalog import CatalogError, ProductChunk, load_catalog
from reply_mcfly.config.settings import Settings
from reply_mcfly.domain.email import WorkflowError


def _catalog_summary(chunks: tuple[ProductChunk, ...]) -> dict[str, object]:
    per_document = Counter(chunk.document_id for chunk in chunks)
    return {
        "documents": [
            {
                "document_id": document_id,
                "product_id": next(c.product_id for c in chunks if c.document_id == document_id),
                "document_version": next(
                    c.document_version for c in chunks if c.document_id == document_id
                ),
                "chunks": count,
            }
            for document_id, count in sorted(per_document.items())
        ],
        "chunk_count": len(chunks),
    }


def _plan_summary(plan: SyncPlan) -> dict[str, object]:
    return {
        "unchanged": len(plan.unchanged),
        "to_embed": list(plan.to_embed),
        "to_delete": list(plan.to_delete),
    }


def _print(payload: dict[str, object]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m reply_mcfly.rag", description=__doc__)
    parser.add_argument("--catalog", type=Path, default=None, help="Catalog directory override")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("validate", help="Validate the catalog offline")
    sync = commands.add_parser("sync", help="Compare the catalog with the database")
    sync.add_argument(
        "--apply",
        action="store_true",
        help="Call Vertex AI for changed chunks and write them (default is a dry run)",
    )
    sync.add_argument("--dry-run", action="store_true", help="Explicit dry run (the default)")
    search = commands.add_parser("search", help="Retrieve passages for one product question")
    search.add_argument("--query", required=True, help="Synthetic or public product question")
    args = parser.parse_args(argv)
    if args.command == "sync" and args.apply and args.dry_run:
        parser.error("--apply and --dry-run are mutually exclusive")
    try:
        chunks = load_catalog(args.catalog)
        if args.command == "validate":
            _print({"status": "valid", **_catalog_summary(chunks)})
            return 0
        settings = Settings()
        engine = make_engine(settings.sqlalchemy_url())
        try:
            with engine.connect() as connection:
                revision = connection.execute(
                    text("SELECT version_num FROM alembic_version")
                ).scalar_one()
            started = time.monotonic()
            if args.command == "sync":
                index = ProductCatalogIndex(engine, settings.rag_embedding_model)
                if args.apply:
                    plan = index.apply(chunks, build_embedder(settings))
                    mode = "applied"
                else:
                    plan = index.plan(chunks)
                    mode = "dry_run"
                _print(
                    {
                        "mode": mode,
                        "migration": revision,
                        "embedding_model": settings.rag_embedding_model,
                        **_catalog_summary(chunks),
                        **_plan_summary(plan),
                        "duration_ms": int((time.monotonic() - started) * 1000),
                    }
                )
                return 0
            provider = PgVectorRAGProvider(
                engine,
                build_embedder(settings),
                embedding_model=settings.rag_embedding_model,
                top_k=settings.rag_top_k,
                timeout=settings.rag_timeout_seconds,
            )
            passages = provider.retrieve(args.query)
            _print(
                {
                    "migration": revision,
                    "embedding_model": settings.rag_embedding_model,
                    "hit_count": len(passages),
                    "duration_ms": int((time.monotonic() - started) * 1000),
                    "passages": [
                        {
                            "rank": rank,
                            "source_id": passage.source_id,
                            "provenance": passage.provenance,
                            "text": passage.text,
                        }
                        for rank, passage in enumerate(passages, start=1)
                    ],
                }
            )
            return 0
        finally:
            engine.dispose()
    except CatalogError as error:
        print(json.dumps({"error": str(error)}), file=sys.stderr)
        return 2
    except WorkflowError as error:
        print(json.dumps({"error": error.code, "retryable": error.retryable}), file=sys.stderr)
        return 1
    except SQLAlchemyError:
        print(json.dumps({"error": "DATABASE_UNAVAILABLE"}), file=sys.stderr)
        return 1
    except ValueError as error:
        print(json.dumps({"error": str(error)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
