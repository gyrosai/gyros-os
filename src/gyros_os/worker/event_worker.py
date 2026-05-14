"""Event worker — async loop consuming the event_queue.

Runs in parallel with the message worker (same process, separate
asyncio task). Processes non-Twilio events like Fireflies transcriptions.
"""

import asyncio

import structlog

from gyros_os.shared.event_queue import (
    claim_next_event,
    mark_event_done,
    mark_event_failed,
)
from gyros_os.worker.event_handlers.fireflies import (
    handle_fireflies_transcription_completed,
)
from gyros_os.worker.event_handlers.pipefy import (
    handle_pipefy_card_moved_to_phase,
)

logger = structlog.get_logger("event_worker")

HANDLERS = {
    "fireflies.transcription_completed": handle_fireflies_transcription_completed,
    "pipefy.card_moved_to_phase": handle_pipefy_card_moved_to_phase,
}


async def run_event_worker(shutdown_event: asyncio.Event) -> None:
    """Main loop for the event worker.

    Claims events from event_queue and dispatches to the appropriate
    handler based on event_type.

    Args:
        shutdown_event: Set this to gracefully stop the loop.
    """
    logger.info("event_worker_starting")

    while not shutdown_event.is_set():
        event = await claim_next_event(lease_seconds=60)
        if not event:
            await asyncio.sleep(1)
            continue

        try:
            handler = HANDLERS[event.event_type]
            result = await handler(event)
            await mark_event_done(event.id, result=result)
            logger.info(
                "event_handled",
                event_id=event.id,
                event_type=event.event_type,
                result=result,
            )
        except KeyError:
            logger.error(
                "unknown_event_type",
                event_id=event.id,
                event_type=event.event_type,
            )
            await mark_event_failed(
                event.id,
                error=f"unknown event type: {event.event_type}",
                retry=False,
            )
        except Exception as e:
            logger.error(
                "event_handler_failed",
                event_id=event.id,
                event_type=event.event_type,
                error=str(e),
            )
            await mark_event_failed(event.id, error=str(e))

    logger.info("event_worker_stopped")
