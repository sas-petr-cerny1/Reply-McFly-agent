from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from reply_mcfly import bootstrap
from reply_mcfly.config.settings import Settings


def test_mailbox_id_is_normalized_once_in_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MCFLY_MAILBOX_ID", "  Agent@Example.Invalid ")

    assert Settings().mailbox_id == "agent@example.invalid"


def test_bootstrap_stores_the_same_mailbox_key_the_worker_reads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MCFLY_MAILBOX_ID", "Agent@Example.Invalid")
    monkeypatch.setenv("MCFLY_ALLOWED_SENDERS", '["sender@customer.invalid"]')
    monkeypatch.setenv("MCFLY_GMAIL_OAUTH_SECRET_VERSION", "projects/p/secrets/s/versions/1")
    monkeypatch.setenv("MCFLY_INGRESS_AUDIENCE", "https://ingress.invalid")
    monkeypatch.setenv("MCFLY_WORKER_URL", "https://worker.invalid")
    monkeypatch.setenv("MCFLY_PUBSUB_SERVICE_ACCOUNT", "pubsub@project.invalid")
    monkeypatch.setenv("MCFLY_DATABASE_URL", "postgresql+psycopg://u:p@db.invalid/mcfly")
    repository = MagicMock()
    with (
        patch.object(bootstrap, "GmailAdapter") as gmail_factory,
        patch.object(bootstrap, "GmailServiceFactory"),
        patch.object(bootstrap, "make_engine"),
        patch.object(bootstrap, "PostgresEmailRepository", return_value=repository),
    ):
        gmail = gmail_factory.return_value
        gmail.profile_history.return_value = "100"
        gmail.watch.return_value.historyId = "100"
        gmail.watch.return_value.expiration = "1700000000000"
        bootstrap.main()

    assert gmail_factory.call_args.args[1] == "agent@example.invalid"
    stored = [call.args for call in repository.initialize.call_args_list]
    assert [args[0] for args in stored] == ["agent@example.invalid"] * 2
    assert isinstance(stored[1][2], datetime)
