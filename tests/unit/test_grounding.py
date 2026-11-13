from datetime import UTC, datetime
from uuid import uuid4

import pytest

from reply_mcfly.application.reply_service import FallbackTemplates, ReplyService
from reply_mcfly.domain.email import (
    Evidence,
    IncomingEmail,
    Job,
    MessageMetadata,
    ReplyDraft,
    Status,
    WorkflowError,
)
from reply_mcfly.domain.grounding import LiteralReplyValidator, render_verified_reply
from reply_mcfly.domain.reply_templates import (
    FALLBACK_MISSING_INFORMATION,
    FALLBACK_UNSUPPORTED_ATTACHMENT,
)
from reply_mcfly.domain.sender_policy import parse_sender_policy


def test_approved_missing_information_template_is_exact() -> None:
    assert FALLBACK_MISSING_INFORMATION == "\n\n".join(
        [
            "Dobrý den,",
            "děkujeme za Vaši zprávu.",
            "Na základě dostupných informací zatím nemůžeme připravit "
            "spolehlivou odpověď na Váš dotaz.",
            "Prosíme o doplnění potřebných informací nebo upřesnění Vašeho požadavku.",
            "Jakmile informace doplníte, budeme moci na Váš dotaz lépe odpovědět.",
            "S pozdravem\nReply McFly – AI Email Assistant",
        ]
    )


def test_approved_attachment_template_is_exact() -> None:
    assert FALLBACK_UNSUPPORTED_ATTACHMENT == "\n\n".join(
        [
            "Dobrý den,",
            "děkujeme za Vaši zprávu.",
            "Bohužel se nám nepodařilo zpracovat jednu nebo více přiložených příloh.",
            "Podporované formáty jsou PDF, MP3, WAV, JPEG a PNG.",
            "Prosíme o opětovné zaslání přílohy v některém z podporovaných formátů a v rámci "
            "povolených velikostních limitů.",
            "S pozdravem\nReply McFly – AI Email Assistant",
        ]
    )


@pytest.fixture
def email() -> IncomingEmail:
    return IncomingEmail(
        MessageMetadata("a1", "b1", datetime.now(UTC), frozenset({"INBOX", "UNREAD"})),
        "sender@customer.invalid",
        "Test",
        "<test@customer.invalid>",
        "",
        "Můj požadavek má číslo 123. Prosím o potvrzení přijetí.",
    )


def verified_draft(email: IncomingEmail) -> ReplyDraft:
    evidence = [Evidence(source_id="email:a1", exact_quote="Můj požadavek má číslo 123.")]
    return ReplyDraft(
        response_type="GENERATED",
        proposed_reply=render_verified_reply(evidence),
        evidence=evidence,
        missing_information=[],
        requires_review=False,
    )


def test_literal_sender_attribution_passes(email: IncomingEmail) -> None:
    LiteralReplyValidator().validate(email, verified_draft(email))


def test_extra_model_text_in_proposed_reply_is_ignored_at_validation(email: IncomingEmail) -> None:
    draft = verified_draft(email)
    draft.proposed_reply += "\nCena je 999 Kč."
    LiteralReplyValidator().validate(email, draft)


def test_nonexistent_source_and_fabricated_quote_are_rejected(email: IncomingEmail) -> None:
    draft = verified_draft(email)
    draft.evidence[0].source_id = "rag:unknown"
    with pytest.raises(WorkflowError, match="INVALID_EVIDENCE"):
        LiteralReplyValidator().validate(email, draft)
    draft = verified_draft(email)
    draft.evidence[0].exact_quote = "Cena je 999 Kč."
    draft.proposed_reply = render_verified_reply(draft.evidence)
    with pytest.raises(WorkflowError, match="INVALID_EVIDENCE"):
        LiteralReplyValidator().validate(email, draft)


def test_paraphrase_in_proposed_reply_does_not_block_evidence_validation(
    email: IncomingEmail,
) -> None:
    draft = verified_draft(email)
    draft.proposed_reply = "Potvrzujeme, že Vaše objednávka 123 je vyřízena."
    LiteralReplyValidator().validate(email, draft)


def test_reply_service_ignores_model_proposed_reply_body(email: IncomingEmail) -> None:
    job = Job(
        uuid4(),
        "reply@agent.invalid",
        email.metadata.message_id,
        email.metadata.thread_id,
        email.metadata.received_at,
        Status.PROCESSING,
        None,
        None,
        0,
    )
    draft = verified_draft(email)
    draft.proposed_reply = "Model-only text that must not be sent."
    service = ReplyService(
        parse_sender_policy(frozenset({email.sender}), "reply@agent.invalid"),
        FallbackTemplates(),
        LiteralReplyValidator(),
    )
    entry = service.draft(job, email, draft)
    assert entry.draft_body == render_verified_reply(draft.evidence)
