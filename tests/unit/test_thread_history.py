"""Conversation History: source provenance, isolation, and exact-quote grounding."""

from datetime import UTC, datetime

import pytest

from reply_mcfly.domain.email import (
    Evidence,
    IncomingEmail,
    MessageMetadata,
    ReplyDraft,
    ThreadHistoryPassage,
    WorkflowError,
)
from reply_mcfly.domain.grounding import LiteralReplyValidator, render_verified_reply


def make_email(history: tuple[ThreadHistoryPassage, ...] = ()) -> IncomingEmail:
    return IncomingEmail(
        metadata=MessageMetadata(
            "current", "thread-A", datetime.now(UTC), frozenset({"INBOX", "UNREAD"})
        ),
        sender="sender@example.invalid",
        subject="Follow-up",
        message_id_header="<current@example.invalid>",
        references="",
        text="Co jsem uvedl v předchozi zprave?",
        thread_history=history,
    )


def draft(source: str, quote: str) -> ReplyDraft:
    evidence = [Evidence(source_id=source, exact_quote=quote)]
    return ReplyDraft(
        response_type="GENERATED",
        proposed_reply=render_verified_reply(evidence),
        evidence=evidence,
        missing_information=[],
        requires_review=False,
    )


def test_previous_message_can_ground_follow_up() -> None:
    email = make_email(
        (
            ThreadHistoryPassage(
                "thread:previous",
                "sender@example.invalid",
                "Cislo pozadavku je 12345.",
            ),
        )
    )
    LiteralReplyValidator().validate(email, draft("thread:previous", "Cislo pozadavku je 12345."))


def test_unknown_cross_thread_source_rejected() -> None:
    email = make_email(
        (
            ThreadHistoryPassage(
                "thread:previous",
                "sender@example.invalid",
                "Cislo pozadavku je 12345.",
            ),
        )
    )
    with pytest.raises(WorkflowError, match="INVALID_EVIDENCE"):
        LiteralReplyValidator().validate(
            email, draft("thread:other-thread", "Cislo pozadavku je 12345.")
        )


def test_invented_history_quote_rejected() -> None:
    email = make_email(
        (
            ThreadHistoryPassage(
                "thread:previous",
                "sender@example.invalid",
                "Cislo pozadavku je 12345.",
            ),
        )
    )
    with pytest.raises(WorkflowError, match="INVALID_EVIDENCE"):
        LiteralReplyValidator().validate(
            email, draft("thread:previous", "Cislo pozadavku je 99999.")
        )


def test_history_source_is_absent_for_new_thread() -> None:
    with pytest.raises(WorkflowError, match="INVALID_EVIDENCE"):
        LiteralReplyValidator().validate(
            make_email(), draft("thread:previous", "Cislo pozadavku je 12345.")
        )
