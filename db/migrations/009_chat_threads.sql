-- Tabela auxiliar para rastrear threads do chat studio.
-- O checkpointer do LangGraph não é projetado para listagem de threads,
-- então mantemos uma tabela leve para a UI.

CREATE TABLE IF NOT EXISTS chat_threads (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    organization_id UUID NOT NULL REFERENCES organizations(id),
    title TEXT NOT NULL DEFAULT 'Nova conversa',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS chat_threads_user_id_idx
    ON chat_threads (user_id, updated_at DESC);
