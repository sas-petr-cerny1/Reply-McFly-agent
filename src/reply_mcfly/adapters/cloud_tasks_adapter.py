import hashlib
import json
from uuid import UUID

from google.api_core.exceptions import AlreadyExists, GoogleAPICallError
from google.cloud import tasks_v2
from google.protobuf.duration_pb2 import Duration

from reply_mcfly.domain.email import WorkflowError


class CloudTasksAdapter:
    def __init__(
        self,
        project: str,
        location: str,
        sync_queue: str,
        process_queue: str,
        worker_url: str,
        service_account: str,
    ) -> None:
        self.project, self.location = project, location
        self.sync_queue, self.process_queue = sync_queue, process_queue
        self.worker_url, self.service_account = worker_url.rstrip("/"), service_account
        if not self.worker_url.startswith("https://"):
            raise ValueError("Cloud Tasks requires an HTTPS Worker URL")

    def _enqueue(self, queue: str, name: str, path: str, payload: dict[str, str]) -> None:
        parent = tasks_v2.CloudTasksClient.queue_path(self.project, self.location, queue)
        task = tasks_v2.Task(
            name=f"{parent}/tasks/{name}",
            dispatch_deadline=Duration(seconds=110),
            http_request=tasks_v2.HttpRequest(
                http_method=tasks_v2.HttpMethod.POST,
                url=self.worker_url + path,
                headers={"Content-Type": "application/json"},
                body=json.dumps(payload).encode(),
                oidc_token=tasks_v2.OidcToken(
                    service_account_email=self.service_account,
                    audience=self.worker_url,
                ),
            ),
        )
        try:
            with tasks_v2.CloudTasksClient() as client:
                client.create_task(request={"parent": parent, "task": task}, timeout=10, retry=None)
        except AlreadyExists:
            return
        except GoogleAPICallError:
            raise WorkflowError("TASK_QUEUE_UNAVAILABLE", retryable=True, status=503) from None

    def sync(self, mailbox_id: str, event_id: str) -> None:
        name = hashlib.sha256(f"{mailbox_id}\0{event_id}".encode()).hexdigest()
        self._enqueue(self.sync_queue, f"sync-{name}", "/tasks/sync", {"mailbox_id": mailbox_id})

    def process(self, job_id: UUID) -> None:
        self._enqueue(
            self.process_queue, f"process-{job_id}", "/tasks/process", {"job_id": str(job_id)}
        )
