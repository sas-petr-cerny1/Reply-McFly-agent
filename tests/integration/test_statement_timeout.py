import os

import pytest
from sqlalchemy import text

from reply_mcfly.adapters.postgres_adapter import make_engine

pytestmark = pytest.mark.integration


@pytest.mark.parametrize(("timeout_ms", "expected"), [(3000, "3s"), (None, "0")])
def test_statement_timeout_applies_to_requests_but_not_migrations(
    timeout_ms: int | None, expected: str
) -> None:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.fail("TEST_DATABASE_URL is required")
    engine = make_engine(url, statement_timeout_ms=timeout_ms)
    try:
        with engine.connect() as connection:
            assert connection.execute(text("SHOW statement_timeout")).scalar_one() == expected
    finally:
        engine.dispose()


def test_request_engine_keeps_the_default_limit() -> None:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.fail("TEST_DATABASE_URL is required")
    engine = make_engine(url)
    try:
        with engine.connect() as connection:
            assert connection.execute(text("SHOW statement_timeout")).scalar_one() == "3s"
    finally:
        engine.dispose()
