"""Ferramenta de memória semântica para agentes.

Permite ao agente salvar informações importantes sobre o usuário
para lembrar em conversas futuras. Usa o LangGraph Store para
persistência cross-thread.

Fluxo:
    1. Usuário menciona algo importante (nome, preferência, etc.)
    2. Agente decide chamar save_memory com a informação
    3. Informação é salva no Store com namespace (user_id, "memories")
    4. Em conversas futuras, o middleware de recall busca essas memórias

Exemplo:
    from whatsapp_langchain.agents.tools import save_memory

    agent = create_agent(model=model, tools=[save_memory], store=store)
"""

import uuid

import structlog
from langchain_core.tools import tool
from langgraph.prebuilt import ToolRuntime

logger = structlog.get_logger()


@tool
async def save_memory(memory: str, runtime: ToolRuntime) -> str:
    """Salva informação importante sobre o usuário para lembrar depois.

    Use quando o usuário mencionar nome, preferências, interesses,
    decisões ou qualquer informação que valha lembrar depois.

    Args:
        memory: A informação a ser lembrada, em texto livre.
    """
    configurable = runtime.config.get("configurable") or {}
    user_id = configurable.get("user_id", "")

    if not user_id or not runtime.store:
        return "Não foi possível salvar a memória."

    namespace = (user_id, "memories")
    key = str(uuid.uuid4())
    await runtime.store.aput(namespace, key, {"memory": memory})

    logger.info("memory_saved", user_id=user_id, key=key, memory=memory)
    return f"Memória salva: {memory}"
