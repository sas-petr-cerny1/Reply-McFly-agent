import base64
from datetime import UTC, datetime
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from reply_mcfly.adapters.gmail_adapter import (
    GmailAdapter,
    GmailMessagePayload,
    encode_reply,
    parse_message,
)
from reply_mcfly.domain.email import Job, OutboxEntry, ReplyDraft, Status, WorkflowError


def raw_payload(message: EmailMessage) -> GmailMessagePayload:
    return GmailMessagePayload(
        id="a1",
        threadId="b1",
        internalDate="1700000000000",
        labelIds=["INBOX", "UNREAD"],
        raw=base64.urlsafe_b64encode(message.as_bytes()).decode(),
    )


def test_original_sender_is_used_and_reply_to_is_ignored() -> None:
    message = EmailMessage()
    message["From"] = "Sender <sender@customer.invalid>"
    message["Reply-To"] = "attacker@other.invalid"
    message["Subject"] = "Synthetic question"
    message["Message-ID"] = "<original@customer.invalid>"
    message.set_content("Synthetic body")
    incoming = parse_message(raw_payload(message))
    assert incoming.sender == "sender@customer.invalid"
    assert incoming.text == "Synthetic body"


def test_html_does_not_execute_or_include_script_content() -> None:
    message = EmailMessage()
    message["From"] = "sender@customer.invalid"
    message.set_content(
        "<p>Hello</p><script>do_bad_thing()</script><style>hidden</style>", subtype="html"
    )
    incoming = parse_message(raw_payload(message))
    assert incoming.text == "Hello"


def test_multiple_senders_require_review() -> None:
    message = EmailMessage()
    message["From"] = "one@customer.invalid, two@customer.invalid"
    message.set_content("Body")
    with pytest.raises(WorkflowError, match="AMBIGUOUS_EMAIL_ADDRESS"):
        parse_message(raw_payload(message))


def test_unknown_charset_is_reported_without_echoing_untrusted_header() -> None:
    message = EmailMessage()
    message["From"] = "sender@customer.invalid"
    message["Content-Type"] = 'text/plain; charset="private-input-unknown-charset"'
    message.set_payload("Synthetic body")
    with pytest.raises(WorkflowError, match="UNREADABLE_EMAIL_BODY") as failure:
        parse_message(raw_payload(message))
    assert "private-input" not in str(failure.value)


def test_supported_attachment_bytes_are_decoded() -> None:
    message = EmailMessage()
    message["From"] = "sender@customer.invalid"
    message.set_content("Body")
    message.add_attachment(
        b"%PDF-1.4 test\n",
        maintype="application",
        subtype="pdf",
        filename="invoice.pdf",
    )
    incoming = parse_message(raw_payload(message))
    assert incoming.has_attachments
    assert not incoming.unsupported_attachment
    assert len(incoming.attachments) == 1
    assert incoming.attachments[0].data.startswith(b"%PDF-")


def test_automatic_sender_and_unsupported_attachment_are_identified() -> None:
    message = EmailMessage()
    message["From"] = "sender@customer.invalid"
    message["Auto-Submitted"] = "auto-generated"
    message.set_content("Body")
    message.add_attachment(
        b"not executable", maintype="application", subtype="octet-stream", filename="test.bin"
    )
    incoming = parse_message(raw_payload(message))
    assert incoming.automatic
    assert incoming.has_attachments
    assert incoming.unsupported_attachment


def test_reply_contains_thread_headers_and_only_backend_selected_recipient() -> None:
    job = Job(
        uuid4(),
        "agent@agent.invalid",
        "a1",
        "b1",
        datetime.now(UTC),
        Status.PROCESSING,
        uuid4(),
        None,
        1,
    )
    entry = OutboxEntry(
        job.id,
        "<outgoing@agent.invalid>",
        "sender@customer.invalid",
        "Synthetic question",
        "Reply body",
        "<original@customer.invalid>",
        "<original@customer.invalid>",
    )
    raw = encode_reply(job, entry)
    message = BytesParser(policy=policy.default).parsebytes(base64.urlsafe_b64decode(raw))
    assert message["To"] == entry.recipient
    assert message["In-Reply-To"] == entry.in_reply_to
    assert message["References"] == entry.references
    assert message["Message-ID"] == entry.outbound_message_id
    assert message["Auto-Submitted"] == "auto-replied"
    assert message["Bcc"] is None
    service = MagicMock()
    service.users.return_value.getProfile.return_value.execute.return_value = {
        "emailAddress": job.mailbox_id
    }
    service.users.return_value.messages.return_value.send.return_value.execute.return_value = {
        "id": "sent1",
        "threadId": "b1",
    }
    assert GmailAdapter(lambda: service, job.mailbox_id).send(job, entry) == "sent1"
    body = service.users.return_value.messages.return_value.send.call_args.kwargs["body"]
    assert body["threadId"] == "b1"


def test_mismatched_oauth_mailbox_prevents_send() -> None:
    service = MagicMock()
    service.users.return_value.getProfile.return_value.execute.return_value = {
        "emailAddress": "other@agent.invalid"
    }
    adapter = GmailAdapter(lambda: service, "agent@agent.invalid")
    with pytest.raises(WorkflowError, match="FORBIDDEN"):
        adapter.metadata("a1")
    service.users.return_value.messages.assert_not_called()


def test_ai_output_cannot_choose_a_recipient() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ReplyDraft.model_validate(
            {
                "response_type": "GENERATED",
                "proposed_reply": "Hello",
                "evidence": [],
                "missing_information": [],
                "requires_review": False,
                "recipient": "attacker@other.invalid",
            }
        )


@pytest.mark.parametrize("same_body", [True, False])
def test_sent_lookup_confirms_only_matching_outbox_content(same_body: bool) -> None:
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
        "Reply body",
        "<original@customer.invalid>",
        "<original@customer.invalid>",
    )
    message = BytesParser(policy=policy.default).parsebytes(
        base64.urlsafe_b64decode(encode_reply(job, entry))
    )
    if not isinstance(message, EmailMessage):
        pytest.fail("Expected EmailMessage")
    message.set_content("Reply body" if same_body else "Different content")
    service = MagicMock()
    service.users.return_value.getProfile.return_value.execute.return_value = {
        "emailAddress": job.mailbox_id
    }
    service.users.return_value.messages.return_value.list.return_value.execute.return_value = {
        "messages": [{"id": "c1"}]
    }
    service.users.return_value.messages.return_value.get.return_value.execute.return_value = {
        "id": "c1",
        "threadId": "b1",
        "internalDate": "1700000000000",
        "labelIds": ["SENT"],
        "raw": base64.urlsafe_b64encode(message.as_bytes()).decode(),
    }
    result = GmailAdapter(lambda: service, job.mailbox_id).find_sent(job, entry)
    assert result == ("c1" if same_body else None)
    service.users.return_value.messages.return_value.send.assert_not_called()
