-- ============================================================================
-- 005_gyros_os_foundation.sql
-- ----------------------------------------------------------------------------
-- Fundação do Gyros OS sobre o harness whatsapp-langchain.
--
-- Adiciona:
--   1. organizations    — base multi-tenant (1 linha hoje, N no futuro)
--   2. kb_docs          — documentos longos (transcrições, contratos)
--   3. kb_chunks        — chunks com embeddings p/ retrieval
--   4. event_queue      — fila para eventos não-Twilio (Fireflies, GCal, etc.)
--
-- Não toca em: message_queue, conversations, checkpoints, store, store_vectors
-- (essas tabelas continuam exatamente como o harness as deixou).
--
-- pgvector já está instalado (usado pelo store_vectors do LangGraph),
-- então não precisamos de CREATE EXTENSION.
-- ============================================================================

BEGIN;

-- ----------------------------------------------------------------------------
-- 1. ORGANIZATIONS
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS organizations (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug        TEXT NOT NULL UNIQUE,
    name        TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO organizations (slug, name)
VALUES ('gyros', 'Gyros AI Solutions')
ON CONFLICT (slug) DO NOTHING;

-- ----------------------------------------------------------------------------
-- 2. KB_DOCS
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS kb_docs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id),
    source_type     TEXT NOT NULL,                 -- 'fireflies' | 'manual' | etc
    source_ref      TEXT,                          -- id externo (nullable)
    title           TEXT NOT NULL,
    content         TEXT NOT NULL,                 -- texto bruto completo
    project_tag     TEXT,                          -- tag livre, nullable
    metadata        JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (organization_id, source_type, source_ref)
);

CREATE INDEX IF NOT EXISTS idx_kb_docs_org_created
    ON kb_docs (organization_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_kb_docs_org_project
    ON kb_docs (organization_id, project_tag)
    WHERE project_tag IS NOT NULL;

-- ----------------------------------------------------------------------------
-- 3. KB_CHUNKS
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS kb_chunks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id),
    doc_id          UUID NOT NULL REFERENCES kb_docs(id) ON DELETE CASCADE,
    chunk_index     INTEGER NOT NULL,
    content         TEXT NOT NULL,
    token_count     INTEGER,
    embedding       vector(1536),
    metadata        JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (doc_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_kb_chunks_embedding_hnsw
    ON kb_chunks
    USING hnsw (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS idx_kb_chunks_org
    ON kb_chunks (organization_id);

-- ----------------------------------------------------------------------------
-- 4. EVENT_QUEUE
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS event_queue (
    id              BIGSERIAL PRIMARY KEY,
    organization_id UUID NOT NULL REFERENCES organizations(id),
    event_type      TEXT NOT NULL,
    payload         JSONB NOT NULL DEFAULT '{}'::jsonb,

    status          TEXT NOT NULL DEFAULT 'queued'
                    CHECK (status IN ('queued','processing','done','failed')),
    attempts        INTEGER NOT NULL DEFAULT 0,
    max_attempts    INTEGER NOT NULL DEFAULT 5,
    process_after   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    lease_until     TIMESTAMPTZ,

    result          JSONB,
    error           TEXT,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processed_at    TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_event_queue_claim
    ON event_queue (status, process_after)
    WHERE status = 'queued';

CREATE INDEX IF NOT EXISTS idx_event_queue_org_type
    ON event_queue (organization_id, event_type, created_at DESC);

COMMIT;
