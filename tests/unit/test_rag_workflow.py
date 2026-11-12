from dataclasses import replace
from datetime import UTC, datetime
from unittest.mock import create_autospec
from uuid import uuid4

from reply_mcfly.adapters.markdown_rag_adapter import MarkdownRAGProvider
from reply_mcfly.application.email_processing_service import EmailProcessingService
from reply_mcfly.application.reply_service import FallbackTemplates, ReplyService
from reply_mcfly.domain.email import (
    Evidence,
    IncomingEmail,
    Job,
    MessageMetadata,
    OutboxEntry,
    ReplyDraft,
    Status,
)
from reply_mcfly.domain.grounding import LiteralReplyValidator, render_verified_reply
from reply_mcfly.ports.email import EmailRepository, GmailPort


class CapturingRunner:
    def __init__(self) -> None:
        self.last_email: IncomingEmail | None = None

    def run(self, email: IncomingEmail, timeout: float) -> ReplyDraft:
        self.last_email = email
        assert email.rag_passages, "RAG must be attached before Gemini call"
        sid = email.rag_passages[0].source_id
        quote = "- **Měsíční cena:** 179 Kč včetně DPH za jedno měsíční zúčtovací období."
        evidence = [Evidence(source_id=sid, exact_quote=quote)]
        return ReplyDraft(
            response_type="GENERATED",
            proposed_reply=render_verified_reply(evidence),
            evidence=evidence,
            missing_information=[],
            requires_review=False,
        )


def test_processing_attaches_rag_before_runner() -> None:
    email = IncomingEmail(
        MessageMetadata("m1", "t1", datetime.now(UTC), frozenset()),
        "sender@customer.invalid",
        "Dotaz",
        "<q@customer.invalid>",
        "",
        "Jaká je měsíční cena služby DemoBox+?",
    )
    job = Job(
        uuid4(),
        "agent@synthetic.invalid",
        email.metadata.message_id,
        email.metadata.thread_id,
        email.metadata.received_at,
        Status.QUEUED,
        None,
        None,
        0,
    )
    repo = create_autospec(EmailRepository, instance=True, spec_set=True)
    repo.get.return_value = job
    repo.claim.return_value = replace(job, status=Status.PROCESSING, lease_token=uuid4())
    repo.outbox.return_value = None
    gmail = create_autospec(GmailPort, instance=True, spec_set=True)
    gmail.message.return_value = email
    runner = CapturingRunner()
    replies = ReplyService(frozenset({email.sender}), FallbackTemplates(), LiteralReplyValidator())
    service = EmailProcessingService(
        repo,
        gmail,
        runner,
        job.mailbox_id,
        replies,
        rag=MarkdownRAGProvider(),
        enable_rag=True,
    )
    assert service.process(job.id, send_enabled=False) == Status.READY_TO_SEND
    assert runner.last_email is not None
    assert runner.last_email.rag_passages[0].source_id.startswith("rag:KB01_")

    repo.get.assert_called_once_with(job.id)
    repo.prepare.assert_called_once()
    entry = repo.prepare.call_args.args[1]
    assert isinstance(entry, OutboxEntry)
    assert "179 Kč" in entry.draft_body
    repo.release_lease.assert_called_once()
    gmail.send.assert_not_called()
