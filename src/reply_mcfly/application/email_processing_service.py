import time
from datetime import UTC, datetime
from uuid import UUID, uuid4

from reply_mcfly.application.reply_service import ReplyService
from reply_mcfly.application.telemetry import emit
from reply_mcfly.domain.email import (
    TERMINAL,
    FallbackReason,
    Status,
    WorkflowError,
    require_mailbox,
)
from reply_mcfly.ports.email import EmailRepository, GmailPort, WorkflowRunner


class EmailProcessingService:
    def __init__(
        self,
        repository: EmailRepository,
        gmail: GmailPort,
        runner: WorkflowRunner,
        mailbox_id: str,
        replies: ReplyService,
    ) -> None:
        self.repository, self.gmail, self.runner = repository, gmail, runner
        self.mailbox_id, self.replies = mailbox_id, replies

    def process(self, job_id: UUID) -> Status:
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
                elif email.has_attachments and not email.unsupported_attachment:
                    raise WorkflowError("ATTACHMENT_PROCESSING_NOT_IMPLEMENTED")
                else:
                    remaining = deadline - time.monotonic() - 45
                    if remaining <= 0:
                        raise WorkflowError("DEPENDENCY_TIMEOUT", retryable=True, status=503)
                    draft = self.runner.run(email, min(30, remaining))
                    entry = self.replies.draft(job, email, draft)
            else:
                self.replies.validate_stored(job, email, entry)
            if time.monotonic() + 45 > deadline:
                raise WorkflowError("DEPENDENCY_TIMEOUT", retryable=True, status=503)
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
