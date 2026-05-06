# Tech debt

Registro de atalhos conhecidos que funcionam hoje mas precisam voltar.
Cada item indica sintoma, workaround, fix futuro, quando atacar e
severidade.

---

### 🆕 Contrato do ExecutorFn recebe apenas `payload`, não `Approval` inteiro

**Descoberto em:** Fatia 3.3 Checkpoint 2 (executor `gcal_create_event`).

**Sintoma:** o executor precisava de `user_id` (E.164 com +) pra chamar `get_google_calendar_client`. A fonte natural seria `approval.requested_by`, mas o contrato atual de `ExecutorFn` (em `approvals/executors.py:21` e dispatch em `service.py:321`) passa apenas `payload: dict` ao executor, não a `Approval` inteira nem o pool.

**Workaround aplicado:** a tool `create_calendar_event` duplica `user_id` dentro do `payload` no momento da criação da approval. Funciona porque `payload["user_id"]` e `approval.requested_by` são o mesmo valor por construção (ambos vêm do Twilio webhook, mesma request, mesma Convenção 1). Mas viola DRY e cria risco de divergência sutil se alguém refatorar uma fonte sem a outra.

**Fix futuro:** mudar assinatura de `ExecutorFn` pra `async def (approval: Approval, pool: AsyncConnectionPool) -> dict`. Impacto: tocar em 3 arquivos (`executors.py`, `service.py`, tests dos executores + o `noop_test`). Custo estimado: 1-2h de refactor mecânico.

**Quando atacar:** quando houver 2 ou mais executores reais precisando de contexto além do payload. Hoje temos 1 (`gcal_create_event`) + 1 teste (`noop_test`). Candidato natural: Fatia Semana 3 Proposta, quando o executor `send_proposal_draft` for escrito e provavelmente precisar de mais contexto da approval.

**Severidade:** média. Não bloqueia nada hoje, mas vai piorar com cada executor novo que entrar no workaround.

**Adicionado na:** Fatia 3.3 Checkpoint 2.

---

### 🆕 `[FERNET_DEBUG]` prints expostos em logs de produção
**Descoberto em:** Fatia 5.1 (smoke test `test_pipefy_drive.py`).

**Sintoma:** Toda chamada que decripte tokens emite `print()` com `[FERNET_DEBUG] raw length: 44`, `[FERNET_DEBUG] first 10: '9l2jg1OMRb'`, `[FERNET_DEBUG] last 5: 'pZpI='`, `[FERNET_DEBUG] has whitespace: False`, `[FERNET_DEBUG] has newline: False`, `[FERNET_DEBUG] Fernet initialized OK`. Aparece em `oauth/crypto.py`. Provavelmente sobreviveu de uma sessão de debug e nunca foi removido.

**Workaround aplicado:** Nenhum. Logs ficam poluídos mas funcionam. Em prod, esses prints vão pra stdout do Railway sem filtro.

**Fix futuro:** Remover os `print()` ou trocar por `logger.debug()` em `oauth/crypto.py`. Confirmar antes que nenhum teste/CI depende desse output. Pequeno risco residual: prefixos parciais (10 chars start + 5 end) da chave Fernet vazam pra logs persistentes.

**Quando atacar:** Antes de qualquer deploy de produção que use OAuth (qualquer fatia que adicione Google Drive ou Calendar em prod). Bloqueia compliance básica.

**Severidade:** baixa-média (poluição de log + leak parcial mínimo de chave; não é exploitável diretamente mas ofende princípio de "logs nunca contém secrets").

**Adicionado na:** Fatia 5.1.

---

### 🆕 `provider_user_id` ficando NULL silenciosamente após autorização OAuth
**Descoberto em:** Fatia 5.1 (validação manual da autorização Google em `+5521981354432`).

**Sintoma:** Após fluxo OAuth completo bem-sucedido (token salvo, refresh funcionando, scopes OK), o registro em `oauth_credentials` fica com `provider_user_id = NULL` em vez do email da conta Google que autorizou (esperado: `camila.martins@cimi360.com.br`). O `google.py:exchange_code_for_tokens` chama `_fetch_userinfo(access_token)` e o docstring documenta explicitamente "Se userinfo falhar, seguimos com `email=None`, porque ele é auditoria e não chave."

**Workaround aplicado:** Nenhum — o sistema funciona sem `provider_user_id`. Mas perde rastreabilidade de qual conta Google autorizou um determinado `user_id` E.164. Em multi-tenant com clientes futuros, isso vira problema operacional ("quem do CIMI autorizou Calendar?").

**Fix futuro:** Três opções, em ordem de invasividade: (a) aumentar log level de `oauth_userinfo_failed` de `warning` pra `error` pra trackear quão frequente é, (b) adicionar retry com backoff antes de desistir, (c) tornar `provider_user_id` obrigatório com fail-fast no exchange — mais invasivo mas mais correto pra auditoria.

**Quando atacar:** Antes de adicionar segundo cliente no Gyros OS (multi-tenant real). Hoje só tem CIMI, então 1 NULL é gerenciável; com 5 clientes, vira caos.

