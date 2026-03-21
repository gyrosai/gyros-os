# Deploy no Railway

Guia completo para deploy do whatsapp-langchain no Railway, cobrindo topologia de servicos, rede interna, watch paths e todas as variaveis de ambiente necessarias.

## Topologia de Servicos

O projeto usa 4 servicos no Railway:

| Servico  | Dockerfile            | Porta | Visibilidade | Replicas | Dominio                       |
|----------|-----------------------|-------|--------------|----------|-------------------------------|
| API      | `Dockerfile.api`      | 8000  | Publico      | 2        | `api-*.up.railway.app`        |
| Worker   | `Dockerfile.worker`   | ---   | Privado      | 1        | ---                           |
| Frontend | `Dockerfile.frontend` | 3000  | Publico      | 1        | `frontend-*.up.railway.app`   |
| DB       | `Dockerfile.db`       | 5432  | Privado      | 1        | ---                           |

### API

Servico publico que recebe webhooks do Twilio e expoe o health check.

- **Rotas publicas:** `/webhook/twilio` e `/health`
- **Rotas protegidas:** `/api/*` requerem o header `INTERNAL_SERVICE_TOKEN`
- O Frontend se comunica com a API via rede interna do Railway (`http://api.railway.internal:8000`), nunca pelo dominio publico
- **2 replicas** para reduzir indisponibilidade durante redeploy e servir como exemplo de load balancing no curso

> **Nota:** o rate limit atual e em memoria. Com 2 replicas, o limite efetivo fica por instancia, nao global.

### Worker

Servico privado que consome a fila de mensagens do PostgreSQL.

- Sem porta exposta --- nao recebe requisicoes HTTP
- Faz polling na tabela de fila do banco para processar mensagens pendentes
- Executa os agentes LangGraph e envia respostas via Twilio

### Frontend

Admin Panel em Next.js, publico para acesso dos administradores.

- Consome a API internamente via `http://api.railway.internal:8000`
- O `INTERNAL_SERVICE_TOKEN` garante que apenas o Frontend consegue chamar as rotas `/api/*`
- Conecta diretamente ao banco para o Better Auth (sessoes, usuarios, tokens)

### DB (PostgreSQL + pgvector)

Container customizado usando a imagem `pgvector/pgvector:pg16`.

- Acessivel apenas pela rede interna (privado)
- Volume persistente montado em `/var/lib/postgresql/data`
- pgvector habilitado para memoria semantica (extensao criada via migracao SQL)
- **Nao e um plugin nativo do Railway** --- usa `Dockerfile.db` com a imagem do pgvector

---

## Rede Interna (Reference Variables)

Os servicos se comunicam pela rede privada do Railway. Para que o dashboard visualize as conexoes entre servicos, usamos **reference variables** (`${{service.VARIABLE}}`) em vez de strings hardcoded.

### Conexoes

```
                    +----------+
                    |    db    | (privado)
                    | pgvector |
                    +----+-----+
              +----------+----------+
              |          |          |
         +----v---+ +----v----+ +--v-------+
         |  api   | | worker  | | frontend |
         | :8000  | | (priv.) | | Next.js  |
         +----+---+ +---------+ +--+-------+
              |                    |
              |<-------------------+
              |   INTERNAL_API_URL
              |   (rede interna)
```

### DATABASE_URL (api, worker, frontend)

```
postgresql://${{db.POSTGRES_USER}}:${{db.POSTGRES_PASSWORD}}@${{db.RAILWAY_PRIVATE_DOMAIN}}:5432/${{db.POSTGRES_DB}}
```

Isso referencia as variaveis do servico `db` e resolve para algo como:

```
postgresql://postgres:SENHA@db.railway.internal:5432/whatsapp_langchain
```

### INTERNAL_API_URL (frontend)

```
http://${{api.RAILWAY_PRIVATE_DOMAIN}}:8000
```

