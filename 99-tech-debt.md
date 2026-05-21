# Tech debt

Registro de atalhos conhecidos que funcionam hoje mas precisam voltar.
Cada item indica sintoma, workaround, fix futuro, quando atacar e
severidade.

---

### 🆕 `event_worker` engole `KeyError` do handler como "unknown event type"
**Descoberto em:** Fatia 5.3 Parte A (tentando reproduzir o suposto bug de `event_queue.error` NULL).

**Sintoma:** Em `worker/event_worker.py`, o dispatcher faz `handler = HANDLERS[event.event_type]` dentro do mesmo `try:` que executa `await handler(event)`. O `except KeyError:` foi pensado pra capturar event_types não registrados — mas captura também `KeyError`s levantados de DENTRO do handler. Concretamente: um evento `pipefy.card_moved_to_phase` com payload faltando `card_id` levanta `KeyError("card_id")` em `event.payload["card_id"]`. O worker classifica isso como "unknown event type" e marca o evento como `failed` com `retry=False` — mensagem de erro misleading e payload inválido nunca retentado mesmo quando o problema é transiente do enqueue (ex: webhook que perdeu um campo).

**Workaround aplicado:** Nenhum hoje — payloads bem-formados (Fatia 5.2 e 5.3 Parte A) não acionam o caso. Mas qualquer mudança futura no contrato de payload pode entrar nessa armadilha silenciosamente.

**Fix futuro:** Em `event_worker.py`, separar a lookup do dispatch: `handler = HANDLERS.get(event.event_type)` antes do `try`, e usar `if handler is None:` pra o caminho "unknown event type". O `try` ao redor do `await handler(event)` então só captura erros de execução. Esse design já é o padrão típico de dispatchers; o atual é um descuido.

**Quando atacar:** Antes do webhook Pipefy real entrar em prod (Fatia 5.3 Parte B). Webhook real pode mandar payloads incompletos por bug do remetente, e a operação precisa ver `event_handler_failed` no log, não `unknown event type`.

**Severidade:** média (debug fica confuso; eventos com payload quebrado não retentam quando deveriam).

**Adicionado na:** Fatia 5.3 Parte A.

---

### 🆕 Duplicatas no próprio `99-tech-debt.md`
**Descoberto em:** Fatia 5.3 Parte A (marcando os 5 débitos como resolvidos).

**Sintoma:** Três débitos aparecem **duas vezes** no arquivo, com conteúdo quase idêntico:
- `[FERNET_DEBUG]` prints (linhas ~68 e ~131)
- `provider_user_id` NULL silencioso (linhas ~79 e ~142)
- `scripts/create_user.py` bcrypt (linhas ~92 e ~155)
- `make up` no rebuild (linhas ~109 e ~172)

Provavelmente uma colagem acidental em alguma revisão da Fatia 5.1. Não afetou nada operacionalmente — só dobra a leitura.

**Workaround aplicado:** Marquei TODAS as duplicatas como resolvidas na Fatia 5.3 Parte A (3 itens × 2 cópias = 6 entradas tocadas). O `create_user.py` continua aberto nas duas cópias porque está fora do escopo desta fatia.

**Fix futuro:** Próxima edição manual do `99-tech-debt.md`, deletar as duplicatas (manter só a primeira ocorrência de cada). Tarefa de 5 minutos, mas requer ler com atenção pra não derrubar histórico legítimo.

**Quando atacar:** Próxima limpeza do arquivo (qualquer fatia).

**Severidade:** baixa (não afeta código; só ruído de leitura).

**Adicionado na:** Fatia 5.3 Parte A.

---

### ✅ `Acesso negado` do Pipefy é retentado desnecessariamente — RESOLVIDO na Fatia 5.3 Parte A
**Descoberto em:** Fatia 5.2 Checkpoint 3 (validação fim-a-fim).

