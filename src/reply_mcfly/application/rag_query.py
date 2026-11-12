"""Build a safe lexical retrieval query from trusted customer text and attachment facts."""

from __future__ import annotations

import re

from reply_mcfly.domain.email import IncomingEmail

_MAX_QUERY_CHARS = 12_000
_UNTRUSTED_LINE = re.compile(
    r"(?i)("
    r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions?"
    r"|system\s*:"
    r"|you\s+are\s+now"
    r"|knowledge\s*base"
    r"|přepsat|přepiš|nová\s+pravidla"
    r"|instrukce\s+pro\s+asistenta"
    r"|spoluúčast\s+je\s+0"
    r"|assistant\s+must"
    r")"
)


def _factual_attachment_lines(text: str) -> str:
    kept: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or _UNTRUSTED_LINE.search(stripped):
            continue
        kept.append(stripped)
    return "\n".join(kept)


def build_rag_retrieval_query(email: IncomingEmail) -> str:
    parts: list[str] = []
    if email.text.strip():
        parts.append(email.text.strip())
    for passage in email.attachment_passages:
        facts = _factual_attachment_lines(passage.text)
        if facts:
            parts.append(facts)
    if not parts:
        return ""
    combined = "\n".join(parts)
    return combined[:_MAX_QUERY_CHARS]
