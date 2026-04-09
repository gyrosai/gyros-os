"""Operations on the event_queue table in PostgreSQL.

Mirrors the pattern of shared/queue.py (message_queue) but for
non-Twilio events (Fireflies, GCal, etc.).

Usage:
    from gyros_os.shared.event_queue import enqueue_event, claim_next_event

    event_id = await enqueue_event(org_id, "fireflies.transcription_completed", {...})
    event = await claim_next_event(lease_seconds=60)
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import structlog
from pydantic import BaseModel, Field

from gyros_os.shared.db import get_pool

logger = structlog.get_logger()


class Event(BaseModel):
    """Mapped row from event_queue table."""

    id: int
    organization_id: UUID
    event_type: str
    payload: dict = Field(default_factory=dict)
    status: str = "queued"
    attempts: int = 0
    max_attempts: int = 5
    process_after: datetime | None = None
    lease_until: datetime | None = None
    result: dict | None = None
    error: str | None = None
    created_at: datetime
    processed_at: datetime | None = None


async def enqueue_event(
    org_id: UUID,
    event_type: str,
    payload: dict,
    process_after: datetime | None = None,
) -> int:
    """Insert a new event into the event_queue.

    Args:
        org_id: Organization UUID.
        event_type: Event type string (e.g. 'fireflies.transcription_completed').
        payload: JSON-serializable event payload.
        process_after: Optional delayed processing time.

    Returns:
        The event ID (bigint).
    """
    import json

    pool = await get_pool()
    pa = process_after or datetime.now(UTC)

    async with pool.connection() as conn:
        cursor = await conn.execute(
            """
            INSERT INTO event_queue
                (organization_id, event_type, payload, process_after)
            VALUES (%s, %s, %s::jsonb, %s)
            RETURNING id
            """,
            (str(org_id), event_type, json.dumps(payload), pa),
        )
        row = await cursor.fetchone()
        assert row is not None
        event_id = row[0]
        await conn.commit()

    logger.info(
        "event_enqueued",
        event_id=event_id,
        org_id=str(org_id),
        event_type=event_type,
    )
    return event_id


async def claim_next_event(lease_seconds: int = 60) -> Event | None:
    """Claim the next ready event using FOR UPDATE SKIP LOCKED.

    Returns:
        Event if one is available, None otherwise.
    """
    pool = await get_pool()
    lease_until = datetime.now(UTC) + timedelta(seconds=lease_seconds)

    async with pool.connection() as conn:
        # Expire stuck events that exceeded max attempts
        await conn.execute(
            """
            UPDATE event_queue
            SET status = 'failed',
                error = COALESCE(error, 'Processing lease expired after max attempts'),
                processed_at = NOW()
            WHERE status = 'processing'
              AND lease_until IS NOT NULL
              AND lease_until <= NOW()
              AND attempts >= max_attempts
            """
        )

        cursor = await conn.execute(
            """
            UPDATE event_queue
            SET status = 'processing',
                lease_until = %s,
                attempts = attempts + 1
            WHERE id = (
                SELECT id FROM event_queue
                WHERE (
                    status = 'queued'
                    AND process_after <= NOW()
                    AND attempts < max_attempts
                )
                OR (
                    status = 'processing'
                    AND lease_until IS NOT NULL
                    AND lease_until <= NOW()
                    AND attempts < max_attempts
                )
                ORDER BY created_at ASC
                LIMIT 1
                FOR UPDATE SKIP LOCKED
            )
            RETURNING id, organization_id, event_type, payload,
                      status, attempts, max_attempts,
                      process_after, lease_until,
                      result, error, created_at, processed_at
            """,
            (lease_until,),
        )
        row = await cursor.fetchone()
        await conn.commit()

        if row is None:
            return None

        event = Event(
            id=row[0],
            organization_id=row[1],
            event_type=row[2],
            payload=row[3] if row[3] else {},
            status=row[4],
            attempts=row[5],
            max_attempts=row[6],
            process_after=row[7],
            lease_until=row[8],
            result=row[9],
            error=row[10],
            created_at=row[11],
            processed_at=row[12],
        )

        logger.info(
            "event_claimed",
            event_id=event.id,
            event_type=event.event_type,
            attempt=event.attempts,
        )
        return event


async def mark_event_done(event_id: int, result: dict | None = None) -> None:
    """Mark an event as successfully processed.

    Args:
        event_id: Event ID.
        result: Optional result dict to store.
    """
    import json

    pool = await get_pool()
    result_json = json.dumps(result) if result else None

    async with pool.connection() as conn:
        await conn.execute(
            """
            UPDATE event_queue
            SET status = 'done',
                result = %s::jsonb,
                processed_at = NOW()
            WHERE id = %s
            """,
            (result_json, event_id),
        )
        await conn.commit()

    logger.info("event_done", event_id=event_id)


async def mark_event_failed(
    event_id: int,
    error: str,
    retry: bool = True,
) -> None:
    """Mark an event as failed, with optional retry.

    If retry=True and attempts remain, returns to 'queued' with
    progressive backoff (attempts * 5 seconds).

    Args:
        event_id: Event ID.
        error: Error description.
        retry: Whether to retry (default True).
    """
    pool = await get_pool()

    async with pool.connection() as conn:
        if retry:
            cursor = await conn.execute(
                "SELECT attempts, max_attempts FROM event_queue WHERE id = %s",
                (event_id,),
            )
            row = await cursor.fetchone()

            if row and row[0] < row[1]:
                backoff_seconds = row[0] * 5
                await conn.execute(
                    """
                    UPDATE event_queue
                    SET status = 'queued',
                        error = %s,
                        lease_until = NULL,
                        process_after = NOW() + make_interval(secs => %s)
                    WHERE id = %s
                    """,
                    (error, backoff_seconds, event_id),
                )
                await conn.commit()
                logger.warning(
                    "event_retry",
                    event_id=event_id,
                    attempt=row[0],
                    max_attempts=row[1],
                    backoff_seconds=backoff_seconds,
                    error=error,
                )
                return

        # No retry or exhausted attempts: fail permanently
        await conn.execute(
            """
            UPDATE event_queue
            SET status = 'failed',
                error = %s,
                processed_at = NOW()
            WHERE id = %s
            """,
            (error, event_id),
        )
        await conn.commit()
        logger.error("event_failed", event_id=event_id, error=error)
