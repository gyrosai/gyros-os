"""Ingest text into the knowledge base.

Main entry point: ingest_text() — idempotent ingestion of a document
into kb_docs + kb_chunks with embeddings.
"""

import time
from uuid import UUID

import structlog

from gyros_os.rag.chunking import chunk_text
from gyros_os.rag.embeddings import embed_texts
from gyros_os.shared.db import get_pool

logger = structlog.get_logger()


async def ingest_text(
    org_id: UUID,
    source_type: str,
    source_ref: str | None,
    title: str,
    content: str,
    project_tag: str | None = None,
    metadata: dict | None = None,
) -> dict:
    """Ingest a text document: chunk, embed, and store in the KB.

    Idempotent: if (org_id, source_type, source_ref) already exists,
    updates the doc and regenerates all chunks.

    Args:
        org_id: Organization UUID.
        source_type: Source identifier (e.g. 'fireflies', 'manual').
        source_ref: External reference ID (e.g. Fireflies meeting_id).
        title: Document title.
        content: Full raw text content.
        project_tag: Optional project classification tag.
        metadata: Optional metadata dict.

    Returns:
        Dict with doc_id, num_chunks, total_tokens, latency_ms.
    """
    start = time.monotonic()
    meta = metadata or {}
    pool = await get_pool()

    async with pool.connection() as conn:
        # Upsert the document
        cursor = await conn.execute(
            """
            INSERT INTO kb_docs (organization_id, source_type, source_ref,
                                 title, content, project_tag, metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
            ON CONFLICT (organization_id, source_type, source_ref)
            DO UPDATE SET
                title = EXCLUDED.title,
                content = EXCLUDED.content,
                project_tag = EXCLUDED.project_tag,
                metadata = EXCLUDED.metadata,
                updated_at = NOW()
            RETURNING id
            """,
            (
                str(org_id),
                source_type,
                source_ref,
                title,
                content,
                project_tag,
                _json_dumps(meta),
            ),
        )
        row = await cursor.fetchone()
        assert row is not None
        doc_id: UUID = row[0]

        # Delete existing chunks (idempotent re-ingestion)
        await conn.execute(
            "DELETE FROM kb_chunks WHERE doc_id = %s",
            (str(doc_id),),
        )
        await conn.commit()

    # Chunk the text
    chunks = chunk_text(content)
    total_tokens = sum(tok for _, tok in chunks)

    # Generate embeddings in batch
    chunk_texts = [c for c, _ in chunks]
    embeddings = await embed_texts(chunk_texts)

    # Insert chunks with embeddings
    async with pool.connection() as conn:
        for i, ((chunk_content, token_count), embedding) in enumerate(
            zip(chunks, embeddings)
        ):
            await conn.execute(
                """
                INSERT INTO kb_chunks
                    (organization_id, doc_id, chunk_index, content,
                     token_count, embedding, metadata)
                VALUES (%s, %s, %s, %s, %s, %s::vector, %s::jsonb)
                """,
                (
                    str(org_id),
                    str(doc_id),
                    i,
                    chunk_content,
                    token_count,
                    _vector_literal(embedding),
                    _json_dumps({}),
                ),
            )
        await conn.commit()

    latency_ms = round((time.monotonic() - start) * 1000)

    logger.info(
        "rag_ingest_complete",
        doc_id=str(doc_id),
        num_chunks=len(chunks),
        total_tokens=total_tokens,
        latency_ms=latency_ms,
    )

    return {
        "doc_id": str(doc_id),
        "num_chunks": len(chunks),
        "total_tokens": total_tokens,
        "latency_ms": latency_ms,
    }


def _vector_literal(vec: list[float]) -> str:
    """Convert a float list to pgvector literal format: '[0.1,0.2,...]'."""
    return "[" + ",".join(str(v) for v in vec) + "]"


def _json_dumps(obj: dict) -> str:
    """Serialize dict to JSON string for Postgres."""
    import json

    return json.dumps(obj)