**Sintoma:** Quando `PipefyClient.get_card(card_id)` retorna `"Acesso negado"` (card foi movido pra outro pipe, arquivado, ou perdeu permissão), o handler propaga como exceção genérica e o `event_worker` retenta 5x com backoff (5+10+15+20s = ~50s totais) antes de marcar `failed`. Em produção, descobrimos isso quando o card 1327680921 (Cristina Gravina) ficou inacessível entre uma execução e outra — provavelmente movido pela equipe da CIMI no Pipefy.

**Resolução:** `PipefyClient._post` detecta `extensions.code=="PERMISSION_DENIED"` (com fallback pra `message=="Acesso negado"` caso a API deixe de mandar extensions) e levanta `PipefyAccessDenied` (subclasse de `PipefyError`, com `card_id` no atributo). O handler `pipefy.card_moved_to_phase` captura antes do `except` genérico e retorna `{"action":"skipped","reason":"card_access_denied","card_id":...}`. Validado fim-a-fim com o mesmo card 1327680921: `event_queue` foi de `status=failed/attempts=5` (antes) pra `status=done/attempts=1` (depois).

**Adicionado na:** Fatia 5.2 Checkpoint 3. **Resolvido na:** Fatia 5.3 Parte A.

---

### ✅ `event_queue.error` fica NULL após failure — VERIFICADO RESOLVIDO na Fatia 5.3 Parte A
**Descoberto em:** Fatia 5.2 Checkpoint 3 (evento 11 falhou 5x com `Acesso negado`).

**Sintoma observado:** Quando um evento falhou definitivamente (esgotou retries), os logs do `event_worker` mostraram a string de erro mas a coluna `event_queue.error` aparecia `NULL` em pelo menos uma inspeção do evento 11.

**Resolução (sem mudança de código):** Verificado durante a Fatia 5.3 Parte A que o código atual de `gyros_os/shared/event_queue.py:mark_event_failed` **já persiste `error` em ambos os paths** — retry (linhas ~228-237, `SET error=%s`) e terminal failure (linhas ~251-260, `SET error=%s`). Reproduzido o cenário de retry-exhaustion via `max_attempts=1` + handler `fireflies.transcription_completed` com `meeting_id` bogus: linha terminou com `status=failed, attempts=1, error="Transcript not found: ..."`. Re-inspecionado o próprio evento 11 hoje: `error="Acesso negado"` (não NULL). `git log` em `event_queue.py` mostra um único commit — não houve fix silencioso. Conclusão: a observação original foi de estado transiente (provavelmente entre claim e mark_event_failed, ou tabela lida durante reset de retry).

**Adicionado na:** Fatia 5.2 Checkpoint 3. **Resolvido na:** Fatia 5.3 Parte A (verificação, sem mudança de código).

---

### 🆕 `camila.martins@cimi360.com.br` sem permissão de delete/trash no Shared Drive `0AMWOAOVQ2sFvUk9PVA`
**Descoberto em:** Fatia 5.2 Checkpoint 2.

**Sintoma:** A conta da Camila consegue **criar** e **atualizar** arquivos no Shared Drive da CIMI Curadoria via OAuth API, mas não consegue **deletar** nem **trashear** arquivos individuais. As capabilities reais retornadas pelo Drive API pra `foto_*.jpg` que ela mesma criou via standalone: `canDelete=False, canTrash=False, canEdit=True, canModifyContent=True`. Tentar `files().delete(fileId=...)` retorna 404 (Drive API mascara "no permission" como 404 em delete); `files().update(body={"trashed": True})` retorna 403 com `"The user does not have sufficient permissions for this file"`.

O standalone `~/Documents/cimi-automation/pipefy_to_drive.py` exibia esse 404 como warning em todas as execuções ("ruído em 100% dos cards") e o efeito real ficou camuflado: as fotos antigas nunca eram apagadas, e cada execução criava uma nova foto. A pasta da Ana Tedoldi acumulou 4 cópias de `foto_ana_carolina_tedoldi_pinto.jpg` antes do problema ser visto na Fatia 5.2 Checkpoint 2.

