import time
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from reply_mcfly.application.attachment_service import UnconfiguredAttachmentService
from reply_mcfly.application.rag_query import build_rag_retrieval_query
from reply_mcfly.application.reply_service import ReplyService
from reply_mcfly.application.telemetry import emit
from reply_mcfly.application.web_query import build_web_public_query, should_invoke_web_search
from reply_mcfly.domain.email import (
    TERMINAL,
    FallbackReason,
    IncomingEmail,
    OutboxEntry,
    RagPassage,
    Status,
    WebPassage,
    WorkflowError,
    require_mailbox,
    validate_untrusted_content,
)
from reply_mcfly.ports.capabilities import (
    RAGProvider,
    SourceLookup,
    SourcePassage,
    WebSearchProvider,
)
from reply_mcfly.ports.email import AttachmentEnricher, EmailRepository, GmailPort, WorkflowRunner


class EmailProcessingService:
    def __init__(
        self,
        repository: EmailRepository,
        gmail: GmailPort,
        runner: WorkflowRunner,
        mailbox_id: str,
        replies: ReplyService,
        attachments: AttachmentEnricher | None = None,
        *,
        rag: RAGProvider | None = None,
        enable_rag: bool = False,
        rag_query_builder: Callable[[IncomingEmail], str] = build_rag_retrieval_query,
        rag_timeout: float = 0.0,
        web: WebSearchProvider | None = None,
        enable_web_search: bool = False,
        web_query_builder: Callable[[IncomingEmail], str] = build_web_public_query,
        web_timeout: float = 0.0,
        sender_daily_reply_limit: int | None = None,
    ) -> None:
        self._rag_query_builder, self._rag_timeout = rag_query_builder, rag_timeout
        self._web_query_builder, self._web_timeout = web_query_builder, web_timeout
        self.sender_daily_reply_limit = sender_daily_reply_limit
        self.repository, self.gmail, self.runner = repository, gmail, runner
        self.mailbox_id, self.replies = mailbox_id, replies
        self.attachments = attachments or UnconfiguredAttachmentService()
        self._rag = rag if enable_rag else None
        self._web = web if enable_web_search else None

    def _apply_rag(
        self, email: IncomingEmail, job_id: UUID, deadline: float, entry: OutboxEntry | None = None
    ) -> IncomingEmail:
        if self._rag is None:
            return email
        passages: tuple[SourcePassage, ...]
        if entry is not None and isinstance(self._rag, SourceLookup):
            # A stored reply is checked against the exact passage versions it cites. A
            # document changed since then is not found, so validation sends it to review.
            passages = self._rag.lookup(
                tuple(source for source, _ in entry.evidence if source.startswith("rag:"))
            )
        else:
            # Leave room for generation and send; never start a call the deadline cannot fit.
            if self._rag_timeout and deadline - time.monotonic() - 45 < self._rag_timeout:
                raise WorkflowError("DEPENDENCY_TIMEOUT", retryable=True, status=503)
            passages = self._rag.retrieve(self._rag_query_builder(email))
        emit("rag_context_attached", job_id=str(job_id), rag_hit_count=len(passages))
        if not passages:
            return email
        for passage in passages:
            validate_untrusted_content(passage.text)
        return replace(
            email,
            rag_passages=tuple(
                RagPassage(item.source_id, item.text, item.provenance) for item in passages
            ),
        )

    def _apply_web(self, email: IncomingEmail, job_id: UUID, deadline: float) -> IncomingEmail:
        if self._web is None or not should_invoke_web_search(email):
            return email
        if self._web_timeout and deadline - time.monotonic() - 45 < self._web_timeout:
            raise WorkflowError("DEPENDENCY_TIMEOUT", retryable=True, status=503)
        public_query = self._web_query_builder(email)
        if not public_query:
            return email
        try:
            passages = self._web.search(public_query)
        except WorkflowError:
            raise
        except Exception:
            emit("web_search_failed", job_id=str(job_id))
            return email
        emit("web_context_attached", job_id=str(job_id), web_hit_count=len(passages))
        if not passages:
            return email
        for passage in passages:
            validate_untrusted_content(passage.text)
        return replace(
            email,
            web_passages=tuple(
                WebPassage(item.source_id, item.text, item.provenance) for item in passages
            ),
        )

    def _require_reply_budget(self, recipient: str) -> None:
        # Two auto-responders without auto-reply headers would otherwise answer each other forever.
        if self.sender_daily_reply_limit is None:
            return
        sent = self.repository.sent_reply_count(self.mailbox_id, recipient, timedelta(days=1))
        if sent >= self.sender_daily_reply_limit:
            raise WorkflowError("SENDER_REPLY_LIMIT_REACHED")

    def process(self, job_id: UUID, *, send_enabled: bool = True) -> Status:
        require_mailbox(self.repository.get(job_id).mailbox_id, self.mailbox_id)
        deadline = time.monotonic() + 100
        job = self.repository.claim(job_id, uuid4())
        if job.status in TERMINAL:
            return job.status
        emit("processing_started", job_id=str(job.id), status=job.status.value)
        entry = self.repository.outbox(job.id)
        if job.status == Status.DELIVERY_UNKNOWN:
            if entry is None:
                self.repository.transition(job, Status.REVIEW_REQUIRED, "OUTBOX_MISSING")
                return Status.REVIEW_REQUIRED
            try:
                sent_id = self.gmail.find_sent(job, entry)
            except WorkflowError as error:
                if error.retryable:
                    raise
                self.repository.transition(job, Status.REVIEW_REQUIRED, error.code)
                return Status.REVIEW_REQUIRED
            if sent_id:
                self.repository.sent(job, sent_id)
                return Status.SENT
            self.repository.transition(job, Status.REVIEW_REQUIRED, "DELIVERY_NOT_CONFIRMED")
            return Status.REVIEW_REQUIRED
        try:
            email = self.gmail.message(job.gmail_message_id)
            self.replies.validate_recipient(job, email)
            if entry is None:
                if email.unsupported_attachment and not email.text.strip():
                    entry = self.replies.fallback(job, email, FallbackReason.UNSUPPORTED_ATTACHMENT)
                else:
                    if email.has_attachments and not email.unsupported_attachment:
                        remaining = deadline - time.monotonic() - 55
                        if remaining <= 0:
                            raise WorkflowError("DEPENDENCY_TIMEOUT", retryable=True, status=503)
                        email = self.attachments.enrich(email, min(25, remaining))
                    email = self._apply_rag(email, job.id, deadline)
                    email = self._apply_web(email, job.id, deadline)
                    remaining = deadline - time.monotonic() - 45
                    if remaining <= 0:
                        raise WorkflowError("DEPENDENCY_TIMEOUT", retryable=True, status=503)
                    draft = self.runner.run(email, min(30, remaining))
                    entry = self.replies.draft(job, email, draft)
            else:
                if entry.attachment_passages:
                    # Reuse the extraction the stored evidence was verified against.
                    email = replace(email, attachment_passages=entry.attachment_passages)
                elif email.has_attachments and not email.unsupported_attachment:
                    # Outbox rows written before passages were persisted.
                    remaining = deadline - time.monotonic() - 55
                    if remaining > 0:
                        email = self.attachments.enrich(email, min(25, remaining))
                email = self._apply_rag(email, job.id, deadline, entry)
                email = self._apply_web(email, job.id, deadline)
                self.replies.validate_stored(job, email, entry)
            if not send_enabled:
                self.repository.prepare(job, entry)
                self.repository.release_lease(job)
                emit(
                    "live_email_dry_run_complete",
                    job_id=str(job.id),
                    status=Status.READY_TO_SEND.value,
                    gmail_thread_id=job.gmail_thread_id,
                    gmail_message_id=job.gmail_message_id,
                    mode="dry_run",
                    response_type=entry.response_type.value,
                    duration_seconds=(datetime.now(UTC) - job.received_at).total_seconds(),
                )
                return Status.READY_TO_SEND
            if time.monotonic() + 45 > deadline:
                raise WorkflowError("DEPENDENCY_TIMEOUT", retryable=True, status=503)
            self._require_reply_budget(entry.recipient)
            self.repository.prepare(job, entry)
            self.repository.transition(job, Status.SENDING)
            try:
                sent_id = self.gmail.send(job, entry)
            except WorkflowError:
                # Even a transport error can occur after Gmail accepted the message.
                self.repository.transition(job, Status.DELIVERY_UNKNOWN, "DELIVERY_UNKNOWN")
                return Status.DELIVERY_UNKNOWN
            self.repository.sent(job, sent_id)
            emit(
                "email_sent",
                job_id=str(job.id),
                status=Status.SENT.value,
                duration_seconds=(datetime.now(UTC) - job.received_at).total_seconds(),
            )
            return Status.SENT
        except WorkflowError as error:
            if error.code in {"LEASE_LOST", "INVALID_TRANSITION"}:
                raise
            target = Status.RETRY_PENDING if error.retryable else Status.REVIEW_REQUIRED
            self.repository.transition(job, target, error.code)
            if error.retryable:
                raise
            return target
