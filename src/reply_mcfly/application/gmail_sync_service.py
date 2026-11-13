import time
from collections.abc import Iterator
from uuid import uuid4

from reply_mcfly.application.telemetry import emit
from reply_mcfly.domain.email import WorkflowError, incoming
from reply_mcfly.ports.email import (
    EmailRepository,
    GmailPort,
    HistoryPage,
    MailboxMaintenancePort,
    TaskQueuePort,
)


class GmailSyncService:
    def __init__(
        self,
        repository: EmailRepository,
        gmail: GmailPort,
        queue: TaskQueuePort,
        *,
        maintenance: MailboxMaintenancePort | None = None,
    ) -> None:
        self.repository, self.gmail, self.queue = repository, gmail, queue
        self.maintenance = maintenance

    def _pages(self, start: str) -> Iterator[HistoryPage]:
        try:
            yield from self.gmail.history(start)
        except WorkflowError as error:
            if error.code != "HISTORY_EXPIRED" or self.maintenance is None:
                raise
            # Read the baseline first: anything that arrives later stays reachable via history.
            baseline = self.maintenance.profile_history()
            message_ids = self.maintenance.unread_inbox()
            emit("history_recovery", status=str(len(message_ids)), error_code=error.code)
            yield HistoryPage(message_ids, baseline)

    def sync(self, mailbox_id: str) -> int:
        token = uuid4()
        start = self.repository.acquire_sync(mailbox_id, token)
        deadline = time.monotonic() + 100
        count = 0
        checkpoint = start
        try:
            for page in self._pages(start):
                for message_id in page.message_ids:
                    if time.monotonic() + 10 > deadline:
                        raise WorkflowError("DEPENDENCY_TIMEOUT", retryable=True, status=503)
                    try:
                        metadata = self.gmail.metadata(message_id)
                    except WorkflowError as error:
                        if error.code != "GMAIL_RESOURCE_NOT_FOUND":
                            raise
                        # Deleted since the history record; retrying can never succeed.
                        emit(
                            "sync_message_skipped",
                            gmail_message_id=message_id,
                            error_code=error.code,
                        )
                        continue
                    if incoming(metadata):
                        job_id = self.repository.enqueue(mailbox_id, metadata)
                        self.queue.process(job_id)
                        count += 1
                checkpoint = page.history_id
                if page.resume_history_id is not None:
                    # Persist progress so a later timeout does not replay enqueued pages.
                    self.repository.checkpoint(mailbox_id, token, page.resume_history_id)
            # Queue failure leaves the last saved checkpoint, so redelivery discovers the
            # remaining jobs again.
            self.repository.checkpoint(mailbox_id, token, checkpoint)
            return count
        finally:
            self.repository.release_sync(mailbox_id, token)