**Workaround aplicado (Fatia 5.2 Checkpoint 2):** `drive_sync._upload_photo` foi escrito de forma a **nunca chamar delete**. Em vez disso: lista por prefixo `foto_<slug>` na pasta, e se existir arquivo, faz `update(media_body=)` no primeiro encontrado (com rename via `body={"name":...}` se a extensão mudou). Se não existir, faz `create`. Idempotente sem precisar da permissão ausente. As fotos órfãs já acumuladas continuam na pasta e precisam ser apagadas manualmente via UI do Drive (a Camila vai fazer isso antes do Checkpoint 3).

**Fix futuro:** elevar a role da `camila.martins@cimi360.com.br` no Shared Drive `0AMWOAOVQ2sFvUk9PVA` de "Contributor" pra "Editor" (ou "Content manager"). Isso é uma operação de admin do Workspace da CIMI — não é mudança de código. Após resolvido: opcionalmente escrever script one-off que percorra as pastas e apague arquivos `foto_*` órfãos (qualquer um além do mais recente).

**Quando atacar:** próxima sessão de admin Workspace na CIMI. Não bloqueia mais o Gyros OS depois do workaround do Checkpoint 2; só deixa lixo lentamente acumulado nas pastas até alguém apagar manualmente.

**Severidade:** baixa (não bloqueia funcionalidade após o workaround; só deixa orphan files no Drive).

**Adicionado na:** Fatia 5.2 Checkpoint 2.

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

### ✅ `[FERNET_DEBUG]` prints expostos em logs de produção — RESOLVIDO na Fatia 5.3 Parte A
**Descoberto em:** Fatia 5.1 (smoke test `test_pipefy_drive.py`).

**Sintoma:** Toda chamada que decripte tokens emitia `print()` com `[FERNET_DEBUG] raw length: 44`, `[FERNET_DEBUG] first 10: '9l2jg1OMRb'`, `[FERNET_DEBUG] last 5: 'pZpI='`, `[FERNET_DEBUG] has whitespace: False`, `[FERNET_DEBUG] has newline: False`, `[FERNET_DEBUG] Fernet initialized OK`, indo pra stdout do Railway sem filtro. Prefixos parciais da chave Fernet vazavam pra logs persistentes.

**Resolução:** `oauth/crypto.py` agora usa `structlog.get_logger().debug(...)` em vez de `print()`, com eventos estáveis (`fernet_key_loaded`, `fernet_key_validated`, `fernet_initialized`). Os prefixos parciais (`first 10` / `last 5`) foram **removidos completamente** — não aparecem nem em DEBUG, atendendo o princípio de "logs nunca contém secrets, nem partes deles". Falha de inicialização loga só o nome do tipo da exceção, não a mensagem (que pode incluir bytes da chave). `grep -r FERNET_DEBUG .` confirma zero ocorrências.

**Adicionado na:** Fatia 5.1. **Resolvido na:** Fatia 5.3 Parte A.

---

### ✅ `provider_user_id` ficando NULL silenciosamente após autorização OAuth — PARCIALMENTE RESOLVIDO na Fatia 5.3 Parte A
**Descoberto em:** Fatia 5.1 (validação manual da autorização Google em `+5521981354432`).

**Sintoma:** Após fluxo OAuth completo bem-sucedido (token salvo, refresh funcionando, scopes OK), o registro em `oauth_credentials` fica com `provider_user_id = NULL` em vez do email da conta Google que autorizou (esperado: `camila.martins@cimi360.com.br`). O `google.py:exchange_code_for_tokens` chama `_fetch_userinfo(access_token)` e o docstring documenta explicitamente "Se userinfo falhar, seguimos com `email=None`, porque ele é auditoria e não chave."

