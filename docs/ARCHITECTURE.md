# Arquitetura

> **Fase atual:** Apenas o pacote de agentes está implementado. Este documento descreve a arquitetura completa do projeto para que você entenda o destino. Seções marcadas com 🔜 serão implementadas nas próximas fases.

## Visão Geral

O sistema será composto por 4 serviços isolados que se comunicam via PostgreSQL:

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

| Serviço | Responsabilidade | Status |
|---------|-----------------|--------|
| **Agentes** | Definição de comportamento, middleware de contexto | Implementado |
| **API** | Recebe webhooks, valida, enfileira | 🔜 Fase 2 |
| **Worker** | Consome fila, executa agentes, envia resposta | 🔜 Fase 2 |
| **PostgreSQL** | Fila de mensagens + memória dos agentes | 🔜 Fase 2 |
| **Twilio** | Integração WhatsApp, mídia, rate limiting | 🔜 Fase 3 |
| **Frontend** | Admin Panel (métricas, conversas) | 🔜 Fase 4 |

> **Fase 3** não cria serviços novos — adiciona funcionalidades à API e ao Worker: integração com Twilio (receber/enviar mensagens WhatsApp), processamento de mídia (imagem e áudio), e rate limiting por telefone.

## Fluxo de uma Mensagem

```
1. Usuário envia mensagem no WhatsApp

2. Twilio recebe e faz POST no webhook da API
   POST /webhook/twilio?agent=rhawk_assistant

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

---

## Agentes (implementado)

Esta é a única parte implementada na fase atual. O pacote de agentes define o comportamento dos bots.

### Estrutura de um Agente

```
agents/catalog/rhawk_assistant/
├── __init__.py     # Exports: build_graph, SYSTEM_PROMPT
├── agent.py        # Factory build_graph() — configura modelo e middleware
├── graph.py        # Exporta variável graph para langgraph dev
└── prompts.py      # System prompt do agente
```

**`agent.py`** é o coração do agente. Usa `create_agent()` do LangChain:

```python
from langchain.agents import create_agent

def build_graph(checkpointer=None):
    model = ChatOpenAI(model=DEFAULT_MODEL, ...)
    middleware = get_context_middleware()  # Lê CONTEXT_STRATEGY do .env

    return create_agent(
        model=model,
        tools=[],
        system_prompt=SYSTEM_PROMPT,
        middleware=middleware,
        checkpointer=checkpointer,
    )
```

**`graph.py`** existe apenas para o LangGraph Studio. Exporta uma variável `graph` (não uma função):

```python
from whatsapp_langchain.agents.catalog.rhawk_assistant.agent import build_graph

