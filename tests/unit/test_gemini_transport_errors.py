from datetime import UTC, datetime
from unittest.mock import patch

import httpx
import pytest

from reply_mcfly.adapters.gemini_adapter import GeminiAdapter
from reply_mcfly.application.attachment_processor import ValidatedAttachment
from reply_mcfly.domain.email import IncomingEmail, MessageMetadata, WorkflowError

TRANSPORT_FAILURES = [
    httpx.ReadTimeout("synthetic timeout"),
    httpx.ConnectTimeout("synthetic timeout"),
    httpx.ConnectError("synthetic connection failure"),
    httpx.RemoteProtocolError("synthetic disconnect"),
]


def email() -> IncomingEmail:
    return IncomingEmail(
        MessageMetadata("a1", "b1", datetime.now(UTC), frozenset({"INBOX", "UNREAD"})),
        "sender@customer.invalid",
        "Synthetic test",
        "<original@customer.invalid>",
        "",
        "Test",
    )


@pytest.mark.parametrize("failure", TRANSPORT_FAILURES, ids=lambda item: type(item).__name__)
def test_generation_transport_failure_is_retryable(failure: Exception) -> None:
    with patch("reply_mcfly.adapters.gemini_adapter.genai.Client") as factory:
        client = factory.return_value.__enter__.return_value
        client.models.generate_content.side_effect = failure
        with pytest.raises(WorkflowError, match="GEMINI_UNAVAILABLE") as error:
            GeminiAdapter("synthetic-project", "eu", "synthetic-model").run(email(), 10)
    assert error.value.retryable is True
    assert error.value.status == 503


@pytest.mark.parametrize("failure", TRANSPORT_FAILURES, ids=lambda item: type(item).__name__)
def test_extraction_transport_failure_is_retryable(failure: Exception) -> None:
    attachment = ValidatedAttachment("attachment:0", "scan.pdf", "application/pdf", b"%PDF-1.7")
    with patch("reply_mcfly.adapters.gemini_adapter.genai.Client") as factory:
        client = factory.return_value.__enter__.return_value
        client.models.generate_content.side_effect = failure
        with pytest.raises(WorkflowError, match="GEMINI_UNAVAILABLE") as error:
            GeminiAdapter("synthetic-project", "eu", "synthetic-model").extract(
                email(), (attachment,), 10
            )
    assert error.value.retryable is True
