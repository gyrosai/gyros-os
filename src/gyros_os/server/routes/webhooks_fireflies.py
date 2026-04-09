"""Fireflies webhook endpoint.

Receives transcription events from Fireflies.ai and enqueues them
for async processing by the event worker.
"""

import hashlib
import hmac

import structlog
from fastapi import APIRouter, Header, Request, Response
from pydantic import BaseModel

from gyros_os.shared.config import settings
from gyros_os.shared.db import get_pool
from gyros_os.shared.event_queue import enqueue_event

logger = structlog.get_logger()

router = APIRouter()


class FirefliesWebhookPayload(BaseModel):
    """Payload from Fireflies webhook."""

    meetingId: str
    eventType: str
    clientReferenceId: str | None = None


@router.post("/webhook/fireflies")
async def webhook_fireflies(
    request: Request,
    x_hub_signature: str | None = Header(default=None),
) -> Response:
    """Handle Fireflies webhook events.

    Only processes 'Transcription completed' events. Others are
    acknowledged with 200 but ignored.

    Signature validation uses HMAC-SHA256 when FIREFLIES_WEBHOOK_SECRET
    is configured. In dev mode (no secret), logs a warning but accepts.
    """
    body = await request.body()

    # Validate HMAC signature if secret is configured
    secret = settings.fireflies_webhook_secret
    if secret:
        if not x_hub_signature:
            logger.warning("fireflies_webhook_missing_signature")
            return Response(
                content='{"error": "missing signature"}',
                status_code=401,
                media_type="application/json",
            )

        expected = hmac.new(
            secret.encode(),
            body,
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(expected, x_hub_signature):
            logger.warning("fireflies_webhook_invalid_signature")
            return Response(
                content='{"error": "invalid signature"}',
                status_code=401,
                media_type="application/json",
            )
    else:
        logger.warning("fireflies_webhook_no_secret_configured")

    # Parse payload
    import json

    try:
        payload = FirefliesWebhookPayload(**json.loads(body))
    except Exception:
        logger.warning("fireflies_webhook_invalid_payload")
        return Response(
            content='{"error": "invalid payload"}',
            status_code=400,
            media_type="application/json",
        )

    # Only process transcription completed events
    if payload.eventType != "Transcription completed":
        logger.info(
            "fireflies_webhook_ignored",
            event_type=payload.eventType,
        )
        return Response(
            content='{"status": "ignored"}',
            status_code=200,
            media_type="application/json",
        )

    # TODO: In v0.2, resolve org_id from a mapping (e.g. clientReferenceId
    # or a Fireflies workspace → org mapping). For now, always use 'gyros'.
    pool = await get_pool()
    async with pool.connection() as conn:
        cursor = await conn.execute(
            "SELECT id FROM organizations WHERE slug = 'gyros'"
        )
        row = await cursor.fetchone()
        if row is None:
            logger.error("fireflies_webhook_org_not_found", slug="gyros")
            return Response(
                content='{"error": "organization not found"}',
                status_code=500,
                media_type="application/json",
            )
        gyros_org_id = row[0]

    event_id = await enqueue_event(
        org_id=gyros_org_id,
        event_type="fireflies.transcription_completed",
        payload={
            "meeting_id": payload.meetingId,
            "client_reference_id": payload.clientReferenceId,
        },
    )

    logger.info(
        "fireflies_webhook_enqueued",
        event_id=event_id,
        meeting_id=payload.meetingId,
    )

    return Response(
        content=json.dumps({"status": "queued", "event_id": event_id}),
        status_code=202,
        media_type="application/json",
    )
