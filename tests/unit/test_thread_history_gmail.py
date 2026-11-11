"""Fake Gmail API tests for thread isolation and bounded context."""
import base64
from email.message import EmailMessage
from unittest.mock import MagicMock

import pytest

from reply_mcfly.adapters.gmail_adapter import GmailAdapter
from reply_mcfly.domain.email import WorkflowError

MAILBOX = "agent@example.invalid"
SENDER = "sender@example.invalid"


def make_payload(message_id: str, thread_id: str, stamp: int, sender: str, text: str):
    message = EmailMessage()
    message["From"] = sender
    message["To"] = MAILBOX
    message["Message-ID"] = f"<{message_id}@example.invalid>"
    message["Subject"] = "Synthetic thread"
    message.set_content(text)
    return {
        "id": message_id,
        "threadId": thread_id,
        "internalDate": str(stamp),
        "labelIds": ["INBOX", "UNREAD"],
        "raw": base64.urlsafe_b64encode(message.as_bytes()).decode("ascii"),
    }


def fake_service(payloads, order, *, thread_id="thread-a"):
    service = MagicMock()
    service.users.return_value.getProfile.return_value.execute.return_value = {
        "emailAddress": MAILBOX,
    }
    service.users.return_value.threads.return_value.get.return_value.execute.return_value = {
        "id": thread_id,
        "messages": [{"id": item} for item in order],
    }

    def message_get(*, userId, id, format):
        assert userId == "me" and format == "raw"
        request = MagicMock()
        request.execute.return_value = payloads[id]
        return request

    service.users.return_value.messages.return_value.get.side_effect = message_get
    return service


def test_gmail_fetches_previous_same_thread_and_ignores_other_sender(monkeypatch):
    monkeypatch.setenv("MCFLY_ENABLE_THREAD_HISTORY", "true")
    payloads = {
        "m0": make_payload("m0", "thread-a", 1000, SENDER, "Ref ID: 3456"),
        "m1": make_payload("m1", "thread-a", 2000, "third@example.invalid", "Secret"),
        "m2": make_payload("m2", "thread-a", 3000, SENDER, "What was my ID?"),
    }
    service = fake_service(payloads, ["m0", "m1", "m2"])
    email = GmailAdapter(lambda: service, MAILBOX).message("m2")
    assert [p.source_id for p in email.thread_history] == ["thread:m0"]
    assert email.thread_history[0].text == "Ref ID: 3456"
    assert "Secret" not in str(email.thread_history)


def test_gmail_rejects_mismatched_history_thread(monkeypatch):
    monkeypatch.setenv("MCFLY_ENABLE_THREAD_HISTORY", "true")
    payloads = {
        "m0": make_payload("m0", "thread-b", 1000, SENDER, "Wrong thread"),
        "m1": make_payload("m1", "thread-a", 2000, SENDER, "Follow up"),
    }
    service = fake_service(payloads, ["m0", "m1"])
    with pytest.raises(WorkflowError, match="THREAD_CONTEXT_MISMATCH"):
        GmailAdapter(lambda: service, MAILBOX).message("m1")


def test_gmail_history_disabled_by_default(monkeypatch):
    monkeypatch.delenv("MCFLY_ENABLE_THREAD_HISTORY", raising=False)
    payloads = {"m1": make_payload("m1", "thread-a", 2000, SENDER, "Follow up")}
    service = fake_service(payloads, ["m1"])
    email = GmailAdapter(lambda: service, MAILBOX).message("m1")
    assert email.thread_history == ()
    service.users.return_value.threads.return_value.get.assert_not_called()
