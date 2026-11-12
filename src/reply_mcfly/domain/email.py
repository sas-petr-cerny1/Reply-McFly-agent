import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from reply_mcfly.domain.sender_policy import SenderPolicy


class WorkflowError(Exception):
    def __init__(self, code: str, *, retryable: bool = False, status: int = 400) -> None:
        super().__init__(code)
        self.code = code
        self.retryable = retryable
        self.status = status


class Status(StrEnum):
    RECEIVED = "RECEIVED"
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    READY_TO_SEND = "READY_TO_SEND"
    SENDING = "SENDING"
    SENT = "SENT"
    RETRY_PENDING = "RETRY_PENDING"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    FAILED = "FAILED"
    DELIVERY_UNKNOWN = "DELIVERY_UNKNOWN"


TERMINAL = {Status.SENT, Status.REVIEW_REQUIRED, Status.FAILED}
TRANSITIONS = {
    Status.PROCESSING: {
        Status.READY_TO_SEND,
        Status.RETRY_PENDING,
        Status.REVIEW_REQUIRED,
        Status.FAILED,
    },
    Status.READY_TO_SEND: {Status.SENDING, Status.REVIEW_REQUIRED},
    Status.SENDING: {Status.SENT, Status.DELIVERY_UNKNOWN},
    Status.DELIVERY_UNKNOWN: {Status.SENT, Status.REVIEW_REQUIRED},
}


@dataclass(frozen=True)
class MessageMetadata:
    message_id: str
    thread_id: str
    received_at: datetime
    labels: frozenset[str]


@dataclass(frozen=True)
class ThreadHistoryPassage:
    source_id: str
    sender: str
    text: str


@dataclass(frozen=True)
class EmailAttachment:
    source_id: str
    filename: str
    declared_mime: str
    data: bytes


@dataclass(frozen=True)
class AttachmentPassage:
    source_id: str
    text: str


@dataclass(frozen=True)
class RagPassage:
    source_id: str
    text: str
    provenance: str


@dataclass(frozen=True)
class IncomingEmail:
    metadata: MessageMetadata
    sender: str
    subject: str
    message_id_header: str
    references: str
    text: str
    automatic: bool = False
    has_attachments: bool = False
    unsupported_attachment: bool = False
    attachments: tuple[EmailAttachment, ...] = ()
    attachment_passages: tuple[AttachmentPassage, ...] = ()
    thread_history: tuple[ThreadHistoryPassage, ...] = ()
    rag_passages: tuple[RagPassage, ...] = ()


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    source_id: str = Field(min_length=1, max_length=512)
    exact_quote: str = Field(min_length=1, max_length=5000)


class ReplyDraft(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    response_type: Literal["GENERATED", "FALLBACK"]
    proposed_reply: str = Field(max_length=10000)
    evidence: list[Evidence] = Field(max_length=8)
    missing_information: list[str] = Field(max_length=10)
    requires_review: bool


class ResponseType(StrEnum):
    GENERATED = "GENERATED"
    FALLBACK = "FALLBACK"


class FallbackReason(StrEnum):
    INSUFFICIENT_INFORMATION = "INSUFFICIENT_INFORMATION"
    UNSUPPORTED_ATTACHMENT = "UNSUPPORTED_ATTACHMENT"


@dataclass(frozen=True)
class Job:
    id: UUID
    mailbox_id: str
    gmail_message_id: str
    gmail_thread_id: str
    received_at: datetime
    status: Status
    lease_token: UUID | None
    lease_until: datetime | None
    attempt_count: int


@dataclass(frozen=True)
class OutboxEntry:
    job_id: UUID
    outbound_message_id: str
    recipient: str
    subject: str
    draft_body: str
    in_reply_to: str
    references: str
    response_type: ResponseType = ResponseType.GENERATED
    fallback_reason: FallbackReason | None = None
    evidence: tuple[tuple[str, str], ...] = ()


def require_mailbox(actual: str, allowed: str) -> None:
    if actual.casefold() != allowed.casefold():
        raise WorkflowError("FORBIDDEN", status=403)


def incoming(metadata: MessageMetadata) -> bool:
    return {"INBOX", "UNREAD"} <= metadata.labels and not (
        {"SENT", "DRAFT", "SPAM", "TRASH"} & metadata.labels
    )


def validate_recipient(job: Job, email: IncomingEmail, policy: SenderPolicy) -> None:
    if (
        email.metadata.message_id != job.gmail_message_id
        or email.metadata.thread_id != job.gmail_thread_id
    ):
        raise WorkflowError("MESSAGE_THREAD_MISMATCH")
    if (
        email.automatic
        or email.sender.casefold() == job.mailbox_id.casefold()
        or not policy.permits_sender(email.sender)
    ):
        raise WorkflowError("RECIPIENT_REQUIRES_REVIEW")
    for value in (email.sender, email.subject, email.message_id_header, email.references):
        if "\r" in value or "\n" in value or len(value) > 998:
            raise WorkflowError("INVALID_REPLY_HEADERS")
    if not re.fullmatch(r"<[^<>\s]+@[^<>\s]+>", email.message_id_header):
        raise WorkflowError("INVALID_MESSAGE_ID")
    validate_untrusted_content(email.text)


def validate_untrusted_content(text: str) -> None:
    # Additional review triggers, not a general prompt-injection classifier.
    if re.search(
        r"ignore\s+(?:(?:all\s+)?(?:previous|prior)\s+|all\s+)?instructions|"
        r"ignoruj.{0,40}(?:instrukce|pravidla)|system\s+prompt|"
        r"(?:api[_ -]?key|access[_ -]?token|refresh[_ -]?token|password|heslo)\s*[:=]|"
        r"-----BEGIN.{0,30}PRIVATE KEY|\bya29\.",
        text,
        re.IGNORECASE,
    ):
        raise WorkflowError("UNTRUSTED_CONTENT_REQUIRES_REVIEW")


def prepare_reply(
    job: Job,
    email: IncomingEmail,
    body: str,
    policy: SenderPolicy,
    response_type: ResponseType = ResponseType.GENERATED,
    fallback_reason: FallbackReason | None = None,
    evidence: tuple[tuple[str, str], ...] = (),
) -> OutboxEntry:
    validate_recipient(job, email, policy)
    if (
        not body.strip()
        or len(body) > 10000
        or any(ord(c) < 32 and c not in "\n\t\r" for c in body)
    ):
        raise WorkflowError("REPLY_REQUIRES_REVIEW")
    if (response_type == ResponseType.FALLBACK) != (fallback_reason is not None):
        raise WorkflowError("INVALID_RESPONSE_TYPE")
    if email.has_attachments and not email.unsupported_attachment and not email.attachment_passages:
        raise WorkflowError("ATTACHMENT_REQUIRES_REVIEW")
    return OutboxEntry(
        job_id=job.id,
        outbound_message_id=f"<reply-mcfly-{job.id}@{job.mailbox_id.split('@')[-1]}>",
        recipient=email.sender,
        subject=email.subject,
        draft_body=body,
        in_reply_to=email.message_id_header,
        references=" ".join((email.references + " " + email.message_id_header).split()),
        response_type=response_type,
        fallback_reason=fallback_reason,
        evidence=evidence,
    )
