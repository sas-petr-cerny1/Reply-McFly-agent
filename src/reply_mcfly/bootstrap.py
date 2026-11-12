from datetime import UTC, datetime

from reply_mcfly.adapters.gmail_adapter import GmailAdapter
from reply_mcfly.adapters.google_clients import GmailServiceFactory
from reply_mcfly.adapters.postgres_adapter import PostgresEmailRepository, make_engine
from reply_mcfly.config.settings import Settings
from reply_mcfly.domain.sender_policy import SenderConfigurationError, parse_sender_policy


def main() -> None:
    settings = Settings()
    if not all(
        (
            settings.mailbox_id,
            settings.allowed_senders,
            settings.gmail_oauth_secret_version,
            settings.ingress_audience,
            settings.worker_url,
            settings.pubsub_service_account,
        )
    ):
        raise RuntimeError(
            "Configure OAuth, dedicated mailbox, sender allowlist and notification endpoints first"
        )
    try:
        parse_sender_policy(settings.allowed_senders, settings.mailbox_id)
    except SenderConfigurationError as error:
        raise RuntimeError("Invalid MCFLY_ALLOWED_SENDERS configuration for bootstrap") from error
    gmail = GmailAdapter(
        GmailServiceFactory(settings.gmail_oauth_secret_version), settings.mailbox_id
    )
    engine = make_engine(settings.sqlalchemy_url())
    try:
        repository = PostgresEmailRepository(engine)
        # Persist the baseline first, preserving messages arriving during watch setup.
        repository.initialize(settings.mailbox_id, gmail.profile_history(), None)
        watch = gmail.watch(settings.gmail_topic)
        repository.initialize(
            settings.mailbox_id,
            watch.historyId,
            datetime.fromtimestamp(int(watch.expiration) / 1000, UTC),
        )
        print("Gmail Watch configured. Existing synchronization checkpoint preserved.")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
