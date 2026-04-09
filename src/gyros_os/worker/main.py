"""Entry point do Worker — loops de processamento de mensagens e eventos.

Inicia dois workers em paralelo no mesmo processo:
1. Message worker: consome message_queue (Twilio/WhatsApp)
2. Event worker: consome event_queue (Fireflies, GCal, etc.)

Uso:
    python -m gyros_os.worker.main
"""

import asyncio
import signal

import structlog

from gyros_os.shared.config import settings
from gyros_os.shared.db import (
    close_pool,
    get_pool,
    open_checkpointer,
    open_store,
    run_migrations,
)
from gyros_os.shared.observability import setup_logging
from gyros_os.worker.consumer import claim_next_message
from gyros_os.worker.event_worker import run_event_worker
from gyros_os.worker.processor import process_message
from gyros_os.worker.twilio_client import TwilioClient

logger = structlog.get_logger()


async def run_message_worker(
    shutdown_event: asyncio.Event,
    pool,
    checkpointer,
    store,
    twilio,
) -> None:
    """Message worker loop — consumes message_queue.

    This is the original worker logic, extracted into a coroutine
    so it can run alongside the event worker via asyncio.gather.
    """
    logger.info("message_worker_starting")

    while not shutdown_event.is_set():
        message = await claim_next_message(pool, settings.lease_seconds)

        if message is None:
            await asyncio.sleep(settings.poll_interval_seconds)
            continue

        await process_message(
            message,
            pool,
            checkpointer=checkpointer,
            store=store,
            twilio=twilio,
        )

    logger.info("message_worker_stopped")


async def main() -> None:
    """Boot both workers and run them in parallel.

    1. Configura logging e banco de dados
    2. Aplica migrações pendentes
    3. Inicia message_worker e event_worker em paralelo
    """
    setup_logging(log_level=settings.log_level, json_output=settings.log_json)
    logger.info("worker_starting")

    pool = await get_pool()
    await run_migrations(pool)
    checkpointer_stack, checkpointer = await open_checkpointer()
    await checkpointer.setup()

    store_stack, store = await open_store()
    if store:
        await store.setup()

    outbound_mode = settings.resolved_twilio_outbound_mode
    if outbound_mode == "real":
        missing = []
        if not settings.twilio_account_sid:
            missing.append("TWILIO_ACCOUNT_SID")
        if not settings.twilio_api_key_sid:
            missing.append("TWILIO_API_KEY_SID")
        if not settings.twilio_api_key_secret:
            missing.append("TWILIO_API_KEY_SECRET")
        if not settings.twilio_from_number:
            missing.append("TWILIO_FROM_NUMBER")

        if missing:
            logger.error(
                "twilio_credentials_missing",
                missing=missing,
                outbound_mode=outbound_mode,
            )
            msg = (
                "Twilio outbound em modo real requer variáveis: "
                f"{', '.join(missing)}"
            )
            raise SystemExit(msg)

    twilio = TwilioClient(
        account_sid=settings.twilio_account_sid,
        api_key_sid=settings.twilio_api_key_sid,
        api_key_secret=settings.twilio_api_key_secret,
        from_number=settings.twilio_from_number,
        delivery_mode=outbound_mode,
    )
    logger.info(
        "twilio_client_ready",
        outbound_mode=outbound_mode,
        from_number=settings.twilio_from_number or None,
    )

    logger.info(
        "worker_ready",
        poll_interval=settings.poll_interval_seconds,
        memory_enabled=store is not None,
    )

    shutdown_event = asyncio.Event()

    # Register signal handlers for graceful shutdown
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, shutdown_event.set)

    try:
        await asyncio.gather(
            run_message_worker(
                shutdown_event, pool, checkpointer, store, twilio
            ),
            run_event_worker(shutdown_event),
        )
    finally:
        if store_stack is not None:
            await store_stack.aclose()
        await checkpointer_stack.aclose()
        await close_pool()
        logger.info("worker_stopped")


if __name__ == "__main__":
    asyncio.run(main())
