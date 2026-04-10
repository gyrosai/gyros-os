-- ============================================================================
-- 006_approvals.sql
-- ----------------------------------------------------------------------------
-- Human-in-the-Loop: tabela de aprovações pendentes para ações que escrevem
-- no mundo externo (calendário, email, etc).
--
-- Fluxo: agente chama propose_action -> linha em approvals (status pending)
--        -> usuário responde ✅ no WhatsApp -> handler marca approved
--        -> executor roda -> linha vira executed | failed
--
-- Esta fatia (3.1) introduz só a infra; nenhum executor real ainda — só
-- 'noop_test' para validar o loop ponta a ponta.
-- ============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS approvals (
    id               BIGSERIAL PRIMARY KEY,
    organization_id  UUID NOT NULL REFERENCES organizations(id),
    action_type      TEXT NOT NULL,
    payload          JSONB NOT NULL,
    preview_text     TEXT NOT NULL,
    status           TEXT NOT NULL DEFAULT 'pending'
                     CHECK (status IN ('pending','approved','rejected','executed','failed')),
    proposed_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    decided_at       TIMESTAMPTZ,
    executed_at      TIMESTAMPTZ,
    execution_result JSONB,
    execution_error  TEXT,
    requested_by     TEXT,
    thread_id        TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Lookup principal: "qual é a última approval pending deste usuário?"
-- (suporta aprovação por ✅ sem ID).
CREATE INDEX IF NOT EXISTS idx_approvals_pending_by_user
    ON approvals (organization_id, requested_by, status, proposed_at DESC)
    WHERE status = 'pending';

-- Lookup secundário: limpeza/auditoria por status global.
CREATE INDEX IF NOT EXISTS idx_approvals_status_proposed
    ON approvals (status, proposed_at DESC);

COMMIT;