**Severidade:** média (auditoria comprometida, mas funcionalidade core OK).

**Adicionado na:** Fatia 5.1.

---

### 🆕 `scripts/create_user.py` (Python legado) usa bcrypt em vez de scrypt do Better Auth
**Descoberto em:** Fatia 5.1 (criação dos users `camila.martins@cimi360.com.br` e `daniels.claudino@cimi360.com.br` no banco local).

**Sintoma:** Script `scripts/create_user.py` tem comentário literal `"""Hash compatível com Better Auth (bcrypt)."""` mas Better Auth não usa bcrypt — usa scrypt nativo via `hashPassword` de `better-auth/crypto`. Users criados pelo script Python conseguem ser inseridos no banco mas **não conseguem logar via Better Auth API** porque o hash não bate.

**Workaround aplicado:** Criado `frontend/scripts/create-user.ts` (TypeScript) seguindo padrão de `bootstrap-admin-core.ts`, que usa `hashPassword` nativo. Os 2 users da CIMI foram criados via TS e logaram OK.

**Fix futuro:** Decidir se mantém o `scripts/create_user.py` (apagar OU marcar `DEPRECATED` no docstring). Quem chegar no projeto pode usar o script errado e gastar 1h debuggando. Apagar é mais seguro; marcar como DEPRECATED preserva histórico.

**Quando atacar:** Próxima limpeza de `scripts/`. Não bloqueia nada agora porque o TS funciona.

**Severidade:** baixa (não quebra nada em uso; só confunde dev novo).

**Adicionado na:** Fatia 5.1.

---

### 🆕 `make up` não detecta mudanças de código no backend
**Descoberto em:** Fatia 5.1 (rota `/oauth/google/start` retornando 404 mesmo após adicionar `get_google_drive_client` e reiniciar com `make down && make up`).

**Sintoma:** Mudanças em arquivos Python sob `src/gyros_os/` não são refletidas após `make down && make up`. Container sobe com imagem antiga em cache. Sintoma típico: rota nova retorna 404, função nova lança `AttributeError`, ou comportamento antigo persiste apesar do código novo. Resolve apenas com `docker compose up -d --build` manual.

**Workaround aplicado:** Documentar mentalmente que mudanças backend exigem `--build` explícito. Hoje na Fatia 5.1 perdi ~10min debuggando "rota não existe" antes de descobrir que era cache.

**Fix futuro:** Três opções: (a) adicionar volume bind mount em `docker-compose.yml` que mapeia `./src` pra dentro do container (hot reload, mas precisa garantir que `--reload` do uvicorn está ligado em dev), (b) criar `make up-build` no Makefile que sempre força build, (c) documentar em `docs/GETTING_STARTED.md` que mudanças backend exigem `--build`.

**Quando atacar:** Próxima fatia que mexer em código backend (Fatia 5.2 já vai precisar). Resolver com (a) é o ideal — DX muito melhor pra todas as próximas fatias.

**Severidade:** média (custa tempo recorrente de debug em cada fatia que mexa em backend).

**Adicionado na:** Fatia 5.1.

---

### ✅ `test_pipefy_drive.py` lista vazio em Shared Drive — RESOLVIDO na Fatia 5.2 Checkpoint 1
**Descoberto em:** Fatia 5.1 (smoke test final).

**Sintoma:** O smoke test imprime `Arquivos na pasta 1Fj_PmBVM8nSXk0Z5DcCt0jRNxobQzPJh: 0` apesar da pasta ter 20+ subpastas. Faltava `includeItemsFromAllDrives=True` / `supportsAllDrives=True` nas chamadas Drive API.

**Resolução:** Criado helper `gyros_os.integrations.google_drive.helpers.drive_kwargs()` que retorna os 2 kwargs obrigatórios. `scripts/test_pipefy_drive.py` agora usa o helper e lista 27 arquivos na pasta-mãe. A próxima fatia (5.2 drive_sync) vai aplicar o mesmo helper em todas as chamadas Drive.

**Adicionado na:** Fatia 5.1. **Resolvido na:** Fatia 5.2 Checkpoint 1.

---

### 🆕 `[FERNET_DEBUG]` prints expostos em logs de produção
**Descoberto em:** Fatia 5.1 (smoke test `test_pipefy_drive.py`).

**Sintoma:** Toda chamada que decripte tokens emite `print()` com `[FERNET_DEBUG] raw length: 44`, `[FERNET_DEBUG] first 10: '9l2jg1OMRb'`, `[FERNET_DEBUG] last 5: 'pZpI='`, `[FERNET_DEBUG] has whitespace: False`, `[FERNET_DEBUG] has newline: False`, `[FERNET_DEBUG] Fernet initialized OK`. Aparece em `oauth/crypto.py`. Provavelmente sobreviveu de uma sessão de debug e nunca foi removido.

**Workaround aplicado:** Nenhum. Logs ficam poluídos mas funcionam. Em prod, esses prints vão pra stdout do Railway sem filtro.

