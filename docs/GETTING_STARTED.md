# Primeiros Passos

Este guia tem duas trilhas:
- **Trilha A (agentes):** LangGraph Studio para desenvolver comportamento
- **Trilha B (sistema):** API + Worker + DB para aprender arquitetura operacional

## Pré-requisitos

- Python 3.11+
- `uv` (gerenciador de pacotes)
- Docker + Docker Compose
- conta OpenRouter (API key)

## 1. Setup local

```bash
git clone <repo-url>
cd whatsapp-langchain
make setup
cp .env.example .env
```

Edite `.env` e configure no mínimo:

```bash
OPENROUTER_API_KEY=sk-or-v1-...
```

## 2. Trilha A: desenvolvimento de agente no Studio

```bash
make dev
# abre o LangGraph Studio
```

O grafo padrão é `rhawk_assistant`, registrado em `langgraph.json`.

Arquivos centrais do agente:
- `src/whatsapp_langchain/agents/catalog/rhawk_assistant/agent.py`
- `src/whatsapp_langchain/agents/catalog/rhawk_assistant/prompts.py`
- `src/whatsapp_langchain/agents/catalog/rhawk_assistant/graph.py`

## 3. Trilha B: stack completo da Fase 2

### Subir serviços

```bash
make up
```

Isso sobe:
- `db` (PostgreSQL + pgvector)
- `api` (FastAPI)
- `worker` (consumidor da fila)

### Validar saúde

```bash
curl http://localhost:8000/health
```

### Ver logs

```bash
make logs
```

## 4. Testes de fluxo

### 4.1 Endpoint síncrono (didático)

```bash
curl -X POST "http://localhost:8000/webhook/sync?agent=rhawk_assistant" \
  -H "Content-Type: application/json" \
  -d '{"phone":"+5511999999999","message":"Me explique debounce"}'
```

Use para debugging rápido sem fila.

### 4.2 Webhook assíncrono (arquitetura real)

```bash
curl -X POST "http://localhost:8000/webhook/twilio?agent=rhawk_assistant" \
  -d "MessageSid=SM123" \
  -d "From=whatsapp:+5511999999999" \
  -d "To=whatsapp:+14155238886" \
  -d "Body=Mensagem de teste" \
  -d "NumMedia=0"
```

Depois consulte:

```bash
curl http://localhost:8000/api/metrics
curl http://localhost:8000/api/chats
curl http://localhost:8000/api/chats/+5511999999999
```

## 5. Configurações importantes (.env)

### Contexto

```bash
CONTEXT_STRATEGY=trim            # trim | summarize | none
TRIM_KEEP_TURNS=5
SUMMARIZE_TRIGGER_TOKENS=4000
SUMMARIZE_KEEP_MESSAGES=10
SUMMARIZE_MODEL=x-ai/grok-4.1-fast
```

### Memória semântica

```bash
MEMORY_ENABLED=true
EMBEDDING_MODEL=openai/text-embedding-3-small
EMBEDDING_DIMS=1536
MEMORY_SEARCH_LIMIT=5
```

### Operação da fila

```bash
MESSAGE_BUFFER_SECONDS=2.0
POLL_INTERVAL_SECONDS=1.0
LEASE_SECONDS=60
MAX_ATTEMPTS=3
RATE_LIMIT_PER_HOUR=30
```

## 6. Qualidade e testes

```bash
make test
make check
```

Comandos úteis:

```bash
make test-x
make test-v
make lint
make format
make typecheck
```

## 7. Troubleshooting

### `OPENROUTER_API_KEY` ausente

```bash
grep OPENROUTER_API_KEY .env
```

### API sem conectar no banco

- confira `DATABASE_URL` no `.env`
- se estiver em Docker, lembre que API/Worker usam host `db` via `docker-compose.yml`

### Worker não processa mensagens

- verifique se o serviço `worker` está rodando (`make logs`)
- confira se há mensagens `queued` e `process_after <= now()`
- valide se o agente passado em `agent=` existe no catálogo

### Mídia não transcreve/processa

- confirme `MEDIA_IMAGE_ENABLED` / `MEDIA_AUDIO_ENABLED`
- confira se há chave OpenRouter válida
- verifique logs de `worker.media`

## Próximos passos

- [Arquitetura](ARCHITECTURE.md)
- [Criando Agentes](ADDING_AGENTS.md)
- [Deploy](DEPLOY.md)
