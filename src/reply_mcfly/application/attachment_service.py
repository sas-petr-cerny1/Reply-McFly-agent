from __future__ import annotations

from dataclasses import replace
from typing import Protocol

from reply_mcfly.application.attachment_processor import ValidatedAttachment, validate_attachments
from reply_mcfly.application.telemetry import emit
from reply_mcfly.domain.email import AttachmentPassage, IncomingEmail, WorkflowError


class AttachmentExtractor(Protocol):
    def extract(
        self,
        email: IncomingEmail,
        attachments: tuple[ValidatedAttachment, ...],
        timeout: float,
    ) -> tuple[AttachmentPassage, ...]: ...


class AttachmentService:
    def __init__(self, extractor: AttachmentExtractor) -> None:
        self.extractor = extractor

    def enrich(self, email: IncomingEmail, timeout: float) -> IncomingEmail:
        if not email.has_attachments or email.unsupported_attachment:
            return email
        if not email.attachments:
            raise WorkflowError("ATTACHMENT_INVALID")
        validated = validate_attachments(email.attachments)
        emit(
            "attachment_validation_completed",
            gmail_message_id=email.metadata.message_id,
            status=str(len(validated)),
        )
        passages = self.extractor.extract(email, validated, timeout)
        if not passages:
            raise WorkflowError("ATTACHMENT_REQUIRES_REVIEW")
        return replace(email, attachment_passages=passages)


class UnconfiguredAttachmentService:
    """Preserves explicit failure until attachment extraction is wired."""

    def enrich(self, email: IncomingEmail, timeout: float) -> IncomingEmail:
        if email.has_attachments and not email.unsupported_attachment:
            raise WorkflowError("ATTACHMENT_PROCESSING_NOT_IMPLEMENTED")
        return email
