# Deploy no Railway

Guia completo para deploy do whatsapp-langchain no Railway, cobrindo a topologia de servicos e todas as variaveis de ambiente necessarias.

## Topologia de Servicos

O projeto usa 4 servicos no Railway:

| Servico  | Dockerfile            | Porta | Visibilidade | Dominio                       |
|----------|-----------------------|-------|--------------|-------------------------------|
| API      | `Dockerfile.api`      | 8000  | Publico      | `api-*.up.railway.app`        |
| Worker   | `Dockerfile.worker`   | ---   | Privado      | ---                           |
| Frontend | `frontend/Dockerfile` | 3000  | Publico      | `frontend-*.up.railway.app`   |
| DB       | PostgreSQL plugin     | 5432  | Privado      | ---                           |

### API

Servico publico que recebe webhooks do Twilio e expoe o health check.

- **Rotas publicas:** `/webhook/twilio` e `/health`
- **Rotas protegidas:** `/api/*` requerem o header `INTERNAL_SERVICE_TOKEN`
- O Frontend se comunica com a API via rede interna do Railway (`http://api.railway.internal:8000`), nunca pelo dominio publico

### Worker

Servico privado que consome a fila de mensagens do PostgreSQL.

- Sem porta exposta --- nao recebe requisicoes HTTP
- Faz polling na tabela de fila do banco para processar mensagens pendentes
- Executa os agentes LangGraph e envia respostas via Twilio

### Frontend

Admin Panel em Next.js, publico para acesso dos administradores.

- Consome a API internamente via `http://api.railway.internal:8000`
- O `INTERNAL_SERVICE_TOKEN` garante que apenas o Frontend consegue chamar as rotas `/api/*`

### DB (PostgreSQL)

Plugin nativo do Railway.

- Acessivel apenas pela rede interna (privado)
- A connection string e injetada automaticamente via `${{Postgres.DATABASE_URL}}`
- Usado pela API (fila de mensagens), Worker (consumo da fila) e Frontend (auth/admin)

### Deploy Automatico

Todos os servicos fazem auto-deploy quando ha push na branch `main`.

---

## Variaveis de Ambiente

Abaixo estao todas as variaveis necessarias, organizadas por servico. Variaveis marcadas com **(shared)** devem usar Railway Shared Variables para manter o mesmo valor entre servicos.

### API

| Variavel | Valor / Exemplo | Descricao |
|----------|----------------|-----------|
| `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` | Connection string do PostgreSQL (referencia ao plugin) |
| `ENVIRONMENT` | `production` | Ambiente de execucao — desabilita `/webhook/sync` em production |
| `LOG_LEVEL` | `info` | Nivel de log (debug, info, warning, error) |
| `LOG_JSON` | `true` | Logs em formato JSON estruturado (melhor para producao) |
| `VALIDATE_TWILIO_SIGNATURE` | `true` | Validar assinatura dos webhooks do Twilio |
| `TWILIO_AUTH_TOKEN` | --- | Token de autenticacao do Twilio **(shared)** |
| `TWILIO_WEBHOOK_URL` | `https://api-*.up.railway.app` | URL base publica da API (sem path — o codigo concatena o path automaticamente) |
| `TWILIO_ACCOUNT_SID` | --- | Account SID do Twilio **(shared)** |
| `TWILIO_API_KEY_SID` | --- | API Key SID para envio de mensagens **(shared)** |
| `TWILIO_API_KEY_SECRET` | --- | API Key Secret para envio de mensagens **(shared)** |
| `TWILIO_FROM_NUMBER` | `whatsapp:+14155238886` | Numero do WhatsApp remetente **(shared)** |
| `RATE_LIMIT_PER_HOUR` | `30` | Maximo de mensagens por telefone por hora |
| `MESSAGE_BUFFER_SECONDS` | `2.0` | Tempo de espera para agrupar mensagens consecutivas |
| `INTERNAL_SERVICE_TOKEN` | --- | Token para proteger rotas `/api/*` **(shared com Frontend)** |
| `OPENROUTER_API_KEY` | --- | Chave de API do OpenRouter **(shared)** |
| `OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` | URL base do OpenRouter **(shared)** |
| `OPENROUTER_MODEL` | --- | Modelo principal para o agente **(shared)** |
| `OPENROUTER_MIDIA_MODEL` | --- | Modelo para processamento de midia **(shared)** |

### Worker

