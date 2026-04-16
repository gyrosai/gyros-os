"""Agente studio_assistant — assistente da plataforma Studio.

Agente conversacional read-only (v0.1) com busca na base de conhecimento.
Usa create_agent do LangChain 1.0 seguindo o mesmo padrão do gyros_assistant.

Configuração via .env:
    MEMORY_ENABLED=true                # Habilita memória semântica
"""

from langchain.agents import create_agent
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.store.base import BaseStore

from gyros_os.agents.middleware import get_context_middleware
from gyros_os.shared.llm import create_chat_model

from .prompts import STUDIO_SYSTEM_PROMPT
from .tools import search_kb


def build_graph(
    checkpointer: BaseCheckpointSaver | None = None,
    store: BaseStore | None = None,
):
    """Constrói o agente studio_assistant.

    Args:
        checkpointer: Checkpointer para persistência de estado.
        store: Store para memória semântica cross-thread.

    Returns:
        CompiledStateGraph: Agente compilado pronto para uso.
    """
    model = create_chat_model()
    middleware = get_context_middleware()

    tools = [search_kb]

    return create_agent(
        model=model,
        tools=tools,
        system_prompt=STUDIO_SYSTEM_PROMPT,
        middleware=middleware,
        checkpointer=checkpointer,
        store=store,
    )
