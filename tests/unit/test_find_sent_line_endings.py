from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from reply_mcfly.adapters.gmail_adapter import GmailAdapter, encode_reply
from reply_mcfly.domain.email import Job, OutboxEntry, Status
from reply_mcfly.domain.reply_templates import FALLBACK_MISSING_INFORMATION

# One body per transfer encoding the standard library picks for outgoing replies.
BODIES = {
    "7bit": "Reply body\nsecond line",
    "8bit": "Dobrý den,\n\nděkujeme",
    "quoted-printable": "> - **Deductible:** "
    + "long knowledge base line " * 6
    + "500 Kč.\n> next",
    "base64": FALLBACK_MISSING_INFORMATION,
}


@pytest.mark.parametrize("body", BODIES.values(), ids=BODIES.keys())
def test_sent_lookup_matches_the_exact_message_that_was_sent(body: str) -> None:
    job = Job(
        uuid4(),
        "agent@agent.invalid",
        "a1",
        "b1",
        datetime.now(UTC),
        Status.DELIVERY_UNKNOWN,
        uuid4(),
        None,
        1,
    )
    entry = OutboxEntry(
        job.id,
        "<outgoing@agent.invalid>",
        "sender@customer.invalid",
        "Synthetic question",
        body,
        "<original@customer.invalid>",
        "<original@customer.invalid>",
    )
    service = MagicMock()
    service.users.return_value.getProfile.return_value.execute.return_value = {
        "emailAddress": job.mailbox_id
    }
    service.users.return_value.messages.return_value.list.return_value.execute.return_value = {
        "messages": [{"id": "c1"}]
    }
    # Gmail returns the stored message exactly as encode_reply serialized it (CRLF, QP).
    service.users.return_value.messages.return_value.get.return_value.execute.return_value = {
        "id": "c1",
        "threadId": "b1",
        "internalDate": "1700000000000",
        "labelIds": ["SENT"],
        "raw": encode_reply(job, entry),
    }

    assert GmailAdapter(lambda: service, job.mailbox_id).find_sent(job, entry) == "c1"
