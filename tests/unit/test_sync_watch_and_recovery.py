from collections.abc import Iterator
from datetime import UTC, datetime
from typing import cast
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest

from reply_mcfly.adapters.gmail_adapter import GmailAdapter
from reply_mcfly.application.gmail_sync_service import GmailSyncService
from reply_mcfly.domain.email import MessageMetadata, WorkflowError
from reply_mcfly.ports.email import EmailRepository, GmailPort, HistoryPage, TaskQueuePort

MAILBOX = "agent@agent.invalid"


class FakeGmail:
    def __init__(self) -> None:
        self.history_error: WorkflowError | None = None
        self.calls: list[str] = []

    def history(self, start: str) -> Iterator[HistoryPage]:
        if self.history_error:
            raise self.history_error
        yield HistoryPage(("a1",), "200")

    def metadata(self, message_id: str) -> MessageMetadata:
        return MessageMetadata(
            message_id, "thread", datetime.now(UTC), frozenset({"INBOX", "UNREAD"})
        )

    def profile_history(self) -> str:
        self.calls.append("profile_history")
        return "900"

    def unread_inbox(self) -> tuple[str, ...]:
        self.calls.append("unread_inbox")
        return ("u1", "u2")


class FakeRepository:
    def __init__(self) -> None:
        self.enqueued: list[str] = []
        self.checkpoints: list[str] = []

    def acquire_sync(self, mailbox_id: str, token: UUID) -> str:
        return "100"

    def release_sync(self, mailbox_id: str, token: UUID) -> None:
        pass

    def checkpoint(self, mailbox_id: str, token: UUID, history_id: str) -> None:
        self.checkpoints.append(history_id)

    def enqueue(self, mailbox_id: str, metadata: MessageMetadata) -> UUID:
        self.enqueued.append(metadata.message_id)
        return uuid4()


class FakeQueue:
    def process(self, job_id: UUID) -> None:
        pass


def _sync(
    gmail: FakeGmail, repository: FakeRepository, *, maintenance: bool = True
) -> GmailSyncService:
    return GmailSyncService(
        cast(EmailRepository, repository),
        cast(GmailPort, gmail),
        cast(TaskQueuePort, FakeQueue()),
        maintenance=gmail if maintenance else None,
    )


def test_expired_history_recovers_from_unread_inbox() -> None:
    gmail = FakeGmail()
    gmail.history_error = WorkflowError("HISTORY_EXPIRED", status=503)
    repository = FakeRepository()

    assert _sync(gmail, repository).sync(MAILBOX) == 2
    assert repository.enqueued == ["u1", "u2"]
    assert repository.checkpoints == ["900"]
    # Baseline before listing, so mail arriving in between is still found through history.
    assert gmail.calls == ["profile_history", "unread_inbox"]


def test_expired_history_without_maintenance_port_still_fails() -> None:
    gmail = FakeGmail()
    gmail.history_error = WorkflowError("HISTORY_EXPIRED", status=503)
    repository = FakeRepository()

    with pytest.raises(WorkflowError, match="HISTORY_EXPIRED"):
        _sync(gmail, repository, maintenance=False).sync(MAILBOX)
    assert repository.checkpoints == []


def _gmail_service() -> MagicMock:
    service = MagicMock()
    service.users.return_value.getProfile.return_value.execute.return_value = {
        "emailAddress": MAILBOX
    }
    return service


def test_adapter_lists_unread_inbox_messages_once_each() -> None:
    service = _gmail_service()
    messages = service.users.return_value.messages.return_value
    messages.list.return_value.execute.return_value = {
        "messages": [{"id": "u1"}, {"id": "u2"}, {"id": "u1"}],
        "nextPageToken": "ignored",
    }

    assert GmailAdapter(lambda: service, MAILBOX).unread_inbox() == ("u1", "u2")
    assert messages.list.call_args.kwargs["labelIds"] == ["INBOX", "UNREAD"]


def test_adapter_rejects_malformed_unread_listing() -> None:
    service = _gmail_service()
    service.users.return_value.messages.return_value.list.return_value.execute.return_value = {
        "messages": [{"id": ""}]
    }

    with pytest.raises(WorkflowError, match="INVALID_GMAIL_RESPONSE"):
        GmailAdapter(lambda: service, MAILBOX).unread_inbox()
