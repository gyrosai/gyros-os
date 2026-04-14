"""Testes unitários do executor gcal_create_event.

Não toca Google real — todas as chamadas a `get_google_calendar_client`
e ao client Google Calendar são mockadas. Cobre happy path, validações
defensivas do payload, ausência de credencial, e tratamento granular de
HttpError por status code.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from googleapiclient.errors import HttpError

from gyros_os.approvals.executors import execute_gcal_create_event
from gyros_os.oauth.providers.google import GoogleCredentialsNotFound


VALID_PAYLOAD = {
    "user_id": "+5521981354432",
    "title": "Call com Pedro",
    "start": "2026-04-15T14:00:00-03:00",
    "end": "2026-04-15T14:30:00-03:00",
}


def make_http_error(status: int, reason: str = "Test") -> HttpError:
    resp = MagicMock()
    resp.status = status
    resp.reason = reason
    return HttpError(resp=resp, content=b"{}")


def _client_returning(insert_result: dict) -> MagicMock:
    """Mock de client cujo events().insert().execute() devolve insert_result."""
    client = MagicMock()
    client.events.return_value.insert.return_value.execute.return_value = insert_result
    return client


def _client_raising(exc: Exception) -> MagicMock:
    client = MagicMock()
    client.events.return_value.insert.return_value.execute.side_effect = exc
    return client


def _run(payload: dict):
    return asyncio.run(execute_gcal_create_event(payload))


# ---------- Happy path ----------


def test_happy_path_returns_ok_dict():
    client = _client_returning(
        {"id": "evt_123", "htmlLink": "https://calendar.google.com/event?eid=abc"}
    )
    with patch(
        "gyros_os.approvals.executors.get_google_calendar_client",
        new=AsyncMock(return_value=client),
    ):
        result = _run(VALID_PAYLOAD)

    assert result["ok"] is True
    assert result["event_id"] == "evt_123"
    assert result["html_link"] == "https://calendar.google.com/event?eid=abc"
    assert result["calendar_id"] == "primary"
    assert result["summary"] == "Call com Pedro"


# ---------- Validação defensiva do payload ----------


def test_payload_missing_user_id_raises():
    payload = {k: v for k, v in VALID_PAYLOAD.items() if k != "user_id"}
    with pytest.raises(Exception, match="user_id"):
        _run(payload)


def test_payload_missing_title_raises():
    payload = {k: v for k, v in VALID_PAYLOAD.items() if k != "title"}
    with pytest.raises(Exception, match="Payload incompleto"):
        _run(payload)


# ---------- Credencial ausente ----------


def test_credentials_not_found_raises_helpful_message():
    with patch(
        "gyros_os.approvals.executors.get_google_calendar_client",
        new=AsyncMock(side_effect=GoogleCredentialsNotFound(user_id="+5521981354432")),
    ):
        with pytest.raises(Exception) as exc:
            _run(VALID_PAYLOAD)

    msg = str(exc.value)
    assert "Re-autorize" in msg
    assert "+5521981354432" in msg


# ---------- HttpError por status ----------


def test_http_error_401_raises_reauth_message():
    client = _client_raising(make_http_error(401, "Unauthorized"))
    with patch(
        "gyros_os.approvals.executors.get_google_calendar_client",
        new=AsyncMock(return_value=client),
    ):
        with pytest.raises(Exception) as exc:
            _run(VALID_PAYLOAD)

    msg = str(exc.value)
    assert "401" in msg
    assert "Re-autorize" in msg


def test_http_error_403_raises_scope_message():
    client = _client_raising(make_http_error(403, "Forbidden"))
    with patch(
        "gyros_os.approvals.executors.get_google_calendar_client",
        new=AsyncMock(return_value=client),
    ):
        with pytest.raises(Exception) as exc:
            _run(VALID_PAYLOAD)

    msg = str(exc.value)
    assert "403" in msg
    assert "scope" in msg.lower()


def test_http_error_400_logs_warning_and_raises():
    client = _client_raising(make_http_error(400, "Invalid dateTime"))
    with patch(
        "gyros_os.approvals.executors.get_google_calendar_client", return_value=client
    ), patch("gyros_os.approvals.executors.logger") as mock_logger:
        with pytest.raises(Exception):
            _run(VALID_PAYLOAD)

    warning_calls = [c for c in mock_logger.warning.call_args_list]
    assert any(
        c.args and c.args[0] == "gcal_insert_rejected_400" for c in warning_calls
    )


def test_http_error_500_raises_retry_message():
    client = _client_raising(make_http_error(500, "Internal Server Error"))
    with patch(
        "gyros_os.approvals.executors.get_google_calendar_client",
        new=AsyncMock(return_value=client),
    ):
        with pytest.raises(Exception, match="instável"):
            _run(VALID_PAYLOAD)


# ---------- Event body ----------


def test_event_body_includes_optional_fields():
    client = _client_returning({"id": "evt_x", "htmlLink": "http://x"})
    payload = {
        **VALID_PAYLOAD,
        "description": "Review trimestral",
        "location": "Google Meet",
    }
    with patch(
        "gyros_os.approvals.executors.get_google_calendar_client",
        new=AsyncMock(return_value=client),
    ):
        _run(payload)

    body = client.events.return_value.insert.call_args.kwargs["body"]
    assert body["description"] == "Review trimestral"
    assert body["location"] == "Google Meet"
    assert body["summary"] == "Call com Pedro"
    assert body["start"] == {
        "dateTime": "2026-04-15T14:00:00-03:00",
        "timeZone": "America/Sao_Paulo",
    }


def test_event_body_omits_optional_fields_when_absent():
    client = _client_returning({"id": "evt_x", "htmlLink": "http://x"})
    with patch(
        "gyros_os.approvals.executors.get_google_calendar_client",
        new=AsyncMock(return_value=client),
    ):
        _run(VALID_PAYLOAD)

    body = client.events.return_value.insert.call_args.kwargs["body"]
    assert "description" not in body
    assert "location" not in body


def test_send_updates_is_none():
    client = _client_returning({"id": "evt_x", "htmlLink": "http://x"})
    with patch(
        "gyros_os.approvals.executors.get_google_calendar_client",
        new=AsyncMock(return_value=client),
    ):
        _run(VALID_PAYLOAD)

    kwargs = client.events.return_value.insert.call_args.kwargs
    assert kwargs["sendUpdates"] == "none"
    assert kwargs["calendarId"] == "primary"
