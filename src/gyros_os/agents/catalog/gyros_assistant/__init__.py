"""Agente gyros_assistant - assistente pessoal da Camila Martins (Gyros AI).

Agente conversacional com tom sóbrio e direto, sem tools nesta versão.

Uso:
    from gyros_os.agents.catalog.gyros_assistant import build_graph

    agent = build_graph()
    result = agent.invoke({"messages": [{"role": "user", "content": "oi"}]})
"""

from .agent import build_graph
from .prompts import SYSTEM_PROMPT

__all__ = ["build_graph", "SYSTEM_PROMPT"]
