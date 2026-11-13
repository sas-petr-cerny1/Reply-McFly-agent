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
    def __init__(self, pages: list[HistoryPage]) -> None:
        self.pages = pages

    def history(self, start: str) -> Iterator[HistoryPage]:
        yield from self.pages

    def metadata(self, message_id: str) -> MessageMetadata:
        return MessageMetadata(
            message_id, "thread", datetime.now(UTC), frozenset({"INBOX", "UNREAD"})
        )


class FakeRepository:
    def __init__(self) -> None:
        self.checkpoints: list[str] = []

    def acquire_sync(self, mailbox_id: str, token: UUID) -> str:
        return "100"

    def release_sync(self, mailbox_id: str, token: UUID) -> None:
        pass

    def checkpoint(self, mailbox_id: str, token: UUID, history_id: str) -> None:
        self.checkpoints.append(history_id)

    def enqueue(self, mailbox_id: str, metadata: MessageMetadata) -> UUID:
        return uuid4()


class FakeQueue:
    def __init__(self, fail_on_call: int | None = None) -> None:
        self.calls = 0
        self.fail_on_call = fail_on_call

    def process(self, job_id: UUID) -> None:
        self.calls += 1
        if self.calls == self.fail_on_call:
            raise WorkflowError("TASK_QUEUE_UNAVAILABLE", retryable=True, status=503)


def _sync(pages: list[HistoryPage], queue: FakeQueue) -> tuple[GmailSyncService, FakeRepository]:
    repository = FakeRepository()
    service = GmailSyncService(
        cast(EmailRepository, repository),
        cast(GmailPort, FakeGmail(pages)),
        cast(TaskQueuePort, queue),
    )
    return service, repository


def test_each_completed_page_is_checkpointed_before_the_final_history_id() -> None:
    pages = [HistoryPage(("a1",), "500", "210"), HistoryPage(("a2",), "500", "320")]
    service, repository = _sync(pages, FakeQueue())

    assert service.sync(MAILBOX) == 2
    assert repository.checkpoints == ["210", "320", "500"]


def test_failure_on_a_later_page_keeps_progress_of_completed_pages() -> None:
    pages = [HistoryPage(("a1",), "500", "210"), HistoryPage(("a2",), "500", "320")]
    service, repository = _sync(pages, FakeQueue(fail_on_call=2))

    with pytest.raises(WorkflowError, match="TASK_QUEUE_UNAVAILABLE"):
        service.sync(MAILBOX)
    # Never the mailbox-wide id "500": that would skip the unprocessed second page.
    assert repository.checkpoints == ["210"]


def test_page_without_record_ids_only_checkpoints_at_the_end() -> None:
    service, repository = _sync([HistoryPage(("a1",), "500")], FakeQueue())

    assert service.sync(MAILBOX) == 1
    assert repository.checkpoints == ["500"]


def test_adapter_reports_the_last_record_id_of_each_page() -> None:
    service = MagicMock()
    service.users.return_value.getProfile.return_value.execute.return_value = {
        "emailAddress": MAILBOX
    }
    service.users.return_value.history.return_value.list.return_value.execute.side_effect = [
        {
            "historyId": "500",
            "nextPageToken": "next",
            "history": [
                {"id": "205", "messagesAdded": [{"message": {"id": "a1"}}]},
                {"id": "210", "messagesAdded": [{"message": {"id": "a2"}}]},
            ],
        },
        {"historyId": "500"},
    ]

    pages = list(GmailAdapter(lambda: service, MAILBOX).history("100"))

    assert pages == [HistoryPage(("a1", "a2"), "500", "210"), HistoryPage((), "500", None)]
