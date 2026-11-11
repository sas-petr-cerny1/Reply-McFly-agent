from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


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


class ReplyDraft(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    proposed_reply: str = Field(max_length=10000)
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


def require_mailbox(actual: str, allowed: str) -> None:
    if actual.casefold() != allowed.casefold():
        raise WorkflowError("FORBIDDEN", status=403)


def incoming(metadata: MessageMetadata) -> bool:
    return {"INBOX", "UNREAD"} <= metadata.labels and not (
        {"SENT", "DRAFT", "SPAM", "TRASH"} & metadata.labels
    )
