from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable


@dataclass(frozen=True)
class SourcePassage:
    source_id: str
    source_type: Literal["EMAIL", "THREAD", "RAG", "WEB"]
    text: str
    provenance: str


class ThreadContextProvider(Protocol):
    def get_context(self, gmail_thread_id: str) -> tuple[SourcePassage, ...]: ...


class RAGProvider(Protocol):
    def retrieve(self, query: str) -> tuple[SourcePassage, ...]: ...


@runtime_checkable
class SourceLookup(Protocol):
    """Re-reads exact passage versions that an already stored reply cites."""

    def lookup(self, source_ids: tuple[str, ...]) -> tuple[SourcePassage, ...]: ...


class EmbeddingProvider(Protocol):
    def embed_query(self, text: str, timeout: float) -> tuple[float, ...]: ...
    def embed_document(self, title: str, text: str, timeout: float) -> tuple[float, ...]: ...


class WebSearchProvider(Protocol):
    def search(self, public_query: str) -> tuple[SourcePassage, ...]: ...
