"""RAG module — ingest documents and retrieve relevant chunks.

Usage:
    from gyros_os.rag import ingest_text, retrieve
"""

from gyros_os.rag.ingest import ingest_text
from gyros_os.rag.retrieve import retrieve

__all__ = ["ingest_text", "retrieve"]
