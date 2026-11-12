import io
import wave
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from reply_mcfly.application.attachment_processor import validate_attachments
from reply_mcfly.application.attachment_service import AttachmentService
from reply_mcfly.application.email_processing_service import EmailProcessingService
from reply_mcfly.domain.email import (
    AttachmentPassage,
    EmailAttachment,
    IncomingEmail,
    Job,
    MessageMetadata,
    ReplyDraft,
    Status,
    WorkflowError,
)


def minimal_pdf() -> bytes:
    return b"%PDF-1.4 test attachment body\n"


def minimal_png() -> bytes:
    return b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + b"\x00" * 32


def minimal_jpeg() -> bytes:
    return b"\xff\xd8\xff\xe0" + b"\x00" * 32


def minimal_wav() -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(8000)
        handle.writeframes(b"\x00\x00" * 400)
    return buffer.getvalue()


def minimal_mp3() -> bytes:
    return b"ID3" + b"\x00" * 24


def attachment(source_id: str, mime: str, data: bytes) -> EmailAttachment:
    return EmailAttachment(source_id, f"{source_id}.bin", mime, data)


@pytest.mark.parametrize(
    ("mime", "payload"),
    [
        ("application/pdf", minimal_pdf),
        ("image/png", minimal_png),
        ("image/jpeg", minimal_jpeg),
        ("audio/wav", minimal_wav),
        ("audio/mpeg", minimal_mp3),
    ],
)
def test_supported_formats_pass_magic_validation(mime: str, payload) -> None:
    validated = validate_attachments((attachment("attachment:0", mime, payload()),))
    assert validated[0].mime_type == mime.replace("audio/x-wav", "audio/wav")


def test_fake_extension_with_wrong_mime_is_rejected() -> None:
    with pytest.raises(WorkflowError, match="ATTACHMENT_INVALID"):
        validate_attachments((attachment("attachment:0", "application/pdf", minimal_png()),))


def test_corrupted_pdf_is_rejected() -> None:
    with pytest.raises(WorkflowError, match="ATTACHMENT_INVALID"):
        validate_attachments((attachment("attachment:0", "application/pdf", b"not-a-pdf"),))


def test_oversized_attachment_is_rejected() -> None:
    huge = minimal_pdf() + b"x" * (6 * 1024 * 1024)
    with pytest.raises(WorkflowError, match="ATTACHMENT_LIMIT_EXCEEDED"):
        validate_attachments((attachment("attachment:0", "application/pdf", huge),))


class FakeAttachmentExtractor:
    def extract(self, email, attachments, timeout: float) -> tuple[AttachmentPassage, ...]:
        return tuple(
            AttachmentPassage(item.source_id, f"extracted-from-{item.source_id}")
            for item in attachments
        )


class FakeRunner:
    def run(self, email: IncomingEmail, timeout: float) -> ReplyDraft:
        quote = email.attachment_passages[0].text
        from reply_mcfly.domain.email import Evidence

        evidence = [Evidence(source_id=email.attachment_passages[0].source_id, exact_quote=quote)]
        from reply_mcfly.domain.grounding import render_verified_reply

        return ReplyDraft(
            response_type="GENERATED",
            proposed_reply=render_verified_reply(evidence),
            evidence=evidence,
            missing_information=[],
            requires_review=False,
        )


class FakeRepository:
    def __init__(self) -> None:
        self.job = Job(
            uuid4(),
            "reply@agent.invalid",
            "a1",
            "b1",
            datetime.now(UTC),
            Status.PROCESSING,
            uuid4(),
            None,
            1,
        )

    def get(self, job_id):
        return self.job

    def claim(self, job_id, token):
        return self.job

    def outbox(self, job_id):
        return None

    def transition(self, job, target, code=None):
        self.job = Job(
            job.id,
            job.mailbox_id,
            job.gmail_message_id,
            job.gmail_thread_id,
            job.received_at,
            target,
            job.lease_token,
            job.lease_until,
            job.attempt_count,
        )

    def prepare(self, job, entry):
        pass

    def release_lease(self, job):
        pass

    def sent(self, job, gmail_message_id):
        pass


class FakeGmail:
    def __init__(self, email: IncomingEmail) -> None:
        self.email = email

    def message(self, message_id: str) -> IncomingEmail:
        return self.email


class FakeReplies:
    def validate_recipient(self, job, email):
        pass

    def draft(self, job, email, draft):
        from reply_mcfly.domain.email import OutboxEntry, ResponseType

        return OutboxEntry(
            job.id,
            "<out@agent.invalid>",
            email.sender,
            email.subject,
            "body",
            email.message_id_header,
            email.references,
            ResponseType.GENERATED,
        )

    def validate_stored(self, job, email, entry):
        pass


def test_email_processing_enriches_supported_attachments_before_runner() -> None:
    passage_text = "DEMO-84721 je identifikátor objednávky."
    email = IncomingEmail(
        MessageMetadata("a1", "b1", datetime.now(UTC), frozenset()),
        "sender@customer.invalid",
        "Příloha",
        "<m@customer.invalid>",
        "",
        "Prosím o kontrolu přílohy.",
        has_attachments=True,
        attachments=(attachment("attachment:0", "application/pdf", minimal_pdf()),),
        attachment_passages=(),
    )

    class Extractor:
        def extract(self, current, attachments, timeout):
            assert attachments
            return (AttachmentPassage("attachment:0", passage_text),)

    repository = FakeRepository()
    runner = FakeRunner()
    service = EmailProcessingService(
        repository,  # type: ignore[arg-type]
        FakeGmail(email),  # type: ignore[arg-type]
        runner,  # type: ignore[arg-type]
        repository.job.mailbox_id,
        FakeReplies(),  # type: ignore[arg-type]
        AttachmentService(Extractor()),  # type: ignore[arg-type]
    )
    status = service.process(repository.job.id, send_enabled=False)
    assert status == Status.READY_TO_SEND
