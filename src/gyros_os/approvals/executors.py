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

from typing import Any, Awaitable, Callable

import structlog

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
