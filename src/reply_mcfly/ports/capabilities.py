from dataclasses import dataclass
from typing import Literal, Protocol


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


class WebSearchProvider(Protocol):
    def search(self, public_query: str) -> tuple[SourcePassage, ...]: ...
