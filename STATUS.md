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

## Fatia 5.2 (2026-05-13) — Drive sync + handler Pipefy

- Criados:
  - `src/gyros_os/integrations/google_drive/__init__.py`
  - `src/gyros_os/integrations/google_drive/helpers.py`
    (kwargs `supportsAllDrives` / `includeItemsFromAllDrives` para
    Shared Drives, extraído como helper único usado pelo `drive_sync`)
  - `src/gyros_os/integrations/google_drive/drive_sync.py`
    (`sync_instructor_to_drive` idempotente — pasta por slug do nome,
    `foto_<slug>` sem delete, `informacoes.md` com upsert por nome;
    `SyncResult` com flags `folder_action`, `photo_action`,
    `info_action` pra audit em `event_queue.result`)
  - `src/gyros_os/integrations/pipefy/field_mapping.py`
    (mapa `field_id → atributo` do pipe CIMI360 Curadoria 2026)
  - `src/gyros_os/integrations/pipefy/instructor.py`
    (`InstructorInfo` Pydantic + `InstructorInfo.from_card` — usa
    `field_mapping` + `PipefyClient.extract_field` pra extrair os
    22 campos necessários ao Drive a partir do `CardData`)
  - `src/gyros_os/worker/event_handlers/pipefy.py`
    (`handle_pipefy_card_moved_to_phase` — filtra por `phase_id`
    estável, busca card, monta `InstructorInfo`, chama `drive_sync`;
    fase ignorada retorna `{"action": "ignored", ...}` sem erro)
  - `scripts/test_drive_sync.py` (smoke test standalone do
    `sync_instructor_to_drive` — usado no Checkpoint 2)
  - `scripts/enqueue_pipefy_event.py` (CLI pra enfileirar
    `pipefy.card_moved_to_phase` manualmente — usado no Checkpoint 3
    pra validar fim-a-fim via worker rodando, sem precisar de webhook)
- Modificados:
  - `src/gyros_os/shared/config.py` — adicionados
    `pipefy_drive_user_id` (E.164 com `+` do dono dos tokens OAuth
    Drive que o handler usa) e `drive_parent_folder_instrutores`
    (folder pai onde as pastas dos instrutores moram).
  - `src/gyros_os/worker/event_worker.py` — `HANDLERS` recebeu
    `"pipefy.card_moved_to_phase": handle_pipefy_card_moved_to_phase`.
  - `src/gyros_os/worker/event_handlers/__init__.py` — re-export do
    `handle_pipefy_card_moved_to_phase`.
  - `scripts/test_pipefy_drive.py` — passou a usar
    `drive_helpers.supports_all_drives_kwargs()` em vez de inline
    (consistência com o `drive_sync` real).
  - `.env.example` — variáveis novas `PIPEFY_DRIVE_USER_ID` e
    `DRIVE_PARENT_FOLDER_INSTRUTORES`.
- Validado em 12–13/maio/2026 via `event_queue` real (worker
  Docker processando, eventos enfileirados com
  `scripts/enqueue_pipefy_event.py`):
  - ✓ Evento 9 — card novo (Ana Tedoldi `1323177433`):
    `folder_action=created`, `photo_action=created`,
    `info_action=created`.
  - ✓ Evento 10 — `phase_id` errado: handler retornou
    `{"action": "ignored", "reason": "phase_not_handled"}` sem
    chamar Pipefy nem Drive; `event_queue.status=succeeded`.
  - ✓ Evento 12 — re-enqueue do mesmo card (Ana Tedoldi):
    `folder_action=existing`, `photo_action=updated`,
    `info_action=updated` → idempotência confirmada.
  - Nota: card `1327680921` (Cristina Gravina) ficou
    `Acesso negado` no Pipefy entre Checkpoint 2 e Checkpoint 3
    (provavelmente movido pela equipe CIMI). Substituído por
    Ana Tedoldi (`1323177433`) na validação. Descoberta
    registrada como débito técnico (retry desnecessário em
    `Acesso negado`).
- 2 débitos técnicos novos (ver `99-tech-debt.md`):
  retry desnecessário em `Acesso negado` do Pipefy, e
  `event_queue.error` ficando `NULL` após failure terminal.
- PR: `feat/gyros-os-week-5-slice-2-drive-sync` — aguardando
  code review (não mergeada).
- Próximo: Fatia 5.3 (webhook Pipefy + deploy Railway + os
  2 tech debts críticos acima).
