import json
import os
import stat
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from reply_mcfly.adapters.google_clients import (
    GmailOAuthFileFactory,
    assert_private_credentials_file,
)
from reply_mcfly.domain.email import WorkflowError


def test_credentials_file_rejects_group_or_world_permissions(tmp_path: Path) -> None:
    target = tmp_path / "gmail-token.json"
    target.write_text('{"refresh_token":"x"}', encoding="utf-8")
    os.chmod(target, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP)
    with pytest.raises(WorkflowError, match="INSECURE_CREDENTIALS_PERMISSIONS"):
        assert_private_credentials_file(target)


def test_credentials_file_rejects_symlinks(tmp_path: Path) -> None:
    real = tmp_path / "real.json"
    real.write_text("{}", encoding="utf-8")
    os.chmod(real, stat.S_IRUSR | stat.S_IWUSR)
    link = tmp_path / "link.json"
    link.symlink_to(real)
    with pytest.raises(WorkflowError, match="INSECURE_CREDENTIALS_PATH"):
        assert_private_credentials_file(link)


def test_oauth_file_factory_builds_gmail_service(tmp_path: Path) -> None:
    target = tmp_path / "gmail-token.json"
    target.write_text(
        json.dumps(
            {
                "client_id": "synthetic",
                "client_secret": "synthetic",
                "refresh_token": "synthetic",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        ),
        encoding="utf-8",
    )
    os.chmod(target, stat.S_IRUSR | stat.S_IWUSR)
    credentials = MagicMock()
    with (
        patch(
            "reply_mcfly.adapters.google_clients.Credentials.from_authorized_user_file",
            return_value=credentials,
        ) as loader,
        patch(
            "reply_mcfly.adapters.google_clients.build_gmail_service",
            return_value="gmail-service",
        ) as builder,
    ):
        service = GmailOAuthFileFactory(target)()
        assert service == "gmail-service"
        loader.assert_called_once()
        builder.assert_called_once_with(credentials)
