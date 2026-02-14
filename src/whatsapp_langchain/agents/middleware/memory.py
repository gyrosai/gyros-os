"""Middleware de Recall — busca memórias relevantes antes do modelo.

Parte da estratégia de memória semântica: antes de cada chamada ao LLM,
busca memórias salvas sobre o usuário e as injeta como SystemMessage.

Fluxo:
    1. Middleware roda @before_model
    2. Extrai user_id do config (passado pelo processor/webhook)
    3. Busca memórias por similaridade semântica no Store
    4. Injeta SystemMessage com as memórias encontradas

Requer:
    - Store configurado com embeddings (AsyncPostgresStore com index)
    - user_id passado no config["configurable"]["user_id"]

Exemplo:
    from whatsapp_langchain.agents.middleware import create_memory_middleware

    recall = create_memory_middleware(search_limit=5)
    agent = create_agent(model=model, middleware=[recall], store=store)
"""

from typing import Any

import structlog
from langchain.agents import AgentState
from langchain.agents.middleware import before_model
from langchain_core.messages import SystemMessage
from langgraph.config import get_config
from langgraph.runtime import Runtime

logger = structlog.get_logger()


def create_memory_middleware(search_limit: int = 5):
    """Cria middleware que busca memórias relevantes antes de chamar o modelo.

    Usa busca por similaridade semântica no LangGraph Store para encontrar
    memórias salvas sobre o usuário. As memórias são injetadas como
    SystemMessage adicional no contexto do agente.

    Args:
        search_limit: Número máximo de memórias a buscar. Default: 5.

    Returns:
        Função middleware decorada com @before_model.

    Exemplo:
        Usuário salvou: "Meu nome é João", "Gosto de Python"

        Antes do modelo ver:
            [system_prompt] [user: "O que eu gosto?"]

        Depois do recall:
            [system_prompt] [memories: "- Meu nome é João\\n- Gosto de Python"]
            [user: "O que eu gosto?"]
    """

    @before_model
    async def recall_memories(
        state: AgentState, runtime: Runtime
    ) -> dict[str, Any] | None:
        # Sem store, não há memórias para buscar
        if not runtime.store:
            return None

        # Extrai user_id do config (passado pelo processor/webhook)
        # Runtime não tem config — usamos get_config() do LangGraph
        config = get_config()
        user_id = config.get("configurable", {}).get("user_id", "")
        if not user_id:
            return None

        # Usa a última mensagem do usuário como query de busca
        last_message = state["messages"][-1]
        query = str(last_message.content)

        # Busca memórias relevantes por similaridade semântica
        namespace = (user_id, "memories")
        memories = await runtime.store.asearch(
            namespace,
            query=query,
            limit=search_limit,
        )

        if not memories:
            return None

        # Formata memórias e injeta como SystemMessage
        memory_text = "\n".join(f"- {m.value['memory']}" for m in memories)
        memory_msg = SystemMessage(
            content=f"## Memórias sobre este usuário\n{memory_text}"
        )

        logger.info(
            "memories_recalled",
            user_id=user_id,
            count=len(memories),
        )

        return {"messages": [memory_msg]}

    return recall_memories
