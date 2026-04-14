"""Registry de executores de approvals.

Cada `action_type` registra uma função async que recebe o payload da
approval e retorna um dict que vira `execution_result`. Falhas devem
levantar exceção — `execute_approval` no service.py converte em
status='failed' + execution_error.

Esta fatia (3.1) só registra o executor 'noop_test', usado para validar
o loop ponta a ponta sem integração externa. Executores reais (Google
Calendar, email, etc) vêm nas Fatias 3.2/3.3.
"""

from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable

import structlog
from googleapiclient.errors import HttpError

from gyros_os.oauth.providers.google import (
    GoogleCredentialsNotFound,
    get_google_calendar_client,
)

logger = structlog.get_logger()

ExecutorFn = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]

_registry: dict[str, ExecutorFn] = {}


def register_executor(action_type: str) -> Callable[[ExecutorFn], ExecutorFn]:
    """Decorator para registrar um executor por action_type.

    Levanta ValueError se o action_type já estiver registrado, para
    evitar duplo-registro silencioso após refactor.
    """

    def decorator(fn: ExecutorFn) -> ExecutorFn:
        if action_type in _registry:
            raise ValueError(f"executor já registrado para action_type='{action_type}'")
        _registry[action_type] = fn
        return fn

    return decorator


def get_executor(action_type: str) -> ExecutorFn | None:
    """Retorna o executor registrado, ou None se não houver."""
    return _registry.get(action_type)


# ---------- Executores registrados ----------


@register_executor("noop_test")
async def _noop_test_executor(payload: dict[str, Any]) -> dict[str, Any]:
    """Executor de teste — não faz nada externo, só ecoa o payload.

    Existe para permitir validar o loop completo de HITL sem depender de
    nenhuma integração real. Será removido junto com a instrução
    temporária do prompt da Lyra na Fatia 3.3 (ou antes, quando houver
    executores reais suficientes para validar o sistema).
    """
    logger.info("noop_executor_called", payload=payload)
    return {
        "ok": True,
        "message": "noop executed",
        "echoed_payload": payload,
    }


@register_executor("gcal_create_event")
async def execute_gcal_create_event(payload: dict[str, Any]) -> dict[str, Any]:
    """Cria evento no Google Calendar primário do usuário que pediu.

    Consome payload montado pela tool create_calendar_event (Fatia 3.3).
    Resolve user_id de payload["user_id"] (E.164 com + per Convenção 1).

    O payload tem user_id duplicado de approval.requested_by como workaround
    porque o contrato atual de ExecutorFn só recebe payload, não Approval
    inteiro. Tech debt médio documentado em 99-tech-debt.md.

    Sucesso: retorna dict que vai pra approval.execution_result.
    Erro: raise Exception, capturado pelo service.py:execute_approval e
    gravado em approval.execution_error.
    """
    user_id = payload.get("user_id")
    if not user_id:
        raise Exception("Payload sem user_id. Bug de montagem na tool.")

    title = payload.get("title")
    start_iso = payload.get("start")
    end_iso = payload.get("end")
    if not all([title, start_iso, end_iso]):
        raise Exception(
            f"Payload incompleto: title={bool(title)}, "
            f"start={bool(start_iso)}, end={bool(end_iso)}"
        )

    try:
        client = await get_google_calendar_client(user_id=user_id)
    except GoogleCredentialsNotFound as e:
        raise Exception(
            f"Não achei credencial OAuth pra {e.user_id}. "
            f"Re-autorize em /oauth/google/start?user_id={user_id}"
        )

    event_body: dict[str, Any] = {
        "summary": title,
        "start": {
            "dateTime": start_iso,
            "timeZone": "America/Sao_Paulo",
        },
        "end": {
            "dateTime": end_iso,
            "timeZone": "America/Sao_Paulo",
        },
    }
    if payload.get("description"):
        event_body["description"] = payload["description"]
    if payload.get("location"):
        event_body["location"] = payload["location"]

    logger.info(
        "gcal_create_event_executing",
        user_id=user_id,
        title=title,
        start=start_iso,
        end=end_iso,
    )

    try:
        created = await asyncio.to_thread(
            lambda: client.events()
            .insert(
                calendarId="primary",
                body=event_body,
                sendUpdates="none",
            )
            .execute()
        )
    except HttpError as e:
        status_code = e.resp.status
        reason = e.reason or "desconhecido"

        if status_code == 401:
            raise Exception(
                "Google recusou acesso (401). Token revogado? "
                f"Re-autorize em /oauth/google/start?user_id={user_id}"
            )
        elif status_code == 403:
            raise Exception(
                f"Google recusou permissão (403): {reason}. "
                f"Possível problema de scope. Re-autorize se persistir."
            )
        elif status_code == 400:
            logger.warning(
                "gcal_insert_rejected_400",
                user_id=user_id,
                reason=reason,
                event_body=event_body,
            )
            raise Exception(f"Google rejeitou os dados do evento: {reason}")
        elif 500 <= status_code < 600:
            raise Exception(
                f"Google Calendar instável ({status_code}). "
                f"Tenta daqui a alguns minutos."
            )
        else:
            raise Exception(f"Google retornou HTTP {status_code}: {reason}")

    logger.info(
        "gcal_create_event_succeeded",
        user_id=user_id,
        event_id=created["id"],
        html_link=created.get("htmlLink"),
    )

    return {
        "ok": True,
        "event_id": created["id"],
        "html_link": created.get("htmlLink"),
        "calendar_id": "primary",
        "summary": title,
    }
