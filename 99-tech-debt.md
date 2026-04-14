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
