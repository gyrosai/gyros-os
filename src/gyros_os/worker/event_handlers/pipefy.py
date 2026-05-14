"""Handler do evento `pipefy.card_moved_to_phase`.

Disparado quando um card do Pipefy é movido pra uma fase monitorada.
Hoje, monitoramos UMA fase: a "Formalização e Confirmação de Contrato"
do pipe CIMI360 Curadoria 2026 (`settings.pipefy_phase_formalizacao_id`).
Quando um card entra nela, criamos/atualizamos a pasta do instrutor no
Drive via `sync_instructor_to_drive`.

POR QUÊ filtrar por `phase_id` (não por nome): `phase_id` é estável no
Pipefy; o nome muda quando alguém renomeia a fase na UI. Se monitorássemos
por nome, qualquer renomeação acidental quebraria o handler em silêncio.

POR QUÊ não tratar `PipefyNotFound` aqui: o `event_worker` já tem
try/except global que retenta até `max_attempts=5` antes de marcar
o evento como `failed`. Levantar a exceção é o caminho correto —
adicionar tratamento especial seria YAGNI.
"""

from __future__ import annotations

import structlog

from gyros_os.integrations.google_drive.drive_sync import sync_instructor_to_drive
from gyros_os.integrations.pipefy import PipefyClient
from gyros_os.integrations.pipefy.instructor import InstructorInfo
from gyros_os.oauth.providers.google import get_google_drive_client
from gyros_os.shared.config import settings
from gyros_os.shared.event_queue import Event

logger = structlog.get_logger()


async def handle_pipefy_card_moved_to_phase(event: Event) -> dict:
    """Sincroniza um card do Pipefy pro Drive quando entra na fase Formalização.

    Payload esperado:
        - `card_id` (str): ID do card no Pipefy.
        - `phase_id` (str): fase pra qual o card foi movido. Se diferente
          de `settings.pipefy_phase_formalizacao_id`, ignora.

    Returns:
        - Se ignorado: `{"action": "ignored", "reason": "phase_not_handled",
          "phase_id": ..., "expected": ...}`.
        - Se processado: `SyncResult.model_dump()` do `drive_sync` — folder
          + foto + informacoes.md IDs e flags pra audit em `event_queue.result`.
    """
    card_id = event.payload["card_id"]
    phase_id = event.payload["phase_id"]

    logger.info(
        "pipefy_event_received",
        event_id=event.id,
        card_id=card_id,
        phase_id=phase_id,
    )

    expected_phase = settings.pipefy_phase_formalizacao_id
    if phase_id != expected_phase:
        ignored = {
            "action": "ignored",
            "reason": "phase_not_handled",
            "phase_id": phase_id,
            "expected": expected_phase,
        }
        logger.info(
            "pipefy_event_ignored",
            event_id=event.id,
            card_id=card_id,
            reason=ignored["reason"],
            phase_id=phase_id,
            expected=expected_phase,
        )
        return ignored

    client = PipefyClient()
    card = await client.get_card(card_id)
    info = InstructorInfo.from_card(card)

    logger.info(
        "pipefy_event_processing",
        event_id=event.id,
        card_id=card_id,
        instructor_name=info.nome,
    )

    drive_service = await get_google_drive_client(
        user_id=settings.pipefy_drive_user_id
    )

    sync_result = await sync_instructor_to_drive(
        info,
        drive_service,
        settings.drive_parent_folder_instrutores,
    )

    result = sync_result.model_dump()

    logger.info(
        "pipefy_event_completed",
        event_id=event.id,
        card_id=card_id,
        result=result,
    )

    return result
