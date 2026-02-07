"""Factory para middlewares de gerenciamento de contexto.

Este módulo fornece uma interface unificada para escolher entre diferentes
estratégias de gerenciamento de contexto via variável de ambiente.

Estratégias disponíveis:
    - trim: Remove turnos antigos (custo zero, perde contexto)
    - summarize: Sumariza mensagens antigas (custo extra, preserva contexto)
    - none: Sem gerenciamento (para testes ou conversas curtas)

Configuração via .env:
    CONTEXT_STRATEGY=trim              # trim | summarize | none

    # Para TRIM:
    TRIM_KEEP_TURNS=5                  # Turnos recentes a manter

    # Para SUMMARIZE:
    SUMMARIZE_TRIGGER_TOKENS=4000      # Tokens antes de sumarizar
    SUMMARIZE_KEEP_MESSAGES=10         # Mensagens a manter após sumarização
    SUMMARIZE_MODEL=anthropic/claude-3-haiku  # Modelo para sumarização

Exemplo:
    from whatsapp_langchain.agents.middleware import get_context_middleware

    # Lê configuração do .env automaticamente
    middlewares = get_context_middleware()

    agent = create_agent(
        model=model,
        middleware=middlewares,
        ...
    )
"""

import os
from typing import Any

from whatsapp_langchain.agents.middleware.summarize import create_summarize_middleware
from whatsapp_langchain.agents.middleware.trim import create_trim_middleware


def get_context_middleware(
    strategy: str | None = None,
    trim_keep_turns: int | None = None,
    summarize_trigger_tokens: int | None = None,
    summarize_keep_messages: int | None = None,
    summarize_model: str | None = None,
    summarize_prompt: str | None = None,
) -> list[Any]:
    """Retorna lista de middlewares baseado na estratégia configurada.

    Lê configuração de variáveis de ambiente, mas permite override via parâmetros.

    Args:
        strategy: Estratégia de contexto (trim/summarize/none).
                  Default: env CONTEXT_STRATEGY ou "summarize".
        trim_keep_turns: Turnos recentes a manter no trim.
                         Default: env TRIM_KEEP_TURNS ou 5.
        summarize_trigger_tokens: Tokens antes de acionar sumarização.
                                  Default: env SUMMARIZE_TRIGGER_TOKENS ou 4000.
        summarize_keep_messages: Mensagens a manter após sumarização.
                                 Default: env SUMMARIZE_KEEP_MESSAGES ou 10.
        summarize_model: Modelo para sumarização.
                         Default: env SUMMARIZE_MODEL ou "anthropic/claude-3-haiku".
        summarize_prompt: Prompt customizado para sumarização.
                          Default: prompt padrão em português (ver summarize.py).

    Returns:
        Lista de middlewares para passar ao create_agent().
        Lista vazia se strategy="none".

    Exemplo:
        # Usando configuração do .env
        middlewares = get_context_middleware()

        # Override para testes
        middlewares = get_context_middleware(strategy="trim", trim_keep_turns=3)
    """
    # Lê configuração com fallback para env vars
    resolved_strategy = strategy or os.getenv("CONTEXT_STRATEGY", "summarize")

    if resolved_strategy == "trim":
        resolved_keep = trim_keep_turns or int(os.getenv("TRIM_KEEP_TURNS", "5"))
        return [create_trim_middleware(keep_turns=resolved_keep)]

    elif resolved_strategy == "summarize":
        resolved_tokens = summarize_trigger_tokens or int(
            os.getenv("SUMMARIZE_TRIGGER_TOKENS", "4000")
        )
        resolved_keep = summarize_keep_messages or int(
            os.getenv("SUMMARIZE_KEEP_MESSAGES", "10")
        )
        # prompt é passado para create_summarize_middleware
        # model é criado internamente usando env vars
        return [
            create_summarize_middleware(
                trigger_tokens=resolved_tokens,
                keep_messages=resolved_keep,
                prompt=summarize_prompt,
            )
        ]

    # strategy == "none" ou qualquer outro valor
    return []
