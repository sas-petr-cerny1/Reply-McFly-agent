import time
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
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

# Gmail Watch lives for 7 days; renew well before that so a quiet weekend cannot expire it.
WATCH_RENEWAL_MARGIN = timedelta(days=3)


class GmailSyncService:
    def __init__(
        self,
        repository: EmailRepository,
        gmail: GmailPort,
        queue: TaskQueuePort,
        *,
        maintenance: MailboxMaintenancePort | None = None,
        watch_topic: str = "",
    ) -> None:
        self.repository, self.gmail, self.queue = repository, gmail, queue
        self.maintenance, self.watch_topic = maintenance, watch_topic

    def _renew_watch(self, mailbox_id: str, history_id: str) -> None:
        if self.maintenance is None or not self.watch_topic:
            return
        expiration = self.repository.watch_expiration(mailbox_id)
        if expiration is not None and expiration - datetime.now(UTC) > WATCH_RENEWAL_MARGIN:
            return
        try:
            renewed = self.maintenance.renew_watch(self.watch_topic)
        except WorkflowError as error:
            # Renewal is opportunistic; the next sync retries it and mail must still flow.
            emit("watch_renewal_failed", error_code=error.code)
            return
        self.repository.initialize(mailbox_id, history_id, renewed)
        emit("watch_renewed")

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
            self._renew_watch(mailbox_id, start)
            for page in self._pages(start):
                for message_id in page.message_ids:
                    if time.monotonic() + 10 > deadline:
                        raise WorkflowError("DEPENDENCY_TIMEOUT", retryable=True, status=503)
                    metadata = self.gmail.metadata(message_id)
                    if incoming(metadata):
                        job_id = self.repository.enqueue(mailbox_id, metadata)
                        self.queue.process(job_id)
                        count += 1
                checkpoint = page.history_id
            # Queue failure leaves the old checkpoint, so redelivery discovers the jobs again.
            self.repository.checkpoint(mailbox_id, token, checkpoint)
            return count
        finally:
            self.repository.release_sync(mailbox_id, token)
