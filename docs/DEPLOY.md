# Deploy no Railway

Guia completo para publicar o projeto **whatsapp-langchain** no Railway, incluindo API, Worker, Frontend e PostgreSQL.

## Pre-requisitos

- Conta no [Railway](https://railway.app)
- Repositorio no GitHub (com o codigo do projeto)
- Conta no [Twilio](https://www.twilio.com) com sandbox WhatsApp configurado
- API key do [OpenRouter](https://openrouter.ai)

## Topologia

```
Internet --> Frontend (Next.js, :3000, publico)
                |
                | (server-side, INTERNAL_SERVICE_TOKEN)
                v
             API (FastAPI, :8000, publico para webhook)
                |
                v
             Worker (privado, consome fila)
                |
                v
             PostgreSQL (privado)
```

O Frontend faz chamadas server-side para a API usando a rede interna do Railway (`*.railway.internal`). O Worker consome mensagens da fila no PostgreSQL e processa com o agente. A API recebe webhooks do Twilio e expoe rotas administrativas.

## Passo a passo

### 1. Criar projeto no Railway

1. Acesse [railway.app](https://railway.app) e faca login.
2. Clique em **New Project** → **Deploy from GitHub Repo**.
3. Selecione o repositorio do projeto.
4. Railway vai criar um servico inicial — vamos configurar cada servico manualmente.

### 2. Adicionar PostgreSQL

1. No projeto, clique em **New** → **Database** → **PostgreSQL**.
2. Railway gera a variavel `DATABASE_URL` automaticamente.
3. Essa variavel sera referenciada pelos outros servicos.

> A extensao `pgvector` e instalada automaticamente nas imagens PostgreSQL do Railway.

### 3. Configurar servico API

| Configuracao     | Valor                          |
|------------------|--------------------------------|
| Root Directory   | `/` (raiz do projeto)          |
| Dockerfile       | `Dockerfile.api`               |
| Port             | `8000`                         |
| Dominio publico  | Generate Domain                |

**Variaveis de ambiente:**

- `DATABASE_URL` — referencia ao PostgreSQL do Railway (use a variavel compartilhada)
- `OPENROUTER_API_KEY` — chave da API OpenRouter
- `OPENROUTER_BASE_URL` — URL base do OpenRouter
- `OPENROUTER_MODEL` — modelo a usar (ex: `google/gemini-2.0-flash-001`)
- `TWILIO_AUTH_TOKEN` — token de autenticacao do Twilio
- `VALIDATE_TWILIO_SIGNATURE` — `true` em producao
- `LOG_JSON` — `true`
- `INTERNAL_SERVICE_TOKEN` — token compartilhado com o Frontend para autenticacao interna

Variaveis opcionais de operacao:

- `CONTEXT_STRATEGY`, `MESSAGE_BUFFER_SECONDS`, `MEMORY_ENABLED`, `EMBEDDING_MODEL`, `EMBEDDING_DIMS`

### 4. Configurar servico Worker

| Configuracao     | Valor                          |
|------------------|--------------------------------|
| Root Directory   | `/` (raiz do projeto)          |
| Dockerfile       | `Dockerfile.worker`            |
| Port             | Nenhuma (servico interno)      |
| Dominio          | Nenhum (privado)               |

**Variaveis de ambiente:**

- `DATABASE_URL` — referencia ao PostgreSQL
- `OPENROUTER_API_KEY`, `OPENROUTER_BASE_URL`, `OPENROUTER_MODEL`
- `TWILIO_OUTBOUND_MODE` — `real` em producao
- `TWILIO_ACCOUNT_SID` — SID da conta Twilio (para envio de respostas)
- `TWILIO_AUTH_TOKEN` — token de autenticacao do Twilio
- `TWILIO_FROM_NUMBER` — numero WhatsApp do Twilio (ex: `whatsapp:+14155238886`)
- `LOG_JSON` — `true`

Variaveis opcionais do worker:

- `POLL_INTERVAL_SECONDS`, `LEASE_SECONDS`, `MAX_ATTEMPTS`, `MESSAGE_BUFFER_SECONDS`
- `MEMORY_ENABLED`, `EMBEDDING_MODEL`, `EMBEDDING_DIMS`

### 5. Configurar servico Frontend

| Configuracao     | Valor                          |
|------------------|--------------------------------|
| Root Directory   | `/frontend`                    |
| Dockerfile       | `Dockerfile` (em `frontend/`)  |
| Port             | `3000`                         |
| Dominio publico  | Generate Domain                |

**Variaveis de ambiente:**

- `INTERNAL_API_URL` — `http://api.railway.internal:8000` (rede interna do Railway)
- `INTERNAL_SERVICE_TOKEN` — mesmo token configurado na API
- `DATABASE_URL` — referencia ao PostgreSQL (para Better Auth)
- `BETTER_AUTH_SECRET` — secret para sessoes do Better Auth (gere um valor aleatorio forte)
- `BETTER_AUTH_URL` — URL publica do Frontend (ex: `https://frontend-domain.up.railway.app`)

### 6. Bootstrap do primeiro usuario admin

Quando o banco de auth estiver vazio, o primeiro acesso a `/login` cria
automaticamente o admin educacional padrao.

Credenciais iniciais:
- email: `ronnald@rhawk.pro`
- senha: `meuSistema`

Se quiser um usuario inicial diferente antes do primeiro login, rode o seed
manualmente:

```bash
cd frontend
npx tsx scripts/seed-admin.ts
```

Se quiser sobrescrever os defaults:

```bash
cd frontend
ADMIN_EMAIL=admin@empresa.com ADMIN_PASSWORD=senhaForte123 npx tsx scripts/seed-admin.ts
```

> O script e idempotente: se o email ja existir, nao cria duplicata. Os defaults acima sao para uso educacional; em ambientes nao educacionais, sobrescreva as credenciais.

Assim que o primeiro login for concluido, acesse `/settings` no painel e
troque a senha bootstrap. O projeto agora oferece esse fluxo no proprio
frontend, sem precisar editar o banco de dados.

### 7. Configurar webhook do Twilio

1. No console do Twilio, va para **Messaging** → **Settings** → **WhatsApp Sandbox**.
2. Configure a URL do webhook:

```
https://api-domain.up.railway.app/webhook/twilio?agent=rhawk_assistant
```

3. Na API, certifique-se de que `VALIDATE_TWILIO_SIGNATURE=true` esta ativo.

> A validacao de assinatura garante que apenas requests vindos do Twilio sejam aceitos. Nunca desative em producao.

## Verificacao

Apos o deploy, verifique se tudo esta funcionando:

1. **Health check da API:**

```bash
curl https://api-domain.up.railway.app/health
# Esperado: HTTP 200
```

2. **Pagina de login do Frontend:**

```
https://frontend-domain.up.railway.app/login
# Esperado: pagina de login renderizada
```

3. **Rotacao inicial de senha no painel:**

```
https://frontend-domain.up.railway.app/settings
# Esperado: formulario protegido para atualizar a senha do admin
```

4. **Teste end-to-end:**
   - Envie uma mensagem WhatsApp para o numero do sandbox Twilio.
   - Verifique nos logs do Worker que a mensagem foi processada.
   - Verifique que a resposta chegou no WhatsApp.

## Troubleshooting

### Logs

No Railway Dashboard, selecione o servico e clique em **Logs**. Todos os servicos usam `structlog` com formato JSON em producao, o que facilita a busca por campos especificos.

### Acesso ao banco

Usando o Railway CLI:

```bash
railway connect postgres
```

Isso abre um shell `psql` conectado ao banco de producao. Util para verificar a fila de mensagens:

```sql
SELECT status, count(*) FROM message_queue GROUP BY status;
```

### Migracoes

As migracoes rodam automaticamente no startup da API. Se precisar verificar:

```sql
SELECT * FROM schema_migrations ORDER BY applied_at DESC LIMIT 5;
```

### Better Auth

As tabelas de autenticacao sao criadas automaticamente no schema `auth` na primeira execucao do Frontend. Se houver problemas, verifique se `DATABASE_URL` e `BETTER_AUTH_SECRET` estao configurados corretamente.

### Problemas comuns

- **Worker nao processa mensagens:** verifique se `DATABASE_URL` esta correto e se o Worker esta rodando (sem porta, mas deve aparecer como "running" no dashboard).
- **Frontend nao conecta na API:** verifique se `INTERNAL_API_URL` usa o endereco interno (`*.railway.internal`) e se `INTERNAL_SERVICE_TOKEN` e o mesmo nos dois servicos.
- **Webhook retorna 403:** verifique `TWILIO_AUTH_TOKEN` e `VALIDATE_TWILIO_SIGNATURE`.

## `/webhook/sync` em producao

A rota `/webhook/sync` existe apenas para desenvolvimento local — ela processa a mensagem de forma sincrona, sem passar pela fila.

**NAO exponha essa rota em producao.** Em producao, toda mensagem deve passar pela fila assincrona (`/webhook/twilio`), que garante:

- Debounce de mensagens consecutivas
- Retries em caso de falha
- Rate limiting
- Processamento isolado no Worker

## Custo estimado

| Servico    | Custo mensal (aprox.) |
|------------|-----------------------|
| API        | ~$5                   |
| Worker     | ~$5                   |
| Frontend   | ~$5                   |
| PostgreSQL | ~$5 (hobby tier)      |
| **Total**  | **~$20/mes**          |

Para volume baixo de mensagens. O custo escala com uso de CPU/memoria e volume de requests.
