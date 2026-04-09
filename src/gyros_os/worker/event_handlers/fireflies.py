"""Handler for fireflies.transcription_completed events.

Fetches the transcript from Fireflies GraphQL API and ingests it
into the knowledge base via the RAG pipeline.
"""

import structlog

from gyros_os.integrations.fireflies import FirefliesClient
from gyros_os.rag import ingest_text
from gyros_os.shared.event_queue import Event

logger = structlog.get_logger()


def _format_time(seconds: float) -> str:
    """Format seconds to HH:MM."""
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}"


def _format_duration_minutes(seconds: float | None) -> str:
    """Format duration in seconds to 'N min'."""
    if seconds is None:
        return "unknown"
    return f"{int(seconds / 60)} min"


async def handle_fireflies_transcription_completed(event: Event) -> dict:
    """Fetch a Fireflies transcript and ingest it into the KB.

    Args:
        event: Event from event_queue with payload containing meeting_id.

    Returns:
        Result dict with num_chunks for logging.
    """
    meeting_id = event.payload["meeting_id"]

    logger.info(
        "fireflies_handler_start",
        event_id=event.id,
        meeting_id=meeting_id,
    )

    # Fetch transcript from Fireflies API
    client = FirefliesClient()
    transcript = await client.get_transcript(meeting_id)

    # Build consolidated text
    lines = [
        f"Reunião: {transcript.title}",
        f"Data: {transcript.date or 'N/A'}",
        f"Duração: {_format_duration_minutes(transcript.duration)}",
        f"Participantes: {', '.join(transcript.participants)}",
        "---",
    ]

    for sentence in transcript.sentences:
        timestamp = _format_time(sentence.start_time)
        lines.append(f"[{timestamp}] {sentence.speaker_name}: {sentence.text}")

    content = "\n\n".join(lines)

    # TODO: In v0.2, auto-classify project_tag based on participants
    # or meeting title patterns. For now, None.
    project_tag = None

    metadata = {
        "participants": transcript.participants,
        "duration_seconds": transcript.duration,
        "fireflies_url": transcript.transcript_url,
        "date": transcript.date,
    }

    if transcript.summary:
        metadata["summary_overview"] = transcript.summary.overview
        metadata["summary_keywords"] = transcript.summary.keywords

    result = await ingest_text(
        org_id=event.organization_id,
        source_type="fireflies",
        source_ref=meeting_id,
        title=transcript.title,
        content=content,
        project_tag=project_tag,
        metadata=metadata,
    )

    logger.info(
        "fireflies_handler_complete",
        event_id=event.id,
        meeting_id=meeting_id,
        num_chunks=result["num_chunks"],
        total_tokens=result["total_tokens"],
        latency_ms=result["latency_ms"],
    )

    return {
        "num_chunks": result["num_chunks"],
        "total_tokens": result["total_tokens"],
        "doc_id": result["doc_id"],
    }
