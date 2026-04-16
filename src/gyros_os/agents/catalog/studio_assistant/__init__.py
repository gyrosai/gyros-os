"""Agente studio_assistant - assistente da plataforma Studio.

Agente read-only (v0.1) com busca semântica na base de conhecimento.

Uso:
    from gyros_os.agents.catalog.studio_assistant import build_graph

    agent = build_graph()
    result = agent.invoke({"messages": [{"role": "user", "content": "oi"}]})
"""

from .agent import build_graph
from .prompts import STUDIO_SYSTEM_PROMPT

__all__ = ["build_graph", "STUDIO_SYSTEM_PROMPT"]