**Resolução parcial (opções (a)+(b) do plano original):** `_fetch_userinfo` agora (i) tenta até 3x com backoff 1s + 3s pra erros transientes (5xx, exceções `httpx.HTTPError`); (ii) curto-circuita em 401/403 (token rejeitado não melhora em segundos); (iii) loga falha final como `level=error` com campo `attempt` em vez de `warning` — pra `provider_user_id NULL` virar sinal acionável em prod. Timeout por tentativa caiu de 10s pra 5s pra manter o teto agregado da retry sequence (~19s) dentro do budget do callback OAuth do browser.

**Pendente (opção (c) do plano original):** Tornar `provider_user_id` obrigatório com fail-fast no exchange. Mais invasivo e só faz sentido quando tivermos segundo cliente real (multi-tenant). Fica pra próxima fatia que mexer em OAuth depois de um cliente novo entrar.

**Adicionado na:** Fatia 5.1. **Parcialmente resolvido na:** Fatia 5.3 Parte A.

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

### ✅ `make up` não detecta mudanças de código no backend — RESOLVIDO na Fatia 5.3 Parte A
**Descoberto em:** Fatia 5.1 (rota `/oauth/google/start` retornando 404 mesmo após adicionar `get_google_drive_client` e reiniciar com `make down && make up`).

**Sintoma:** Mudanças em arquivos Python sob `src/gyros_os/` não eram refletidas após `make down && make up`. Container subia com imagem antiga em cache. Sintoma típico: rota nova retornava 404, função nova lançava `AttributeError`, ou comportamento antigo persistia apesar do código novo. Resolvia apenas com `docker compose up -d --build` manual.

**Resolução (opção (a) do plano original):** `docker-compose.yml` agora monta `./src:/app/src` em `api` e `worker`, e gateia o startup em `GYROS_DEV_MODE=true`: `api` roda `uvicorn ... --reload --reload-dir /app/src`, `worker` roda `python -m watchfiles "python -m gyros_os.worker.main" /app/src`. Foi necessário também adicionar `PYTHONPATH=/app/src` — sem isso, Python preferia a cópia estagnada de `site-packages/` (instalada pelo `uv pip install --system .` no Dockerfile) sobre o bind mount, fazendo `watchfiles` reiniciar o processo mas as importações continuarem velhas. Validado: editar `shared/config.py` dispara reload do api em ~2s e do worker em ~2s. Compose é dev-only (Railway/Nixpacks pra prod), Dockerfile.api/worker `CMD` intactos.

**Adicionado na:** Fatia 5.1. **Resolvido na:** Fatia 5.3 Parte A.

---

### ✅ `test_pipefy_drive.py` lista vazio em Shared Drive — RESOLVIDO na Fatia 5.2 Checkpoint 1
**Descoberto em:** Fatia 5.1 (smoke test final).

**Sintoma:** O smoke test imprime `Arquivos na pasta 1Fj_PmBVM8nSXk0Z5DcCt0jRNxobQzPJh: 0` apesar da pasta ter 20+ subpastas. Faltava `includeItemsFromAllDrives=True` / `supportsAllDrives=True` nas chamadas Drive API.

**Resolução:** Criado helper `gyros_os.integrations.google_drive.helpers.drive_kwargs()` que retorna os 2 kwargs obrigatórios. `scripts/test_pipefy_drive.py` agora usa o helper e lista 27 arquivos na pasta-mãe. A próxima fatia (5.2 drive_sync) vai aplicar o mesmo helper em todas as chamadas Drive.

**Adicionado na:** Fatia 5.1. **Resolvido na:** Fatia 5.2 Checkpoint 1.

---

### ✅ `[FERNET_DEBUG]` prints expostos em logs de produção — RESOLVIDO na Fatia 5.3 Parte A
**Descoberto em:** Fatia 5.1 (smoke test `test_pipefy_drive.py`).

