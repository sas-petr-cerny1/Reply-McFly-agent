from __future__ import annotations

import time
from dataclasses import dataclass
from uuid import UUID

from reply_mcfly.application.email_processing_service import EmailProcessingService
from reply_mcfly.application.telemetry import emit
from reply_mcfly.domain.email import Status, WorkflowError, incoming
from reply_mcfly.domain.sender_policy import SenderConfigurationError, SenderPolicy, parse_sender_policy
from reply_mcfly.ports.email import EmailRepository, GmailPort


@dataclass(frozen=True)
class LiveEmailRunResult:
    job_id: UUID
    gmail_message_id: str
    gmail_thread_id: str
    status: Status
    send_enabled: bool
    duration_seconds: float


class LiveEmailRunner:
    def __init__(
        self,
        repository: EmailRepository,
        gmail: GmailPort,
        processing: EmailProcessingService,
        mailbox_id: str,
    ) -> None:
        self.repository = repository
        self.gmail = gmail
        self.processing = processing
        self.mailbox_id = mailbox_id.casefold()

    def run(self, message_id: str, *, send_enabled: bool = False) -> LiveEmailRunResult:
        message_id = message_id.strip()
        if not message_id or len(message_id) > 255:
            raise WorkflowError("INVALID_MESSAGE_ID")
        self.repository.initialize(self.mailbox_id, "0", None)
        emit(
            "live_email_run_started",
            gmail_message_id=message_id,
            mode="send" if send_enabled else "dry_run",
        )
        started = time.monotonic()
        metadata = self.gmail.metadata(message_id)
        if metadata.message_id != message_id:
            raise WorkflowError("GMAIL_MESSAGE_MISMATCH")
        if not incoming(metadata):
            raise WorkflowError("MESSAGE_NOT_INCOMING")
        emit(
            "live_email_message_selected",
            gmail_message_id=message_id,
            gmail_thread_id=metadata.thread_id,
            mode="send" if send_enabled else "dry_run",
        )
        job_id = self.repository.enqueue(self.mailbox_id, metadata)
        status = self.processing.process(job_id, send_enabled=send_enabled)
        duration = time.monotonic() - started
        outbox = self.repository.outbox(job_id)
        emit(
            "live_email_run_complete",
            job_id=str(job_id),
            status=status.value,
            gmail_message_id=message_id,
            gmail_thread_id=metadata.thread_id,
            mode="send" if send_enabled else "dry_run",
            response_type=outbox.response_type.value if outbox else None,
            duration_seconds=round(duration, 3),
        )
        return LiveEmailRunResult(
            job_id,
            message_id,
            metadata.thread_id,
            status,
            send_enabled,
            duration,
        )


def validate_live_email_settings(
    mailbox_id: str, allowed_senders: frozenset[str]
) -> SenderPolicy:
    if not mailbox_id or "@" not in mailbox_id:
        raise RuntimeError("Set MCFLY_MAILBOX_ID to the dedicated Gmail mailbox address")
    if not allowed_senders:
        raise RuntimeError("Set MCFLY_ALLOWED_SENDERS to an explicit sender allowlist")
    try:
        return parse_sender_policy(allowed_senders, mailbox_id)
    except SenderConfigurationError as error:
        raise RuntimeError("Invalid MCFLY_ALLOWED_SENDERS configuration for live email runs") from error
