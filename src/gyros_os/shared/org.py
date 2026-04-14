"""Helper de resolução do organization_id default (single-tenant v0.1).

Centraliza a query SELECT id FROM organizations WHERE slug='gyros' com cache
em memória. Quando multi-tenant chegar, vira "given contexto, retorne org_id".

Nota: `scripts/backfill_meetings.py` tem a mesma query inline e NÃO foi
migrado conscientemente — é script one-shot operacional, sem benefício
de cache. Ver item no 99-tech-debt.md.
"""

from __future__ import annotations

import asyncio
from uuid import UUID

from psycopg_pool import AsyncConnectionPool

_cached: UUID | None = None
_lock = asyncio.Lock()


async def get_default_org_id(pool: AsyncConnectionPool) -> UUID:
    """Retorna UUID da organization default (slug='gyros').

    Cacheado em memória (single-tenant v0.1). Thread-safe via asyncio.Lock
    pra evitar dogpile na primeira chamada. Quando multi-tenant chegar,
    esta função provavelmente será substituída por um resolver por fonte.

    Raises:
        RuntimeError: se organization 'gyros' não existe (migrations não rodaram?)
    """
    global _cached
    if _cached is not None:
        return _cached
    async with _lock:
        if _cached is not None:
            return _cached
        async with pool.connection() as conn:
            cursor = await conn.execute(
                "SELECT id FROM organizations WHERE slug = 'gyros'"
            )
            row = await cursor.fetchone()
        if not row:
            raise RuntimeError(
                "Organization 'gyros' não existe. Rodou as migrations?"
            )
        _cached = row[0]
        return _cached
