import json
import logging

import pytest
from fastapi.testclient import TestClient

from reply_mcfly.api.health import create_app
from reply_mcfly.application.diagnostics import DiagnosticsService


class FakeStore:
    def check_health(self) -> None:
        pass

    def create_mailbox(self, mailbox_id: str) -> None:
        pass

    def mailbox_exists(self, mailbox_id: str) -> bool:
        return False


def test_failed_request_is_logged_with_the_correlation_id_returned_to_the_caller(
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = logging.getLogger("reply_mcfly.workflow")
    logger.addHandler(caplog.handler)
    try:
        with TestClient(create_app("worker", DiagnosticsService(FakeStore()))) as client:
            response = client.post("/tasks/process", json={})
    finally:
        logger.removeHandler(caplog.handler)

    assert response.status_code == 401
    correlation_id = response.json()["error"]["correlation_id"]
    events = [json.loads(record.getMessage()) for record in caplog.records]
    failures = [event for event in events if event["event"] == "request_failed"]
    assert failures == [
        {
            "timestamp": failures[0]["timestamp"],
            "event": "request_failed",
            "job_id": None,
            "correlation_id": correlation_id,
            "status": "401",
            "error_code": "UNAUTHORIZED",
            "duration_seconds": None,
            "path": "/tasks/process",
        }
    ]
