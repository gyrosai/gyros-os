"""Enfileira manualmente um evento `pipefy.card_moved_to_phase`.

Usado pra validar fim-a-fim a Fatia 5.2 sem webhook (webhook entra na
Fatia 5.3). O event_worker pega o evento, dispara o handler, sincroniza
o card no Drive.

Uso:
    uv run python scripts/enqueue_pipefy_event.py --card-id 1327680921

Pré-requisitos no .env:
    PIPEFY_TOKEN, PIPEFY_PHASE_FORMALIZACAO_ID, PIPEFY_PIPE_CURADORIA_ID
    PIPEFY_DRIVE_USER_ID, DRIVE_PARENT_FOLDER_INSTRUTORES
    (mais GOOGLE_OAUTH_* e o user_id já autorizado com scope drive)

O script só ENFILEIRA — não processa. O processamento acontece no worker
que já está rodando via `docker compose up`. Acompanhe com:
    docker compose logs --tail 100 worker | grep pipefy_event
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import UTC, datetime

import structlog

from gyros_os.shared.config import settings
from gyros_os.shared.db import get_pool
from gyros_os.shared.event_queue import enqueue_event
from gyros_os.shared.org import get_default_org_id

logger = structlog.get_logger("enqueue_pipefy_event")


async def main(card_id: str) -> int:
    if not settings.pipefy_phase_formalizacao_id:
        print(
            "PIPEFY_PHASE_FORMALIZACAO_ID não configurado no .env",
            file=sys.stderr,
        )
        return 2
    if not settings.pipefy_pipe_curadoria_id:
        print(
            "PIPEFY_PIPE_CURADORIA_ID não configurado no .env",
            file=sys.stderr,
        )
        return 2

    # Pool singleton: não chamamos close_pool() aqui.
    # Em CLI standalone, o processo encerra e libera conexões naturalmente.
    # Fechar explicitamente quebra se este módulo for importado por outro código.
    pool = await get_pool()

    # TODO multi-tenant (Fatia 5.3+): quando houver org dedicada CIMI
    # no banco, resolver via SELECT id FROM organizations WHERE slug = 'cimi360'.
    # Hoje single-tenant — reusa a org 'gyros' default, igual webhook_fireflies
    # e backfill_meetings. Princípio: não abstrair multi-tenancy antes de
    # ter 3 instâncias reais.
    org_id = await get_default_org_id(pool)

    payload = {
        "card_id": str(card_id),
        "phase_id": settings.pipefy_phase_formalizacao_id,
        "pipe_id": settings.pipefy_pipe_curadoria_id,
        "moved_at": datetime.now(UTC).isoformat(),
    }

    event_id = await enqueue_event(
        org_id=org_id,
        event_type="pipefy.card_moved_to_phase",
        payload=payload,
    )

    print(f"event_id={event_id} queued")
    return 0


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Enfileira um evento pipefy.card_moved_to_phase manualmente.",
    )
    p.add_argument(
        "--card-id",
        required=True,
        help="ID do card Pipefy a sincronizar (ex: 1327680921)",
    )
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    try:
        sys.exit(asyncio.run(main(args.card_id)))
    except Exception as exc:
        print(f"✗ Falha: {exc}", file=sys.stderr)
        raise
