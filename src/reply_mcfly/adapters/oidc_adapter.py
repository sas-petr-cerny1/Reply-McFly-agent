from collections.abc import Mapping
from typing import Any, Literal

import requests
from google.auth import transport
from google.auth.exceptions import GoogleAuthError
from google.oauth2 import id_token
from pydantic import BaseModel, ConfigDict, StrictBool, ValidationError

from reply_mcfly.domain.email import WorkflowError


class _CertificateResponse(transport.Response):
    def __init__(self, response: requests.Response) -> None:
        self.response = response

    @property
    def status(self) -> int:
        return self.response.status_code

    @property
    def data(self) -> bytes:
        return self.response.content

    @property
    def headers(self) -> Mapping[str, str]:
        return self.response.headers


class _CertificateRequest(transport.Request):
    def __call__(
        self,
        url: str,
        method: str = "GET",
        body: bytes | None = None,
        headers: Mapping[str, str] | None = None,
        timeout: float | None = None,
        **kwargs: Any,
    ) -> _CertificateResponse:
        return _CertificateResponse(
            requests.request(method, url, data=body, headers=headers, timeout=5)
        )


class _Claims(BaseModel):
    model_config = ConfigDict(strict=True)
    iss: Literal["https://accounts.google.com", "accounts.google.com"]
    email: str
    email_verified: StrictBool
    sub: str


class GoogleOidcVerifier:
    def __init__(self, audience: str, service_account: str) -> None:
        self.audience, self.service_account = audience, service_account

    def verify(self, token: str) -> None:
        try:
            # Verifies signature, expiry and audience before trusting identity claims.
            claims = _Claims.model_validate(
                id_token.verify_token(token, _CertificateRequest(), audience=self.audience)
            )
        except (ValueError, GoogleAuthError, ValidationError):
            raise WorkflowError("UNAUTHORIZED", status=401) from None
        except requests.RequestException:
            raise WorkflowError(
                "OIDC_VERIFICATION_UNAVAILABLE", retryable=True, status=503
            ) from None
        if not claims.email_verified or claims.email != self.service_account or not claims.sub:
            raise WorkflowError("FORBIDDEN", status=403)
