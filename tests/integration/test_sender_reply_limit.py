import os
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import delete, select, update
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
from reply_mcfly.config.settings import Settings
from reply_mcfly.domain.email import (
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
OTHER = "other@customer.invalid"


class FakeGmail:
    def __init__(self) -> None:
        self.emails: dict[str, IncomingEmail] = {}
        self.sent: list[str] = []

    def add(self, sender: str) -> MessageMetadata:
        identifier = uuid4().hex
        metadata = MessageMetadata(
            identifier, f"thread-{identifier}", datetime.now(UTC), frozenset({"INBOX", "UNREAD"})
        )
        self.emails[identifier] = IncomingEmail(
            metadata, sender, "Synthetic", f"<{identifier}@customer.invalid>", "", "Test"
        )
        return metadata

    def message(self, message_id: str) -> IncomingEmail:
        return self.emails[message_id]

    def send(self, job: Job, entry: OutboxEntry) -> str:
        self.sent.append(entry.recipient)
        return f"sent-{len(self.sent)}"


class EchoRunner:
    def run(self, email: IncomingEmail, timeout: float) -> ReplyDraft:
        return ReplyDraft(
            response_type="GENERATED",
            proposed_reply="",
            evidence=[
                Evidence(source_id=f"email:{email.metadata.message_id}", exact_quote=email.text)
            ],
            missing_information=[],
            requires_review=False,
        )


class Mailbox:
    def __init__(self, engine: Engine, limit: int | None) -> None:
        self.engine = engine
        self.mailbox = f"{uuid4()}@agent.invalid"
        self.repository = PostgresEmailRepository(engine)
        self.repository.initialize(self.mailbox, "100", None)
        self.gmail = FakeGmail()
        self.processing = EmailProcessingService(
            self.repository,
            cast(GmailPort, self.gmail),
            EchoRunner(),
            self.mailbox,
            ReplyService(
                parse_sender_policy(frozenset({"*"}), self.mailbox),
                FallbackTemplates(),
                LiteralReplyValidator(),
            ),
            sender_daily_reply_limit=limit,
        )

    def receive(self, sender: str = SENDER, *, send_enabled: bool = True) -> tuple[UUID, Status]:
        job_id = self.repository.enqueue(self.mailbox, self.gmail.add(sender))
        return job_id, self.processing.process(job_id, send_enabled=send_enabled)

    def error_code(self, job_id: UUID) -> str | None:
        with self.engine.connect() as connection:
            return connection.execute(
                select(EmailJobModel.error_code).where(EmailJobModel.id == job_id)
            ).scalar_one()

    def cleanup(self) -> None:
        with self.engine.begin() as connection:
            ids = select(EmailJobModel.id).where(EmailJobModel.mailbox_id == self.mailbox)
            connection.execute(delete(EmailOutboxModel).where(EmailOutboxModel.job_id.in_(ids)))
            connection.execute(
                delete(EmailJobModel).where(EmailJobModel.mailbox_id == self.mailbox)
            )
            connection.execute(
                delete(MailboxSyncState).where(MailboxSyncState.mailbox_id == self.mailbox)
            )


@pytest.fixture
def engine() -> Iterator[Engine]:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.fail("TEST_DATABASE_URL is required")
    engine = make_engine(url)
    yield engine
    engine.dispose()


@pytest.fixture
def mailbox(engine: Engine) -> Iterator[Mailbox]:
    mailbox = Mailbox(engine, limit=2)
    yield mailbox
    mailbox.cleanup()


def test_replies_beyond_the_daily_limit_wait_for_review(mailbox: Mailbox) -> None:
    assert mailbox.receive()[1] == Status.SENT
    assert mailbox.receive()[1] == Status.SENT

    job_id, status = mailbox.receive()

    assert status == Status.REVIEW_REQUIRED
    assert mailbox.error_code(job_id) == "SENDER_REPLY_LIMIT_REACHED"
    assert mailbox.gmail.sent == [SENDER, SENDER]
    assert mailbox.repository.outbox(job_id) is None


def test_limit_is_counted_per_sender(mailbox: Mailbox) -> None:
    mailbox.receive()
    mailbox.receive()

    assert mailbox.receive(OTHER)[1] == Status.SENT
    assert mailbox.receive()[1] == Status.REVIEW_REQUIRED


def test_limit_is_counted_per_mailbox(engine: Engine, mailbox: Mailbox) -> None:
    other = Mailbox(engine, limit=2)
    try:
        other.receive()
        other.receive()

        assert mailbox.receive()[1] == Status.SENT
    finally:
        other.cleanup()


def test_replies_older_than_a_day_do_not_count(mailbox: Mailbox) -> None:
    first, _ = mailbox.receive()
    mailbox.receive()
    with mailbox.engine.begin() as connection:
        connection.execute(
            update(EmailOutboxModel)
            .where(EmailOutboxModel.job_id == first)
            .values(sent_at=datetime.now(UTC) - timedelta(hours=25))
        )

    assert mailbox.receive()[1] == Status.SENT


def test_prepared_but_unsent_replies_do_not_use_the_budget(mailbox: Mailbox) -> None:
    for _ in range(3):
        assert mailbox.receive(send_enabled=False)[1] == Status.READY_TO_SEND

    assert mailbox.receive()[1] == Status.SENT


def test_duplicate_task_for_a_sent_job_is_not_counted_twice(mailbox: Mailbox) -> None:
    job_id, _ = mailbox.receive()
    assert mailbox.processing.process(job_id) == Status.SENT

    assert mailbox.receive()[1] == Status.SENT
    assert len(mailbox.gmail.sent) == 2


def test_limit_can_be_left_out_by_tests_and_tools(engine: Engine) -> None:
    unlimited = Mailbox(engine, limit=None)
    try:
        assert [unlimited.receive()[1] for _ in range(4)] == [Status.SENT] * 4
    finally:
        unlimited.cleanup()


def test_limit_setting_defaults_to_twenty_and_rejects_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("MCFLY_SENDER_DAILY_REPLY_LIMIT", raising=False)
    assert Settings().sender_daily_reply_limit == 20
    monkeypatch.setenv("MCFLY_SENDER_DAILY_REPLY_LIMIT", "0")
    with pytest.raises(ValidationError):
        Settings()
