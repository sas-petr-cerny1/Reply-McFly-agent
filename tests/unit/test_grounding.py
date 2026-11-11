from datetime import UTC, datetime

import pytest

from reply_mcfly.domain.email import (
    Evidence,
    IncomingEmail,
    MessageMetadata,
    ReplyDraft,
    WorkflowError,
)
from reply_mcfly.domain.grounding import LiteralReplyValidator, render_verified_reply
from reply_mcfly.domain.reply_templates import (
    FALLBACK_MISSING_INFORMATION,
    FALLBACK_UNSUPPORTED_ATTACHMENT,
)


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


@pytest.mark.parametrize(
    "unsupported", ["Cena je 999 Kč.", "Doručení bude 12. prosince.", "https://invented.invalid"]
)
def test_new_claims_cannot_be_hidden_behind_valid_evidence(
    email: IncomingEmail, unsupported: str
) -> None:
    draft = verified_draft(email)
    draft.proposed_reply += "\n" + unsupported
    with pytest.raises(WorkflowError, match="UNSUPPORTED_REPLY_CLAIM"):
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


def test_citation_does_not_authorize_paraphrase(email: IncomingEmail) -> None:
    draft = verified_draft(email)
    draft.proposed_reply = "Potvrzujeme, že Vaše objednávka 123 je vyřízena."
    with pytest.raises(WorkflowError, match="UNSUPPORTED_REPLY_CLAIM"):
        LiteralReplyValidator().validate(email, draft)
