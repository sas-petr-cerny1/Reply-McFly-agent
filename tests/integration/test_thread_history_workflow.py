"""Integration: Conversation History through DB, validator, ReplyService, and send gate.

Mirrors the live ""Reply McFly - test 06"" thread from Gmail export:
  1) Customer mail with RM-105 in body
  2) Follow-up asking what number they gave earlier
  3) Outgoing mail cites the *first* message via thread_history, not the question text
"""
from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
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
from reply_mcfly.application.live_email_runner import LiveEmailRunner
from reply_mcfly.application.reply_service import FallbackTemplates, ReplyService
from reply_mcfly.domain.email import (
    Evidence,
    IncomingEmail,
    MessageMetadata,
    ReplyDraft,
    Status,
    ThreadHistoryPassage,
    WorkflowError,
)
from reply_mcfly.domain.grounding import LiteralReplyValidator, render_verified_reply
from reply_mcfly.ports.email import HistoryPage

pytestmark = pytest.mark.integration

SENDER = "procyon.technology.consulting@gmail.com"
MAILBOX_SUFFIX = "@agent.invalid"
ORIGINAL_MESSAGE_ID = "1a1ccac5412b26b1"
FOLLOW_UP_MESSAGE_ID = "1a1ccaed8efd18b8"
THREAD_ID = "1a1ccac5412b26b1"
ORIGINAL_QUOTE = "Dobrý den, číslo mého testovacího požadavku je RM-105."
FOLLOW_UP_TEXT = "Jaké číslo jsem uvedl v předchozí zprávě?"


class ScenarioGmail:
    """In-memory thread: follow-up is current; first customer mail is thread_history."""

    def __init__(self, mailbox: str, *, send_enabled: bool = True) -> None:
        self.mailbox = mailbox
        self.send_enabled = send_enabled
        self.send_calls = 0
        self.first = IncomingEmail(
            MessageMetadata(
                ORIGINAL_MESSAGE_ID,
                THREAD_ID,
                datetime.now(UTC) - timedelta(minutes=3),
                frozenset({"INBOX"}),
            ),
            SENDER,
            "Reply McFly - test 06",
            f"<{ORIGINAL_MESSAGE_ID}@customer.invalid>",
            "",
            ORIGINAL_QUOTE,
        )
        self.follow_up = IncomingEmail(
            MessageMetadata(
                FOLLOW_UP_MESSAGE_ID,
                THREAD_ID,
                datetime.now(UTC),
                frozenset({"INBOX", "UNREAD"}),
            ),
            SENDER,
            "Re: Reply McFly - test 06",
            f"<{FOLLOW_UP_MESSAGE_ID}@customer.invalid>",
            f"<{ORIGINAL_MESSAGE_ID}@customer.invalid>",
            FOLLOW_UP_TEXT,
            thread_history=(
                ThreadHistoryPassage(
                    f"thread:{ORIGINAL_MESSAGE_ID}",
                    SENDER,
                    ORIGINAL_QUOTE,
                ),
            ),
        )

    def history(self, start: str) -> Iterator[HistoryPage]:
        yield HistoryPage((self.follow_up.metadata.message_id,), "200")

    def metadata(self, message_id: str) -> MessageMetadata:
        if message_id == FOLLOW_UP_MESSAGE_ID:
            return self.follow_up.metadata
        if message_id == ORIGINAL_MESSAGE_ID:
            return self.first.metadata
        raise WorkflowError("GMAIL_RESOURCE_NOT_FOUND")

    def message(self, message_id: str) -> IncomingEmail:
        if message_id == FOLLOW_UP_MESSAGE_ID:
            return self.follow_up
        if message_id == ORIGINAL_MESSAGE_ID:
            return self.first
        raise WorkflowError("GMAIL_RESOURCE_NOT_FOUND")

    def send(self, job, entry) -> str:
        if not self.send_enabled:
            raise WorkflowError("SEND_DISABLED")
        self.send_calls += 1
        return "sent-follow-up-1"

    def find_sent(self, job, entry) -> str | None:
        return "sent-follow-up-1"


