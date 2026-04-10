"""Agente gyros_assistant - assistente pessoal da Camila Martins.

Agente conversacional usando create_agent do LangChain 1.0.
Usa middleware de contexto configurável (trim ou summarize)
e memória semântica cross-thread via LangGraph Store.

Este arquivo contém a factory `build_graph()`. Para langgraph dev,
veja graph.py que exporta a variável `graph`.

Configuração via .env:
    MEMORY_ENABLED=true                # Habilita memória semântica
"""

from langchain.agents import create_agent
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.store.base import BaseStore

from gyros_os.agents.middleware import get_context_middleware
from gyros_os.agents.tools import (
    propose_action,
    read_memory,
    save_memory,
    search_meetings,
)
from gyros_os.shared.llm import create_chat_model

from .prompts import SYSTEM_PROMPT


def build_graph(
    checkpointer: BaseCheckpointSaver | None = None,
    store: BaseStore | None = None,
):
    """Constrói o agente gyros_assistant.

    Se store for fornecido, habilita memória semântica:
    - Recall automático via middleware (busca memórias antes de cada chamada)
    - Save explícito via tool save_memory (agente decide quando salvar)

    Args:
        checkpointer: Checkpointer para persistência de estado.
        store: Store para memória semântica cross-thread.

    Returns:
        CompiledStateGraph: Agente compilado pronto para uso.
    """
    model = create_chat_model()
    middleware = get_context_middleware()

    # Tools — propose_action (HITL) sempre disponível; memória/RAG só quando store existe.
    tools: list = [propose_action]
    if store:
        tools.extend([save_memory, read_memory, search_meetings])

    return create_agent(
        model=model,
        tools=tools,
        system_prompt=SYSTEM_PROMPT,
        middleware=middleware,
        checkpointer=checkpointer,
        store=store,
    )
