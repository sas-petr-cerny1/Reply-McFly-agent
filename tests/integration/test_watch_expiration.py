import os
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import delete
from sqlalchemy.engine import Engine

from reply_mcfly.adapters.postgres_adapter import (
    MailboxSyncState,
    PostgresEmailRepository,
    make_engine,
)

pytestmark = pytest.mark.integration


@pytest.fixture
def engine() -> Iterator[Engine]:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.fail("TEST_DATABASE_URL is required")
    engine = make_engine(url)
    yield engine
    engine.dispose()


def test_watch_expiration_is_stored_and_renewed_without_moving_the_checkpoint(
    engine: Engine,
) -> None:
    mailbox = f"{uuid4()}@agent.invalid"
    repository = PostgresEmailRepository(engine)
    first = datetime.now(UTC).replace(microsecond=0) + timedelta(days=1)
    renewed = first + timedelta(days=6)
    try:
        assert repository.watch_expiration(mailbox) is None
        repository.initialize(mailbox, "100", first)
        assert repository.watch_expiration(mailbox) == first
        repository.initialize(mailbox, "999", renewed)
        assert repository.watch_expiration(mailbox) == renewed
        assert repository.acquire_sync(mailbox, uuid4()) == "100"
    finally:
        with engine.begin() as connection:
            connection.execute(
                delete(MailboxSyncState).where(MailboxSyncState.mailbox_id == mailbox)
            )
