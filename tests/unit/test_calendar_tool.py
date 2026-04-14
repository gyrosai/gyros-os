"""Testes unitários da tool create_calendar_event.

Cobertura: nome/schema da tool, validações (título, ISO, end>start),
inclusão do user_id como primeira chave do payload, e delegação a
propose_action via patch do atributo .coroutine.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from gyros_os.agents.tools import calendar as calendar_module
from gyros_os.agents.tools.calendar import (
    _parse_iso_with_tz,
    create_calendar_event,
)

create_calendar_event_fn = create_calendar_event.coroutine


def _make_runtime(*, user_id: str | None = "+5511999999999"):
    configurable = {"thread_id": "thread-test"}
    if user_id:
        configurable["user_id"] = user_id
    runtime = MagicMock()
    runtime.config = {"configurable": configurable}
    return runtime


def _patched_propose():
    """Substitui propose_action.coroutine por AsyncMock isolado."""
    mock = AsyncMock(
        return_value={
            "status": "approval_proposed",
            "approval_id": 123,
            "user_facing_message": "📋 Aprovação pendente #123\n\n…",
        }
    )
    return patch.object(calendar_module.propose_action, "coroutine", new=mock), mock


class TestCreateCalendarEventTool:
    def test_tool_has_correct_name(self):
        assert create_calendar_event.name == "create_calendar_event"

    def test_tool_has_expected_schema_fields(self):
        schema = create_calendar_event.get_input_schema()
        fields = schema.model_fields
        for name in ("title", "start", "end", "description", "location"):
            assert name in fields
        # attendees é 3.4 — não deve estar no schema da 3.3
        assert "attendees" not in fields

    def test_happy_path_delegates_to_propose_action_with_user_id_first(self):
        ctx, mock_propose = _patched_propose()
        runtime = _make_runtime(user_id="+5511888888888")

        with ctx:
            result = asyncio.run(
                create_calendar_event_fn(
                    title="Call com Pedro",
                    start="2026-04-14T14:00:00-03:00",
                    end="2026-04-14T15:00:00-03:00",
                    description="Review trimestral",
                    location="Google Meet",
                    runtime=runtime,
                )
            )

        assert result["status"] == "approval_proposed"
        mock_propose.assert_awaited_once()
        kwargs = mock_propose.await_args.kwargs
        # action_type tem que ser "gcal_create_event" (nome do executor do Checkpoint 2),
        # não "create_calendar_event" (nome da tool).
        assert kwargs["action_type"] == "gcal_create_event"
        payload = kwargs["payload"]
        # user_id deve ser a PRIMEIRA chave do payload
        assert list(payload.keys())[0] == "user_id"
        assert payload["user_id"] == "+5511888888888"
        assert payload["title"] == "Call com Pedro"
        assert payload["description"] == "Review trimestral"
        assert payload["location"] == "Google Meet"
        # attendees é 3.4 — nunca deve aparecer no payload da 3.3
        assert "attendees" not in payload
        # preview formatado tem título e horários
        assert "Call com Pedro" in kwargs["preview_text"]
        assert "14:00" in kwargs["preview_text"]

    def test_rejects_end_before_start(self):
        ctx, mock_propose = _patched_propose()
        runtime = _make_runtime()

        with ctx:
            result = asyncio.run(
                create_calendar_event_fn(
                    title="X",
                    start="2026-04-14T15:00:00-03:00",
                    end="2026-04-14T14:00:00-03:00",
                    runtime=runtime,
                )
            )

        assert result["status"] == "error"
        assert "fim" in result["error"].lower() or "início" in result["error"].lower()
        mock_propose.assert_not_awaited()

    def test_rejects_invalid_iso(self):
        ctx, mock_propose = _patched_propose()
        runtime = _make_runtime()

        with ctx:
            result = asyncio.run(
                create_calendar_event_fn(
                    title="X",
                    start="amanhã às 14h",
                    end="2026-04-14T15:00:00-03:00",
                    runtime=runtime,
                )
            )

        assert result["status"] == "error"
        assert "datetime" in result["error"].lower() or "inválido" in result["error"].lower()
        mock_propose.assert_not_awaited()

    def test_rejects_empty_title(self):
        ctx, mock_propose = _patched_propose()
        runtime = _make_runtime()

        with ctx:
            result = asyncio.run(
                create_calendar_event_fn(
                    title="   ",
                    start="2026-04-14T14:00:00-03:00",
                    end="2026-04-14T15:00:00-03:00",
                    runtime=runtime,
                )
            )

        assert result["status"] == "error"
        assert "título" in result["error"].lower() or "titulo" in result["error"].lower()
        mock_propose.assert_not_awaited()

    def test_naive_datetime_gets_default_tz(self):
        dt = _parse_iso_with_tz("2026-04-14T14:00:00")
        assert dt.tzinfo is not None
        assert "Sao_Paulo" in str(dt.tzinfo)

    def test_aware_datetime_in_other_tz_converts_to_sao_paulo(self):
        """ISO com offset explícito UTC é convertido pra America/Sao_Paulo.

        17:00 UTC = 14:00 BRT (BR não tem DST desde 2019, então -3 fixo).
        """
        result = _parse_iso_with_tz("2026-04-15T17:00:00+00:00")

        assert str(result.tzinfo) == "America/Sao_Paulo"
        assert result.hour == 14
        assert result.day == 15
        assert result.month == 4
