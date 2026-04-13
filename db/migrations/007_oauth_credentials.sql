-- 007_oauth_credentials.sql
-- Fatia 3.2 — OAuth Google Calendar + persistência de tokens

CREATE TABLE IF NOT EXISTS oauth_credentials (
    id                      BIGSERIAL PRIMARY KEY,
    organization_id         UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id                 TEXT NOT NULL,
    provider                TEXT NOT NULL,
    provider_user_id        TEXT,
    scopes                  TEXT[] NOT NULL,
    access_token_encrypted  BYTEA NOT NULL,
    refresh_token_encrypted BYTEA,
    token_type              TEXT NOT NULL DEFAULT 'Bearer',
    expires_at              TIMESTAMPTZ NOT NULL,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_oauth_user_provider UNIQUE (user_id, provider)
);

CREATE INDEX IF NOT EXISTS idx_oauth_credentials_org
    ON oauth_credentials (organization_id);

COMMENT ON TABLE oauth_credentials IS
    'OAuth2 credentials per (user_id, provider). Tokens encrypted at rest via Fernet.';
COMMENT ON COLUMN oauth_credentials.refresh_token_encrypted IS
    'Nullable: Google only returns refresh_token on first consent or with prompt=consent. On refresh, preserve existing value — do NOT overwrite with NULL.';
