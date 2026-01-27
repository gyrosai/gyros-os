# Arquitetura

## Visão Geral

O sistema é composto por 4 serviços isolados que se comunicam via PostgreSQL:

![Arquitetura](architecture.png)

```
┌─────────────────────────────────────────────────────────────────┐
│                        Railway (Produção)                       │
├───────────────┬───────────────┬───────────────┬─────────────────┤
│      API      │    Worker     │   Frontend    │   PostgreSQL    │
│   (FastAPI)   │   (Python)    │   (Next.js)   │   (Database)    │
└───────────────┴───────────────┴───────────────┴─────────────────┘
```

Cada serviço tem uma responsabilidade clara:

| Serviço | Responsabilidade | Porta |
|---------|-----------------|-------|
| **API** | Recebe webhooks, valida, enfileira | 8000 |
| **Worker** | Consome fila, executa agentes, envia resposta | — |
| **Frontend** | Admin Panel (métricas, conversas) | 3000 |
| **PostgreSQL** | Fila de mensagens + memória dos agentes | 5432 |

## Fluxo de uma Mensagem

```
1. Usuário envia mensagem no WhatsApp

2. Twilio recebe e faz POST no webhook da API
   POST /webhook/twilio?agent=assistant

3. API valida, aplica rate limit, e enfileira no PostgreSQL
   INSERT INTO message_queue (phone, agent_id, body, process_after)
   Responde 200 OK em < 100ms

4. Worker faz polling na fila
   SELECT ... FROM message_queue
   WHERE status = 'queued' AND process_after <= NOW()
   FOR UPDATE SKIP LOCKED

5. Worker processa:
   - Download de mídia (se imagem/áudio)
   - Monta mensagem para o agente
   - Invoca o grafo LangGraph
   - Checkpointer salva o histórico

6. Worker envia resposta via Twilio
   - Typing indicator (opcional)
   - Mensagem de texto

7. Marca como done na fila
   UPDATE message_queue SET status = 'done'
```

## Por que PostgreSQL como Fila?

Em vez de Redis ou RabbitMQ, usamos o próprio PostgreSQL como fila:

- **Simplicidade** — Um banco, menos infraestrutura
- **Confiabilidade** — Transações ACID, mensagens nunca se perdem
- **Suficiente** — Aguenta < 1000 msgs/minuto (muito para a maioria dos casos)
- **`FOR UPDATE SKIP LOCKED`** — Permite múltiplos workers sem conflito

Quando escalar? Se a fila crescer consistentemente, considere Redis ou RabbitMQ. Mas para a maioria dos projetos WhatsApp, PostgreSQL é mais que suficiente.

## Database

### Tabelas

O sistema cria as tabelas automaticamente no boot (padrão `ensure_*_table()`):

#### message_queue

Fila de mensagens + histórico de processamento.

```sql
CREATE TABLE IF NOT EXISTS message_queue (
    id SERIAL PRIMARY KEY,
    phone_number TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    body TEXT NOT NULL,
    media_type TEXT,              -- null, 'image', 'audio'
    media_url TEXT,
    status TEXT DEFAULT 'queued', -- queued, processing, done, failed
    process_after TIMESTAMPTZ,   -- debounce: só processa depois desse horário
    attempts INT DEFAULT 0,
    max_attempts INT DEFAULT 3,
    leased_until TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

#### conversations

Conversas ativas (para o Admin Panel).

```sql
CREATE TABLE IF NOT EXISTS conversations (
    id SERIAL PRIMARY KEY,
    phone_number TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    message_count INT DEFAULT 0,
    last_message_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(phone_number, agent_id)
);
```

#### checkpoints (LangGraph)

Criada automaticamente pelo LangGraph. Armazena o histórico de mensagens de cada conversa.

### Por que `ensure_*_table()` em vez de migrations?

Em projetos com equipes grandes e schemas complexos, ferramentas como Alembic são essenciais. Mas para um template educacional:

- **Simplicidade** — Tabelas criadas automaticamente no boot
- **Sem dependências extras** — Não precisa de Alembic, migration runner, etc
- **Idempotente** — `CREATE TABLE IF NOT EXISTS` é seguro para rodar múltiplas vezes

Quando migrar para Alembic? Quando o schema ficar complexo (10+ tabelas) ou quando múltiplos devs precisarem coordenar mudanças no banco.

## Debounce de Mensagens

Quando alguém manda 3 mensagens seguidas no WhatsApp:

```
"Oi"           → enqueue, process_after = agora + 2s
"tudo bem?"    → concatena body, reseta timer
"me ajuda aí"  → concatena body, reseta timer
                 → Worker processa: "Oi\ntudo bem?\nme ajuda aí"
