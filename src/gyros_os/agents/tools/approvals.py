"""Tool propose_action — Human-in-the-Loop.

Quando o agente decide que uma ação precisa escrever no mundo externo
(criar evento, enviar email, etc), ele NÃO executa direto. Chama
`propose_action`, que registra a ação como pending em `approvals` e
retorna ao agente um texto pronto pra ser enviado à usuária pedindo
aprovação.

A execução real só acontece depois que a usuária responder ✅, no
handler do worker (não nesta tool).
"""

from __future__ import annotations

from typing import Annotated, Any

import structlog
from langchain_core.runnables.config import var_child_runnable_config
from langchain_core.tools import InjectedToolArg, tool
from pydantic import BaseModel, Field

from gyros_os.approvals.service import create_approval
from gyros_os.shared.db import get_pool
from gyros_os.shared.org import get_default_org_id

logger = structlog.get_logger()


def _extract_configurable(runtime: Any) -> dict:
    """Mesma estratégia usada em tools/memory.py para pegar `configurable`.

    Tenta primeiro o `runtime` injetado, depois cai no contextvar global
    do LangChain. Mantido inline porque é o 2º uso e a abstração ainda
    é prematura.
    """
    if runtime is not None:
        config = getattr(runtime, "config", None)
        if isinstance(config, dict):
            configurable = config.get("configurable", {})
            if isinstance(configurable, dict):
                return configurable

    cfg = var_child_runnable_config.get(None)
    if isinstance(cfg, dict):
        configurable = cfg.get("configurable", {})
        if isinstance(configurable, dict):
            return configurable

    return {}


class ProposeActionInput(BaseModel):
    action_type: str = Field(
        description=(
            "Identificador técnico do tipo de ação a ser executada após "
            "aprovação. Deve bater com um executor registrado via "
            "@register_executor. Exemplo válido no projeto: "
            "'gcal_create_event' (criar evento no Google Calendar). "
            "NÃO invente action_types novos — use apenas os documentados "
            "no system prompt da Lyra."
        )
    )
    payload: dict[str, Any] = Field(
        description=(
            "Parâmetros da ação. Será passado ao executor depois da aprovação. "
            "Estrutura livre — depende do action_type."
        )
    )
    preview_text: str = Field(
        description=(
            "Texto curto e claro mostrando à Camila o que será feito se ela "
            "aprovar. Cabe em 3-5 linhas de WhatsApp. Sem placeholders — se "
            "faltar informação, pergunte antes de propor."
        )
    )


@tool("propose_action", args_schema=ProposeActionInput)
async def propose_action(
    action_type: str,
    payload: dict[str, Any],
    preview_text: str,
    *,
    runtime: Annotated[Any, InjectedToolArg()] = None,
) -> dict[str, Any]:
    """Propõe uma ação que escreve no mundo externo.

    A ação NÃO é executada imediatamente. É registrada como pending de
    aprovação humana e a Camila precisa responder ✅ no WhatsApp para
    confirmar (ou ❌ para cancelar).

    Use sempre que ela pedir para criar, modificar, enviar ou agendar
    qualquer coisa real — evento de calendário, email, etc. Nunca diga
    que "fez" algo antes da aprovação acontecer.

    Retorna um dict estruturado. Quando essa tool retorna, a ação JÁ
    ESTÁ REGISTRADA — NÃO chame `propose_action` de novo no mesmo turno.
    Copie `user_facing_message` como sua resposta final, sem modificar
    nem adicionar preâmbulo.
    """
    configurable = _extract_configurable(runtime)
    user_id = configurable.get("user_id", "unknown")
    thread_id = configurable.get("thread_id")

    pool = await get_pool()
    org_id = await get_default_org_id(pool)

    approval_id = await create_approval(
        organization_id=org_id,
        action_type=action_type,
        payload=payload,
        preview_text=preview_text,
        requested_by=str(user_id),
        thread_id=thread_id,
    )

    logger.info(
        "propose_action_registered",
        approval_id=approval_id,
        action_type=action_type,
        requested_by=user_id,
    )

    return {
        "status": "approval_proposed",
        "approval_id": approval_id,
        "user_facing_message": (
            f"📋 *Aprovação pendente #{approval_id}*\n\n"
            f"{preview_text}\n\n"
            f"Responda ✅ pra aprovar ou ❌ pra cancelar."
        ),
    }
