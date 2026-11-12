"""Tiny offline RAG provider for up to three operator-controlled Markdown/TXT documents.

No embeddings, vector database, external API, or customer data persistence.
Only relevant passages are offered as evidence to the downstream LLM.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from reply_mcfly.ports.capabilities import SourcePassage

_MAX_DOCUMENTS = 3
_MAX_BYTES_PER_DOCUMENT = 20_000
_STOP = frozenset(
    "a aby ale anebo bez byl byla bylo byly co do doba dalsi kdy kde ktera ktere ktereho "
    "ktery ma mam mas me mi mohu musi na nam ne nebo nej nejake o od po pod podle pokud "
    "popis prosim pri pro se si s jsem jsem jen je jeho jsou jak jaky jako tak ta tato ten "
    "to tomu u uz v ve vas vase vy z za ze zdar zda zasilka balik objednavka cislo "
    "potrebuji chci otazka dotaz dnes aktualni stav".split()
)
# Topic anchors reduce the risk of returning an unrelated policy on generic queries.
_TOPIC_PREFIXES = {
    "KB01": ("demobox", "pojist", "spoluuc", "kryt", "pojist", "polit", "aktivac"),
    "KB02": ("poskoz", "preprav", "doprav", "krabic", "trhlin", "obal", "protrz", "promack"),
    "KB03": ("chybej", "chyb", "kabel", "adapter", "prislusen", "soucast", "neupln", "nahradni"),
}


def _tokens(text: str) -> set[str]:
    clean = unicodedata.normalize("NFKD", text.casefold())
    clean = "".join(ch for ch in clean if not unicodedata.combining(ch))
    return {word for word in re.findall(r"[a-z0-9]+", clean) if len(word) > 2 and word not in _STOP}


def _related(token: str, prefix: str) -> bool:
    return token.startswith(prefix) or (len(token) >= 5 and prefix.startswith(token))


@dataclass(frozen=True)
class _Document:
    source: SourcePassage
    tokens: frozenset[str]
    topic: str


class MarkdownRAGProvider:
    """Read-only lexical retrieval for 1-3 small, fictional knowledge documents.

    The caller must decide whether RAG is needed and must validate generated quotes
    against the returned SourcePassages (never against arbitrary model-provided IDs).
    """

    def __init__(self, directory: Path | None = None, *, max_results: int = 2) -> None:
        if max_results < 1 or max_results > _MAX_DOCUMENTS:
            raise ValueError("RAG_MAX_RESULTS_INVALID")
        root = directory or (Path(__file__).resolve().parents[1] / "knowledge_base")
        if not root.is_dir() or root.is_symlink():
            raise ValueError("RAG_KNOWLEDGE_BASE_MISSING")
        paths = sorted(p for p in root.iterdir() if p.suffix.lower() in {".md", ".txt"})
        if not 1 <= len(paths) <= _MAX_DOCUMENTS:
            raise ValueError("RAG_DOCUMENT_COUNT_INVALID")
        docs: list[_Document] = []
        for path in paths:
            if not path.is_file() or path.is_symlink():
                raise ValueError("RAG_DOCUMENT_INVALID")
            size = path.stat().st_size
            if size < 1 or size > _MAX_BYTES_PER_DOCUMENT:
                raise ValueError("RAG_DOCUMENT_SIZE_INVALID")
            content = path.read_text(encoding="utf-8").strip()
            if not content:
                raise ValueError("RAG_DOCUMENT_EMPTY")
            version = hashlib.sha256(content.encode("utf-8")).hexdigest()[:12]
            source = SourcePassage(
                source_id=f"rag:{path.stem}:{version}",
                source_type="RAG",
                text=content,
                provenance=path.name,
            )
            topic = path.stem.split("_", 1)[0]
            docs.append(_Document(source, frozenset(_tokens(content)), topic))
        self._documents = tuple(docs)
        self._max_results = max_results

    def retrieve(self, query: str) -> tuple[SourcePassage, ...]:
        terms = _tokens(query[:12_000])
        if not terms:
            return ()
        scored: list[tuple[float, _Document]] = []
        for document in self._documents:
            anchors = _TOPIC_PREFIXES.get(document.topic, ())
            anchor_hits = sum(any(_related(t, prefix) for prefix in anchors) for t in terms)
            if anchor_hits == 0:
                continue
            overlap = sum(
                any(_related(t, dt) or _related(dt, t) for dt in document.tokens) for t in terms
            )
            # Anchor matches identify the subject. Overlap breaks ties.
            score = anchor_hits * 10 + overlap / max(len(terms), 1)
            scored.append((score, document))
        scored.sort(key=lambda item: (-item[0], item[1].source.source_id))
        return tuple(item.source for _, item in scored[: self._max_results])
