# STATUS — Gyros OS

Histórico curto e linear das fatias entregues. Cada entrada lista
exatamente o que foi criado/modificado e como foi validado.

## Fatia 5.1 (2026-05-06) — Cliente Pipefy + Drive helper

- Criados:
  - `src/gyros_os/integrations/pipefy/__init__.py`
  - `src/gyros_os/integrations/pipefy/client.py`
    (`PipefyClient`, modelos `PipefyField`/`CardData`/`CardSummary`,
    exceções `PipefyError`/`PipefyAuthError`/`PipefyNotFound`,
    helper estático `extract_field`)
  - `scripts/test_pipefy_drive.py` (smoke test manual)
- Modificados:
  - `src/gyros_os/shared/config.py` — adicionados `pipefy_token`,
    `pipefy_pipe_curadoria_id`, `pipefy_phase_formalizacao_id`,
    `drive_parent_folder_instrutores` (sem alterar nada existente).
  - `src/gyros_os/oauth/providers/google.py` — adicionado
    `get_google_drive_client(user_id)`, espelhando o helper de
    Calendar (mesmo refresh proativo).
  - `.env.example` — variáveis novas Pipefy/Drive e scope `drive`
    incluído em `GOOGLE_OAUTH_SCOPES`.
- Validado via `scripts/test_pipefy_drive.py` em 06/maio/2026 14:43:
  - ✓ Pipefy: 6 cards listados na fase Formalização, primeiro card fetch OK (ANA CAROLINA TEDOLDI PINTO, 22 fields).
  - ✓ Drive: auth OAuth + connect ao Shared Drive `0AMWOAOVQ2sFvUk9PVA` funcionando.
- Débitos técnicos identificados (ver `99-tech-debt.md`).
- Próximo: Fatia 5.2 (drive_sync + handler de evento Pipefy).
