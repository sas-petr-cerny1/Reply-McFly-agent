"""Vertex AI text embeddings for product knowledge retrieval.

Independent of reply generation: no system instruction, no tools, no content generation.
Callers pass only catalog text (indexing) or a sanitized product question (retrieval).
"""

from __future__ import annotations

import math

import httpx
from google import genai
from google.genai import errors, types

from reply_mcfly.domain.email import WorkflowError

MAX_QUERY_CHARS = 600
MAX_DOCUMENT_CHARS = 2_500
_DOCUMENT_TASK = "RETRIEVAL_DOCUMENT"
_QUERY_TASK = "RETRIEVAL_QUERY"


def _transport_errors() -> tuple[type[Exception], ...]:
    # The SDK raises raw transport exceptions from httpx or its optional fork httpx2.
    found: list[type[Exception]] = [httpx.TransportError]
    try:
        import httpx2
    except ImportError:
        return tuple(found)
    found.append(httpx2.TransportError)
    return tuple(found)


_TRANSPORT_ERRORS = _transport_errors()


def validate_embedding(values: object, dimensions: int) -> tuple[float, ...]:
    """Accept only a full-length vector of finite numbers that is not all zeros."""
    if not isinstance(values, list | tuple) or len(values) != dimensions:
        raise WorkflowError("EMBEDDING_INVALID")
    vector: list[float] = []
    for value in values:
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise WorkflowError("EMBEDDING_INVALID")
        number = float(value)
        if not math.isfinite(number):
            raise WorkflowError("EMBEDDING_INVALID")
        vector.append(number)
    if not any(vector):
        raise WorkflowError("EMBEDDING_INVALID")
    return tuple(vector)


class VertexEmbeddingAdapter:
    def __init__(self, project: str, location: str, model: str, dimensions: int) -> None:
        if not project or not location or not model or dimensions < 1:
            raise ValueError("EMBEDDING_CONFIGURATION_INVALID")
        self.project, self.location = project, location
        self.model, self.dimensions = model, dimensions

    def embed_query(self, text: str, timeout: float) -> tuple[float, ...]:
        if not text.strip() or len(text) > MAX_QUERY_CHARS:
            raise WorkflowError("EMBEDDING_INPUT_INVALID")
        return self._embed(text, _QUERY_TASK, None, timeout)

    def embed_document(self, title: str, text: str, timeout: float) -> tuple[float, ...]:
        if not text.strip() or len(text) > MAX_DOCUMENT_CHARS:
            raise WorkflowError("EMBEDDING_INPUT_INVALID")
        return self._embed(text, _DOCUMENT_TASK, title, timeout)

    def _embed(self, text: str, task: str, title: str | None, timeout: float) -> tuple[float, ...]:
        if timeout < 1.0:
            # Never start a paid network call that cannot finish inside the deadline.
            raise WorkflowError("DEPENDENCY_TIMEOUT", retryable=True, status=503)
        try:
            with genai.Client(
                vertexai=True,
                project=self.project,
                location=self.location,
                http_options=types.HttpOptions(
                    timeout=int(timeout * 1000),
                    retry_options=types.HttpRetryOptions(attempts=1),
                ),
            ) as client:
                # One text per request: the model accepts a single input on Vertex AI.
                response = client.models.embed_content(
                    model=self.model,
                    contents=text,
                    config=types.EmbedContentConfig(
                        task_type=task,
                        output_dimensionality=self.dimensions,
                        title=title,
                    ),
                )
        except errors.APIError as error:
            raise WorkflowError(
                "EMBEDDING_API_ERROR", retryable=error.code == 429 or error.code >= 500, status=503
            ) from None
        except _TRANSPORT_ERRORS:
            raise WorkflowError("EMBEDDING_UNAVAILABLE", retryable=True, status=503) from None
        embeddings = response.embeddings
        if not embeddings or len(embeddings) != 1:
            raise WorkflowError("EMBEDDING_INVALID")
        return validate_embedding(embeddings[0].values, self.dimensions)