class ThreadHistoryFakeRunner:
    """Stand-in for Gemini: pick a literal quote from thread_history when present."""

    def __init__(self) -> None:
        self.last_email: IncomingEmail | None = None

    def run(self, email: IncomingEmail, timeout: float) -> ReplyDraft:
        self.last_email = email
        if not email.thread_history:
            raise WorkflowError("UNEXPECTED_EMPTY_THREAD_HISTORY")
        passage = email.thread_history[0]
        if ORIGINAL_QUOTE not in passage.text:
            raise WorkflowError("UNEXPECTED_THREAD_PASSAGE")
        evidence = [Evidence(source_id=passage.source_id, exact_quote=ORIGINAL_QUOTE)]
        return ReplyDraft(
            response_type="GENERATED",
            proposed_reply="ignored-by-backend",
            evidence=evidence,
            missing_information=[],
            requires_review=False,
        )


@pytest.fixture
def thread_history_harness() -> Iterator[tuple[LiveEmailRunner, ScenarioGmail, ThreadHistoryFakeRunner, Engine]]:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.fail("TEST_DATABASE_URL is required")
    engine = make_engine(url)
    mailbox = f"{uuid4()}{MAILBOX_SUFFIX}"
    repository = PostgresEmailRepository(engine)
    repository.initialize(mailbox, "100", datetime.now(UTC) + timedelta(days=1))
    gmail = ScenarioGmail(mailbox)
    runner = ThreadHistoryFakeRunner()
    replies = ReplyService(frozenset({SENDER}), FallbackTemplates(), LiteralReplyValidator())
    processing = EmailProcessingService(repository, gmail, runner, mailbox, replies)
    live = LiveEmailRunner(repository, gmail, processing, mailbox)
    try:
        yield live, gmail, runner, engine
    finally:
        with engine.begin() as connection:
            ids = select(EmailJobModel.id).where(EmailJobModel.mailbox_id == mailbox)
            connection.execute(delete(EmailOutboxModel).where(EmailOutboxModel.job_id.in_(ids)))
            connection.execute(delete(EmailJobModel).where(EmailJobModel.mailbox_id == mailbox))
            connection.execute(
                delete(MailboxSyncState).where(MailboxSyncState.mailbox_id == mailbox)
            )
        engine.dispose()


def test_reply_mcfly_test_06_follow_up_sends_rm105_from_thread_history(
    thread_history_harness: tuple[LiveEmailRunner, ScenarioGmail, ThreadHistoryFakeRunner, Engine],
) -> None:
    live, gmail, runner, engine = thread_history_harness
    result = live.run(FOLLOW_UP_MESSAGE_ID, send_enabled=True)
    assert result.status == Status.SENT
    assert result.gmail_thread_id == THREAD_ID
    assert gmail.send_calls == 1
    assert runner.last_email is not None
    assert runner.last_email.text == FOLLOW_UP_TEXT
    assert len(runner.last_email.thread_history) == 1
    assert runner.last_email.thread_history[0].source_id == f"thread:{ORIGINAL_MESSAGE_ID}"

    repository = PostgresEmailRepository(engine)
    entry = repository.outbox(result.job_id)
    assert entry is not None
    assert "RM-105" in entry.draft_body
    assert ORIGINAL_QUOTE in entry.draft_body
    assert FOLLOW_UP_TEXT not in entry.draft_body
    assert "v naší předchozí e-mailové konverzaci zaznělo:" in entry.draft_body
    assert entry.evidence == ((f"thread:{ORIGINAL_MESSAGE_ID}", ORIGINAL_QUOTE),)
    assert entry.draft_body == render_verified_reply(
        [Evidence(source_id=f"thread:{ORIGINAL_MESSAGE_ID}", exact_quote=ORIGINAL_QUOTE)]
    )


def test_follow_up_cannot_invent_rm105_without_thread_passage() -> None:
    email = IncomingEmail(
        MessageMetadata("current", "t1", datetime.now(UTC), frozenset({"INBOX", "UNREAD"})),
        SENDER,
        "Re: test",
        "<c@x>",
        "",
        FOLLOW_UP_TEXT,
        thread_history=(),
    )
    draft = ReplyDraft(
        response_type="GENERATED",
        proposed_reply="",
        evidence=[Evidence(source_id=f"thread:{ORIGINAL_MESSAGE_ID}", exact_quote=ORIGINAL_QUOTE)],
        missing_information=[],
        requires_review=False,
    )
    with pytest.raises(WorkflowError, match="INVALID_EVIDENCE"):
        LiteralReplyValidator().validate(email, draft)
