"""Deterministic, offline chunking of the approved fictional product catalog.

The catalog is separate from ``knowledge_base`` (KB01-KB03). Nothing here computes
embeddings or touches a database; customer emails and thread history never enter it.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

CATALOG_DIRECTORY = Path(__file__).resolve().parents[1] / "product_catalog"
APPROVED_PRODUCT_IDS = frozenset({"MF-DOCK-08", "MF-AUDIO-02", "MF-SENSOR-03"})
EXPECTED_CHUNK_COUNT = 18
CATALOG_LANGUAGE = "cs"
_MAX_DOCUMENT_BYTES = 20_000
_MAX_CHUNK_CHARS = 2_500
_MIN_SECTIONS = 4
_DOCUMENT_NAME = re.compile(r"PX\d\d_[A-Za-z0-9_]+\.md")
_PRODUCT_ID = re.compile(r"^\*\*ID produktu:\*\*\s*(.+?)\s*$", re.MULTILINE)
_VERSION = re.compile(r"^\*\*Verze znalostí:\*\*\s*(.+?)\s*$", re.MULTILINE)
_SYNTHETIC_MARKER = re.compile(r"^\*\*Typ:\*\*\s*Fiktivní produkt\b", re.MULTILINE)


class CatalogError(ValueError):
    pass


@dataclass(frozen=True)
class ProductChunk:
    chunk_id: str
    document_id: str
    product_id: str
    product_name: str
    section_name: str
    document_version: str
    language: str
    content: str
    content_sha256: str
    source_id: str
    provenance: str


def slug(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text.casefold())
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", "-", normalized).strip("-")


def chunk_document(file_name: str, raw: str) -> tuple[ProductChunk, ...]:
    """Split one product document into one chunk per H2 section."""
    if not _DOCUMENT_NAME.fullmatch(file_name):
        raise CatalogError(f"CATALOG_DOCUMENT_NAME_INVALID: {file_name}")
    raw = raw.strip()
    if not raw or len(raw.encode("utf-8")) > _MAX_DOCUMENT_BYTES:
        raise CatalogError(f"CATALOG_DOCUMENT_SIZE_INVALID: {file_name}")
    first_line = raw.splitlines()[0]
    if not first_line.startswith("# ") or not first_line[2:].strip():
        raise CatalogError(f"CATALOG_TITLE_MISSING: {file_name}")
    title = first_line[2:].strip()
    product_id, version = _PRODUCT_ID.search(raw), _VERSION.search(raw)
    if product_id is None or version is None or _SYNTHETIC_MARKER.search(raw) is None:
        raise CatalogError(f"CATALOG_METADATA_MISSING: {file_name}")
    sections = re.split(r"(?m)^##\s+", raw)[1:]
    if len(sections) < _MIN_SECTIONS:
        raise CatalogError(f"CATALOG_SECTIONS_MISSING: {file_name}")
    document_id = file_name.removesuffix(".md")
    chunks: list[ProductChunk] = []
    for part in sections:
        heading, _, body = part.partition("\n")
        section, body = heading.strip(), body.strip()
        if not section or not body:
            raise CatalogError(f"CATALOG_SECTION_EMPTY: {file_name}")
        # Every chunk names its product, so a passage is never read out of context.
        content = f"# {title}\n**ID produktu:** {product_id.group(1)}\n## {section}\n{body}"
        if len(content) > _MAX_CHUNK_CHARS:
            raise CatalogError(f"CATALOG_SECTION_TOO_LONG: {file_name}")
        checksum = hashlib.sha256(content.encode("utf-8")).hexdigest()
        chunk_id = f"{product_id.group(1).casefold()}:{slug(section)}"
        chunks.append(
            ProductChunk(
                chunk_id=chunk_id,
                document_id=document_id,
                product_id=product_id.group(1),
                product_name=title,
                section_name=section,
                document_version=version.group(1),
                language=CATALOG_LANGUAGE,
                content=content,
                content_sha256=checksum,
                # The content hash makes a citation specific to one exact wording.
                source_id=f"rag:{chunk_id}:{checksum[:12]}",
                provenance=f"{file_name}#{slug(section)}@{version.group(1)}",
            )
        )
    return tuple(chunks)


def load_catalog(directory: Path | None = None) -> tuple[ProductChunk, ...]:
    """Read and validate the whole approved catalog: 3 documents, 18 chunks."""
    root = directory or CATALOG_DIRECTORY
    if not root.is_dir() or root.is_symlink():
        raise CatalogError("CATALOG_DIRECTORY_MISSING")
    paths = sorted(path for path in root.iterdir() if path.suffix.lower() == ".md")
    if len(paths) != len(APPROVED_PRODUCT_IDS):
        raise CatalogError("CATALOG_DOCUMENT_COUNT_INVALID")
    chunks: list[ProductChunk] = []
    for path in paths:
        if not path.is_file() or path.is_symlink():
            raise CatalogError(f"CATALOG_DOCUMENT_INVALID: {path.name}")
        try:
            raw = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            raise CatalogError(f"CATALOG_DOCUMENT_NOT_UTF8: {path.name}") from None
        chunks.extend(chunk_document(path.name, raw))
    if {chunk.product_id for chunk in chunks} != APPROVED_PRODUCT_IDS:
        raise CatalogError("CATALOG_PRODUCTS_NOT_APPROVED")
    if len({chunk.document_id for chunk in chunks}) != len({c.product_id for c in chunks}):
        raise CatalogError("CATALOG_PRODUCT_DUPLICATED")
    if len(chunks) != EXPECTED_CHUNK_COUNT:
        raise CatalogError("CATALOG_CHUNK_COUNT_INVALID")
    for name in ("chunk_id", "source_id"):
        if len({getattr(chunk, name) for chunk in chunks}) != len(chunks):
            raise CatalogError(f"CATALOG_DUPLICATE_{name.upper()}")
    return tuple(chunks)