Resolve para `http://api.railway.internal:8000`.

### Como setar via CLI

A CLI do Railway (`railway variables`) mostra os valores **resolvidos**, mas internamente o Railway armazena as referencias. Para setar via CLI, use aspas simples para evitar que o shell interprete `${{}}` como substituicao bash:

```bash
# DATABASE_URL com referencias ao servico db
railway variables --service api --set 'DATABASE_URL=postgresql://${{db.POSTGRES_USER}}:${{db.POSTGRES_PASSWORD}}@${{db.RAILWAY_PRIVATE_DOMAIN}}:5432/${{db.POSTGRES_DB}}'

# INTERNAL_API_URL com referencia ao servico api
railway variables --service frontend --set 'INTERNAL_API_URL=http://${{api.RAILWAY_PRIVATE_DOMAIN}}:8000'
```

> **Por que nao hardcodar?** Alem da visualizacao no dashboard, se o Railway alterar hostnames internos ou credenciais do banco, as referencias se atualizam automaticamente.

---

## Watch Paths

Watch paths controlam quais arquivos disparam redeploy de cada servico. Sem eles, qualquer push na branch causa redeploy de todos os servicos --- mesmo que a mudanca nao afete aquele servico.

Configurados via dashboard em **Service Settings > Source > Watch Paths**.

| Servico      | Watch Paths                                                                                      | Motivo                               |
|--------------|--------------------------------------------------------------------------------------------------|--------------------------------------|
| **API**      | `src/whatsapp_langchain/server/**`, `src/whatsapp_langchain/shared/**`, `pyproject.toml`, `uv.lock`, `Dockerfile.api` | Codigo da API + dependencias compartilhadas |
| **Worker**   | `src/whatsapp_langchain/worker/**`, `src/whatsapp_langchain/agents/**`, `src/whatsapp_langchain/shared/**`, `pyproject.toml`, `uv.lock`, `Dockerfile.worker` | Worker + agentes + dependencias compartilhadas |
| **Frontend** | `frontend/**`                                                                                    | Isolado do backend                   |
| **DB**       | `db/**`, `Dockerfile.db`                                                                         | Migracoes e imagem do Postgres       |

### Por que nao usar `src/**` para tudo?

O diretorio `src/whatsapp_langchain/` contem codigo de ambos os servicos:

```
src/whatsapp_langchain/
├── server/    # usado apenas pela API
├── worker/    # usado apenas pelo Worker
├── agents/    # usado apenas pelo Worker
└── shared/    # usado por API e Worker
```

Se ambos assistirem `src/**`, uma mudanca em `server/` causaria redeploy do Worker (desnecessario), e vice-versa. Watch paths granulares evitam redeploys inuteis.

### Por que `db/**` nao esta nos watch paths da API/Worker?

Migracoes SQL sao executadas manualmente (`python db/migrate.py`), nao durante o build dos servicos. Uma nova migracao nao deve triggerar redeploy automatico --- voce roda a migracao separadamente e so faz redeploy se o codigo mudou.

> **Nota:** o Railway nao suporta watch paths via `railway.toml` para multiplos servicos no mesmo repo. A configuracao e feita pelo dashboard, por servico.

---

## RAILWAY_DOCKERFILE_PATH

Todo servico que usa Dockerfile customizado **precisa** da variavel `RAILWAY_DOCKERFILE_PATH` apontando para o arquivo correto.

```bash
railway variables --service api --set 'RAILWAY_DOCKERFILE_PATH=Dockerfile.api'
railway variables --service worker --set 'RAILWAY_DOCKERFILE_PATH=Dockerfile.worker'
railway variables --service frontend --set 'RAILWAY_DOCKERFILE_PATH=Dockerfile.frontend'
railway variables --service db --set 'RAILWAY_DOCKERFILE_PATH=Dockerfile.db'
```

