"""Agente gyros_assistant - assistente pessoal da Camila Martins.

Agente conversacional sem tools, usando create_agent do LangChain 1.0.
Usa middleware de contexto configurável (trim ou summarize).

Nesta versão (Fatia 2.1) o agente é puramente conversacional — sem
tools, sem memória semântica, sem RAG. As capacidades serão adicionadas
nas fatias seguintes.

Este arquivo contém a factory `build_graph()`. Para langgraph dev,
veja graph.py que exporta a variável `graph`.
"""

from langchain.agents import create_agent
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.store.base import BaseStore

from gyros_os.agents.middleware import get_context_middleware
from gyros_os.shared.llm import create_chat_model

from .prompts import SYSTEM_PROMPT


def build_graph(
    checkpointer: BaseCheckpointSaver | None = None,
    store: BaseStore | None = None,
):
    """Constrói o agente gyros_assistant.

    Args:
        checkpointer: Checkpointer para persistência de estado.
        store: Store para memória semântica (não usado nesta versão).

    Returns:
        CompiledStateGraph: Agente compilado pronto para uso.
    """
    model = create_chat_model()
    middleware = get_context_middleware()

    # Sem tools nesta versão — agente puramente conversacional
    tools = []

    return create_agent(
        model=model,
        tools=tools,
        system_prompt=SYSTEM_PROMPT,
        middleware=middleware,
        checkpointer=checkpointer,
        store=store,
    )
