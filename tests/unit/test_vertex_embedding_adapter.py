import math
from unittest.mock import MagicMock, patch

import httpx
import pytest
from google.genai import errors, types

from reply_mcfly.adapters.vertex_embedding_adapter import VertexEmbeddingAdapter, validate_embedding
from reply_mcfly.domain.email import WorkflowError

DIMS = 768
CLIENT = "reply_mcfly.adapters.vertex_embedding_adapter.genai.Client"


def _adapter() -> VertexEmbeddingAdapter:
    return VertexEmbeddingAdapter("synthetic-project", "europe-west1", "synthetic-embedding", DIMS)


def _response(*vectors: list[float]) -> types.EmbedContentResponse:
    return types.EmbedContentResponse(
        embeddings=[types.ContentEmbedding(values=vector) for vector in vectors]
    )


def _client(factory: MagicMock) -> MagicMock:
    client = factory.return_value.__enter__.return_value
    assert isinstance(client, MagicMock)
    return client


def test_valid_vector_is_returned_as_floats() -> None:
    assert validate_embedding([1, 0.5, -2.0], 3) == (1.0, 0.5, -2.0)


@pytest.mark.parametrize(
    "values",
    [
        [],
        [0.1] * (DIMS - 1),
        [0.1] * (DIMS + 1),
        [0.0] * DIMS,
        [math.nan] + [0.1] * (DIMS - 1),
        [math.inf] + [0.1] * (DIMS - 1),
        ["0.1"] * DIMS,
        [True] * DIMS,
        None,
    ],
    ids=["empty", "short", "long", "zeros", "nan", "inf", "strings", "booleans", "none"],
)
def test_invalid_vector_is_rejected(values: object) -> None:
    with pytest.raises(WorkflowError, match="EMBEDDING_INVALID") as error:
        validate_embedding(values, DIMS)
    assert error.value.retryable is False


def test_query_and_document_use_their_retrieval_task_types() -> None:
    with patch(CLIENT) as factory:
        client = _client(factory)
        client.models.embed_content.return_value = _response([0.25] * DIMS)
        adapter = _adapter()

        assert adapter.embed_query("Kolik stojí AirDock 8?", 6) == (0.25,) * DIMS
        query = client.models.embed_content.call_args.kwargs
        adapter.embed_document("McFly AirDock 8", "# McFly AirDock 8\n## Cena", 6)
        document = client.models.embed_content.call_args.kwargs

    assert query["model"] == document["model"] == "synthetic-embedding"
    assert query["contents"] == "Kolik stojí AirDock 8?"
    assert (query["config"].task_type, query["config"].title) == ("RETRIEVAL_QUERY", None)
    assert document["config"].task_type == "RETRIEVAL_DOCUMENT"
    assert document["config"].title == "McFly AirDock 8"
    assert query["config"].output_dimensionality == DIMS
    assert document["config"].output_dimensionality == DIMS
    options = factory.call_args.kwargs["http_options"]
    assert options.timeout == 6000
    assert options.retry_options.attempts == 1
    assert factory.call_args.kwargs["location"] == "europe-west1"


@pytest.mark.parametrize(
    "response",
    [
        types.EmbedContentResponse(embeddings=None),
        types.EmbedContentResponse(embeddings=[]),
        _response([0.1] * DIMS, [0.1] * DIMS),
        _response([0.1] * 3072),
        types.EmbedContentResponse(embeddings=[types.ContentEmbedding(values=None)]),
    ],
    ids=["missing", "empty", "two-vectors", "wrong-dimension", "no-values"],
)
def test_unusable_response_is_rejected(response: types.EmbedContentResponse) -> None:
    with patch(CLIENT) as factory:
        _client(factory).models.embed_content.return_value = response
        with pytest.raises(WorkflowError, match="EMBEDDING_INVALID"):
            _adapter().embed_query("Kolik stojí AirDock 8?", 6)


@pytest.mark.parametrize("status,retryable", [(400, False), (403, False), (429, True), (503, True)])
def test_api_failure_classification(status: int, retryable: bool) -> None:
    with patch(CLIENT) as factory:
        _client(factory).models.embed_content.side_effect = errors.APIError(
            status, {"message": "synthetic"}
        )
        with pytest.raises(WorkflowError, match="EMBEDDING_API_ERROR") as error:
            _adapter().embed_query("Kolik stojí AirDock 8?", 6)
    assert error.value.retryable is retryable


@pytest.mark.parametrize(
    "failure", [httpx.ReadTimeout("synthetic"), httpx.ConnectError("synthetic")]
)
def test_timeout_and_connection_failure_are_retryable(failure: Exception) -> None:
    with patch(CLIENT) as factory:
        _client(factory).models.embed_content.side_effect = failure
        with pytest.raises(WorkflowError, match="EMBEDDING_UNAVAILABLE") as error:
            _adapter().embed_query("Kolik stojí AirDock 8?", 6)
    assert error.value.retryable is True


def test_no_request_is_started_without_time_budget() -> None:
    with patch(CLIENT) as factory:
        with pytest.raises(WorkflowError, match="DEPENDENCY_TIMEOUT") as error:
            _adapter().embed_query("Kolik stojí AirDock 8?", 0.5)
        factory.assert_not_called()
    assert error.value.retryable is True


@pytest.mark.parametrize("text", ["", "   ", "x" * 601])
def test_empty_or_oversized_query_never_leaves_the_process(text: str) -> None:
    with patch(CLIENT) as factory:
        with pytest.raises(WorkflowError, match="EMBEDDING_INPUT_INVALID"):
            _adapter().embed_query(text, 6)
        factory.assert_not_called()


def test_incomplete_configuration_is_rejected() -> None:
    with pytest.raises(ValueError, match="EMBEDDING_CONFIGURATION_INVALID"):
        VertexEmbeddingAdapter("synthetic-project", "", "synthetic-embedding", DIMS)
