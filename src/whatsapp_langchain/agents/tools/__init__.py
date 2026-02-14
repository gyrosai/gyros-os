"""Ferramentas reutilizáveis para agentes LangGraph.

Ferramentas são funções que o agente pode chamar durante a conversa.
Cada ferramenta é decorada com @tool e recebe acesso ao runtime
para interagir com store, config, etc.

Exemplo:
    from whatsapp_langchain.agents.tools import save_memory

    agent = create_agent(model=model, tools=[save_memory], ...)
"""

from whatsapp_langchain.agents.tools.memory import save_memory

__all__ = [
    "save_memory",
]
