from collections.abc import Iterator
from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

import pytest

from reply_mcfly.application.gmail_sync_service import GmailSyncService
from reply_mcfly.domain.email import IncomingEmail, Job, MessageMetadata, OutboxEntry, WorkflowError
from reply_mcfly.ports.email import EmailRepository, HistoryPage

MAILBOX = "agent@agent.invalid"


class FakeGmail:
    def __init__(self, error: WorkflowError) -> None:
        self.error = error

    def history(self, start: str) -> Iterator[HistoryPage]:
        yield HistoryPage(("deleted", "kept"), "200")

    def metadata(self, message_id: str) -> MessageMetadata:
        if message_id == "deleted":
            raise self.error
        return MessageMetadata(
            message_id, "thread", datetime.now(UTC), frozenset({"INBOX", "UNREAD"})
        )

    def message(self, message_id: str) -> IncomingEmail:
        raise AssertionError("not used")

    def send(self, job: Job, entry: OutboxEntry) -> str:
        raise AssertionError("not used")

    def find_sent(self, job: Job, entry: OutboxEntry) -> str | None:
        raise AssertionError("not used")


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
    def sync(self, mailbox_id: str, event_id: str) -> None:
        pass

    def process(self, job_id: UUID) -> None:
        pass


def _service(error: WorkflowError) -> tuple[GmailSyncService, FakeRepository]:
    repository = FakeRepository()
    service = GmailSyncService(cast(EmailRepository, repository), FakeGmail(error), FakeQueue())
    return service, repository


def test_deleted_message_is_skipped_and_checkpoint_advances() -> None:
    service, repository = _service(WorkflowError("GMAIL_RESOURCE_NOT_FOUND"))

    assert service.sync(MAILBOX) == 1
    assert repository.enqueued == ["kept"]
    assert repository.checkpoints[-1] == "200"


def test_other_metadata_errors_still_stop_the_sync() -> None:
    service, repository = _service(WorkflowError("GMAIL_API_ERROR", retryable=True, status=503))

    with pytest.raises(WorkflowError, match="GMAIL_API_ERROR"):
        service.sync(MAILBOX)
    assert repository.checkpoints == []
