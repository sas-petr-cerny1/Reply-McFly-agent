import json
from collections.abc import Callable
from http.client import HTTPConnection, HTTPException
from typing import Any, cast

import google_auth_httplib2
import httplib2
from google.api_core.exceptions import GoogleAPICallError
from google.auth.exceptions import GoogleAuthError
from google.cloud import secretmanager
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from pydantic import BaseModel, SecretStr

from reply_mcfly.domain.email import WorkflowError


class OAuthSecret(BaseModel):
    client_id: SecretStr
    client_secret: SecretStr
    refresh_token: SecretStr


class OneShotHttp(httplib2.Http):
    """Disable httplib2's implicit reconnect/resend after an ambiguous response."""

    def _conn_request(
        self,
        conn: HTTPConnection,
        request_uri: str,
        method: str,
        body: bytes | str | None,
        headers: dict[str, str],
    ) -> tuple[httplib2.Response, bytes]:
        headers = {**headers, "accept-encoding": "identity"}
        try:
            if conn.sock is None:
                conn.connect()
            conn.request(method, request_uri, body, headers)
            response = conn.getresponse()
            return httplib2.Response(response), response.read()
        except (OSError, HTTPException):
            conn.close()
            raise


class GmailServiceFactory:
    def __init__(self, secret_version: str) -> None:
        self.secret_version = secret_version

    def __call__(self) -> Any:
        try:
            with secretmanager.SecretManagerServiceClient() as client:
                result = client.access_secret_version(
                    request={"name": self.secret_version}, timeout=5, retry=None
                )
            info = OAuthSecret.model_validate(json.loads(result.payload.data))
            # The SDK stub leaves this factory untyped; constrain its documented boundary.
            from_info: Callable[[dict[str, str], list[str]], Credentials] = (
                Credentials.from_authorized_user_info
            )
            credentials = from_info(
                {
                    "client_id": info.client_id.get_secret_value(),
                    "client_secret": info.client_secret.get_secret_value(),
                    "refresh_token": info.refresh_token.get_secret_value(),
                },
                [
                    "https://www.googleapis.com/auth/gmail.readonly",
                    "https://www.googleapis.com/auth/gmail.send",
                ],
            )
            http = OneShotHttp(timeout=10)
            http.follow_redirects = False
            transport = google_auth_httplib2.AuthorizedHttp(
                credentials, http=http, max_refresh_attempts=0
            )
            # Discovery stubs omit the AuthorizedHttp wrapper supported by the SDK.
            return build(
                "gmail",
                "v1",
                http=cast(httplib2.Http, transport),
                cache_discovery=False,
                static_discovery=True,
            )
        except (GoogleAPICallError, GoogleAuthError, ValueError, OSError):
            raise WorkflowError(
                "GMAIL_CREDENTIALS_UNAVAILABLE", retryable=True, status=503
            ) from None
