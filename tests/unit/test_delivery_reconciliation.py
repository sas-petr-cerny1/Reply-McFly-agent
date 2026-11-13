import base64
from datetime import UTC, datetime
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from typing import Any
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from reply_mcfly.adapters.gmail_adapter import JOB_HEADER, GmailAdapter, encode_reply
from reply_mcfly.domain.email import Job, OutboxEntry, Status, WorkflowError
from reply_mcfly.domain.reply_templates import FALLBACK_MISSING_INFORMATION

MAILBOX = "agent@agent.invalid"
# One body per transfer encoding the standard library picks for outgoing replies.
BODIES = {
    "7bit": "Reply body\nsecond line",
    "8bit": "Dobrý den,\n\nděkujeme",
    "quoted-printable": "> - **Deductible:** "
    + "long knowledge base line " * 6
    + "500 Kč.\n> next",
    "base64": FALLBACK_MISSING_INFORMATION,
}


def _job() -> Job:
    return Job(
        uuid4(), MAILBOX, "a1", "b1", datetime.now(UTC), Status.DELIVERY_UNKNOWN, uuid4(), None, 1
    )


def _entry(job: Job, body: str = "Reply body\nsecond line") -> OutboxEntry:
    return OutboxEntry(
        job.id,
        "<outgoing@agent.invalid>",
        "sender@customer.invalid",
        "Synthetic question",
        body,
        "<original@customer.invalid>",
        "<original@customer.invalid>",
    )


def _stored(job: Job, entry: OutboxEntry, **headers: str | None) -> str:
    """The reply as Gmail stores it, optionally with headers rewritten or removed."""
    message = BytesParser(policy=policy.default).parsebytes(
        base64.urlsafe_b64decode(encode_reply(job, entry))
    )
    assert isinstance(message, EmailMessage)
    for name, value in headers.items():
        header = name.replace("_", "-")
        del message[header]
        if value is not None:
            message[header] = value
    return base64.urlsafe_b64encode(message.as_bytes(policy=policy.SMTP)).decode("ascii")


def _gmail(
    messages: dict[str, dict[str, Any]], thread_id: str = "b1"
) -> tuple[GmailAdapter, MagicMock]:
    """Gmail with one thread; ``messages`` maps id to {"labelIds": [...], "raw": ...}."""
    service = MagicMock()
    users = service.users.return_value
    users.getProfile.return_value.execute.return_value = {"emailAddress": MAILBOX}
    users.threads.return_value.get.return_value.execute.return_value = {
        "id": thread_id,
        "messages": [
            {"id": identifier, "threadId": thread_id, "labelIds": item["labelIds"]}
            for identifier, item in messages.items()
        ],
    }

    def get(*, userId: str, id: str, format: str) -> MagicMock:
        request = MagicMock()
        request.execute.return_value = {
            "id": id,
            "threadId": messages[id].get("threadId", thread_id),
            "internalDate": "1700000000000",
            **messages[id],
        }
        return request

    users.messages.return_value.get.side_effect = get
    return GmailAdapter(lambda: service, MAILBOX), service


def _adapter(messages: dict[str, dict[str, Any]]) -> GmailAdapter:
    return _gmail(messages)[0]


@pytest.mark.parametrize("body", BODIES.values(), ids=BODIES.keys())
def test_delivered_reply_is_confirmed_for_every_transfer_encoding(body: str) -> None:
    job = _job()
    entry = _entry(job, body)
    adapter = _adapter({"c1": {"labelIds": ["SENT"], "raw": encode_reply(job, entry)}})

    assert adapter.find_sent(job, entry) == "c1"


def test_reply_is_confirmed_even_when_gmail_replaced_its_message_id() -> None:
    job = _job()
    entry = _entry(job)
    raw = _stored(job, entry, Message_ID="<CAxyz-rewritten@mail.gmail.com>")
    adapter = _adapter(
        {
            "a1": {"labelIds": ["INBOX", "UNREAD"], "raw": "ignored"},
            "c1": {"labelIds": ["SENT"], "raw": raw},
        }
    )

    assert adapter.find_sent(job, entry) == "c1"


def test_original_message_id_still_confirms_a_reply_without_the_job_header() -> None:
    job = _job()
    entry = _entry(job)
    adapter = _adapter(
        {"c1": {"labelIds": ["SENT"], "raw": _stored(job, entry, **{JOB_HEADER: None})}}
    )

    assert adapter.find_sent(job, entry) == "c1"


@pytest.mark.parametrize(
    "changed",
    [
        {"Message_ID": "<other@mail.gmail.com>", JOB_HEADER: str(uuid4())},
        {"Message_ID": "<other@mail.gmail.com>", JOB_HEADER: None},
        {"To": "attacker@other.invalid"},
        {"In_Reply_To": "<another@customer.invalid>"},
        {"Subject": "Different subject"},
    ],
    ids=["other-job", "no-identity", "other-recipient", "other-parent", "other-subject"],
)
def test_other_message_sent_in_the_thread_is_not_taken_for_the_reply(
    changed: dict[str, str | None],
) -> None:
    job = _job()
    entry = _entry(job)
    adapter = _adapter({"c1": {"labelIds": ["SENT"], "raw": _stored(job, entry, **changed)}})

    assert adapter.find_sent(job, entry) is None


def test_different_body_is_not_confirmed() -> None:
    job = _job()
    entry = _entry(job)
    sent = encode_reply(job, _entry(job, "Different content"))

    assert _adapter({"c1": {"labelIds": ["SENT"], "raw": sent}}).find_sent(job, entry) is None


def test_nothing_sent_in_the_thread_means_not_delivered() -> None:
    job = _job()
    adapter, service = _gmail({"a1": {"labelIds": ["INBOX", "UNREAD"], "raw": "ignored"}})

    assert adapter.find_sent(job, _entry(job)) is None
    service.users.return_value.messages.return_value.get.assert_not_called()


def test_unparseable_message_sent_by_a_person_is_skipped() -> None:
    job = _job()
    entry = _entry(job)
    adapter = _adapter(
        {
            "h1": {"labelIds": ["SENT"], "raw": "!!not-base64!!"},
            "c1": {"labelIds": ["SENT"], "raw": encode_reply(job, entry)},
        }
    )

    assert adapter.find_sent(job, entry) == "c1"


def test_two_matching_replies_require_review() -> None:
    job = _job()
    entry = _entry(job)
    raw = encode_reply(job, entry)
    adapter = _adapter(
        {"c1": {"labelIds": ["SENT"], "raw": raw}, "c2": {"labelIds": ["SENT"], "raw": raw}}
    )

    with pytest.raises(WorkflowError, match="AMBIGUOUS_SENT_RESULT"):
        adapter.find_sent(job, entry)


def test_reply_stored_in_another_thread_is_not_confirmed() -> None:
    job = _job()
    entry = _entry(job)
    adapter = _adapter(
        {"c1": {"labelIds": ["SENT"], "raw": encode_reply(job, entry), "threadId": "other"}}
    )

    assert adapter.find_sent(job, entry) is None


def test_reconciliation_never_sends_or_searches() -> None:
    job = _job()
    entry = _entry(job)
    adapter, service = _gmail({"c1": {"labelIds": ["SENT"], "raw": encode_reply(job, entry)}})

    adapter.find_sent(job, entry)

    messages = service.users.return_value.messages.return_value
    messages.send.assert_not_called()
    messages.list.assert_not_called()
