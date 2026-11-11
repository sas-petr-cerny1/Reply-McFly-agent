from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from reply_mcfly.adapters.gmail_adapter import GmailAdapter
from reply_mcfly.bootstrap import main
from reply_mcfly.config.settings import Settings
from reply_mcfly.domain.email import WorkflowError


def test_bootstrap_persists_baseline_before_watch() -> None:
    settings = Settings(
        database_url="postgresql+psycopg://synthetic:synthetic@localhost/test",
        mailbox_id="agent@synthetic.invalid",
        allowed_senders=frozenset({"sender@synthetic.invalid"}),
        gmail_oauth_secret_version="projects/synthetic/secrets/oauth/versions/1",
        ingress_audience="https://ingress.invalid",
        worker_url="https://worker.invalid",
        pubsub_service_account="pubsub@synthetic.iam.gserviceaccount.com",
    )
    events: list[str] = []
    with (
        patch("reply_mcfly.bootstrap.Settings", return_value=settings),
        patch("reply_mcfly.bootstrap.GmailAdapter") as gmail_factory,
        patch("reply_mcfly.bootstrap.make_engine") as engine_factory,
        patch("reply_mcfly.bootstrap.PostgresEmailRepository") as repo_factory,
    ):
        gmail = gmail_factory.return_value
        gmail.profile_history.return_value = "100"

        def watch(topic: str) -> MagicMock:
            events.append("watch")
            return MagicMock(historyId="200", expiration="2000000000000")

        gmail.watch.side_effect = watch
        repository = repo_factory.return_value
        repository.initialize.side_effect = lambda *args: events.append("initialize")
        main()
        assert events == ["initialize", "watch", "initialize"]
        assert repository.initialize.call_args_list[0].args == (settings.mailbox_id, "100", None)
        assert repository.initialize.call_args_list[1].args == (
            settings.mailbox_id,
            "200",
            datetime.fromtimestamp(2000000000, UTC),
        )
        gmail.watch.assert_called_once_with(settings.gmail_topic)
        engine_factory.return_value.dispose.assert_called_once()


def test_incomplete_bootstrap_never_contacts_google() -> None:
    with (
        patch("reply_mcfly.bootstrap.Settings", return_value=Settings(mailbox_id="")),
        patch("reply_mcfly.bootstrap.GmailAdapter") as factory,
    ):
        with pytest.raises(RuntimeError, match="Configure OAuth"):
            main()
        factory.assert_not_called()


def test_watch_uses_existing_topic_and_inbox_filter() -> None:
    service = MagicMock()
    service.users.return_value.getProfile.return_value.execute.return_value = {
        "emailAddress": "agent@synthetic.invalid",
        "historyId": "100",
    }
    service.users.return_value.watch.return_value.execute.return_value = {
        "historyId": "200",
        "expiration": "2000000000000",
    }
    adapter = GmailAdapter(lambda: service, "agent@synthetic.invalid")
    assert adapter.profile_history() == "100"
    result = adapter.watch("projects/synthetic/topics/existing-topic")
    assert result.historyId == "200"
    service.users.return_value.watch.assert_called_once_with(
        userId="me",
        body={
            "topicName": "projects/synthetic/topics/existing-topic",
            "labelIds": ["INBOX"],
            "labelFilterBehavior": "include",
        },
    )
    service.users.return_value.watch.return_value.execute.return_value = {
        "historyId": "invalid",
        "expiration": "1",
    }
    with pytest.raises(WorkflowError, match="INVALID_GMAIL_WATCH"):
        adapter.watch("projects/synthetic/topics/existing-topic")
