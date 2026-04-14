"""Handler de respostas de aprovação no worker.

Intercepta mensagens inbound que são decisões de aprovação (✅, ❌,
✅ 42, etc) ANTES do graph rodar. Se a mensagem é uma decisão válida E
existe a approval correspondente, aplica a transição, executa (em caso
de aprovação) e responde direto à usuária — sem invocar o LLM.

Princípios:
- Falso-positivo é pior que falso-negativo. Se o parser bate mas não há
  approval correspondente, retornamos False e a mensagem segue para o
  graph normalmente.
- Falha de execução de approval NÃO é falha de processamento de
  mensagem. A approval vira status='failed', mas a inbound vira
  'done' (o pipeline cumpriu seu trabalho).
- O handler é o único caller que sabe responder a `✅` — uma mensagem
  reconhecida como aprovação NUNCA chega ao graph.
"""

from __future__ import annotations

import structlog
from psycopg_pool import AsyncConnectionPool

from gyros_os.approvals.parser import parse_approval_decision
from gyros_os.approvals.service import (
    Approval,
    ApprovalNotFound,
    InvalidApprovalTransition,
    execute_approval,
    get_approval,
    get_latest_pending_for_user,
    mark_approved,
    mark_rejected,
)
from gyros_os.shared.db import get_pool
from gyros_os.shared.models import MessageQueue
from gyros_os.shared.org import get_default_org_id
from gyros_os.shared.queue import mark_done, upsert_conversation
from gyros_os.worker.twilio_client import TwilioClient

logger = structlog.get_logger()


def _format_executed_reply(approval: Approval) -> str:
    """Formata a resposta de uma approval executada com sucesso."""
    result = approval.execution_result or {}
    summary = result.get("message") or "Executado."
    return f"✅ Aprovação #{approval.id} executada.\n\n{summary}"


def _format_failed_reply(approval: Approval) -> str:
    """Formata resposta de approval aprovada mas que falhou na execução."""
    error = approval.execution_error or "erro desconhecido"
    return (
        f"⚠️ Aprovação #{approval.id} aprovada mas falhou na execução: {error}"
    )


def _format_rejected_reply(approval_id: int) -> str:
    return f"❌ Aprovação #{approval_id} cancelada."


async def try_handle_approval_reply(
    message: MessageQueue,
    pool: AsyncConnectionPool,
    twilio: TwilioClient,
) -> bool:
    """Tenta tratar a mensagem como resposta de aprovação.

    Retorna True se a mensagem foi consumida (parser bateu, approval
    encontrada, decisão aplicada, reply enviado, mark_done feito).
    Retorna False se a mensagem não é decisão de aprovação OU se é mas
    não há approval pending correspondente — nesse caso, o caller deve
    seguir o fluxo normal (graph).
    """
    decision = parse_approval_decision(message.incoming_message or "")
    if decision is None:
        return False

    org_id = await get_default_org_id(await get_pool())

    # Resolver qual approval é o alvo: ID explícito ou "última pending".
    approval: Approval | None
    if decision.approval_id is not None:
        approval = await get_approval(decision.approval_id)
        # Sanidade: a approval explicitada precisa ser do mesmo usuário
        # E ainda estar pending. Caso contrário, deixamos o graph lidar
        # (ou ignorar) — não é erro do pipeline.
        if approval is None or approval.requested_by != message.phone_number:
            logger.info(
                "approval_handler_id_not_found_or_not_owner",
                approval_id=decision.approval_id,
                requested_by=message.phone_number,
            )
            return False
        if approval.status != "pending":
            logger.info(
                "approval_handler_id_not_pending",
                approval_id=decision.approval_id,
                status=approval.status,
            )
            return False
    else:
        approval = await get_latest_pending_for_user(
            organization_id=org_id,
            requested_by=message.phone_number,
        )
        if approval is None:
            # Parser bateu mas não há nada pending — não é nossa.
            # Devolve pro graph (ele vai responder como conversa normal).
            logger.info(
                "approval_handler_no_pending",
                requested_by=message.phone_number,
                action=decision.action,
            )
            return False

    approval_id = approval.id

    # Aplicar a decisão.
    try:
        if decision.action == "approve":
            await mark_approved(approval_id)
            executed = await execute_approval(approval_id)
            if executed.status == "executed":
                reply = _format_executed_reply(executed)
            else:
                # status == 'failed'
                reply = _format_failed_reply(executed)
        else:
            await mark_rejected(approval_id)
            reply = _format_rejected_reply(approval_id)
    except (ApprovalNotFound, InvalidApprovalTransition) as e:
        # Race condition rara: alguém já decidiu/executou entre o
        # lookup e a transição. Trata como "não é nossa" e devolve
        # pro graph — o LLM consegue conversar sobre isso melhor que
        # uma mensagem técnica vazia.
        logger.warning(
            "approval_handler_transition_failed",
            approval_id=approval_id,
            error=str(e),
        )
        return False

    # Enviar reply via Twilio (mesmo caminho do fluxo normal).
    await twilio.send_message(message.phone_number, reply)

    # Marcar a inbound como processada com sucesso. mark_failed é só pra
    # falha de pipeline; falha de approval não é falha de pipeline.
    await mark_done(
        pool,
        message.id,
        reply,
        normalized_input=None,
    )
    await upsert_conversation(
        pool,
        phone_number=message.phone_number,
        agent_id=message.agent_id,
        last_message=reply,
    )

    logger.info(
        "approval_reply_handled",
        approval_id=approval_id,
        action=decision.action,
        message_id=message.id,
        phone=message.phone_number,
    )
    return True