| Variavel | Valor / Exemplo | Descricao |
|----------|----------------|-----------|
| `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` | Connection string do PostgreSQL (referencia ao plugin) |
| `OPENROUTER_API_KEY` | --- | Chave de API do OpenRouter **(shared)** |
| `OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` | URL base do OpenRouter **(shared)** |
| `OPENROUTER_MODEL` | --- | Modelo principal para o agente **(shared)** |
| `OPENROUTER_MIDIA_MODEL` | --- | Modelo para processamento de midia **(shared)** |
| `TWILIO_ACCOUNT_SID` | --- | Account SID do Twilio **(shared)** |
| `TWILIO_API_KEY_SID` | --- | API Key SID para envio de mensagens **(shared)** |
| `TWILIO_API_KEY_SECRET` | --- | API Key Secret para envio de mensagens **(shared)** |
| `TWILIO_FROM_NUMBER` | `whatsapp:+14155238886` | Numero do WhatsApp remetente **(shared)** |
| `TWILIO_OUTBOUND_MODE` | `real` | Em producao, o worker deve usar Twilio real |
| `POLL_INTERVAL_SECONDS` | `1.0` | Intervalo de polling na fila (em segundos) |
| `LEASE_SECONDS` | `60` | Tempo maximo que uma mensagem fica em processamento antes de ser reprocessada |
| `MAX_ATTEMPTS` | `3` | Numero maximo de tentativas de processamento por mensagem |
| `MEDIA_IMAGE_ENABLED` | `true` | Habilitar processamento de imagens |
| `MEDIA_AUDIO_ENABLED` | `true` | Habilitar processamento de audio |
| `LLM_RATE_LIMIT_REQUESTS_PER_SECOND` | `0.5` | Limite de requisicoes por segundo ao LLM |
| `LLM_RATE_LIMIT_MAX_BURST` | `10` | Maximo de requisicoes em rajada ao LLM |
| `CONTEXT_STRATEGY` | --- | Estrategia de contexto do middleware (trim, summarize, etc.) |
| `TRIM_KEEP_TURNS` | --- | Numero de turnos a manter ao usar trim |
| `SUMMARIZE_TRIGGER_TOKENS` | --- | Quantidade de tokens que dispara a sumarizacao |
| `MEMORY_ENABLED` | `true` | Habilitar memoria semantica |
| `EMBEDDING_MODEL` | --- | Modelo de embeddings para memoria semantica |
| `EMBEDDING_DIMS` | --- | Dimensoes do vetor de embeddings |

### Frontend

| Variavel | Valor / Exemplo | Descricao |
|----------|----------------|-----------|
| `INTERNAL_API_URL` | `http://api.railway.internal:8000` | URL interna da API (rede privada Railway) |
| `INTERNAL_SERVICE_TOKEN` | --- | Token para autenticar nas rotas `/api/*` **(shared com API)** |
| `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` | Connection string do PostgreSQL (para Better Auth) |
| `BETTER_AUTH_SECRET` | --- | Secret para sessoes do Better Auth (gerar com `openssl rand -base64 32`) |
| `BETTER_AUTH_URL` | `https://frontend-*.up.railway.app` | URL publica do Frontend (usada pelo Better Auth para callbacks) |

---

## Railway Shared Variables

Para evitar duplicacao e garantir consistencia, use **Shared Variables** do Railway para segredos compartilhados entre servicos:

- `TWILIO_AUTH_TOKEN`
- `TWILIO_ACCOUNT_SID`
- `TWILIO_API_KEY_SID`
- `TWILIO_API_KEY_SECRET`
- `TWILIO_FROM_NUMBER`
- `OPENROUTER_API_KEY`
- `OPENROUTER_BASE_URL`
- `OPENROUTER_MODEL`
- `OPENROUTER_MIDIA_MODEL`
- `INTERNAL_SERVICE_TOKEN` (compartilhado entre API e Frontend)

Dessa forma, ao rotacionar um segredo, basta atualizar em um unico lugar.

---

## Checklist de Deploy

1. Criar o projeto no Railway com os 4 servicos
2. Adicionar o plugin PostgreSQL
3. Configurar as Shared Variables com os segredos
4. Configurar as variaveis especificas de cada servico (tabelas acima)
5. Gerar dominio publico para API e Frontend
6. Atualizar `TWILIO_WEBHOOK_URL` com o dominio real da API
7. Atualizar `BETTER_AUTH_URL` com o dominio real do Frontend
8. Verificar que API e Worker conseguem acessar o banco (`DATABASE_URL`)
9. Verificar que Frontend consegue chamar a API via rede interna
10. Testar o health check: `GET https://api-*.up.railway.app/health`
