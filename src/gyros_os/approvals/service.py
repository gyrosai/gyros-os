"""Serviço de approvals — CRUD + transições de estado defensivas + execução.

Toda transição de status valida o estado anterior. Se algo tentar marcar
uma approval já executada como executed de novo, levanta
InvalidApprovalTransition em vez de silenciosamente sobrescrever — isso
protege contra race conditions e contra bugs de chamadores futuros.

execute_approval encapsula a chamada do executor e converte exceções em
status='failed' (com execution_error preenchido). Não levanta exceção
para fora porque quem chama é o worker, e uma tool quebrada não pode
derrubar a mensagem inteira.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

import structlog

from gyros_os.approvals.executors import get_executor
from gyros_os.shared.db import get_pool

logger = structlog.get_logger()


# ---------- Exceções ----------


class ApprovalNotFound(Exception):
    """Approval id solicitado não existe."""

    def __init__(self, approval_id: int) -> None:
        super().__init__(f"approval {approval_id} not found")
        self.approval_id = approval_id


class InvalidApprovalTransition(Exception):
    """Tentativa de transição de status inválida (ex: executed -> executed)."""

    def __init__(self, approval_id: int, current: str, attempted: str) -> None:
        super().__init__(
            f"approval {approval_id}: cannot transition from '{current}' to '{attempted}'"
        )
        self.approval_id = approval_id
        self.current = current
        self.attempted = attempted


# ---------- Modelo interno ----------


@dataclass
class Approval:
    """Espelho da linha em `approvals`. Não cruza fronteira externa.

    Por isso é dataclass, não Pydantic — ver convenção em
    shared/models.py vs uso interno.
    """

    id: int
    organization_id: UUID
    action_type: str
    payload: dict[str, Any]
    preview_text: str
    status: str
    proposed_at: datetime
    decided_at: datetime | None
    executed_at: datetime | None
    execution_result: dict[str, Any] | None
    execution_error: str | None
    requested_by: str | None
    thread_id: str | None
    created_at: datetime


_SELECT_COLUMNS = """
    id, organization_id, action_type, payload, preview_text, status,
    proposed_at, decided_at, executed_at, execution_result, execution_error,
    requested_by, thread_id, created_at
