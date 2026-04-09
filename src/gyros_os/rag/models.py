"""Pydantic models for the RAG module."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class KbDoc(BaseModel):
    """A knowledge-base document (maps to kb_docs table)."""

    id: UUID
    organization_id: UUID
    source_type: str
    source_ref: str | None = None
    title: str
    content: str
    project_tag: str | None = None
    metadata: dict = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class KbChunk(BaseModel):
    """A chunk of a document with its embedding (maps to kb_chunks table)."""

    id: UUID
    organization_id: UUID
    doc_id: UUID
    chunk_index: int
    content: str
    token_count: int | None = None
    metadata: dict = Field(default_factory=dict)
    created_at: datetime


class RetrievalResult(BaseModel):
    """A single retrieval result from semantic search."""

    chunk_id: UUID
    doc_id: UUID
    content: str
    score: float
    token_count: int | None = None
    doc_title: str
    doc_source_type: str
    doc_metadata: dict = Field(default_factory=dict)
