import json
from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from google.genai import errors, types

from reply_mcfly.adapters.gemini_adapter import (
    AttachmentExtractionResult,
    ExtractedPassage,
    GeminiAdapter,
    _draft_from_response,
    _usage_counts,
)
from reply_mcfly.application.attachment_processor import ValidatedAttachment
from reply_mcfly.domain.email import (
    IncomingEmail,
    MessageMetadata,
    RagPassage,
    ReplyDraft,
    WorkflowError,
)


def email() -> IncomingEmail:
    return IncomingEmail(
        MessageMetadata("a1", "b1", datetime.now(UTC), frozenset({"INBOX", "UNREAD"})),
        "sender@customer.invalid",
        "Synthetic",
        "<a1@customer.invalid>",
        "",
        "Synthetic text",
    )


def valid_draft_json() -> str:
    evidence = [
        {
            "source_id": "email:a1",
            "exact_quote": "Synthetic text",
        }
    ]
    return json.dumps(
        {
            "response_type": "GENERATED",
            "proposed_reply": (
                "Dobrý den,\n\nve své zprávě uvádíte:\n\n> Synthetic text\n\n"
                "S pozdravem\nReply McFly – AI Email Assistant"
            ),
            "evidence": evidence,
            "missing_information": [],
            "requires_review": False,
        }
    )


def gemini_response(
    *,
    text: str | None,
    finish_reason: types.FinishReason = types.FinishReason.STOP,
    parsed: ReplyDraft | None = None,
    block_reason: types.BlockedReason | None = None,
) -> types.GenerateContentResponse:
    parts = [types.Part(text=text)] if text else []
    candidate = types.Candidate(
        finish_reason=finish_reason,
        content=types.Content(parts=parts),
    )
    feedback = (
        types.GenerateContentResponsePromptFeedback(block_reason=block_reason)
        if block_reason is not None
        else None
    )
    return types.GenerateContentResponse(
        candidates=[candidate],
        parsed=parsed,
        prompt_feedback=feedback,
        usage_metadata=types.GenerateContentResponseUsageMetadata(
            prompt_token_count=42,
            candidates_token_count=88,
            total_token_count=130,
        ),
    )


def test_gemini_uses_structured_schema_and_bounded_sdk_call() -> None:
    with patch("reply_mcfly.adapters.gemini_adapter.genai.Client") as factory:
        client = factory.return_value.__enter__.return_value
        client.models.generate_content.return_value = gemini_response(
            text=json.dumps(
                {
                    "response_type": "FALLBACK",
                    "proposed_reply": "",
                    "evidence": [],
                    "missing_information": ["Missing product facts"],
                    "requires_review": False,
                }
            )
        )
        draft = GeminiAdapter("synthetic-project", "eu", "synthetic-model").run(email(), 10)
        assert draft.response_type == "FALLBACK"
        kwargs = factory.call_args.kwargs
        assert kwargs["location"] == "eu"
        assert kwargs["http_options"].timeout >= 9000
        assert kwargs["http_options"].retry_options.attempts == 1
        args = client.models.generate_content.call_args.kwargs
        assert json.loads(args["contents"])["source_id"] == "email:a1"
        assert args["config"].automatic_function_calling.disable is True
        assert args["config"].response_mime_type == "application/json"


def test_uses_sdk_parsed_reply_draft_without_revalidation() -> None:
    parsed = ReplyDraft(
        response_type="FALLBACK",
        proposed_reply="",
        evidence=[],
        missing_information=["x"],
        requires_review=False,
    )
    draft = _draft_from_response(gemini_response(text=None, parsed=parsed))
    assert draft is parsed


@pytest.mark.parametrize(
    ("text", "code"),
    [
        (None, "AI_OUTPUT_EMPTY"),
        ("", "AI_OUTPUT_EMPTY"),
        (" \n", "AI_OUTPUT_EMPTY"),
        ("not json", "AI_OUTPUT_INVALID_JSON"),
        ('{"response_type":"GENERATED"}', "AI_OUTPUT_SCHEMA_INVALID"),
    ],
)
def test_output_failure_categories(text: str | None, code: str) -> None:
    with pytest.raises(WorkflowError, match=code):
        _draft_from_response(gemini_response(text=text))


def test_incomplete_generation_when_max_tokens_without_body() -> None:
    with pytest.raises(WorkflowError, match="AI_OUTPUT_INCOMPLETE"):
        _draft_from_response(
            gemini_response(text=None, finish_reason=types.FinishReason.MAX_TOKENS)
        )


def test_blocked_output_when_finish_reason_is_safety() -> None:
    with pytest.raises(WorkflowError, match="AI_OUTPUT_BLOCKED"):
        _draft_from_response(
            gemini_response(text=valid_draft_json(), finish_reason=types.FinishReason.SAFETY)
        )


