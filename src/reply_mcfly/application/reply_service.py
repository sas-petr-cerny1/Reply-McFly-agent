from dataclasses import dataclass
from typing import Protocol

from reply_mcfly.domain.email import (
    Evidence,
    FallbackReason,
    IncomingEmail,
    Job,
    OutboxEntry,
    ReplyDraft,
    ResponseType,
    WorkflowError,
    prepare_reply,
    validate_recipient,
)
from reply_mcfly.domain.reply_templates import (
    FALLBACK_MISSING_INFORMATION,
    FALLBACK_UNSUPPORTED_ATTACHMENT,
)


class GeneratedReplyValidator(Protocol):
    def validate(self, email: IncomingEmail, draft: ReplyDraft) -> None: ...


@dataclass(frozen=True)
class FallbackTemplates:
    insufficient_information: str = FALLBACK_MISSING_INFORMATION
    unsupported_attachment: str = FALLBACK_UNSUPPORTED_ATTACHMENT

    def render(self, reason: FallbackReason) -> str:
        value = (
            self.insufficient_information
            if reason == FallbackReason.INSUFFICIENT_INFORMATION
            else self.unsupported_attachment
        )
        if not value or not value.strip():
            raise WorkflowError("APPROVED_FALLBACK_NOT_CONFIGURED")
        return value


class ReplyService:
    def __init__(
        self,
        recipients: frozenset[str],
        templates: FallbackTemplates,
        generated_validator: GeneratedReplyValidator,
    ) -> None:
        self.recipients, self.templates = recipients, templates
        self.generated_validator = generated_validator

    def validate_recipient(self, job: Job, email: IncomingEmail) -> None:
        validate_recipient(job, email, self.recipients)

    def draft(self, job: Job, email: IncomingEmail, draft: ReplyDraft) -> OutboxEntry:
        self.validate_recipient(job, email)
        if draft.requires_review:
            raise WorkflowError("AI_REQUIRES_REVIEW")
        if draft.missing_information:
            if draft.response_type != "FALLBACK":
                raise WorkflowError("INVALID_RESPONSE_TYPE")
            reason = (
                FallbackReason.UNSUPPORTED_ATTACHMENT
                if email.unsupported_attachment
                else FallbackReason.INSUFFICIENT_INFORMATION
            )
            return self.fallback(job, email, reason)
        self.generated_validator.validate(email, draft)
        return prepare_reply(
            job,
            email,
            draft.proposed_reply,
            self.recipients,
            evidence=tuple((e.source_id, e.exact_quote) for e in draft.evidence),
        )

    def fallback(self, job: Job, email: IncomingEmail, reason: FallbackReason) -> OutboxEntry:
        body = self.templates.render(reason)
        return prepare_reply(
            job,
            email,
            body,
            self.recipients,
            ResponseType.FALLBACK,
            reason,
        )

    def validate_stored(self, job: Job, email: IncomingEmail, entry: OutboxEntry) -> None:
        draft = ReplyDraft(
            response_type=entry.response_type.value,
            proposed_reply=entry.draft_body,
            evidence=[
                Evidence(source_id=source, exact_quote=quote) for source, quote in entry.evidence
            ],
            requires_review=False,
            missing_information=[],
        )
        if entry.response_type == ResponseType.FALLBACK:
            if entry.fallback_reason is None or entry.draft_body != self.templates.render(
                entry.fallback_reason
            ):
                raise WorkflowError("FALLBACK_TEMPLATE_MISMATCH")
        else:
            self.generated_validator.validate(email, draft)
        checked = prepare_reply(
            job,
            email,
            entry.draft_body,
            self.recipients,
            entry.response_type,
            entry.fallback_reason,
            entry.evidence,
        )
        if checked != entry:
            raise WorkflowError("OUTBOX_MISMATCH")
