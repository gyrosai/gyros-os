"""Embedding wrapper for OpenAI text-embedding-3-small.

Single source of truth for generating embeddings in the RAG pipeline.
Uses the OpenAI API directly (not via LangChain or OpenRouter).
"""

import openai
import structlog

from gyros_os.shared.config import settings

logger = structlog.get_logger()

# Lazy-initialized client
_client: openai.AsyncOpenAI | None = None

MODEL = "text-embedding-3-small"
DIMS = 1536


def _get_client() -> openai.AsyncOpenAI:
    """Get or create the async OpenAI client."""
    global _client
    if _client is None:
        _client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
    return _client


async def embed_texts(
    texts: list[str], *, batch_size: int = 100
) -> list[list[float]]:
    """Generate embeddings for a list of texts.

    Batches requests to stay under OpenAI's 300k token-per-request limit.

    Args:
        texts: List of strings to embed.
        batch_size: Max chunks per API call (default 100).

    Returns:
        List of embedding vectors (each 1536-dim float list).
    """
    if not texts:
        return []

    client = _get_client()
    all_embeddings: list[list[float]] = []

    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        response = await client.embeddings.create(
            model=MODEL,
            input=batch,
            dimensions=DIMS,
        )
        sorted_data = sorted(response.data, key=lambda x: x.index)
        all_embeddings.extend([item.embedding for item in sorted_data])

    return all_embeddings


async def embed_query(text: str) -> list[float]:
    """Generate embedding for a single query text.

    Args:
        text: Query string to embed.

    Returns:
        Embedding vector (1536-dim float list).
    """
    result = await embed_texts([text])
    return result[0]
