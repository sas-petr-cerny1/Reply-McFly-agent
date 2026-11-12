from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

from reply_mcfly.adapters.markdown_rag_adapter import MarkdownRAGProvider
from reply_mcfly.application.email_processing_service import EmailProcessingService
from reply_mcfly.application.reply_service import FallbackTemplates, ReplyService
from reply_mcfly.domain.email import (
    Evidence,
    IncomingEmail,
    Job,
    MessageMetadata,
    ReplyDraft,
    Status,
)
from reply_mcfly.domain.grounding import LiteralReplyValidator, render_verified_reply


class InMemoryRepo:
    def __init__(self, job: Job) -> None:
        self.job = job
        self.stored_outbox = None

    def get(self, job_id):
        assert job_id == self.job.id
        return self.job

    def claim(self, job_id, token):
        return replace(self.job, status=Status.PROCESSING, lease_token=token)

    def outbox(self, job_id):
        return self.stored_outbox

    def transition(self, job, target, code=None):
        self.job = replace(job, status=target, last_error_code=code)

    def prepare(self, job, entry):
        self.stored_outbox = entry
        self.job = replace(job, status=Status.READY_TO_SEND)

    def release_lease(self, job):
        self.job = replace(job, lease_token=None)

    def sent(self, job, message_id):
        self.job = replace(job, status=Status.SENT)


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


class GmailStub:
    def __init__(self, email: IncomingEmail) -> None:
        self.email = email

    def message(self, message_id: str) -> IncomingEmail:
        return self.email


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
    repo = InMemoryRepo(job)
    runner = CapturingRunner()
    replies = ReplyService(
        frozenset({email.sender}), FallbackTemplates(), LiteralReplyValidator()
    )
    service = EmailProcessingService(
        repo,  # type: ignore[arg-type]
        GmailStub(email),  # type: ignore[arg-type]
        runner,  # type: ignore[arg-type]
        job.mailbox_id,
        replies,
        rag=MarkdownRAGProvider(),
        enable_rag=True,
    )
    assert service.process(job.id, send_enabled=False) == Status.READY_TO_SEND
    assert runner.last_email is not None
    assert runner.last_email.rag_passages[0].source_id.startswith("rag:KB01_")