Sem essa variavel, o Railway usa o builder automatico (Railpack), que tenta detectar o framework. No caso do servico `db`, o Railpack detectava Python e falhava com "No start command was found" --- porque nao ha nenhum app Python para rodar, e sim um PostgreSQL.

---

## Migracoes

O projeto tem dois mecanismos de migracao que coexistem:

### 1. Automatica (startup da API)

Quando a API sobe, o `lifespan` executa `run_migrations()` antes de aceitar requisicoes. Esse mecanismo:

1. Cria a tabela `_migrations` se nao existir (controle de estado)
2. Le todos os arquivos `.sql` de `db/migrations/` em ordem alfabetica
3. Compara com os nomes ja registrados na tabela `_migrations`
4. Aplica os pendentes e registra cada um

```python
# src/whatsapp_langchain/server/main.py (lifespan)
pool = await get_pool()
await run_migrations(pool)          # migracoes SQL
await bootstrap_langgraph_schema()  # tabelas do checkpointer + store
```

Isso significa que **nao e necessario rodar migracoes manualmente** apos um deploy --- a API cuida disso automaticamente.

### 2. Manual (script standalone)

O script `db/migrate.py` faz a mesma coisa, mas de forma sincrona e independente. Util para:

- Rodar migracoes sem subir a API
- Debugging local
- Aplicar migracoes em ambientes sem a API rodando

```bash
# Local
python db/migrate.py

# No Railway (usando variaveis do servico api)
railway run --service api python db/migrate.py
```

### Arquivos de migracao

```
db/migrations/
├── 001_initial.sql                 # Schema da fila de mensagens
├── 002_media_processing_audit.sql  # Auditoria de midia
├── 003_auth_schema.sql             # Schema de auth
└── 004_better_auth_tables.sql      # Tabelas do Better Auth
```

Para adicionar uma nova migracao, crie um arquivo SQL com o proximo numero sequencial (ex: `005_nova_feature.sql`). A ordem alfabetica dos nomes determina a ordem de aplicacao.

### Idempotencia e replicas

Ambos os mecanismos usam a tabela `_migrations` com constraint `UNIQUE` no nome do arquivo. Se a migracao ja foi aplicada, ela e ignorada silenciosamente.

Com 2 replicas da API, ambas tentam rodar migracoes no startup. O `CREATE TABLE IF NOT EXISTS` e a constraint `UNIQUE` protegem contra duplicatas na maioria dos casos. Em cenarios de alta concorrencia, uma das replicas pode receber um erro de constraint e falhar o startup --- mas o retry do Railway resolve isso automaticamente.

### Bootstrap do LangGraph

Alem das migracoes SQL, o startup da API tambem executa `bootstrap_langgraph_schema()`, que inicializa:

- **Checkpointer** (`AsyncPostgresSaver`) --- tabelas para persistencia de conversas
- **Store vetorial** (`AsyncPostgresStore`) --- tabelas para memoria semantica (quando `MEMORY_ENABLED=true`)

Essas tabelas sao do LangGraph e nao aparecem em `db/migrations/`. O LangGraph gerencia o schema delas internamente via `.setup()`.

---

## Variaveis de Ambiente

Abaixo estao todas as variaveis necessarias, organizadas por servico.

### DB

| Variavel | Valor / Exemplo | Descricao |
|----------|----------------|-----------|
| `POSTGRES_USER` | `postgres` | Usuario do PostgreSQL |
| `POSTGRES_PASSWORD` | --- | Senha do PostgreSQL (gerar com `openssl rand -base64 32`) |
| `POSTGRES_DB` | `whatsapp_langchain` | Nome do banco de dados |
| `PGDATA` | `/var/lib/postgresql/data/pgdata` | Diretorio de dados (dentro do volume) |
| `RAILWAY_DOCKERFILE_PATH` | `Dockerfile.db` | Aponta para o Dockerfile do container Postgres |

### API