```

O campo `process_after` implementa um buffer configurável (`MESSAGE_BUFFER_SECONDS`, default: 2.0). Mensagens do mesmo phone+agent são concatenadas enquanto novas mensagens chegam dentro da janela.

## Rate Limiting

Duas camadas de proteção:

| Camada | Onde | Protege contra | Comportamento |
|--------|------|---------------|--------------|
| **API** | Por phone_number | Abuso/spam | Rejeita (429) |
| **LLM** | InMemoryRateLimiter | Custo excessivo | Aguarda (backpressure) |

- **API**: `RATE_LIMIT_PER_HOUR=30` — limita mensagens por telefone
- **LLM**: `LLM_RATE_LIMIT_REQUESTS_PER_SECOND=0.5` — limita chamadas ao modelo

## Mídia

Suporte configurável a imagem e áudio:

| Tipo | Processamento | Env var |
|------|--------------|---------|
| **Imagem** | Download → base64 → HumanMessage multimodal | `MEDIA_IMAGE_ENABLED` |
| **Áudio** | Download → Whisper (transcrição) → texto | `MEDIA_AUDIO_ENABLED` |
| **Vídeo** | Não suportado (mensagem informativa) | — |
| **Output** | Sempre texto | — |

## Memória dos Agentes

O sistema oferece dois tipos de memória:

### Memória de Conversa (Checkpointer)

Cada conversa tem um `thread_id` no formato `{phone}:{agent_id}`. O checkpointer do LangGraph salva todo o histórico no PostgreSQL.

Para evitar que o contexto cresça infinitamente, dois middlewares estão disponíveis:

| Middleware | Como funciona | Custo |
|-----------|--------------|-------|
| **Trim** | Mantém apenas as últimas N mensagens | Zero (descarta) |
| **Summarize** | Sumariza mensagens antigas com LLM | 1 chamada extra |

### Memória Semântica (Store) — Opcional

Além do histórico de conversa, o agente pode lembrar **fatos sobre o usuário** entre conversas diferentes. Exemplos: "prefere linguagem formal", "é alérgico a amendoim", "já comprou produto X".

Usa o `Store` do LangGraph com **pgvector** para busca por similaridade:

- **Escopo**: Cross-thread (todas as conversas de um usuário)
- **Busca**: Semântica (por significado, não por palavras exatas)
- **Storage**: Mesmo PostgreSQL (extensão pgvector)
- **Custo**: ~$0.02/1M tokens de embedding (negligível)
- **Habilitável via**: `SEMANTIC_MEMORY_ENABLED=true`

Quando habilitada, o docker-compose usa `pgvector/pgvector:pg16` em vez de `postgres:16`.

Escolha por agente. Veja [Criando Agentes](ADDING_AGENTS.md).

## Stack

| Camada | Tecnologia |
|--------|-----------|
| Agentes | LangGraph 1.0+ |
| LLM | OpenRouter (multi-model) |
| API | FastAPI |
| Database | PostgreSQL 16+ (pgvector para memória semântica) |
| Frontend | Next.js + shadcn/ui + Tailwind |
| WhatsApp | Twilio API |
| Logs | structlog (JSON prod, pretty dev) |
| Deploy | Railway (4 serviços) |
| Stress Test | Locust |

## Variáveis de Ambiente

Toda a configuração é feita via variáveis de ambiente. Veja `.env.example` para a lista completa.

| Variável | Default | Descrição |
|----------|---------|-----------|
| `DATABASE_URL` | — | Conexão PostgreSQL |
| `OPENROUTER_API_KEY` | — | Chave da API OpenRouter |
| `OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` | Base URL do LLM |
| `VALIDATE_TWILIO_SIGNATURE` | `false` | Validar webhook (true em prod) |
| `RATE_LIMIT_PER_HOUR` | `30` | Msgs por telefone por hora |
| `MESSAGE_BUFFER_SECONDS` | `2.0` | Janela de debounce |
| `MEDIA_IMAGE_ENABLED` | `true` | Suporte a imagem |
| `MEDIA_AUDIO_ENABLED` | `true` | Suporte a áudio |
| `SEMANTIC_MEMORY_ENABLED` | `false` | Memória semântica (pgvector) |
| `EMBEDDING_MODEL` | `openai:text-embedding-3-small` | Modelo de embedding |
| `POLL_INTERVAL_SECONDS` | `1.0` | Intervalo de polling do Worker |
| `ADMIN_USER` | `admin` | Usuário do Admin Panel |
| `ADMIN_PASSWORD` | — | Senha do Admin Panel |

## Evoluções Futuras

O sistema foi desenhado para crescer. Algumas evoluções possíveis:

- **LISTEN/NOTIFY** — Substituir polling por notificações do PostgreSQL
- **Redis/RabbitMQ** — Fila dedicada para alto volume
- **NextAuth.js** — Autenticação OAuth no Admin Panel
- **Sentry** — Monitoramento de erros em produção
- **Múltiplos Workers** — Escalar horizontalmente (o lock garante não-duplicação)
- **Cache de agentes** — Evitar recarregar grafos a cada mensagem
- **Prometheus/Grafana** — Métricas detalhadas
