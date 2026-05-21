"""Smoke test do drive_sync da Fatia 5.2.

Uso:
    uv run python scripts/test_drive_sync.py --card-id 1323177433

Pré-requisitos no .env:
    PIPEFY_TOKEN=...
    PIPEFY_DRIVE_USER_ID=+5521981354432   (ou outro user com Drive autorizado)
    DRIVE_PARENT_FOLDER_INSTRUTORES=...

Roda fim-a-fim (sem worker, sem evento): busca card via PipefyClient,
monta InstructorInfo, instancia drive client, chama sync_instructor_to_drive
e imprime o SyncResult em JSON. Idempotente — pode rodar quantas vezes
quiser pro mesmo card sem duplicar pasta nem informacoes.md.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from gyros_os.integrations.google_drive.drive_sync import sync_instructor_to_drive
from gyros_os.integrations.pipefy import PipefyClient
from gyros_os.integrations.pipefy.instructor import InstructorInfo
from gyros_os.oauth.providers.google import get_google_drive_client
from gyros_os.shared.config import settings


async def main(card_id: str) -> int:
    if not settings.pipefy_drive_user_id:
        print(
            "PIPEFY_DRIVE_USER_ID não configurado no .env "
            "(ex: +5521981354432)",
            file=sys.stderr,
        )
        return 2
    if not settings.drive_parent_folder_instrutores:
        print(
            "DRIVE_PARENT_FOLDER_INSTRUTORES não configurado no .env",
            file=sys.stderr,
        )
        return 2

    client = PipefyClient()
    card = await client.get_card(card_id)

    info = InstructorInfo.from_card(card)

    drive_service = await get_google_drive_client(
        user_id=settings.pipefy_drive_user_id
    )

    result = await sync_instructor_to_drive(
        info,
        drive_service,
        settings.drive_parent_folder_instrutores,
    )

    print(result.model_dump_json(indent=2))
    return 0


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Smoke test do drive_sync (Fatia 5.2)."
    )
    p.add_argument(
        "--card-id",
        required=True,
        help="ID do card Pipefy a sincronizar (ex: 1323177433)",
    )
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    try:
        sys.exit(asyncio.run(main(args.card_id)))
    except Exception as exc:
        print(f"✗ Falha: {exc}", file=sys.stderr)
        raise
