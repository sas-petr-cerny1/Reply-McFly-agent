import os
from collections.abc import Iterator
from uuid import uuid4

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from reply_mcfly.adapters.postgres_adapter import MailboxSyncState, PostgresAdapter, make_engine
from reply_mcfly.api.health import create_app
from reply_mcfly.application.diagnostics import DiagnosticsService

pytestmark = pytest.mark.integration


@pytest.fixture
def engine() -> Iterator[Engine]:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.fail("Set TEST_DATABASE_URL to an isolated PostgreSQL test database")
    engine = make_engine(url)
    yield engine
    engine.dispose()


@pytest.fixture
def mailbox_id(engine: Engine) -> Iterator[str]:
    mailbox_id = f"{uuid4()}@smoke.invalid"
    yield mailbox_id
    with engine.begin() as connection:
        connection.execute(
            delete(MailboxSyncState).where(MailboxSyncState.mailbox_id == mailbox_id)
        )


def test_migration_schema_and_vector_operation(engine: Engine) -> None:
    assert "mailbox_sync_state" in inspect(engine).get_table_names()
    with engine.connect() as connection:
        assert (
            connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
            == ScriptDirectory.from_config(Config("alembic.ini")).get_current_head()
        )
        distance = connection.execute(
            text("SELECT '[1,2,3]'::vector <-> '[1,2,3]'::vector")
        ).scalar_one()
        assert distance == 0


def test_committed_record_survives_new_connection(engine: Engine, mailbox_id: str) -> None:
    DiagnosticsService(PostgresAdapter(engine)).create_test_mailbox(mailbox_id)
    engine.dispose()
    DiagnosticsService(PostgresAdapter(engine)).verify_test_mailbox(mailbox_id)


def test_duplicate_mailbox_is_rejected(engine: Engine, mailbox_id: str) -> None:
    store = PostgresAdapter(engine)
    store.create_mailbox(mailbox_id)
    with pytest.raises(IntegrityError):
        store.create_mailbox(mailbox_id)
    assert store.mailbox_exists(mailbox_id)


@pytest.mark.parametrize("service_name", ["ingress", "worker"])
def test_health_with_real_postgres(service_name: str, monkeypatch: pytest.MonkeyPatch) -> None:
    # Both app entrypoints use this same factory; exercise their production configuration.
    from reply_mcfly.api.ingress import create_ingress
    from reply_mcfly.api.worker import create_worker

    monkeypatch.setenv("MCFLY_DATABASE_URL", os.environ["TEST_DATABASE_URL"])
    app = create_ingress() if service_name == "ingress" else create_worker()
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": service_name, "database": "ok"}


def test_health_rejects_unmigrated_database(engine: Engine) -> None:
    # An isolated search_path models an empty database without altering migrated tables.
    empty_engine = create_engine(engine.url, connect_args={"options": "-c search_path=nonexistent"})
    try:
        app = create_app("worker", DiagnosticsService(PostgresAdapter(empty_engine)))
        with TestClient(app) as client:
            response = client.get("/health")
        assert response.status_code == 503
        assert "mailbox_sync_state" not in response.text
    finally:
        empty_engine.dispose()
