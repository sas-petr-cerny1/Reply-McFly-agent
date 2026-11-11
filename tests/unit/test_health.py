from typing import Literal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from reply_mcfly.api.health import create_app
from reply_mcfly.application.diagnostics import DiagnosticsService


class FakeStore:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.mailboxes: set[str] = set()

    def check_health(self) -> None:
        if self.error:
            raise self.error

    def create_mailbox(self, mailbox_id: str) -> None:
        self.mailboxes.add(mailbox_id)

    def mailbox_exists(self, mailbox_id: str) -> bool:
        return mailbox_id in self.mailboxes


@pytest.mark.parametrize("service_name", ["ingress", "worker"])
def test_health_contract(service_name: Literal["ingress", "worker"]) -> None:
    app = create_app(service_name, DiagnosticsService(FakeStore()))
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": service_name, "database": "ok"}


@pytest.mark.parametrize(
    "error",
    [
        RuntimeError("internal schema detail"),
        OperationalError("private SQL", {}, Exception("secret")),
    ],
)
def test_database_failure_returns_503_without_internal_details(error: Exception) -> None:
    app = create_app("worker", DiagnosticsService(FakeStore(error)))
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 503
    assert response.json() == {
        "status": "unavailable",
        "service": "worker",
        "database": "unavailable",
    }
    assert "secret" not in response.text
    assert "schema" not in response.text


def test_smoke_only_creates_synthetic_mailboxes() -> None:
    store = FakeStore()
    service = DiagnosticsService(store)
    with pytest.raises(ValueError, match="synthetic"):
        service.create_test_mailbox("customer@example.com")
    assert not store.mailboxes


def test_smoke_verifies_read_after_write_and_missing_record() -> None:
    service = DiagnosticsService(FakeStore())
    service.create_test_mailbox("test@smoke.invalid")
    service.verify_test_mailbox("test@smoke.invalid")
    with pytest.raises(RuntimeError, match="not found"):
        service.verify_test_mailbox("missing@smoke.invalid")
