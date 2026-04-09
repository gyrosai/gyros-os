# Gyros OS — Week 1 Foundation

This document describes what was added in the first foundation slice of Gyros OS, built on top of the whatsapp-langchain harness.

## What changed

### New tables (migration 005)

| Table | Purpose |
|-------|---------|
| `organizations` | Multi-tenant base. Seeded with `gyros`. |
| `kb_docs` | Long documents (transcriptions, contracts). |
| `kb_chunks` | Text chunks with `vector(1536)` embeddings + HNSW index. |
| `event_queue` | Queue for non-Twilio events (Fireflies, GCal, etc.). |

Existing tables (`message_queue`, `conversations`, `checkpoints`, `store`, `store_vectors`) were **not touched**.

### New modules

```
src/gyros_os/
├── rag/                          # RAG pipeline (standalone)
│   ├── chunking.py               # Semantic chunking (512 tok / 50 overlap)
│   ├── embeddings.py             # OpenAI text-embedding-3-small wrapper
│   ├── ingest.py                 # ingest_text() — idempotent doc+chunks
│   ├── retrieve.py               # retrieve() — cosine similarity via pgvector
│   └── models.py                 # KbDoc, KbChunk, RetrievalResult
├── integrations/
│   └── fireflies/
│       └── client.py             # GraphQL client for Fireflies transcripts
├── shared/
│   └── event_queue.py            # enqueue/claim/mark helpers for event_queue
├── server/routes/
│   └── webhooks_fireflies.py     # POST /webhook/fireflies
└── worker/
    ├── event_worker.py           # Async loop consuming event_queue
    └── event_handlers/
        └── fireflies.py          # Transcription → RAG ingestion
```

### New env vars

| Variable | Required | Purpose |
|----------|----------|---------|
| `OPENAI_API_KEY` | Yes (for RAG) | Embeddings via text-embedding-3-small |
| `FIREFLIES_API_KEY` | Yes (for Fireflies) | GraphQL transcript fetching |
| `FIREFLIES_WEBHOOK_SECRET` | No (recommended in prod) | HMAC-SHA256 webhook validation |

### End-to-end flow

```
Meeting ends on Fireflies
  → Fireflies sends POST /webhook/fireflies
  → Endpoint validates and enqueues event in event_queue
  → Event worker claims the event
  → Handler fetches transcript via Fireflies GraphQL API
  → Text is chunked, embedded, and stored as kb_doc + kb_chunks
```

### What was NOT changed

- Twilio webhook, message_queue, existing worker loop behavior
- Agent catalog (`rhawk_assistant`)
- Frontend, Docker configs, LangGraph config
- Existing tests continue to pass

## Architecture decision: single process, two tasks

The event worker runs as a second `asyncio` task alongside the message worker in the same process (`asyncio.gather`). No new Docker service was added. This keeps the deployment simple while cleanly separating the two processing loops.