**Fix futuro:** Remover os `print()` ou trocar por `logger.debug()` em `oauth/crypto.py`. Confirmar antes que nenhum teste/CI depende desse output. Pequeno risco residual: prefixos parciais (10 chars start + 5 end) da chave Fernet vazam pra logs persistentes.

**Quando atacar:** Antes de qualquer deploy de produção que use OAuth (qualquer fatia que adicione Google Drive ou Calendar em prod). Bloqueia compliance básica.

**Severidade:** baixa-média (poluição de log + leak parcial mínimo de chave; não é exploitável diretamente mas ofende princípio de "logs nunca contém secrets").

**Adicionado na:** Fatia 5.1.

---

### 🆕 `provider_user_id` ficando NULL silenciosamente após autorização OAuth
**Descoberto em:** Fatia 5.1 (validação manual da autorização Google em `+5521981354432`).

**Sintoma:** Após fluxo OAuth completo bem-sucedido (token salvo, refresh funcionando, scopes OK), o registro em `oauth_credentials` fica com `provider_user_id = NULL` em vez do email da conta Google que autorizou (esperado: `camila.martins@cimi360.com.br`). O `google.py:exchange_code_for_tokens` chama `_fetch_userinfo(access_token)` e o docstring documenta explicitamente "Se userinfo falhar, seguimos com `email=None`, porque ele é auditoria e não chave."

**Workaround aplicado:** Nenhum — o sistema funciona sem `provider_user_id`. Mas perde rastreabilidade de qual conta Google autorizou um determinado `user_id` E.164. Em multi-tenant com clientes futuros, isso vira problema operacional ("quem do CIMI autorizou Calendar?").

**Fix futuro:** Três opções, em ordem de invasividade: (a) aumentar log level de `oauth_userinfo_failed` de `warning` pra `error` pra trackear quão frequente é, (b) adicionar retry com backoff antes de desistir, (c) tornar `provider_user_id` obrigatório com fail-fast no exchange — mais invasivo mas mais correto pra auditoria.

**Quando atacar:** Antes de adicionar segundo cliente no Gyros OS (multi-tenant real). Hoje só tem CIMI, então 1 NULL é gerenciável; com 5 clientes, vira caos.

**Severidade:** média (auditoria comprometida, mas funcionalidade core OK).

**Adicionado na:** Fatia 5.1.

---

### 🆕 `scripts/create_user.py` (Python legado) usa bcrypt em vez de scrypt do Better Auth
**Descoberto em:** Fatia 5.1 (criação dos users `camila.martins@cimi360.com.br` e `daniels.claudino@cimi360.com.br` no banco local).

**Sintoma:** Script `scripts/create_user.py` tem comentário literal `"""Hash compatível com Better Auth (bcrypt)."""` mas Better Auth não usa bcrypt — usa scrypt nativo via `hashPassword` de `better-auth/crypto`. Users criados pelo script Python conseguem ser inseridos no banco mas **não conseguem logar via Better Auth API** porque o hash não bate.

**Workaround aplicado:** Criado `frontend/scripts/create-user.ts` (TypeScript) seguindo padrão de `bootstrap-admin-core.ts`, que usa `hashPassword` nativo. Os 2 users da CIMI foram criados via TS e logaram OK.

**Fix futuro:** Decidir se mantém o `scripts/create_user.py` (apagar OU marcar `DEPRECATED` no docstring). Quem chegar no projeto pode usar o script errado e gastar 1h debuggando. Apagar é mais seguro; marcar como DEPRECATED preserva histórico.

**Quando atacar:** Próxima limpeza de `scripts/`. Não bloqueia nada agora porque o TS funciona.

**Severidade:** baixa (não quebra nada em uso; só confunde dev novo).

**Adicionado na:** Fatia 5.1.

---

### 🆕 `make up` não detecta mudanças de código no backend
**Descoberto em:** Fatia 5.1 (rota `/oauth/google/start` retornando 404 mesmo após adicionar `get_google_drive_client` e reiniciar com `make down && make up`).

**Sintoma:** Mudanças em arquivos Python sob `src/gyros_os/` não são refletidas após `make down && make up`. Container sobe com imagem antiga em cache. Sintoma típico: rota nova retorna 404, função nova lança `AttributeError`, ou comportamento antigo persiste apesar do código novo. Resolve apenas com `docker compose up -d --build` manual.

**Workaround aplicado:** Documentar mentalmente que mudanças backend exigem `--build` explícito. Hoje na Fatia 5.1 perdi ~10min debuggando "rota não existe" antes de descobrir que era cache. Na 5.2 ficou política consciente: usar `docker compose up -d --build` explícito durante a fatia.

**Fix futuro:** Três opções: (a) adicionar volume bind mount em `docker-compose.yml` que mapeia `./src` pra dentro do container (hot reload, mas precisa garantir que `--reload` do uvicorn está ligado em dev), (b) criar `make up-build` no Makefile que sempre força build, (c) documentar em `docs/GETTING_STARTED.md` que mudanças backend exigem `--build`.

**Quando atacar:** Junto com Railway deploy na Fatia 5.3.

**Severidade:** média (custa tempo recorrente de debug em cada fatia que mexa em backend).

**Adicionado na:** Fatia 5.1.
