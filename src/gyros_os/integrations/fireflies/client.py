"""Fireflies.ai GraphQL client for fetching transcripts.

Usage:
    from gyros_os.integrations.fireflies import FirefliesClient

    client = FirefliesClient()
    transcript = await client.get_transcript("meeting_id_here")
"""

import time

import httpx
import structlog
from pydantic import BaseModel, ConfigDict, ValidationError

from gyros_os.shared.config import settings

logger = structlog.get_logger()

GRAPHQL_URL = "https://api.fireflies.ai/graphql"

TRANSCRIPT_QUERY = """
query Transcript($transcriptId: String!) {
  transcript(id: $transcriptId) {
    id
    title
    date
    duration
    participants
    transcript_url
    sentences {
      speaker_name
      text
      start_time
    }
    summary {
      keywords
      action_items
      outline
      overview
    }
  }
}
"""


class FirefliesAuthError(Exception):
    """Raised when the Fireflies API key is invalid (401)."""


class FirefliesNotFound(Exception):
    """Raised when the transcript/meeting is not found (404 or null result)."""


class FirefliesSentence(BaseModel):
    """A single sentence from a Fireflies transcript."""

    model_config = ConfigDict(extra="allow")

    speaker_name: str
    text: str
    start_time: float


class FirefliesSummary(BaseModel):
    """Summary section of a Fireflies transcript.

    All string fields — Fireflies returns markdown, not structured lists.
    """

    model_config = ConfigDict(extra="allow")

    keywords: str | None = None
    action_items: str | None = None
    outline: str | None = None
    overview: str | None = None


class FirefliesTranscript(BaseModel):
    """Parsed Fireflies transcript.

    Types match the real GraphQL response (validated against meeting
    01KNQY2BTST2KTP35KD1BNCGMH). extra="allow" on all models so new
    fields from Fireflies don't break parsing.
    """

    model_config = ConfigDict(extra="allow")

    id: str
    title: str
    date: int                              # timestamp in milliseconds
    duration: float                        # in MINUTES (not seconds)
    participants: list[str] = []
    transcript_url: str | None = None
    sentences: list[FirefliesSentence] = []
    summary: FirefliesSummary | None = None


class FirefliesClient:
    """Minimal read-only client for the Fireflies.ai GraphQL API."""

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key or settings.fireflies_api_key

    async def get_transcript(self, meeting_id: str) -> FirefliesTranscript:
        """Fetch a transcript by meeting ID.

        Args:
            meeting_id: The Fireflies transcript/meeting ID.

        Returns:
            FirefliesTranscript with all available data.

        Raises:
            FirefliesAuthError: If the API key is invalid.
            FirefliesNotFound: If the meeting is not found.
        """
        start = time.monotonic()

        async with httpx.AsyncClient() as http:
            response = await http.post(
                GRAPHQL_URL,
                json={
                    "query": TRANSCRIPT_QUERY,
                    "variables": {"transcriptId": meeting_id},
                },
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                timeout=30.0,
            )

        latency_ms = round((time.monotonic() - start) * 1000)

        if response.status_code == 401:
            logger.error(
                "fireflies_auth_error",
                meeting_id=meeting_id,
                latency_ms=latency_ms,
            )
            raise FirefliesAuthError("Invalid Fireflies API key")

        if response.status_code == 404:
            logger.warning(
                "fireflies_not_found",
                meeting_id=meeting_id,
                latency_ms=latency_ms,
            )
            raise FirefliesNotFound(f"Transcript not found: {meeting_id}")

        response.raise_for_status()

        data = response.json()

        # GraphQL may return 200 with errors
        if "errors" in data:
            error_msg = data["errors"][0].get("message", "Unknown GraphQL error")
            logger.error(
                "fireflies_graphql_error",
                meeting_id=meeting_id,
                error=error_msg,
                latency_ms=latency_ms,
            )
            if "not found" in error_msg.lower():
                raise FirefliesNotFound(f"Transcript not found: {meeting_id}")
            raise FirefliesNotFound(error_msg)

        transcript_data = data.get("data", {}).get("transcript")
        if transcript_data is None:
            logger.warning(
                "fireflies_transcript_null",
                meeting_id=meeting_id,
                latency_ms=latency_ms,
            )
            raise FirefliesNotFound(f"Transcript not found: {meeting_id}")

        logger.info(
            "fireflies_graphql_response",
            meeting_id=meeting_id,
            raw_response=transcript_data,
        )

        try:
            transcript = FirefliesTranscript(**transcript_data)
        except ValidationError as e:
            logger.error(
                "fireflies_transcript_validation_failed",
                meeting_id=meeting_id,
                raw_response=transcript_data,
                validation_errors=e.errors(),
            )
            raise

        num_sentences = len(transcript.sentences) if transcript.sentences else 0

        logger.info(
            "fireflies_transcript_fetched",
            meeting_id=meeting_id,
            title=transcript.title,
            num_sentences=num_sentences,
            duration=transcript.duration,
            latency_ms=latency_ms,
        )

        return transcript
