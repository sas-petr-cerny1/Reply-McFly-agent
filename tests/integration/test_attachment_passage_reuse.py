import os
from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import uuid4

import pytest
from sqlalchemy import delete, select
from sqlalchemy.engine import Engine

from reply_mcfly.adapters.postgres_adapter import (
    EmailJobModel,
    EmailOutboxModel,
    MailboxSyncState,
    PostgresEmailRepository,
    make_engine,
)
from reply_mcfly.application.email_processing_service import EmailProcessingService
from reply_mcfly.application.reply_service import FallbackTemplates, ReplyService
from reply_mcfly.domain.email import (
    AttachmentPassage,
    Evidence,
    IncomingEmail,
    Job,
    MessageMetadata,
    OutboxEntry,
    ReplyDraft,
    Status,
)
from reply_mcfly.domain.grounding import LiteralReplyValidator
from reply_mcfly.domain.sender_policy import parse_sender_policy
from reply_mcfly.ports.email import GmailPort

pytestmark = pytest.mark.integration

SENDER = "sender@customer.invalid"
EXTRACTIONS = ("Na štítku je kód RM-105.", "Štítek uvádí kód RM-105 a datum.")


class FakeGmail:
    def __init__(self) -> None:
        self.metadata = MessageMetadata(
            "a1", "b1", datetime.now(UTC), frozenset({"INBOX", "UNREAD"})
        )
        self.send_calls = 0

    def message(self, message_id: str) -> IncomingEmail:
        return IncomingEmail(
            self.metadata,
            SENDER,
            "Synthetic test",
            "<original@customer.invalid>",
            "",
            "Jaký kód je na štítku?",
            has_attachments=True,
        )

    def send(self, job: Job, entry: OutboxEntry) -> str:
        self.send_calls += 1
        return "sent1"


class DriftingExtractor:
    """Returns different wording on every call, like a non-deterministic model."""

    def __init__(self) -> None:
        self.calls = 0

    def enrich(self, email: IncomingEmail, timeout: float) -> IncomingEmail:
        text = EXTRACTIONS[min(self.calls, len(EXTRACTIONS) - 1)]
        self.calls += 1
        return replace(email, attachment_passages=(AttachmentPassage("attachment:0", text),))


class QuoteAttachment:
    def run(self, email: IncomingEmail, timeout: float) -> ReplyDraft:
        return ReplyDraft(
            response_type="GENERATED",
            proposed_reply="",
            evidence=[
                Evidence(source_id="attachment:0", exact_quote=email.attachment_passages[0].text)
            ],
            missing_information=[],
            requires_review=False,
        )


@pytest.fixture
def engine() -> Iterator[Engine]:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.fail("TEST_DATABASE_URL is required")
    engine = make_engine(url)
    yield engine
    engine.dispose()


def test_retry_validates_against_the_stored_extraction(engine: Engine) -> None:
    mailbox = f"{uuid4()}@agent.invalid"
    repository = PostgresEmailRepository(engine)
    repository.initialize(mailbox, "100", datetime.now(UTC) + timedelta(days=1))
    gmail = FakeGmail()
    extractor = DriftingExtractor()
    processing = EmailProcessingService(
        repository,
        cast(GmailPort, gmail),
        QuoteAttachment(),
        mailbox,
        ReplyService(
            parse_sender_policy(frozenset({SENDER}), mailbox),
            FallbackTemplates(),
            LiteralReplyValidator(),
        ),
        extractor,
    )
    try:
        job_id = repository.enqueue(mailbox, gmail.metadata)
        assert processing.process(job_id, send_enabled=False) == Status.READY_TO_SEND
        stored = repository.outbox(job_id)
        assert stored is not None
        assert stored.attachment_passages == (AttachmentPassage("attachment:0", EXTRACTIONS[0]),)

        # The second run must not ask the model again and must still accept the stored quote.
        assert processing.process(job_id) == Status.SENT
        assert extractor.calls == 1
        assert gmail.send_calls == 1
        assert repository.outbox(job_id) == stored
    finally:
        with engine.begin() as connection:
            ids = select(EmailJobModel.id).where(EmailJobModel.mailbox_id == mailbox)
            connection.execute(delete(EmailOutboxModel).where(EmailOutboxModel.job_id.in_(ids)))
            connection.execute(delete(EmailJobModel).where(EmailJobModel.mailbox_id == mailbox))
            connection.execute(
                delete(MailboxSyncState).where(MailboxSyncState.mailbox_id == mailbox)
            )