| Variavel | Valor / Exemplo | Descricao |
|----------|----------------|-----------|
| `DATABASE_URL` | `${{db.*}}` (reference) | Connection string do PostgreSQL via rede interna |
| `ENVIRONMENT` | `production` | Ambiente de execucao --- desabilita `/webhook/sync` em production |
| `LOG_LEVEL` | `info` | Nivel de log (debug, info, warning, error) |
| `LOG_JSON` | `true` | Logs em formato JSON estruturado (melhor para producao) |
| `PORT` | `8000` | Porta do FastAPI |
| `VALIDATE_TWILIO_SIGNATURE` | `true` | Validar assinatura dos webhooks do Twilio |
| `TWILIO_AUTH_TOKEN` | --- | Token de autenticacao do Twilio (necessario para validacao de assinatura) |
| `TWILIO_WEBHOOK_URL` | `https://api-*.up.railway.app` | URL base publica da API (sem path) |
| `RATE_LIMIT_PER_HOUR` | `30` | Maximo de mensagens por telefone por hora |
| `MESSAGE_BUFFER_SECONDS` | `2.0` | Tempo de espera para agrupar mensagens consecutivas |
| `INTERNAL_SERVICE_TOKEN` | --- | Token para proteger rotas `/api/*` **(shared com Frontend)** |
| `OPENROUTER_API_KEY` | --- | Chave do OpenRouter (necessaria para bootstrap do LangGraph store — embeddings) |
| `OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` | URL base do OpenRouter (idem) |
| `MEMORY_ENABLED` | `true` | Habilitar memoria semantica — controla se o store vetorial e criado no startup |
| `EMBEDDING_MODEL` | `openai/text-embedding-3-small` | Modelo de embeddings usado no bootstrap do store |
| `EMBEDDING_DIMS` | `1536` | Dimensoes do vetor de embeddings |
| `RAILWAY_DOCKERFILE_PATH` | `Dockerfile.api` | Aponta para o Dockerfile da API |

> **Por que a API precisa de variaveis de embeddings?** No startup, a API chama `bootstrap_langgraph_schema()` que inicializa as tabelas do checkpointer e do store vetorial. O store precisa da configuracao de embeddings para criar os indices. Sem essas variaveis, o startup falha quando `MEMORY_ENABLED=true`.

### Worker

| Variavel | Valor / Exemplo | Descricao |
|----------|----------------|-----------|
| `DATABASE_URL` | `${{db.*}}` (reference) | Connection string do PostgreSQL via rede interna |
| `ENVIRONMENT` | `production` | Ambiente de execucao |
| `LOG_LEVEL` | `info` | Nivel de log |
| `LOG_JSON` | `true` | Logs em formato JSON estruturado |
| `OPENROUTER_API_KEY` | --- | Chave de API do OpenRouter |
| `OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` | URL base do OpenRouter |
| `OPENROUTER_MODEL` | --- | Modelo principal para o agente |
| `OPENROUTER_MIDIA_MODEL` | --- | Modelo para processamento de midia |
| `TWILIO_ACCOUNT_SID` | --- | Account SID do Twilio |
| `TWILIO_API_KEY_SID` | --- | API Key SID para envio de mensagens e download de midia |
| `TWILIO_API_KEY_SECRET` | --- | API Key Secret para envio de mensagens e download de midia |
| `TWILIO_FROM_NUMBER` | `whatsapp:+14155238886` | Numero do WhatsApp remetente |
| `TWILIO_OUTBOUND_MODE` | `real` | Em producao, manter envio Twilio em modo real |
| `POLL_INTERVAL_SECONDS` | `1.0` | Intervalo de polling na fila |
| `LEASE_SECONDS` | `60` | Tempo maximo de processamento antes de retry |
| `MAX_ATTEMPTS` | `3` | Numero maximo de tentativas por mensagem |
| `MEDIA_IMAGE_ENABLED` | `true` | Habilitar processamento de imagens |
| `MEDIA_AUDIO_ENABLED` | `true` | Habilitar processamento de audio |
| `LLM_RATE_LIMIT_REQUESTS_PER_SECOND` | `0.5` | Limite de requisicoes por segundo ao LLM |
| `LLM_RATE_LIMIT_MAX_BURST` | `10` | Maximo de requisicoes em rajada ao LLM |
| `CONTEXT_STRATEGY` | `summarize` | Estrategia de contexto do middleware |
| `TRIM_KEEP_TURNS` | `2` | Turnos a manter ao usar trim |
| `SUMMARIZE_TRIGGER_TOKENS` | `4000` | Tokens que disparam a sumarizacao |
| `SUMMARIZE_KEEP_MESSAGES` | `10` | Mensagens a manter apos sumarizar |
| `SUMMARIZE_MODEL` | --- | Modelo usado para sumarizacao |
| `MEMORY_ENABLED` | `true` | Habilitar memoria semantica |
| `MEMORY_SEARCH_LIMIT` | `5` | Maximo de memorias retornadas por busca |
| `EMBEDDING_MODEL` | `openai/text-embedding-3-small` | Modelo de embeddings |
| `EMBEDDING_DIMS` | `1536` | Dimensoes do vetor de embeddings |
| `RAILWAY_DOCKERFILE_PATH` | `Dockerfile.worker` | Aponta para o Dockerfile do Worker |

