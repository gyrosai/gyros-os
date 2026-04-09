"""Backfill manual de reunioes do Fireflies que perderam o webhook.

Quando o cloudflared tunnel esta fora (laptop fechado, por exemplo),
webhooks de transcricao completada nao chegam. Este script permite
reindexar reunioes manualmente, reusando o handler existente.

Uso:
  # Indexar uma reuniao especifica
  python -m gyros_os.scripts.backfill_meetings one MEETING_ID

  # Listar reunioes dos ultimos N dias que NAO estao indexadas
  python -m gyros_os.scripts.backfill_meetings list --days 7

  # Indexar todas as pendentes dos ultimos N dias
  python -m gyros_os.scripts.backfill_meetings sync --days 7
"""

import argparse
import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID

import httpx
import structlog

from gyros_os.integrations.fireflies.client import GRAPHQL_URL
from gyros_os.shared.config import settings
from gyros_os.shared.db import close_pool, get_pool
from gyros_os.shared.event_queue import Event
from gyros_os.worker.event_handlers.fireflies import (
    handle_fireflies_transcription_completed,
)

log = structlog.get_logger("backfill")

# Query leve — so campos necessarios para listar e comparar.
# Ref: https://docs.fireflies.ai/graphql-api/query/transcripts
TRANSCRIPTS_LIST_QUERY = """
query RecentTranscripts($fromDate: DateTime) {
  transcripts(fromDate: $fromDate) {
    id
    title
    date
    duration
  }
}
"""


async def _list_fireflies_transcripts(days: int) -> list[dict]:
    """Lista reunioes dos ultimos N dias via GraphQL do Fireflies."""
    from_date = datetime.now(UTC) - timedelta(days=days)

    async with httpx.AsyncClient() as http:
        resp = await http.post(
            GRAPHQL_URL,
            json={
                "query": TRANSCRIPTS_LIST_QUERY,
                "variables": {"fromDate": from_date.isoformat()},
            },
            headers={
                "Authorization": f"Bearer {settings.fireflies_api_key}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )
    resp.raise_for_status()
    data = resp.json()

    if "errors" in data:
        raise RuntimeError(f"Fireflies GraphQL error: {data['errors']}")

    return data.get("data", {}).get("transcripts", [])


async def _get_gyros_org_id() -> UUID:
    pool = await get_pool()
    async with pool.connection() as conn:
        cur = await conn.execute("SELECT id FROM organizations WHERE slug = 'gyros'")
        row = await cur.fetchone()
    if row is None:
        raise RuntimeError("Org 'gyros' nao encontrada no banco")
    return row[0]


async def _get_indexed_meeting_ids(org_id: UUID) -> set[str]:
    """Retorna meeting_ids ja indexados em kb_docs."""
    pool = await get_pool()
    async with pool.connection() as conn:
        cur = await conn.execute(
            "SELECT source_ref FROM kb_docs WHERE organization_id = %s AND source_type = 'fireflies'",
            (org_id,),
        )
        rows = await cur.fetchall()
    return {row[0] for row in rows}


def _make_backfill_event(meeting_id: str, org_id: UUID) -> Event:
    """Cria um Event sintetico para reusar o handler em contexto CLI.

    O handler handle_fireflies_transcription_completed espera um Event
    com payload.meeting_id e organization_id. Construimos um Event
    valido com campos dummy (id=0) para satisfazer o modelo Pydantic
    sem precisar inserir nada no banco.
    """
    return Event(
        id=0,
        organization_id=org_id,
        event_type="fireflies.transcription_completed",
        payload={"meeting_id": meeting_id},
        created_at=datetime.now(UTC),
    )


async def backfill_one(meeting_id: str) -> bool:
    """Indexa uma reuniao especifica."""
    org_id = await _get_gyros_org_id()
    log.info("backfill_one_start", meeting_id=meeting_id)

    event = _make_backfill_event(meeting_id, org_id)

    try:
        result = await handle_fireflies_transcription_completed(event)
        log.info("backfill_one_complete", meeting_id=meeting_id, **result)
        print(
            f"  {meeting_id} -> {result.get('num_chunks', 0)} chunks, "
            f"{result.get('total_tokens', 0)} tokens, "
            f"doc_id={result.get('doc_id')}"
        )
        return True
    except Exception as e:
        log.error("backfill_one_failed", meeting_id=meeting_id, error=str(e))
        print(f"  {meeting_id} -> ERROR: {e}")
        return False


async def list_pending(days: int) -> list[dict]:
    """Lista reunioes pendentes (no Fireflies mas nao no banco)."""
    org_id = await _get_gyros_org_id()

    print(f"\nListando reunioes dos ultimos {days} dias...")
    indexed = await _get_indexed_meeting_ids(org_id)
    print(f"  Ja indexadas: {len(indexed)}")

    fireflies = await _list_fireflies_transcripts(days)
    print(f"  No Fireflies: {len(fireflies)}")

    pending = [m for m in fireflies if m["id"] not in indexed]
    print(f"  Pendentes:    {len(pending)}\n")

    if not pending:
        print("Tudo em dia!")
        return []

    print(f"{'meeting_id':<36} {'title':<30} {'date':<20} {'duration'}")
    print("-" * 95)
    for m in pending:
        date_str = datetime.fromtimestamp(m["date"] / 1000, tz=UTC).strftime(
            "%Y-%m-%d %H:%M"
        )
        title = (m.get("title") or "(sem titulo)")[:28]
        duration = f"{int(m.get('duration', 0))}min"
        print(f"{m['id']:<36} {title:<30} {date_str:<20} {duration}")

    return pending


async def sync_pending(days: int) -> None:
    """Indexa todas as reunioes pendentes."""
    pending = await list_pending(days)
    if not pending:
        return

    print(f"\nIndexando {len(pending)} reunioes pendentes...\n")

    success = 0
    fail = 0

    for meeting in pending:
        ok = await backfill_one(meeting["id"])
        if ok:
            success += 1
        else:
            fail += 1

    print("\n=== Resultado ===")
    print(f"  Sucesso: {success}")
    print(f"  Falhas:  {fail}")


async def _run(args: argparse.Namespace) -> None:
    # Garante que o pool esta inicializado antes de qualquer operacao
    await get_pool()
    try:
        if args.command == "one":
            await backfill_one(args.meeting_id)
        elif args.command == "list":
            await list_pending(args.days)
        elif args.command == "sync":
            await sync_pending(args.days)
    finally:
        await close_pool()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill Fireflies meetings que perderam webhook"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    one_p = subparsers.add_parser("one", help="Indexar uma reuniao")
    one_p.add_argument("meeting_id", help="ID da reuniao do Fireflies")

    list_p = subparsers.add_parser("list", help="Listar reunioes pendentes")
    list_p.add_argument(
        "--days", type=int, default=7, help="Quantos dias para tras (default: 7)"
    )

    sync_p = subparsers.add_parser("sync", help="Indexar todas as pendentes")
    sync_p.add_argument(
        "--days", type=int, default=7, help="Quantos dias para tras (default: 7)"
    )

    args = parser.parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
