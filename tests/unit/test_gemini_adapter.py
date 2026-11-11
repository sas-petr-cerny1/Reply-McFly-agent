import json
from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from google.genai import errors

from reply_mcfly.adapters.gemini_adapter import GeminiAdapter
from reply_mcfly.domain.email import IncomingEmail, MessageMetadata, WorkflowError


def email() -> IncomingEmail:
    return IncomingEmail(
        MessageMetadata("a1", "b1", datetime.now(UTC), frozenset({"INBOX", "UNREAD"})),
        "sender@customer.invalid",
        "Synthetic",
        "<a1@customer.invalid>",
        "",
        "Synthetic text",
    )


def test_gemini_uses_structured_schema_and_bounded_sdk_call() -> None:
    with patch("reply_mcfly.adapters.gemini_adapter.genai.Client") as factory:
        client = factory.return_value.__enter__.return_value
        client.models.generate_content.return_value.text = json.dumps(
            {
                "response_type": "FALLBACK",
                "proposed_reply": "",
                "evidence": [],
                "missing_information": ["Missing product facts"],
                "requires_review": False,
            }
        )
        draft = GeminiAdapter("synthetic-project", "eu", "synthetic-model").run(email(), 10)
        assert draft.response_type == "FALLBACK"
        kwargs = factory.call_args.kwargs
        assert kwargs["location"] == "eu"
        assert kwargs["http_options"].timeout == 10000
        assert kwargs["http_options"].retry_options.attempts == 1
        args = client.models.generate_content.call_args.kwargs
        assert json.loads(args["contents"])["source_id"] == "email:a1"
        assert args["config"].automatic_function_calling.disable is True
        assert args["config"].response_mime_type == "application/json"


@pytest.mark.parametrize("value", [None, "not json", '{"recipient":"attacker@customer.invalid"}'])
def test_gemini_invalid_output_requires_review(value: str | None) -> None:
    with patch("reply_mcfly.adapters.gemini_adapter.genai.Client") as factory:
        client = factory.return_value.__enter__.return_value
        client.models.generate_content.return_value.text = value
        with pytest.raises(WorkflowError, match="INVALID_AI_OUTPUT"):
            GeminiAdapter("synthetic-project", "eu", "synthetic-model").run(email(), 10)


@pytest.mark.parametrize("status,retryable", [(400, False), (429, True), (503, True)])
def test_gemini_api_failure_classification(status: int, retryable: bool) -> None:
    with patch("reply_mcfly.adapters.gemini_adapter.genai.Client") as factory:
        client = factory.return_value.__enter__.return_value
        client.models.generate_content.side_effect = errors.APIError(
            status, {"message": "synthetic"}
        )
        with pytest.raises(WorkflowError, match="GEMINI_API_ERROR") as error:
            GeminiAdapter("synthetic-project", "eu", "synthetic-model").run(email(), 10)
        assert error.value.retryable is retryable