# Variável — langgraph dev espera isso
graph = build_graph()
```

No `langgraph.json`, a referência é `graph.py:graph` (variável), não `graph.py:build_graph` (função). Isso porque o LangGraph Studio precisa de um grafo já compilado.

### Middleware de Contexto

Os middlewares gerenciam o tamanho do histórico de conversa. Sem eles, o contexto cresce infinitamente e ultrapassa o limite de tokens do modelo.

#### Padrão `@before_model`

O trim usa o decorator `@before_model` do LangChain. Esse padrão executa código **antes** de cada chamada ao modelo:

```python
@before_model
def trim_messages(state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
    messages = state["messages"]

    # Encontra onde cada turno começa (cada HumanMessage)
    boundaries = [i for i, m in enumerate(messages) if isinstance(m, HumanMessage)]

    if len(boundaries) <= keep_turns:
        return None  # Não precisa fazer trim

    # Remove tudo antes dos últimos N turnos
    cutoff = boundaries[-keep_turns]
    messages_to_remove = messages[:cutoff]

    return {"messages": [RemoveMessage(id=m.id) for m in messages_to_remove if m.id]}
```

Retornar `None` significa "não alterar o estado". Retornar RemoveMessages remove as mensagens via reducer.

#### `SummarizationMiddleware`

O summarize usa `SummarizationMiddleware` do LangChain, uma classe pronta que:
1. Conta tokens do histórico
2. Quando excede `trigger_tokens`, chama um modelo barato para sumarizar
3. Substitui mensagens antigas por um resumo
4. Mantém as `keep_messages` mais recentes intactas

```python
SummarizationMiddleware(
    model=cheap_model,
    trigger=("tokens", 4000),
    keep=("messages", 10),
    summary_prompt="Resuma a conversa...",
)
```

#### Factory `get_context_middleware()`

Em vez de cada agente configurar o middleware manualmente, a factory lê do `.env`:

```python
from whatsapp_langchain.agents.middleware import get_context_middleware

middlewares = get_context_middleware()
# Retorna [create_trim_middleware(...)] se CONTEXT_STRATEGY=trim
# Retorna [create_summarize_middleware(...)] se CONTEXT_STRATEGY=summarize
# Retorna [] se CONTEXT_STRATEGY=none
```

Aceita overrides para testes:

```python
middlewares = get_context_middleware(strategy="trim", trim_keep_turns=3)
```

### Comparação: Trim vs Summarize

| | Trim | Summarize |
|--|------|-----------|
| **Custo** | Zero | 1 chamada LLM extra |
| **Contexto** | Últimos N turnos (perde o resto) | Resumo + recentes |
| **Latência** | Nenhuma | +1-2s por sumarização |
| **Melhor para** | FAQ, conversas curtas | Suporte, vendas, conversas longas |

---

## 🔜 Database (Fase 2)

### Tabelas

O sistema criará as tabelas automaticamente no boot (padrão `ensure_*_table()`):

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

## 🔜 Debounce de Mensagens (Fase 2)

Quando alguém manda 3 mensagens seguidas no WhatsApp:

```
"Oi"           → enqueue, process_after = agora + 2s
"tudo bem?"    → concatena body, reseta timer
"me ajuda aí"  → concatena body, reseta timer
                 → Worker processa: "Oi\ntudo bem?\nme ajuda aí"
```

O campo `process_after` implementa um buffer configurável. Mensagens do mesmo phone+agent são concatenadas enquanto novas mensagens chegam dentro da janela.

## 🔜 Rate Limiting (Fase 3)

Duas camadas de proteção:

| Camada | Onde | Protege contra | Comportamento |
|--------|------|---------------|--------------|
| **API** | Por phone_number | Abuso/spam | Rejeita (429) |
| **LLM** | InMemoryRateLimiter | Custo excessivo | Aguarda (backpressure) |

## 🔜 Mídia (Fase 3)

Suporte configurável a imagem e áudio:

| Tipo | Processamento |
|------|--------------|
| **Imagem** | Download → base64 → HumanMessage multimodal |
| **Áudio** | Download → Whisper (transcrição) → texto |
| **Vídeo** | Não suportado (mensagem informativa) |

## Memória dos Agentes

### Memória de Conversa (Checkpointer)

Cada conversa tem um `thread_id` no formato `{phone}:{agent_id}`. O checkpointer do LangGraph salva todo o histórico no PostgreSQL (em produção) ou in-memory (no LangGraph Studio).

Para evitar que o contexto cresça infinitamente, dois middlewares estão disponíveis:

| Middleware | Como funciona | Custo | Status |
|-----------|--------------|-------|--------|
| **Trim** | Mantém apenas os últimos N turnos | Zero (descarta) | Implementado |
| **Summarize** | Sumariza mensagens antigas com LLM | 1 chamada extra | Implementado |

### Memória Semântica (Store) — Opcional

Além do histórico de conversa, o agente poderá lembrar **fatos sobre o usuário** entre conversas diferentes. Exemplos: "prefere linguagem formal", "é alérgico a amendoim", "já comprou produto X".

Usará o `Store` do LangGraph com **pgvector** para busca por similaridade:

- **Escopo**: Cross-thread (todas as conversas de um usuário)
- **Busca**: Semântica (por significado, não por palavras exatas)
- **Storage**: Mesmo PostgreSQL (extensão pgvector)

Escolha por agente. Veja [Criando Agentes](ADDING_AGENTS.md).

## Stack

| Camada | Tecnologia | Status |
|--------|-----------|--------|
| Agentes | LangGraph + LangChain 1.0 | Implementado |
| LLM | OpenRouter (multi-model) | Implementado |
| API | FastAPI | 🔜 Fase 2 |
| Database | PostgreSQL 16+ | 🔜 Fase 2 |
| Frontend | Next.js + shadcn/ui + Tailwind | 🔜 Fase 4 |
| WhatsApp | Twilio API | 🔜 Fase 3 |
| Deploy | Railway | 🔜 Fase 4 |

## Variáveis de Ambiente

Toda a configuração é feita via variáveis de ambiente. Veja `.env.example` para a lista completa.

| Variável | Default | Descrição |
|----------|---------|-----------|
| `OPENROUTER_API_KEY` | — | Chave da API OpenRouter |
| `OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` | Base URL do LLM |
| `OPENROUTER_MODEL` | `google/gemini-3-flash-preview` | Modelo principal do agente |
| `CONTEXT_STRATEGY` | `trim` | Estratégia de contexto (trim/summarize/none) |
| `TRIM_KEEP_TURNS` | `5` | Turnos a manter no trim |
| `SUMMARIZE_TRIGGER_TOKENS` | `4000` | Tokens antes de sumarizar |
| `SUMMARIZE_KEEP_MESSAGES` | `10` | Mensagens a manter após sumarização |
| `SUMMARIZE_MODEL` | `google/gemini-3-flash-preview` | Modelo para sumarização |

## Evoluções Futuras

O sistema foi desenhado para crescer. Algumas evoluções possíveis:

- **LISTEN/NOTIFY** — Substituir polling por notificações do PostgreSQL
- **Redis/RabbitMQ** — Fila dedicada para alto volume
- **NextAuth.js** — Autenticação OAuth no Admin Panel
- **Sentry** — Monitoramento de erros em produção
- **Múltiplos Workers** — Escalar horizontalmente (o lock garante não-duplicação)
- **Cache de agentes** — Evitar recarregar grafos a cada mensagem
- **Prometheus/Grafana** — Métricas detalhadas
