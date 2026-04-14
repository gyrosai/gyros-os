"""Fireflies webhook endpoint.

Receives transcription events from Fireflies.ai and enqueues them
for async processing by the event worker.
"""

import hashlib
import hmac
import json

import structlog
from fastapi import APIRouter, Header, Request, Response
from pydantic import BaseModel, ValidationError

from gyros_os.shared.config import settings
from gyros_os.shared.db import get_pool
from gyros_os.shared.event_queue import enqueue_event
from gyros_os.shared.org import get_default_org_id

logger = structlog.get_logger()

router = APIRouter()


class FirefliesWebhookPayload(BaseModel):
    """Payload from Fireflies webhook.

    Real format (discovered via test ping — docs were wrong):
    {"event": "transcription_completed", "meeting_id": "abc123", "timestamp": 1775699967472}
    """

    meeting_id: str
    event: str
    timestamp: int | None = None
    client_reference_id: str | None = None


# Normalized event names that trigger transcription processing
_TRANSCRIPTION_EVENTS = {
    "transcription_completed",
    "meeting_transcribed",
}

# Normalized event names we explicitly ignore (no enqueue)
_SUMMARY_EVENTS = {
    "summary_completed",
    "meeting_summarized",
}


def _normalize_event(raw: str) -> str:
    """Normalize event name: lowercase, spaces/hyphens → underscores."""
    return raw.strip().lower().replace(" ", "_").replace("-", "_")


@router.post("/webhook/fireflies")
async def webhook_fireflies(
    request: Request,
    x_hub_signature: str | None = Header(default=None),
) -> Response:
    """Handle Fireflies webhook events.

    Processes 'Meeting Transcribed' events (enqueues for processing).
    Ignores 'Meeting Summarized' and any other event types with 200 OK.

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

    # Parse raw JSON and log everything for observability
    try:
        parsed_json = json.loads(body)
    except (json.JSONDecodeError, ValueError):
        parsed_json = None

    logger.info(
        "fireflies_webhook_received",
        raw_payload=parsed_json if parsed_json is not None else body.decode(errors="replace"),
        headers=dict(request.headers),
    )

    # Accept Fireflies test pings — the "Send Test Event" button sends
    # a payload without the required fields, or with event="test".
    # Return 200 so Fireflies doesn't mark the webhook as broken.
    if parsed_json is None or not (
        isinstance(parsed_json, dict)
        and "meeting_id" in parsed_json
        and "event" in parsed_json
    ):
        logger.info("fireflies_webhook_test_ping", raw_payload=parsed_json)
        return Response(
            content='{"status": "test_acknowledged"}',
            status_code=200,
            media_type="application/json",
        )

    # Validate against schema
    try:
        payload = FirefliesWebhookPayload(**parsed_json)
    except ValidationError as e:
        logger.warning(
            "fireflies_webhook_invalid_payload",
            raw_payload=parsed_json,
            validation_errors=e.errors(),
        )
        return Response(
            content='{"error": "invalid payload"}',
            status_code=400,
            media_type="application/json",
        )

    # Classify event type (case-insensitive, accept both space and snake_case)
    normalized = _normalize_event(payload.event)

    if normalized in _SUMMARY_EVENTS:
        logger.info(
            "fireflies_webhook_ignored_summarized",
            meeting_id=payload.meeting_id,
            raw_event=payload.event,
        )
        return Response(
            content='{"status": "ignored"}',
            status_code=200,
            media_type="application/json",
        )

    if normalized not in _TRANSCRIPTION_EVENTS:
        logger.info(
            "fireflies_unknown_event_type",
            raw_event=payload.event,
            normalized=normalized,
            meeting_id=payload.meeting_id,
        )
        return Response(
            content='{"status": "ignored"}',
            status_code=200,
            media_type="application/json",
        )

    # TODO: In v0.2, resolve org_id from a mapping (e.g. clientReferenceId
    # or a Fireflies workspace → org mapping). For now, always use 'gyros'.
    pool = await get_pool()
    gyros_org_id = await get_default_org_id(pool)

    event_id = await enqueue_event(
        org_id=gyros_org_id,
        event_type="fireflies.transcription_completed",
        payload={
            "meeting_id": payload.meeting_id,
            "client_reference_id": payload.client_reference_id,
        },
    )

    logger.info(
        "fireflies_webhook_enqueued",
        event_id=event_id,
        meeting_id=payload.meeting_id,
    )

    return Response(
        content=json.dumps({"status": "queued", "event_id": event_id}),
        status_code=202,
        media_type="application/json",
    )
