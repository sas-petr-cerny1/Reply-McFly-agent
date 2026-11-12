import time
from uuid import uuid4

from reply_mcfly.application.telemetry import emit
from reply_mcfly.domain.email import WorkflowError, incoming
from reply_mcfly.ports.email import EmailRepository, GmailPort, TaskQueuePort


class GmailSyncService:
    def __init__(self, repository: EmailRepository, gmail: GmailPort, queue: TaskQueuePort) -> None:
        self.repository, self.gmail, self.queue = repository, gmail, queue

    def sync(self, mailbox_id: str) -> int:
        token = uuid4()
        start = self.repository.acquire_sync(mailbox_id, token)
        deadline = time.monotonic() + 100
        count = 0
        checkpoint = start
        try:
            for page in self.gmail.history(start):
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
            # Queue failure leaves the old checkpoint, so redelivery discovers the jobs again.
            self.repository.checkpoint(mailbox_id, token, checkpoint)
            return count
        finally:
            self.repository.release_sync(mailbox_id, token)
