from typing import Any, Self

from google.oauth2.credentials import Credentials

class InstalledAppFlow:
    @classmethod
    def from_client_secrets_file(
        cls, client_secrets_file: str, scopes: list[str], **kwargs: Any
    ) -> Self: ...
    def run_local_server(
        self, host: str = ..., port: int = ..., timeout_seconds: int = ..., **kwargs: Any
    ) -> Credentials: ...
