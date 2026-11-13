import os
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy import delete, select

from reply_mcfly import bootstrap
from reply_mcfly.adapters.postgres_adapter import (
    MailboxSyncState,
    PostgresEmailRepository,
    make_engine,
)

pytestmark = pytest.mark.integration


def _run_bootstrap(
    monkeypatch: pytest.MonkeyPatch, mailbox: str, history_id: str, expiration: datetime
) -> None:
    monkeypatch.setenv("MCFLY_MAILBOX_ID", mailbox)
    monkeypatch.setenv("MCFLY_ALLOWED_SENDERS", '["sender@customer.invalid"]')
    monkeypatch.setenv("MCFLY_GMAIL_OAUTH_SECRET_VERSION", "projects/p/secrets/s/versions/1")
    monkeypatch.setenv("MCFLY_INGRESS_AUDIENCE", "https://ingress.invalid")
    monkeypatch.setenv("MCFLY_WORKER_URL", "https://worker.invalid")
    monkeypatch.setenv("MCFLY_PUBSUB_SERVICE_ACCOUNT", "pubsub@project.invalid")
    monkeypatch.setenv("MCFLY_DATABASE_URL", os.environ["TEST_DATABASE_URL"])
    with (
        patch.object(bootstrap, "GmailAdapter") as gmail_factory,
        patch.object(bootstrap, "GmailServiceFactory"),
    ):
        gmail = gmail_factory.return_value
        gmail.profile_history.return_value = history_id
        gmail.watch.return_value = MagicMock(
            historyId=history_id, expiration=str(int(expiration.timestamp() * 1000))
        )
        bootstrap.main()
        gmail.watch.assert_called_once()


def test_daily_bootstrap_renews_the_watch_and_keeps_the_sync_checkpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if not os.environ.get("TEST_DATABASE_URL"):
        pytest.fail("TEST_DATABASE_URL is required")
    engine = make_engine(os.environ["TEST_DATABASE_URL"])
    mailbox = f"{uuid4()}@agent.invalid"
    repository = PostgresEmailRepository(engine)
    first = datetime(2026, 11, 19, 12, 0, tzinfo=UTC)
    renewed = datetime(2026, 11, 20, 12, 0, tzinfo=UTC)

    def state() -> tuple[str | None, datetime | None]:
        with engine.connect() as connection:
            row = connection.execute(
                select(MailboxSyncState.history_id, MailboxSyncState.watch_expiration).where(
                    MailboxSyncState.mailbox_id == mailbox
                )
            ).one()
        return row[0], row[1]

    try:
        _run_bootstrap(monkeypatch, mailbox, "1000", first)
        assert state() == ("1000", first)

        # The Worker has synchronized further than the first baseline.
        token = uuid4()
        repository.acquire_sync(mailbox, token)
        repository.checkpoint(mailbox, token, "1500")
        repository.release_sync(mailbox, token)

        # The next scheduled run sees a much newer Gmail history id.
        _run_bootstrap(monkeypatch, mailbox, "9000", renewed)

        assert state() == ("1500", renewed)
    finally:
        with engine.begin() as connection:
            connection.execute(
                delete(MailboxSyncState).where(MailboxSyncState.mailbox_id == mailbox)
            )
        engine.dispose()
