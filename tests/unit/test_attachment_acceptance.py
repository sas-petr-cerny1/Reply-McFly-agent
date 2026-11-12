from datetime import UTC, datetime
from uuid import uuid4

import pytest

from reply_mcfly.application.reply_service import FallbackTemplates, ReplyService
from reply_mcfly.domain.email import (
    AttachmentPassage,
    Evidence,
    IncomingEmail,
    Job,
    MessageMetadata,
    ReplyDraft,
    Status,
)
from reply_mcfly.domain.grounding import LiteralReplyValidator, render_verified_reply


def email_with_attachment(quote: str) -> IncomingEmail:
    return IncomingEmail(
        MessageMetadata("a1", "b1", datetime.now(UTC), frozenset()),
        "sender@customer.invalid",
        "Dotaz",
        "<q@customer.invalid>",
        "",
        "Viz přílohu.",
        has_attachments=True,
        attachment_passages=(AttachmentPassage("attachment:0", quote),),
    )


@pytest.mark.parametrize(
    ("quote", "required"),
    [
        ("DEMO-84721", ("DEMO-84721",)),
        ("DEMO-65432 a popis poškození displeje.", ("DEMO-65432", "poškození")),
        ("Záznam 752184: chybí napájecí kabel.", ("752184", "napájecí kabel")),
    ],
)
def test_reply_grounding_requires_attachment_quotes(quote: str, required: tuple[str, ...]) -> None:
    incoming = email_with_attachment(quote)
    evidence = [Evidence(source_id="attachment:0", exact_quote=quote)]
    draft = ReplyDraft(
        response_type="GENERATED",
        proposed_reply=render_verified_reply(evidence),
        evidence=evidence,
        missing_information=[],
        requires_review=False,
    )
    LiteralReplyValidator().validate(incoming, draft)
    job = Job(
        uuid4(),
        "reply@agent.invalid",
        incoming.metadata.message_id,
        incoming.metadata.thread_id,
        incoming.metadata.received_at,
        Status.PROCESSING,
        None,
        None,
        0,
    )
    entry = ReplyService(
        frozenset({incoming.sender}), FallbackTemplates(), LiteralReplyValidator()
    ).draft(job, incoming, draft)
    for fragment in required:
        assert fragment in entry.draft_body
    assert "z ověřeného obsahu přílohy plyne:" in entry.draft_body


def test_image_damage_quote_uses_attachment_intro() -> None:
    order = "DEMO-65432"
    damage = "Pravý roh displeje je roztržený."
    passage = f"{order}\n{damage}"
    incoming = email_with_attachment(passage)
    evidence = [
        Evidence(source_id="attachment:0", exact_quote=order),
        Evidence(source_id="attachment:0", exact_quote=damage),
    ]
    draft = ReplyDraft(
        response_type="GENERATED",
        proposed_reply=render_verified_reply(evidence),
        evidence=evidence,
        missing_information=[],
        requires_review=False,
    )
    LiteralReplyValidator().validate(incoming, draft)
    body = render_verified_reply(evidence)
    assert "z ověřeného obsahu přílohy plyne:" in body
    assert order in body
    assert damage in body
