from google.auth.credentials import Credentials
from httplib2 import Http

class AuthorizedHttp:
    def __init__(
        self,
        credentials: Credentials,
        http: Http | None = ...,
        refresh_status_codes: tuple[int, ...] = ...,
        max_refresh_attempts: int = ...,
    ) -> None: ...
