import os
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy.engine import Engine

from reply_mcfly.adapters.postgres_adapter import (
    EmailJobModel,
    EmailOutboxModel,
    MailboxSyncState,
    PostgresEmailRepository,
    make_engine,
)
from reply_mcfly.application.email_processing_service import EmailProcessingService
from reply_mcfly.application.live_email_runner import LiveEmailRunner, validate_live_email_settings
from reply_mcfly.application.reply_service import FallbackTemplates, ReplyService
from reply_mcfly.domain.email import (
    Evidence,
    IncomingEmail,
    Job,
    MessageMetadata,
    OutboxEntry,
    ReplyDraft,
    Status,
    WorkflowError,
)
from reply_mcfly.domain.grounding import LiteralReplyValidator, render_verified_reply
from reply_mcfly.domain.sender_policy import parse_sender_policy
from reply_mcfly.ports.email import HistoryPage

pytestmark = pytest.mark.integration


class FakeGmail:
    def __init__(self) -> None:
        self.email = IncomingEmail(
            MessageMetadata("a1", "b1", datetime.now(UTC), frozenset({"INBOX", "UNREAD"})),
            "sender@customer.invalid",
            "Synthetic test",
            "<original@customer.invalid>",
            "",
            "Test",
        )
        self.send_calls = 0

    def history(self, start: str) -> Iterator[HistoryPage]:
        raise AssertionError("Live runner must not request Gmail history")

    def metadata(self, message_id: str) -> MessageMetadata:
        return self.email.metadata

    def message(self, message_id: str) -> IncomingEmail:
        return self.email

    def send(self, job: Job, entry: OutboxEntry) -> str:
        self.send_calls += 1
        return "sent1"

    def find_sent(self, job: Job, entry: OutboxEntry) -> str | None:
        return "sent1"


class FakeRunner:
    def __init__(self) -> None:
        self.calls = 0

    def run(self, email: IncomingEmail, timeout: float) -> ReplyDraft:
        self.calls += 1
        evidence = [
            Evidence(source_id=f"email:{email.metadata.message_id}", exact_quote=email.text)
        ]
        return ReplyDraft(
            response_type="GENERATED",
            proposed_reply=render_verified_reply(evidence),
            evidence=evidence,
            missing_information=[],
            requires_review=False,
        )


def test_validate_live_email_settings_rejects_agent_in_allowlist() -> None:
    with pytest.raises(RuntimeError, match="MCFLY_ALLOWED_SENDERS"):
        validate_live_email_settings("agent@test.invalid", frozenset({"agent@test.invalid"}))


@pytest.fixture
def runner_harness() -> Iterator[tuple[LiveEmailRunner, FakeGmail, FakeRunner, Engine, str]]:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.fail("TEST_DATABASE_URL is required")
    engine = make_engine(url)
    mailbox = f"{uuid4()}@agent.invalid"
    repository = PostgresEmailRepository(engine)
    repository.initialize(mailbox, "100", datetime.now(UTC) + timedelta(days=1))
    gmail = FakeGmail()
    gmail.email = IncomingEmail(
        MessageMetadata(
            "msg-live-1", "thread-live-1", datetime.now(UTC), frozenset({"INBOX", "UNREAD"})
        ),
        gmail.email.sender,
        "Live runner test",
        "<live@customer.invalid>",
        "",
        "Jednoduchý testovací text pro literal grounding.",
    )
    runner = FakeRunner()
    replies = ReplyService(
        parse_sender_policy(frozenset({gmail.email.sender}), mailbox),
        FallbackTemplates(),
        LiteralReplyValidator(),
    )
    processing = EmailProcessingService(repository, gmail, runner, mailbox, replies)
    live = LiveEmailRunner(repository, gmail, processing, mailbox)
    try:
        yield live, gmail, runner, engine, mailbox
    finally:
        from sqlalchemy import delete, select

        with engine.begin() as connection:
            ids = select(EmailJobModel.id).where(EmailJobModel.mailbox_id == mailbox)
            connection.execute(delete(EmailOutboxModel).where(EmailOutboxModel.job_id.in_(ids)))
            connection.execute(delete(EmailJobModel).where(EmailJobModel.mailbox_id == mailbox))
            connection.execute(
                delete(MailboxSyncState).where(MailboxSyncState.mailbox_id == mailbox)
            )
        engine.dispose()


def test_live_runner_dry_run_never_sends(
    runner_harness: tuple[LiveEmailRunner, FakeGmail, FakeRunner, Engine, str],
) -> None:
    live, gmail, runner, _, _ = runner_harness
    result = live.run("msg-live-1", send_enabled=False)
    assert result.status == Status.READY_TO_SEND
    assert gmail.send_calls == 0
    assert runner.calls == 1


def test_live_runner_send_uses_existing_workflow(
    runner_harness: tuple[LiveEmailRunner, FakeGmail, FakeRunner, Engine, str],
) -> None:
    live, gmail, runner, _, _ = runner_harness
    dry = live.run("msg-live-1", send_enabled=False)
    assert dry.status == Status.READY_TO_SEND
    assert gmail.send_calls == 0
    sent = live.run("msg-live-1", send_enabled=True)
    assert sent.status == Status.SENT
    assert gmail.send_calls == 1


def test_live_runner_rejects_non_incoming_message(
    runner_harness: tuple[LiveEmailRunner, FakeGmail, FakeRunner, Engine, str],
) -> None:
    live, gmail, _, _, _ = runner_harness
    gmail.email = IncomingEmail(
        MessageMetadata(
            "msg-live-1", "thread-live-1", datetime.now(UTC), frozenset({"INBOX", "SENT"})
        ),
        gmail.email.sender,
        gmail.email.subject,
        gmail.email.message_id_header,
        gmail.email.references,
        gmail.email.text,
    )
    with pytest.raises(WorkflowError, match="MESSAGE_NOT_INCOMING"):
        live.run("msg-live-1", send_enabled=False)