**Sintoma:** Toda chamada que decripte tokens emitia `print()` com `[FERNET_DEBUG] raw length: 44`, `[FERNET_DEBUG] first 10: '9l2jg1OMRb'`, `[FERNET_DEBUG] last 5: 'pZpI='`, `[FERNET_DEBUG] has whitespace: False`, `[FERNET_DEBUG] has newline: False`, `[FERNET_DEBUG] Fernet initialized OK`, indo pra stdout do Railway sem filtro. Prefixos parciais da chave Fernet vazavam pra logs persistentes.

**Resolução:** `oauth/crypto.py` agora usa `structlog.get_logger().debug(...)` em vez de `print()`, com eventos estáveis (`fernet_key_loaded`, `fernet_key_validated`, `fernet_initialized`). Os prefixos parciais (`first 10` / `last 5`) foram **removidos completamente** — não aparecem nem em DEBUG, atendendo o princípio de "logs nunca contém secrets, nem partes deles". Falha de inicialização loga só o nome do tipo da exceção, não a mensagem (que pode incluir bytes da chave). `grep -r FERNET_DEBUG .` confirma zero ocorrências.

**Adicionado na:** Fatia 5.1. **Resolvido na:** Fatia 5.3 Parte A.

---

### ✅ `provider_user_id` ficando NULL silenciosamente após autorização OAuth — PARCIALMENTE RESOLVIDO na Fatia 5.3 Parte A
**Descoberto em:** Fatia 5.1 (validação manual da autorização Google em `+5521981354432`).

**Sintoma:** Após fluxo OAuth completo bem-sucedido (token salvo, refresh funcionando, scopes OK), o registro em `oauth_credentials` fica com `provider_user_id = NULL` em vez do email da conta Google que autorizou (esperado: `camila.martins@cimi360.com.br`). O `google.py:exchange_code_for_tokens` chama `_fetch_userinfo(access_token)` e o docstring documenta explicitamente "Se userinfo falhar, seguimos com `email=None`, porque ele é auditoria e não chave."

**Resolução parcial (opções (a)+(b) do plano original):** `_fetch_userinfo` agora (i) tenta até 3x com backoff 1s + 3s pra erros transientes (5xx, exceções `httpx.HTTPError`); (ii) curto-circuita em 401/403 (token rejeitado não melhora em segundos); (iii) loga falha final como `level=error` com campo `attempt` em vez de `warning` — pra `provider_user_id NULL` virar sinal acionável em prod. Timeout por tentativa caiu de 10s pra 5s pra manter o teto agregado da retry sequence (~19s) dentro do budget do callback OAuth do browser.

**Pendente (opção (c) do plano original):** Tornar `provider_user_id` obrigatório com fail-fast no exchange. Mais invasivo e só faz sentido quando tivermos segundo cliente real (multi-tenant). Fica pra próxima fatia que mexer em OAuth depois de um cliente novo entrar.

**Adicionado na:** Fatia 5.1. **Parcialmente resolvido na:** Fatia 5.3 Parte A.

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

### ✅ `make up` não detecta mudanças de código no backend — RESOLVIDO na Fatia 5.3 Parte A
**Descoberto em:** Fatia 5.1 (rota `/oauth/google/start` retornando 404 mesmo após adicionar `get_google_drive_client` e reiniciar com `make down && make up`).

**Sintoma:** Mudanças em arquivos Python sob `src/gyros_os/` não eram refletidas após `make down && make up`. Container subia com imagem antiga em cache. Sintoma típico: rota nova retornava 404, função nova lançava `AttributeError`, ou comportamento antigo persistia apesar do código novo. Resolvia apenas com `docker compose up -d --build` manual. Na 5.2 ficou política consciente: usar `docker compose up -d --build` explícito durante a fatia.

**Resolução (opção (a) do plano original):** Ver entrada acima — bind mount `./src:/app/src` + `PYTHONPATH=/app/src` em `api` e `worker`, gateando `uvicorn --reload` e `python -m watchfiles` em `GYROS_DEV_MODE=true`. Reload verificado em ~2s editando `shared/config.py`.

**Adicionado na:** Fatia 5.1. **Resolvido na:** Fatia 5.3 Parte A.