"""


def _row_to_approval(row: tuple) -> Approval:
    return Approval(
        id=row[0],
        organization_id=row[1],
        action_type=row[2],
        payload=row[3] or {},
        preview_text=row[4],
        status=row[5],
        proposed_at=row[6],
        decided_at=row[7],
        executed_at=row[8],
        execution_result=row[9],
        execution_error=row[10],
        requested_by=row[11],
        thread_id=row[12],
        created_at=row[13],
    )


# ---------- CRUD básico ----------


async def create_approval(
    organization_id: UUID,
    action_type: str,
    payload: dict[str, Any],
    preview_text: str,
    requested_by: str,
    thread_id: str | None = None,
) -> int:
    """Insere uma nova approval com status 'pending'. Retorna o id gerado."""
    import json

    pool = await get_pool()
    async with pool.connection() as conn:
        cursor = await conn.execute(
            """
            INSERT INTO approvals
                (organization_id, action_type, payload, preview_text,
                 requested_by, thread_id)
            VALUES (%s, %s, %s::jsonb, %s, %s, %s)
            RETURNING id
            """,
            (
                str(organization_id),
                action_type,
                json.dumps(payload),
                preview_text,
                requested_by,
                thread_id,
            ),
        )
        row = await cursor.fetchone()
        await conn.commit()

    approval_id = row[0]
    logger.info(
        "approval_created",
        approval_id=approval_id,
        action_type=action_type,
        requested_by=requested_by,
        thread_id=thread_id,
    )
    return approval_id


async def get_approval(approval_id: int) -> Approval | None:
    """Busca uma approval pelo id. Retorna None se não existir."""
    pool = await get_pool()
    async with pool.connection() as conn:
        cursor = await conn.execute(
            f"SELECT {_SELECT_COLUMNS} FROM approvals WHERE id = %s",
            (approval_id,),
        )
        row = await cursor.fetchone()

    return _row_to_approval(row) if row else None


async def get_latest_pending_for_user(
    organization_id: UUID,
    requested_by: str,
) -> Approval | None:
    """Retorna a última (mais recente) approval pending deste usuário."""
    logger.info(
        "approval_lookup_pending",
        requested_by=requested_by,
        organization_id=str(organization_id),
    )
    pool = await get_pool()
    async with pool.connection() as conn:
        cursor = await conn.execute(
            f"""
            SELECT {_SELECT_COLUMNS}
            FROM approvals
            WHERE organization_id = %s
              AND requested_by = %s
              AND status = 'pending'
            ORDER BY proposed_at DESC
            LIMIT 1
            """,
            (str(organization_id), requested_by),
        )
        row = await cursor.fetchone()

    return _row_to_approval(row) if row else None


# ---------- Transições de status (defensivas) ----------


async def _transition_status(
    approval_id: int,
    expected_current: str,
    new_status: str,
    extra_set_sql: str = "",
    extra_params: tuple = (),
) -> Approval:
    """Helper de transição: só atualiza se status atual bate o esperado.

    Usa UPDATE ... WHERE status = expected dentro de uma única SQL para
    evitar race condition entre SELECT e UPDATE. Se nada foi atualizado,
    relê o estado atual e levanta InvalidApprovalTransition ou
    ApprovalNotFound conforme o caso.
    """
    pool = await get_pool()
    async with pool.connection() as conn:
        cursor = await conn.execute(
            f"""
            UPDATE approvals
            SET status = %s{extra_set_sql}
            WHERE id = %s AND status = %s
            RETURNING {_SELECT_COLUMNS}
            """,
            (new_status, *extra_params, approval_id, expected_current),
        )
        row = await cursor.fetchone()
        await conn.commit()

    if row is None:
        # Atualização não bateu — descobrir por quê.
        current = await get_approval(approval_id)
        if current is None:
            raise ApprovalNotFound(approval_id)
        raise InvalidApprovalTransition(approval_id, current.status, new_status)

    approval = _row_to_approval(row)
    logger.info(
        "approval_transitioned",
        approval_id=approval_id,
        status_before=expected_current,
        status_after=new_status,
    )
    return approval


async def mark_approved(approval_id: int) -> Approval:
    """pending -> approved. Seta decided_at."""
    return await _transition_status(
        approval_id,
        expected_current="pending",
        new_status="approved",
        extra_set_sql=", decided_at = NOW()",
    )


async def mark_rejected(approval_id: int) -> Approval:
    """pending -> rejected. Seta decided_at."""
    return await _transition_status(
        approval_id,
        expected_current="pending",
        new_status="rejected",
        extra_set_sql=", decided_at = NOW()",
    )


async def mark_executed(approval_id: int, result: dict[str, Any]) -> Approval:
    """approved -> executed. Seta executed_at e execution_result."""
    import json

    return await _transition_status(
        approval_id,
        expected_current="approved",
        new_status="executed",
        extra_set_sql=", executed_at = NOW(), execution_result = %s::jsonb",
        extra_params=(json.dumps(result),),
    )


async def mark_failed(approval_id: int, error: str) -> Approval:
    """approved -> failed. Seta executed_at e execution_error."""
    return await _transition_status(
        approval_id,
        expected_current="approved",
        new_status="failed",
        extra_set_sql=", executed_at = NOW(), execution_error = %s",
        extra_params=(error,),
    )


# ---------- Execução ----------


async def execute_approval(approval_id: int) -> Approval:
    """Executa uma approval com status 'approved'.

    Busca o executor pelo action_type, roda, e marca como 'executed' ou
    'failed' conforme o resultado. NÃO levanta exceção do executor pra
    fora — falha vira status='failed' com execution_error preenchido.

    Levanta:
        ApprovalNotFound: se a approval não existir
        InvalidApprovalTransition: se ela não estiver em 'approved'
    """
    approval = await get_approval(approval_id)
    if approval is None:
        raise ApprovalNotFound(approval_id)
    if approval.status != "approved":
        raise InvalidApprovalTransition(
            approval_id, approval.status, "executed"
        )

    executor = get_executor(approval.action_type)
    if executor is None:
        logger.error(
            "approval_no_executor",
            approval_id=approval_id,
            action_type=approval.action_type,
        )
        return await mark_failed(
            approval_id,
            f"no executor registered for action_type '{approval.action_type}'",
        )

    try:
        result = await executor(approval.payload)
        executed = await mark_executed(approval_id, result)
        logger.info(
            "approval_executed",
            approval_id=approval_id,
            action_type=approval.action_type,
        )
        return executed
    except Exception as e:
        logger.exception(
            "approval_execution_failed",
            approval_id=approval_id,
            action_type=approval.action_type,
        )
        return await mark_failed(approval_id, str(e))
