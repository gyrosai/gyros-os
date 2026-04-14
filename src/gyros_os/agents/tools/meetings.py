"""Ferramenta de busca em transcrições de reuniões indexadas (RAG).

Disponibiliza:
- search_meetings: busca semântica em kb_chunks (Fireflies + futuros).
"""

from typing import Annotated, Any

import structlog
from langchain_core.tools import InjectedToolArg, tool

from gyros_os.rag.retrieve import retrieve
from gyros_os.shared.db import get_pool
from gyros_os.shared.org import get_default_org_id

logger = structlog.get_logger()


@tool
async def search_meetings(
    query: str,
    *,
    runtime: Annotated[Any, InjectedToolArg()] = None,
) -> str:
    """Busca trechos relevantes em reuniões transcritas e indexadas.

    Use quando a Camila perguntar sobre conteúdo de reuniões, pessoas
    mencionadas em calls, decisões tomadas em reuniões, ou qualquer
    coisa que pareça vir de uma conversa transcrita pelo Fireflies.

    Args:
        query: Texto da consulta semântica. Pode ser uma pergunta natural
               ('o que falaram sobre Pedro') ou termos-chave ('Pedro Vector
               qualificação').

    Returns:
        String formatada com até 5 trechos relevantes, citando a reunião
        de origem. Retorna mensagem de "nenhum resultado" se não achar nada.
    """
    query = (query or "").strip()
    if not query:
        return "Forneça uma consulta de busca não vazia."

    try:
        pool = await get_pool()
        org_id = await get_default_org_id(pool)

        results = await retrieve(org_id=org_id, query=query, top_k=5)
    except Exception as e:
        logger.error("search_meetings_failed", query=query, error=str(e))
        return f"Erro ao buscar reuniões: {e}"

    if not results:
        return "Nenhum trecho relevante encontrado nas reuniões indexadas."

    # Formata os resultados como texto natural pro LLM
    lines = [f"Encontrei {len(results)} trechos relevantes em reuniões:\n"]
    for i, r in enumerate(results, start=1):
        # Extrai metadados úteis se existirem
        participants = r.doc_metadata.get("participants", [])
        date = r.doc_metadata.get("date", "")
        duration = r.doc_metadata.get("duration_minutes", "")

        header_parts = [f'Reunião: "{r.doc_title}"']
        if date:
            header_parts.append(str(date))
        if duration:
            header_parts.append(f"{duration}min")
        if participants:
            # Limita a 3 participantes pra não inflar a string
            participants_str = ", ".join(str(p) for p in participants[:3])
            header_parts.append(f"com {participants_str}")
        header = " — ".join(header_parts)

        # Trunca o conteúdo em ~400 chars pra não estourar o contexto do LLM
        content = r.content[:400]
        if len(r.content) > 400:
            content += "..."

        lines.append(f"[{i}] {header}")
        lines.append(f"Trecho: {content}\n")

    logger.info(
        "search_meetings_complete",
        query=query,
        num_results=len(results),
        top_score=results[0].score if results else None,
    )

    return "\n".join(lines)
