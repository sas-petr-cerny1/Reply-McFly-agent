import stat
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from reply_mcfly.oauth_setup import main


def test_oauth_uses_pkce_minimal_scopes_and_private_exclusive_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "synthetic-oauth.json"
    monkeypatch.setattr(
        sys, "argv", ["oauth", "--client-file", "synthetic-client.json", "--output", str(target)]
    )
    with patch("reply_mcfly.oauth_setup.InstalledAppFlow") as factory:
        flow = factory.from_client_secrets_file.return_value
        flow.run_local_server.return_value.to_json.return_value = '{"synthetic":true}'
        main()
        assert factory.from_client_secrets_file.call_args.kwargs == {
            "scopes": [
                "https://www.googleapis.com/auth/gmail.readonly",
                "https://www.googleapis.com/auth/gmail.send",
            ],
            "autogenerate_code_verifier": True,
        }
        assert flow.run_local_server.call_args.kwargs["host"] == "localhost"
        assert stat.S_IMODE(target.stat().st_mode) == 0o600
        assert target.read_text() == '{"synthetic":true}'
        factory.reset_mock()
        with pytest.raises(FileExistsError):
            main()
        factory.from_client_secrets_file.assert_not_called()


def test_oauth_without_refresh_token_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "synthetic-oauth.json"
    monkeypatch.setattr(
        sys, "argv", ["oauth", "--client-file", "synthetic-client.json", "--output", str(target)]
    )
    with patch("reply_mcfly.oauth_setup.InstalledAppFlow") as factory:
        flow = factory.from_client_secrets_file.return_value
        flow.run_local_server.return_value.refresh_token = None
        with pytest.raises(RuntimeError, match="No refresh token"):
            main()
        assert not target.exists()
