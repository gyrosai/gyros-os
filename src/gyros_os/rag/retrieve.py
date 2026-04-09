"""Semantic retrieval from the knowledge base.

Pure cosine similarity search via pgvector. No HyDE, hybrid search,
or reranking — those are for a future iteration.
"""

import time
from uuid import UUID

import structlog

from gyros_os.rag.embeddings import embed_query
from gyros_os.rag.models import RetrievalResult
from gyros_os.shared.db import get_pool

logger = structlog.get_logger()


async def retrieve(
    org_id: UUID,
    query: str,
    top_k: int = 5,
    project_tag: str | None = None,
) -> list[RetrievalResult]:
    """Retrieve the most relevant chunks for a query.

    Always filters by organization_id. Optionally filters by project_tag.

    Args:
        org_id: Organization UUID (mandatory filter).
        query: Search query text.
        top_k: Number of results to return.
        project_tag: Optional project tag filter.

    Returns:
        List of RetrievalResult sorted by relevance (highest score first).
    """
    start = time.monotonic()

    query_embedding = await embed_query(query)
    vec_literal = "[" + ",".join(str(v) for v in query_embedding) + "]"

    pool = await get_pool()

    if project_tag is not None:
        sql = """
            SELECT
                c.id, c.doc_id, c.content, c.token_count,
                1 - (c.embedding <=> %s::vector) AS score,
                d.title, d.source_type, d.metadata
            FROM kb_chunks c
            JOIN kb_docs d ON d.id = c.doc_id
            WHERE c.organization_id = %s
              AND c.embedding IS NOT NULL
              AND d.project_tag = %s
            ORDER BY c.embedding <=> %s::vector
            LIMIT %s
        """
        params = (vec_literal, str(org_id), project_tag, vec_literal, top_k)
    else:
        sql = """
            SELECT
                c.id, c.doc_id, c.content, c.token_count,
                1 - (c.embedding <=> %s::vector) AS score,
                d.title, d.source_type, d.metadata
            FROM kb_chunks c
            JOIN kb_docs d ON d.id = c.doc_id
            WHERE c.organization_id = %s
              AND c.embedding IS NOT NULL
            ORDER BY c.embedding <=> %s::vector
            LIMIT %s
        """
        params = (vec_literal, str(org_id), vec_literal, top_k)

    async with pool.connection() as conn:
        cursor = await conn.execute(sql, params)
        rows = await cursor.fetchall()

    results = [
        RetrievalResult(
            chunk_id=row[0],
            doc_id=row[1],
            content=row[2],
            token_count=row[3],
            score=float(row[4]),
            doc_title=row[5],
            doc_source_type=row[6],
            doc_metadata=row[7] if row[7] else {},
        )
        for row in rows
    ]

    latency_ms = round((time.monotonic() - start) * 1000)
    logger.info(
        "rag_retrieve_complete",
        org_id=str(org_id),
        query_len=len(query),
        num_results=len(results),
        top_score=results[0].score if results else None,
        latency_ms=latency_ms,
    )

    return results
