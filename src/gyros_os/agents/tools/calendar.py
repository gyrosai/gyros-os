"""Tool create_calendar_event — propõe criação de evento no Google Calendar.

Valida os parâmetros de entrada, monta um preview legível, e delega a
`propose_action` para registrar a ação como pendente de aprovação
humana. A execução real acontece no worker (executor registrado em
approvals/executors.py na Fatia 3.3 Checkpoint 2) depois que a Camila
aprovar.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any
from zoneinfo import ZoneInfo

import structlog
from langchain_core.tools import InjectedToolArg, tool
from pydantic import BaseModel, Field

from gyros_os.agents.tools.approvals import _extract_configurable, propose_action

logger = structlog.get_logger()

DEFAULT_TZ = "America/Sao_Paulo"


def _parse_iso_with_tz(value: str, default_tz: str = DEFAULT_TZ) -> datetime:
    """Parseia ISO-8601 e normaliza para default_tz (America/Sao_Paulo).

    Se naive, aplica default_tz como tz da observação.
    Se aware, converte pra default_tz (preserva o instante, muda a representação).
    """
    dt = datetime.fromisoformat(value)
    tz = ZoneInfo(default_tz)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=tz)
    return dt.astimezone(tz)


def _format_preview(
    title: str,
    start: datetime,
    end: datetime,
    location: str | None,
    description: str | None,
) -> str:
    """Preview curto (3-5 linhas) pra WhatsApp."""
    lines = [f"📅 Criar evento: *{title}*"]
    tz_label = str(start.tzinfo) if start.tzinfo else ""
    if start.date() == end.date():
        when = (
            f"{start.strftime('%a %d/%m %H:%M')} → {end.strftime('%H:%M')}"
        )
    else:
        when = (
            f"{start.strftime('%a %d/%m %H:%M')} → "
            f"{end.strftime('%a %d/%m %H:%M')}"
        )
    if tz_label:
        when += f" ({tz_label})"
    lines.append(when)
    if location:
        lines.append(f"📍 {location}")
    if description:
        desc = description.strip()
        if len(desc) > 100:
            desc = desc[:97] + "..."
        lines.append(f"📝 {desc}")
    return "\n".join(lines)


class CreateCalendarEventInput(BaseModel):
    title: str = Field(description="Título do evento.")
    start: str = Field(
        description=(
            "Início em ISO-8601 (ex: '2026-04-14T14:00:00-03:00'). "
            "Se vier sem timezone, assume America/Sao_Paulo."
        )
    )
    end: str = Field(
        description="Fim em ISO-8601. Deve ser estritamente posterior ao início."
    )
    description: str | None = Field(default=None, description="Descrição opcional.")
    location: str | None = Field(default=None, description="Local opcional.")


@tool("create_calendar_event", args_schema=CreateCalendarEventInput)
async def create_calendar_event(
    title: str,
    start: str,
    end: str,
    description: str | None = None,
    location: str | None = None,
    *,
    runtime: Annotated[Any, InjectedToolArg()] = None,
) -> dict[str, Any]:
    """Propõe a criação de um evento no Google Calendar da Camila.

    Use quando a Camila pedir para marcar, agendar ou criar um evento.
    Não executa nada direto — registra uma aprovação pendente via
    propose_action. Depois do ✅ dela, o worker cria o evento no Google
    Calendar.

    Se faltar horário, título ou duração, pergunte antes — nunca chute.
    """
    title = (title or "").strip()
    if not title:
        return {"status": "error", "error": "Título do evento não pode ser vazio."}

    try:
        start_dt = _parse_iso_with_tz(start)
        end_dt = _parse_iso_with_tz(end)
    except ValueError as exc:
        return {"status": "error", "error": f"Datetime inválido: {exc}"}

    if end_dt <= start_dt:
        return {
            "status": "error",
            "error": "Horário de fim precisa ser posterior ao início.",
        }

    configurable = _extract_configurable(runtime)
    user_id = configurable.get("user_id", "unknown")

    payload: dict[str, Any] = {
        "user_id": str(user_id),
        "title": title,
        "start": start_dt.isoformat(),
        "end": end_dt.isoformat(),
    }
    if description:
        payload["description"] = description
    if location:
        payload["location"] = location

    preview_text = _format_preview(
        title, start_dt, end_dt, location, description
    )

    logger.info(
        "create_calendar_event_proposed",
        title=title,
        user_id=user_id,
        start=payload["start"],
        end=payload["end"],
    )

    return await propose_action.coroutine(
        action_type="gcal_create_event",
        payload=payload,
        preview_text=preview_text,
        runtime=runtime,
    )
