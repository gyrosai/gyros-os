"""Agente rhawk_assistant - assistente da comunidade Top Hawks.

Agente simples usando create_agent do LangChain 1.0.
Usa middleware de contexto configurável (trim ou summarize).

Este arquivo contém a factory `build_graph()`. Para langgraph dev,
veja graph.py que exporta a variável `graph`.

Configuração via .env:
    OPENROUTER_API_KEY=sk-or-...       # API key do OpenRouter
    OPENROUTER_MODEL=anthropic/...     # Modelo principal
    CONTEXT_STRATEGY=trim              # trim | summarize | none
    TRIM_KEEP_TURNS=5                  # Turnos a manter (trim)
    SUMMARIZE_TRIGGER_TOKENS=4000      # Tokens antes de sumarizar
    SUMMARIZE_KEEP_MESSAGES=10         # Mensagens após sumarização
    SUMMARIZE_MODEL=anthropic/...      # Modelo para sumarização
"""

import os

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.base import BaseCheckpointSaver
from pydantic import SecretStr

from whatsapp_langchain.agents.middleware import get_context_middleware

from .prompts import SYSTEM_PROMPT

load_dotenv()

# Configurações via env vars
DEFAULT_MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-oss-120b")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")


def build_graph(checkpointer: BaseCheckpointSaver | None = None):
    """Constrói o agente rhawk_assistant.

    O agente usa middleware de contexto configurável via CONTEXT_STRATEGY:
    - trim: Remove mensagens antigas (custo zero, perde contexto)
    - summarize: Sumariza mensagens antigas (custo extra, preserva contexto)
    - none: Sem gerenciamento de contexto

    Args:
        checkpointer: Checkpointer para persistência de estado.
                      None em dev (in-memory), PostgresSaver em prod.

    Returns:
        CompiledStateGraph: Agente compilado pronto para uso.
    """
    # SecretStr evita que a API key apareça em logs ou stack traces
    api_key = os.getenv("OPENROUTER_API_KEY")
    secret_key = SecretStr(api_key) if api_key else None

    # Modelo principal para o agente
    model = ChatOpenAI(
        model=DEFAULT_MODEL,
        api_key=secret_key,
        base_url=OPENROUTER_BASE_URL,
    )

    # Middleware de contexto baseado em CONTEXT_STRATEGY
    # Lê configuração automaticamente do .env
    middleware = get_context_middleware()

    return create_agent(
        model=model,
        tools=[],
        system_prompt=SYSTEM_PROMPT,
        middleware=middleware,
        checkpointer=checkpointer,
    )
