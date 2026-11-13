from datetime import UTC, datetime

import pytest

from reply_mcfly.domain.email import (
    Evidence,
    IncomingEmail,
    MessageMetadata,
    RagPassage,
    ReplyDraft,
    WorkflowError,
)
from reply_mcfly.domain.grounding import LiteralReplyValidator

RAG_ID = "rag:KB01:abc"
RAG_TEXT = "- **Vrácení:** Zboží nelze vrátit po 30 dnech.\n- Kód A-17 platí; kód 17 neplatí."


def _email() -> IncomingEmail:
    return IncomingEmail(
        MessageMetadata("a1", "b1", datetime.now(UTC), frozenset({"INBOX", "UNREAD"})),
        "sender@customer.invalid",
        "Synthetic test",
        "<original@customer.invalid>",
        "",
        "Lze zboží vrátit?",
        rag_passages=(RagPassage(RAG_ID, RAG_TEXT, "KB01.md"),),
    )


def _draft(quote: str) -> ReplyDraft:
    return ReplyDraft(
        response_type="GENERATED",
        proposed_reply="",
        evidence=[Evidence(source_id=RAG_ID, exact_quote=quote)],
        missing_information=[],
        requires_review=False,
    )


@pytest.mark.parametrize(
    "quote",
    [
        "lze vrátit",  # drops the negation of "nelze"
        "Zboží nelze vrátit po 3",  # truncates the number of days
        "boží nelze vrátit",
    ],
)
def test_quote_cut_inside_a_word_is_rejected(quote: str) -> None:
    assert quote in RAG_TEXT
    with pytest.raises(WorkflowError, match="INVALID_EVIDENCE"):
        LiteralReplyValidator().validate(_email(), _draft(quote))


@pytest.mark.parametrize(
    "quote",
    [
        RAG_TEXT,
        "- **Vrácení:** Zboží nelze vrátit po 30 dnech.",
        "Zboží nelze vrátit po 30 dnech",
        "**Vrácení:**",
        "kód 17 neplatí",
    ],
)
def test_quote_of_whole_words_is_accepted(quote: str) -> None:
    LiteralReplyValidator().validate(_email(), _draft(quote))
