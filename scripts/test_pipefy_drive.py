"""Smoke test da Fatia 5.1 — cliente Pipefy + helper Drive.

Uso:
    uv run python scripts/test_pipefy_drive.py

Pré-requisitos no .env:
    PIPEFY_TOKEN=...
    PIPEFY_PHASE_FORMALIZACAO_ID=...
    DRIVE_PARENT_FOLDER_INSTRUTORES=...
    GOOGLE_OAUTH_* configurado e o user_id "+5521981354432" já autorizado
    (re-autorize após adicionar o scope drive).

O script falha cedo (`raise`) se algum passo quebrar — é smoke test,
não suite de testes; o objetivo é validar manualmente que a integração
fala com Pipefy e Drive antes de seguir pra Fatia 5.2.
"""

from __future__ import annotations

import asyncio
import sys

from gyros_os.integrations.google_drive.helpers import drive_kwargs
from gyros_os.integrations.pipefy import PipefyClient
from gyros_os.oauth.providers.google import get_google_drive_client
from gyros_os.shared.config import settings


async def check_pipefy() -> None:
    if not settings.pipefy_phase_formalizacao_id:
        raise RuntimeError(
            "PIPEFY_PHASE_FORMALIZACAO_ID não configurado no .env"
        )

    client = PipefyClient()

    cards = await client.get_cards_in_phase(
        settings.pipefy_phase_formalizacao_id
    )
    print(f"  Cards na fase Formalização: {len(cards)}")

    if not cards:
        print("  (fase vazia — pulando get_card)")
        print("✓ Pipefy client OK")
        return

    first = cards[0]
    detail = await client.get_card(first.id)
    print(f"  Primeiro card: {detail.title} (id={detail.id})")
    print(f"  Fase atual: {detail.current_phase.name}")
    print(f"  Campos: {len(detail.fields)}")

    print("✓ Pipefy client OK")


async def check_drive() -> None:
    if not settings.drive_parent_folder_instrutores:
        raise RuntimeError(
            "DRIVE_PARENT_FOLDER_INSTRUTORES não configurado no .env"
        )

    drive = await get_google_drive_client(user_id="+5521981354432")

    # `files().list` é síncrono no SDK do googleapiclient; a chamada
    # de rede roda no thread principal aqui mesmo, é aceitável pra
    # smoke test (o uso real em handlers/worker vai usar executor).
    parent = settings.drive_parent_folder_instrutores
    response = drive.files().list(
        q=f"'{parent}' in parents and trashed = false",
        pageSize=100,
        fields="files(id, name, mimeType)",
        **drive_kwargs(),
    ).execute()

    files = response.get("files", [])
    print(f"  Arquivos na pasta {parent}: {len(files)}")
    for f in files[:5]:
        print(f"   - {f.get('name')} ({f.get('mimeType')})")
    if len(files) > 5:
        print(f"   ... ({len(files) - 5} mais)")

    print("✓ Drive client OK")


async def main() -> None:
    print("=== Pipefy ===")
    await check_pipefy()
    print()
    print("=== Drive ===")
    await check_drive()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as exc:
        print(f"✗ Falha: {exc}", file=sys.stderr)
        raise
