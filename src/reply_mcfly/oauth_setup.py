import argparse
import os
from collections.abc import Callable
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Interactive Gmail OAuth setup; run on your trusted workstation"
    )
    parser.add_argument("--client-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Refusing to overwrite existing OAuth credentials")
    flow = InstalledAppFlow.from_client_secrets_file(
        str(args.client_file),
        scopes=[
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/gmail.send",
        ],
        autogenerate_code_verifier=True,
    )
    credentials = flow.run_local_server(
        host="localhost", port=0, timeout_seconds=300, access_type="offline", prompt="consent"
    )
    if not credentials.refresh_token:
        raise RuntimeError("No refresh token returned; no credentials file was written")
    serialize: Callable[[], str] = credentials.to_json
    descriptor = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as output:
        output.write(serialize())
    print("OAuth credentials saved with mode 0600. Do not paste them into chat or commit them.")


if __name__ == "__main__":
    main()
