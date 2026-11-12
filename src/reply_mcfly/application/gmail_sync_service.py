import time
from uuid import uuid4

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
                    metadata = self.gmail.metadata(message_id)
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
