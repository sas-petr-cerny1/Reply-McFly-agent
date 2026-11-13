import json
import logging
from datetime import UTC, datetime

logger = logging.getLogger("reply_mcfly.workflow")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)
logger.propagate = False


def emit(
    event: str,
    *,
    job_id: str | None = None,
    status: str | None = None,
    error_code: str | None = None,
    duration_seconds: float | None = None,
    gmail_message_id: str | None = None,
    gmail_thread_id: str | None = None,
    mode: str | None = None,
    response_type: str | None = None,
    validation_category: str | None = None,
    finish_reason: str | None = None,
    has_text: bool | None = None,
    text_byte_length: int | None = None,
    prompt_token_count: int | None = None,
    candidates_token_count: int | None = None,
    total_token_count: int | None = None,
    validation_fields: list[str] | None = None,
    attempt: int | None = None,
    embedding_latency_ms: int | None = None,
    vector_query_latency_ms: int | None = None,
    rag_total_latency_ms: int | None = None,
    rag_hit_count: int | None = None,
    rag_error_code: str | None = None,
    embedding_model: str | None = None,
    document_version: str | None = None,
    correlation_id: str | None = None,
    path: str | None = None,
) -> None:
    payload: dict[str, object] = {
        "timestamp": datetime.now(UTC).isoformat(),
        "event": event,
        "job_id": job_id,
        "correlation_id": correlation_id or job_id,
        "status": status,
        "error_code": error_code,
        "duration_seconds": duration_seconds,
    }
    if gmail_message_id is not None:
        payload["gmail_message_id"] = gmail_message_id
    if gmail_thread_id is not None:
        payload["gmail_thread_id"] = gmail_thread_id
    if mode is not None:
        payload["mode"] = mode
    if response_type is not None:
        payload["response_type"] = response_type
    for key, value in (
        ("validation_category", validation_category),
        ("finish_reason", finish_reason),
        ("has_text", has_text),
        ("text_byte_length", text_byte_length),
        ("prompt_token_count", prompt_token_count),
        ("candidates_token_count", candidates_token_count),
        ("total_token_count", total_token_count),
        ("validation_fields", validation_fields),
        ("attempt", attempt),
        ("embedding_latency_ms", embedding_latency_ms),
        ("vector_query_latency_ms", vector_query_latency_ms),
        ("rag_total_latency_ms", rag_total_latency_ms),
        ("rag_hit_count", rag_hit_count),
        ("rag_error_code", rag_error_code),
        ("embedding_model", embedding_model),
        ("document_version", document_version),
        ("path", path),
    ):
        if value is not None:
            payload[key] = value
    logger.info(json.dumps(payload))
