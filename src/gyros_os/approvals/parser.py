"""Parser de mensagens de decisão de aprovação.

Função pura, sem I/O. Reconhece se uma mensagem do usuário é uma decisão
sobre uma approval pendente (aprovar / rejeitar, com ou sem ID explícito).

Regra principal: a mensagem inteira (após strip) precisa bater EXATAMENTE
um dos padrões. Se sobrar texto além do padrão, NÃO é decisão de aprovação
— é conversa normal e deve seguir para o graph.

Exemplos:
    "✅"           -> approve, id=None
    "❌"           -> reject,  id=None
    "✅ 42"        -> approve, id=42
    "✅42"         -> approve, id=42
    "aprova 42"    -> approve, id=42
    "Aprova"       -> approve, id=None
    "rejeita 7"    -> reject,  id=7
    "✅ acho que" -> None (parser NÃO é ganancioso)
    "tudo bem ✅" -> None
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class ApprovalDecision:
    """Decisão de aprovação reconhecida em uma mensagem do usuário."""

    action: Literal["approve", "reject"]
    approval_id: int | None  # None significa "última pending do usuário"


# Aliases textuais aceitos (case-insensitive). Cada um deve ser a mensagem
# inteira, opcionalmente seguida de um número (com ou sem espaço).
_APPROVE_WORDS = ("✅", "aprova", "aprovar", "aprovado")
_REJECT_WORDS = ("❌", "rejeita", "rejeitar", "rejeitado", "cancela", "cancelar")

# Regex: ^(palavra)\s*(\d+)?$ — palavra obrigatória, id opcional, nada a mais.
_APPROVE_RE = re.compile(
    r"^(?:" + "|".join(re.escape(w) for w in _APPROVE_WORDS) + r")\s*(\d+)?$",
    re.IGNORECASE,
)
_REJECT_RE = re.compile(
    r"^(?:" + "|".join(re.escape(w) for w in _REJECT_WORDS) + r")\s*(\d+)?$",
    re.IGNORECASE,
)


def parse_approval_decision(text: str) -> ApprovalDecision | None:
    """Tenta interpretar `text` como uma decisão de aprovação.

    Retorna None se a mensagem não bate nenhum padrão de decisão. Isso
    sinaliza ao chamador que a mensagem deve seguir o fluxo normal (graph).

    O parser é estrito de propósito: se sobrar qualquer texto além do
    padrão (ex: "✅ acho que sim"), retorna None. Falso-positivo aqui é
    pior que falso-negativo — o usuário pode sempre repetir com "✅" sozinho.
    """
    if not text:
        return None

    stripped = text.strip()
    if not stripped:
        return None

    match = _APPROVE_RE.match(stripped)
    if match:
        approval_id = int(match.group(1)) if match.group(1) else None
        return ApprovalDecision(action="approve", approval_id=approval_id)

    match = _REJECT_RE.match(stripped)
    if match:
        approval_id = int(match.group(1)) if match.group(1) else None
        return ApprovalDecision(action="reject", approval_id=approval_id)

    return None
