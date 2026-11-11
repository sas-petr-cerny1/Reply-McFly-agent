import os
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, insert, select, update
from sqlalchemy.engine import Engine

from reply_mcfly.adapters.postgres_adapter import (
    EmailJobModel,
    EmailOutboxModel,
    MailboxSyncState,
    PostgresEmailRepository,
    make_engine,
)
from reply_mcfly.domain.email import MessageMetadata, Status, WorkflowError

pytestmark = pytest.mark.integration


class Harness:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine
        self.mailbox = f"{uuid4()}@agent.invalid"
        self.repository = PostgresEmailRepository(engine)
        with engine.begin() as connection:
            connection.execute(
                insert(MailboxSyncState).values(mailbox_id=self.mailbox, history_id="100")
            )

    def enqueue(self) -> UUID:
        return self.repository.enqueue(
            self.mailbox,
            MessageMetadata("a1", "b1", datetime.now(UTC), frozenset({"INBOX", "UNREAD"})),
        )


@pytest.fixture
def harness() -> Iterator[Harness]:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.fail("TEST_DATABASE_URL is required")
    engine = make_engine(url)
    harness = Harness(engine)
    try:
        yield harness
    finally:
        with engine.begin() as connection:
            ids = select(EmailJobModel.id).where(EmailJobModel.mailbox_id == harness.mailbox)
            connection.execute(delete(EmailOutboxModel).where(EmailOutboxModel.job_id.in_(ids)))
            connection.execute(
                delete(EmailJobModel).where(EmailJobModel.mailbox_id == harness.mailbox)
            )
            connection.execute(
                delete(MailboxSyncState).where(MailboxSyncState.mailbox_id == harness.mailbox)
            )
        engine.dispose()


def test_stale_worker_cannot_prepare_reply(harness: Harness) -> None:
    job_id = harness.enqueue()
    old = harness.repository.claim(job_id, uuid4())
    with pytest.raises(WorkflowError, match="JOB_BUSY"):
        harness.repository.claim(job_id, uuid4())
    with harness.engine.begin() as connection:
        connection.execute(
            update(EmailJobModel)
            .where(EmailJobModel.id == job_id)
            .values(lease_until=datetime.now(UTC) - timedelta(seconds=1))
        )
    new = harness.repository.claim(job_id, uuid4())
    assert new.lease_token != old.lease_token
    with pytest.raises(WorkflowError, match="LEASE_LOST"):
        harness.repository.transition(old, Status.READY_TO_SEND)


def test_mailbox_lease_is_exclusive(harness: Harness) -> None:
    token = uuid4()
    assert harness.repository.acquire_sync(harness.mailbox, token) == "100"
    with pytest.raises(WorkflowError, match="SYNC_BUSY"):
        harness.repository.acquire_sync(harness.mailbox, uuid4())
    harness.repository.release_sync(harness.mailbox, uuid4())
    with pytest.raises(WorkflowError, match="SYNC_BUSY"):
        harness.repository.acquire_sync(harness.mailbox, uuid4())
    harness.repository.release_sync(harness.mailbox, token)
    assert harness.repository.acquire_sync(harness.mailbox, uuid4()) == "100"


def test_concurrent_workers_have_only_one_owner(harness: Harness) -> None:
    job_id = harness.enqueue()

    def claim() -> str:
        try:
            harness.repository.claim(job_id, uuid4())
            return "CLAIMED"
        except WorkflowError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: claim(), range(2)))
    assert sorted(results) == ["CLAIMED", "JOB_BUSY"]


def test_repository_deduplicates_jobs(harness: Harness) -> None:
    assert harness.enqueue() == harness.enqueue()
