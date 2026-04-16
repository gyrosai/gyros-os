"""Ferramentas do agente studio_assistant.

v0.1 — read-only: apenas busca semântica na base de conhecimento.
"""

from typing import Annotated, Any

import structlog
from langchain_core.tools import InjectedToolArg, tool

from gyros_os.rag.retrieve import retrieve
from gyros_os.shared.db import get_pool
from gyros_os.shared.org import get_default_org_id

logger = structlog.get_logger()


@tool
async def search_kb(
    query: str,
    *,
    runtime: Annotated[Any, InjectedToolArg()] = None,
) -> str:
    """Busca informações na base de conhecimento da organização.

    Use para responder perguntas com base nos documentos indexados.
    A query pode ser uma pergunta natural ou termos-chave.

    Args:
        query: Texto da consulta semântica.

    Returns:
        String formatada com trechos relevantes e suas fontes.
    """
    query = (query or "").strip()
    if not query:
        return "Forneça uma consulta de busca não vazia."

    try:
        pool = await get_pool()
        org_id = await get_default_org_id(pool)

        results = await retrieve(org_id=org_id, query=query, top_k=5)
    except Exception as e:
        logger.error("search_kb_failed", query=query, error=str(e))
        return f"Erro ao buscar na base de conhecimento: {e}"

    if not results:
        return "Nenhum resultado encontrado na base de conhecimento."

    lines = [f"Encontrei {len(results)} trechos relevantes:\n"]
    for i, r in enumerate(results, start=1):
        content = r.content[:400]
        if len(r.content) > 400:
            content += "..."

        lines.append(f"[{i}] [Fonte: {r.doc_title}]")
        lines.append(f"Trecho: {content}\n")

    logger.info(
        "search_kb_complete",
        query=query,
        num_results=len(results),
        top_score=results[0].score if results else None,
    )

    return "\n".join(lines)
