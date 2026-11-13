from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from reply_mcfly.config.settings import Settings
from reply_mcfly.domain.email import (
    IncomingEmail,
    Job,
    MessageMetadata,
    Status,
    WorkflowError,
    validate_recipient,
)
from reply_mcfly.domain.sender_policy import SenderConfigurationError, parse_sender_policy

MAILBOX = "agent@agent.invalid"


def test_single_sender_allowlist_permits_only_that_address() -> None:
    policy = parse_sender_policy(frozenset({"User@Customer.invalid"}), MAILBOX)
    assert policy.permits_sender("user@customer.invalid")
    assert not policy.permits_sender("other@customer.invalid")


def test_multiple_senders_allowlist() -> None:
    policy = parse_sender_policy(
        frozenset({"one@customer.invalid", "two@customer.invalid"}),
        MAILBOX,
    )
    assert policy.permits_sender("one@customer.invalid")
    assert policy.permits_sender("two@customer.invalid")
    assert not policy.permits_sender("three@customer.invalid")


def test_wildcard_permits_any_external_address() -> None:
    policy = parse_sender_policy(frozenset({"*"}), MAILBOX)
    assert policy.allow_all
    assert policy.permits_sender("stranger@example.com")


def test_assistant_mailbox_never_permitted_even_in_wildcard_mode() -> None:
    email = IncomingEmail(
        MessageMetadata("a1", "b1", datetime.now(UTC), frozenset({"INBOX", "UNREAD"})),
        MAILBOX,
        "Subject",
        "<mid@invalid>",
        "",
        "Body",
    )
    job = Job(
        uuid4(),
        MAILBOX,
        "a1",
        "b1",
        email.metadata.received_at,
        Status.PROCESSING,
        None,
        None,
        0,
    )
    policy = parse_sender_policy(frozenset({"*"}), MAILBOX)
    with pytest.raises(WorkflowError, match="RECIPIENT_REQUIRES_REVIEW"):
        validate_recipient(job, email, policy)


def test_mailbox_in_allowlist_rejected() -> None:
    with pytest.raises(SenderConfigurationError, match="MAILBOX_IN_ALLOWLIST"):
        parse_sender_policy(frozenset({MAILBOX}), MAILBOX)


def test_wildcard_with_address_rejected_by_parser() -> None:
    with pytest.raises(SenderConfigurationError, match="WILDCARD_NOT_EXCLUSIVE"):
        parse_sender_policy(frozenset({"*", "user@customer.invalid"}), MAILBOX)


def test_wildcard_with_address_rejected_in_settings() -> None:
    with pytest.raises(ValidationError):
        Settings(allowed_senders=frozenset({"*", "user@customer.invalid"}))


def test_empty_allowlist_rejected_by_parser() -> None:
    with pytest.raises(SenderConfigurationError, match="EMPTY_ALLOWED_SENDERS"):
        parse_sender_policy(frozenset(), MAILBOX)


def test_malformed_sender_rejected_by_settings() -> None:
    with pytest.raises(ValidationError):
        Settings(allowed_senders=frozenset({"not-an-email"}))


def test_settings_loads_wildcard_from_json_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MCFLY_ALLOWED_SENDERS", '["*"]')
    assert Settings().allowed_senders == frozenset({"*"})


def test_unauthorized_sender_in_allowlist_mode() -> None:
    policy = parse_sender_policy(frozenset({"allowed@customer.invalid"}), MAILBOX)
    email = IncomingEmail(
        MessageMetadata("a1", "b1", datetime.now(UTC), frozenset({"INBOX", "UNREAD"})),
        "blocked@customer.invalid",
        "Subject",
        "<mid@invalid>",
        "",
        "Body",
    )
    job = Job(
        uuid4(),
        MAILBOX,
        "a1",
        "b1",
        email.metadata.received_at,
        Status.PROCESSING,
        None,
        None,
        0,
    )
    with pytest.raises(WorkflowError, match="RECIPIENT_REQUIRES_REVIEW"):
        validate_recipient(job, email, policy)


def test_automatic_message_rejected() -> None:
    policy = parse_sender_policy(frozenset({"*"}), MAILBOX)
    email = IncomingEmail(
        MessageMetadata("a1", "b1", datetime.now(UTC), frozenset({"INBOX", "UNREAD"})),
        "sender@customer.invalid",
        "Subject",
        "<mid@invalid>",
        "",
        "Body",
        automatic=True,
    )
    job = Job(
        uuid4(),
        MAILBOX,
        "a1",
        "b1",
        email.metadata.received_at,
        Status.PROCESSING,
        None,
        None,
        0,
    )
    with pytest.raises(WorkflowError, match="RECIPIENT_REQUIRES_REVIEW"):
        validate_recipient(job, email, policy)
