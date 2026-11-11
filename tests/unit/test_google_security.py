from http.client import BadStatusLine, HTTPConnection
from unittest.mock import MagicMock

import pytest

from reply_mcfly.adapters.google_clients import OneShotHttp


def test_ambiguous_http_response_does_not_trigger_hidden_resend() -> None:
    connection = MagicMock(spec=HTTPConnection)
    connection.sock = object()
    connection.getresponse.side_effect = BadStatusLine("connection closed after request")
    with pytest.raises(BadStatusLine):
        OneShotHttp(timeout=10)._conn_request(connection, "/send", "POST", b"synthetic", {})
    assert connection.request.call_count == 1
    connection.close.assert_called_once()
