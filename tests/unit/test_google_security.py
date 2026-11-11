import json
from collections.abc import Callable
from http.client import BadStatusLine, HTTPConnection
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from google.api_core.exceptions import AlreadyExists

from reply_mcfly.adapters.cloud_tasks_adapter import CloudTasksAdapter
from reply_mcfly.adapters.google_clients import OneShotHttp


def test_ambiguous_http_response_does_not_trigger_hidden_resend() -> None:
    connection = MagicMock(spec=HTTPConnection)
    connection.sock = object()
    connection.getresponse.side_effect = BadStatusLine("connection closed after request")
    with pytest.raises(BadStatusLine):
        OneShotHttp(timeout=10)._conn_request(connection, "/send", "POST", b"synthetic", {})
    assert connection.request.call_count == 1
    connection.close.assert_called_once()


def test_cloud_tasks_names_are_stable_and_payloads_contain_only_ids() -> None:
    queue = CloudTasksAdapter(
        "synthetic-project",
        "europe-west1",
        "sync-queue",
        "process-queue",
        "https://worker.invalid",
        "tasks@project.iam.gserviceaccount.com",
    )
    job_id = uuid4()
    with patch("reply_mcfly.adapters.cloud_tasks_adapter.tasks_v2.CloudTasksClient") as factory:
        client = factory.return_value.__enter__.return_value
        queue.process(job_id)
        first = client.create_task.call_args.kwargs["request"]["task"]
        queue.process(job_id)
        second = client.create_task.call_args.kwargs["request"]["task"]
        assert first.name == second.name
        assert json.loads(first.http_request.body) == {"job_id": str(job_id)}
        assert first.http_request.oidc_token.audience == "https://worker.invalid"
        assert (
            first.http_request.oidc_token.service_account_email
            == "tasks@project.iam.gserviceaccount.com"
        )
        duplicate: Callable[[str], AlreadyExists] = AlreadyExists
        client.create_task.side_effect = duplicate("synthetic duplicate")
        queue.process(job_id)
