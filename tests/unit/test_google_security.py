import base64
import json
import time
from collections.abc import Callable
from http.client import BadStatusLine, HTTPConnection
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from google.api_core.exceptions import AlreadyExists

from reply_mcfly.adapters.cloud_tasks_adapter import CloudTasksAdapter
from reply_mcfly.adapters.google_clients import OneShotHttp
from reply_mcfly.adapters.oidc_adapter import GoogleOidcVerifier
from reply_mcfly.domain.email import WorkflowError


def b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


@pytest.fixture(scope="module")
def key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def signed_token(key: rsa.RSAPrivateKey, overrides: dict[str, object]) -> str:
    now = int(time.time())
    claims = {
        "iss": "https://accounts.google.com",
        "sub": "synthetic-service-account",
        "aud": "https://worker.invalid",
        "email": "tasks@project.iam.gserviceaccount.com",
        "email_verified": True,
        "iat": now - 10,
        "exp": now + 60,
        **overrides,
    }
    encoded = (
        b64(json.dumps({"alg": "RS256", "kid": "test-key"}).encode())
        + "."
        + b64(json.dumps(claims).encode())
    )
    signature = key.sign(encoded.encode(), padding.PKCS1v15(), hashes.SHA256())
    return encoded + "." + b64(signature)


def install_certificate(monkeypatch: pytest.MonkeyPatch, key: rsa.RSAPrivateKey) -> None:
    response = requests.Response()
    response.status_code = 200
    public = (
        key.public_key()
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode()
    )
    response._content = json.dumps({"test-key": public}).encode()

    def request(*args: object, **kwargs: object) -> requests.Response:
        assert kwargs["timeout"] == 5
        return response

    monkeypatch.setattr(requests, "request", request)


def test_oidc_validates_real_signature_without_network(
    monkeypatch: pytest.MonkeyPatch, key: rsa.RSAPrivateKey
) -> None:
    install_certificate(monkeypatch, key)
    verifier = GoogleOidcVerifier("https://worker.invalid", "tasks@project.iam.gserviceaccount.com")
    verifier.verify(signed_token(key, {}))


@pytest.mark.parametrize(
    "overrides",
    [
        {"aud": "https://other.invalid"},
        {"exp": 1},
        {"iss": "https://attacker.invalid"},
        {"email": "other@project.iam.gserviceaccount.com"},
        {"email_verified": False},
    ],
)
def test_oidc_rejects_invalid_claims(
    monkeypatch: pytest.MonkeyPatch, key: rsa.RSAPrivateKey, overrides: dict[str, object]
) -> None:
    install_certificate(monkeypatch, key)
    verifier = GoogleOidcVerifier("https://worker.invalid", "tasks@project.iam.gserviceaccount.com")
    with pytest.raises(WorkflowError):
        verifier.verify(signed_token(key, overrides))


def test_oidc_rejects_forged_signature(
    monkeypatch: pytest.MonkeyPatch, key: rsa.RSAPrivateKey
) -> None:
    install_certificate(monkeypatch, key)
    header, payload, signature = signed_token(key, {}).split(".")
    decoded = base64.urlsafe_b64decode(signature + "=" * (-len(signature) % 4))
    forged = b64(bytes([decoded[0] ^ 1]) + decoded[1:])
    with pytest.raises(WorkflowError, match="UNAUTHORIZED"):
        GoogleOidcVerifier(
            "https://worker.invalid", "tasks@project.iam.gserviceaccount.com"
        ).verify(f"{header}.{payload}.{forged}")


def test_ambiguous_http_response_does_not_trigger_hidden_resend() -> None:
    connection = MagicMock(spec=HTTPConnection)
    connection.sock = object()
    connection.getresponse.side_effect = BadStatusLine("connection closed after request")
    with pytest.raises(BadStatusLine):
        OneShotHttp(timeout=10)._conn_request(connection, "/send", "POST", b"synthetic", {})
    assert connection.request.call_count == 1
    connection.close.assert_called_once()


def test_cloud_tasks_names_are_stable_and_payloads_contain_only_ids() -> None:
    queue = CloudTasksAdapter(
        "synthetic-project",
        "europe-west1",
        "sync-queue",
        "process-queue",
        "https://worker.invalid",
        "tasks@project.iam.gserviceaccount.com",
    )
    job_id = uuid4()
    with patch("reply_mcfly.adapters.cloud_tasks_adapter.tasks_v2.CloudTasksClient") as factory:
        client = factory.return_value.__enter__.return_value
        queue.process(job_id)
        first = client.create_task.call_args.kwargs["request"]["task"]
        queue.process(job_id)
        second = client.create_task.call_args.kwargs["request"]["task"]
        assert first.name == second.name
        assert json.loads(first.http_request.body) == {"job_id": str(job_id)}
        assert first.http_request.oidc_token.audience == "https://worker.invalid"
        assert (
            first.http_request.oidc_token.service_account_email
            == "tasks@project.iam.gserviceaccount.com"
        )
        duplicate: Callable[[str], AlreadyExists] = AlreadyExists
        client.create_task.side_effect = duplicate("synthetic duplicate")
        queue.process(job_id)
