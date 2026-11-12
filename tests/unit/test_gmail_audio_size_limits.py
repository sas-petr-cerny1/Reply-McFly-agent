"""Regression coverage for Gmail RAW messages with audio attachments.

Do not use expected order numbers in model prompts. These tests exercise MIME
parsing and size limits only; model extraction is tested separately.
"""

import base64
from email.message import EmailMessage

import pytest

from reply_mcfly.adapters import gmail_adapter
from reply_mcfly.adapters.gmail_adapter import GmailMessagePayload, parse_message
from reply_mcfly.domain.email import WorkflowError


def _payload_with_audio(*, subtype: str, suffix: str, length: int) -> GmailMessagePayload:
    message = EmailMessage()
    message["From"] = "tester@example.invalid"
    message["To"] = "assistant@example.invalid"
    message["Subject"] = "Audio size regression"
    message["Message-ID"] = "<audio-regression@example.invalid>"
    message.set_content("Find the order number in the attachment.")
    message.add_attachment(
        b"\0" * length,
        maintype="audio",
        subtype=subtype,
        filename=f"recording.{suffix}",
    )
    return GmailMessagePayload(
        id="audio-test-1",
        threadId="audio-test-thread-1",
        internalDate="1700000000000",
        labelIds=["INBOX", "UNREAD"],
        raw=base64.urlsafe_b64encode(message.as_bytes()).decode("ascii"),
    )


@pytest.mark.parametrize(
    ("subtype", "suffix", "length"),
    [("wav", "wav", 1_274_190), ("mpeg", "mp3", 248_068)],
)
def test_audio_email_parses_below_safety_limit(subtype: str, suffix: str, length: int) -> None:
    payload = _payload_with_audio(subtype=subtype, suffix=suffix, length=length)
    if suffix == "wav":
        # This case was previously blocked by the 2,000,000-character RAW guard.
        assert len(payload.raw or "") > 2_000_000
    parsed = parse_message(payload)
    assert parsed.has_attachments is True
    assert parsed.unsupported_attachment is False


def test_raw_encoded_size_limit_remains_enforced(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = _payload_with_audio(subtype="mpeg", suffix="mp3", length=10_000)
    monkeypatch.setattr(gmail_adapter, "MAX_GMAIL_RAW_CHARS", 1_000)
    with pytest.raises(WorkflowError, match="EMAIL_TOO_LARGE_OR_MISSING"):
        parse_message(payload)


def test_decoded_mime_size_limit_remains_enforced(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = _payload_with_audio(subtype="mpeg", suffix="mp3", length=10_000)
    monkeypatch.setattr(gmail_adapter, "MAX_GMAIL_DECODED_BYTES", 1_000)
    with pytest.raises(WorkflowError, match="EMAIL_TOO_LARGE_OR_MISSING"):
        parse_message(payload)