def test_truncated_json_classified_as_incomplete() -> None:
    with pytest.raises(WorkflowError, match="AI_OUTPUT_INCOMPLETE"):
        _draft_from_response(gemini_response(text='{"response_type":"GENERATED","proposed_reply":'))


def test_retries_once_on_invalid_json_then_succeeds() -> None:
    valid = gemini_response(text=valid_draft_json())
    invalid = gemini_response(text="not json")
    with patch("reply_mcfly.adapters.gemini_adapter.genai.Client") as factory:
        client = factory.return_value.__enter__.return_value
        client.models.generate_content.side_effect = [invalid, valid]
        draft = GeminiAdapter("synthetic-project", "eu", "synthetic-model").run(email(), 15)
        assert draft.response_type == "GENERATED"
        assert client.models.generate_content.call_count == 2


def test_blocked_output_is_not_retried() -> None:
    blocked = gemini_response(
        text=valid_draft_json(),
        finish_reason=types.FinishReason.SAFETY,
    )
    with patch("reply_mcfly.adapters.gemini_adapter.genai.Client") as factory:
        client = factory.return_value.__enter__.return_value
        client.models.generate_content.return_value = blocked
        with pytest.raises(WorkflowError, match="AI_OUTPUT_BLOCKED"):
            GeminiAdapter("synthetic-project", "eu", "synthetic-model").run(email(), 15)
        assert client.models.generate_content.call_count == 1


def test_attachment_extract_includes_email_context() -> None:
    current = email()
    current = IncomingEmail(
        current.metadata,
        current.sender,
        current.subject,
        current.message_id_header,
        current.references,
        "Jaké je číslo objednávky a jaké je poškození na fotce?",
    )
    validated = (
        ValidatedAttachment("attachment:0", "damage.png", "image/png", b"\x89PNG\r\n\x1a\n"),
    )
    with patch("reply_mcfly.adapters.gemini_adapter.genai.Client") as factory:
        client = factory.return_value.__enter__.return_value
        client.models.generate_content.return_value = types.GenerateContentResponse(
            candidates=[types.Candidate(finish_reason=types.FinishReason.STOP)],
            parsed=AttachmentExtractionResult(
                passages=[
                    ExtractedPassage(
                        source_id="attachment:0",
                        extracted_text="DEMO-65432\nPravý roh displeje je roztržený.",
                    )
                ]
            ),
        )
        passages = GeminiAdapter("synthetic-project", "eu", "synthetic-model").extract(
            current, validated, 10
        )
        assert passages[0].text == "DEMO-65432\nPravý roh displeje je roztržený."
        parts = client.models.generate_content.call_args.kwargs["contents"][0].parts
        assert "Jaké je číslo objednávky" in parts[0].text


def test_gemini_payload_includes_rag_passages() -> None:
    rag_id = "rag:KB01_DemoBoxPlus:abc123"
    current = IncomingEmail(
        MessageMetadata("a1", "b1", datetime.now(UTC), frozenset({"INBOX", "UNREAD"})),
        "sender@customer.invalid",
        "Synthetic",
        "<a1@customer.invalid>",
        "",
        "Synthetic text",
        rag_passages=(RagPassage(rag_id, "KB text", "KB01_DemoBoxPlus.md"),),
    )
    with patch("reply_mcfly.adapters.gemini_adapter.genai.Client") as factory:
        client = factory.return_value.__enter__.return_value
        client.models.generate_content.return_value = gemini_response(text=valid_draft_json())
        GeminiAdapter("synthetic-project", "eu", "synthetic-model").run(current, 10)
        payload = json.loads(client.models.generate_content.call_args.kwargs["contents"])
        assert payload["rag_passages"] == [
            {
                "source_id": rag_id,
                "provenance": "KB01_DemoBoxPlus.md",
                "reference_text": "KB text",
            }
        ]


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


@pytest.mark.parametrize(
    ("usage", "expected"),
    [
        (
            None,
            {"prompt_token_count": None, "candidates_token_count": None, "total_token_count": None},
        ),
        (
            types.GenerateContentResponseUsageMetadata(
                prompt_token_count=0, candidates_token_count=12, total_token_count=12
            ),
            {"prompt_token_count": 0, "candidates_token_count": 12, "total_token_count": 12},
        ),
    ],
)
def test_usage_counts_preserves_missing_and_reported_values(
    usage: types.GenerateContentResponseUsageMetadata | None, expected: dict[str, int | None]
) -> None:
    assert _usage_counts(types.GenerateContentResponse(usage_metadata=usage)) == expected