> O `TWILIO_AUTH_TOKEN` fica somente no servico `api`, onde a assinatura
> inbound do webhook e validada. O worker usa `TWILIO_ACCOUNT_SID`,
> `TWILIO_API_KEY_SID`, `TWILIO_API_KEY_SECRET` e `TWILIO_FROM_NUMBER`.

### Frontend

| Variavel | Valor / Exemplo | Descricao |
|----------|----------------|-----------|
| `DATABASE_URL` | `${{db.*}}` (reference) | Connection string do PostgreSQL (para Better Auth) |
| `INTERNAL_API_URL` | `http://${{api.RAILWAY_PRIVATE_DOMAIN}}:8000` | URL interna da API (rede privada Railway) |
| `INTERNAL_SERVICE_TOKEN` | --- | Token para autenticar nas rotas `/api/*` **(shared com API)** |
| `BETTER_AUTH_SECRET` | --- | Secret para sessoes do Better Auth (gerar com `openssl rand -base64 32`) |
| `BETTER_AUTH_URL` | `https://frontend-*.up.railway.app` | URL publica do Frontend (usada pelo Better Auth para callbacks) |
| `RAILWAY_DOCKERFILE_PATH` | `Dockerfile.frontend` | Aponta para o Dockerfile do Frontend |

---

## Checklist de Deploy

1. Criar o projeto no Railway
2. Criar os 4 servicos (db, api, worker, frontend) apontando para o mesmo repo
3. Setar `RAILWAY_DOCKERFILE_PATH` em cada servico
4. Configurar variaveis do DB (user, password, database, pgdata)
5. Configurar `DATABASE_URL` com reference variables nos 3 servicos
6. Configurar variaveis especificas de cada servico (tabelas acima)
7. Gerar dominio publico para API e Frontend
8. Atualizar `TWILIO_WEBHOOK_URL` com o dominio real da API
9. Atualizar `BETTER_AUTH_URL` com o dominio real do Frontend
10. Configurar watch paths por servico (ver tabela acima)
11. Configurar 2 replicas na API
12. Adicionar volume ao servico DB (`/var/lib/postgresql/data`)
13. Verificar migracoes (rodam automaticamente no startup da API --- checar logs por `migration_applying`)
14. Testar health check: `GET https://api-*.up.railway.app/health`
15. Testar login no painel e navegacao completa
16. Testar fluxo completo: mensagem WhatsApp -> fila -> worker -> resposta
