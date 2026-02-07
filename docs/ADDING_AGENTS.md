# Criando Agentes

## Convenção

Cada agente vive em seu próprio diretório dentro de `src/whatsapp_langchain/agents/catalog/`:

```
agents/catalog/meu_agente/
├── __init__.py
├── agent.py      # Factory build_graph() — configura modelo e middleware
├── graph.py      # Exporta variável graph para langgraph dev
└── prompts.py    # System prompt
```

A função `build_graph(checkpointer=None)` é o ponto de entrada. Ela retorna um grafo compilado do LangGraph via `create_agent()`.

## Passo a Passo

### 1. Criar o diretório

```bash
mkdir -p src/whatsapp_langchain/agents/catalog/meu_agente
touch src/whatsapp_langchain/agents/catalog/meu_agente/__init__.py
```

### 2. Definir o prompt

```python
# prompts.py
SYSTEM_PROMPT = """Você é um assistente especializado em vendas.
Seja objetivo, amigável e ajude o cliente a encontrar o produto ideal.
Responda sempre em português."""
```

### 3. Criar o agente

```python
# agent.py
import os

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.base import BaseCheckpointSaver
from pydantic import SecretStr

from whatsapp_langchain.agents.middleware import get_context_middleware

from .prompts import SYSTEM_PROMPT

load_dotenv()

DEFAULT_MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-oss-120b")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")


def build_graph(checkpointer: BaseCheckpointSaver | None = None):
    """Constrói o agente de vendas."""
    api_key = os.getenv("OPENROUTER_API_KEY")
    secret_key = SecretStr(api_key) if api_key else None

    model = ChatOpenAI(
        model=DEFAULT_MODEL,
        api_key=secret_key,
        base_url=OPENROUTER_BASE_URL,
    )

    # Usa a mesma configuração de contexto do .env
    middleware = get_context_middleware()

    return create_agent(
        model=model,
        tools=[],
        system_prompt=SYSTEM_PROMPT,
        middleware=middleware,
        checkpointer=checkpointer,
    )
```

### 4. Exportar o grafo para o LangGraph Studio

```python
# graph.py
from whatsapp_langchain.agents.catalog.meu_agente.agent import build_graph

# Variável graph para langgraph dev (in-memory, sem checkpointer)
graph = build_graph()
```

> **Importante:** O `langgraph.json` referencia uma **variável** (`graph.py:graph`), não uma **função** (`graph.py:build_graph`). O LangGraph Studio precisa de um grafo já compilado. Em produção, o Worker usará `build_graph(checkpointer=...)` de `agent.py` para passar o checkpointer do PostgreSQL.

### 5. Registrar no langgraph.json

```json
{
  "dependencies": ["."],
  "graphs": {
    "rhawk_assistant": "./src/whatsapp_langchain/agents/catalog/rhawk_assistant/graph.py:graph",
    "meu_agente": "./src/whatsapp_langchain/agents/catalog/meu_agente/graph.py:graph"
  },
  "env": ".env"
}
```

### 6. Testar

```bash
make dev   # Abre o LangGraph Studio
```

No Studio, selecione `meu_agente` e converse para validar.

## Middleware de Contexto

Os agentes usam middleware para gerenciar o tamanho do histórico de conversa. O middleware é passado via parâmetro `middleware=` ao `create_agent()`.

### Usando `get_context_middleware()` (recomendado)

A forma mais simples é usar a factory que lê configuração do `.env`:

```python
from whatsapp_langchain.agents.middleware import get_context_middleware

middleware = get_context_middleware()  # Lê CONTEXT_STRATEGY do .env

agent = create_agent(
    model=model,
    middleware=middleware,
    ...
)
```

### Trim (configuração direta)

Mantém apenas os últimos N turnos. Um turno = 1 HumanMessage + todas as respostas (AI, tools, etc). Simples e sem custo extra.

```python
from whatsapp_langchain.agents.middleware import create_trim_middleware

trim = create_trim_middleware(keep_turns=5)

agent = create_agent(
    model=model,
    middleware=[trim],
    ...
)
```

**Quando usar**: Conversas curtas, respostas baseadas em contexto recente.

### Summarize (configuração direta)

Sumariza mensagens antigas usando uma chamada extra ao LLM. Preserva mais contexto.

```python
from whatsapp_langchain.agents.middleware import create_summarize_middleware

summarize = create_summarize_middleware(
    trigger_tokens=4000,    # Sumariza quando exceder 4000 tokens
    keep_messages=10,       # Mantém as 10 mais recentes
)

agent = create_agent(
    model=model,
    middleware=[summarize],
    ...
)
```

O modelo para sumarização é criado automaticamente usando `SUMMARIZE_MODEL` do `.env`. Para passar um modelo específico:

```python
summarize = create_summarize_middleware(
    model=my_cheap_model,   # ChatOpenAI já instanciado
    trigger_tokens=4000,
    keep_messages=10,
)
```

**Quando usar**: Conversas longas onde o histórico é importante (ex: suporte ao cliente).

### Trade-offs

| | Trim | Summarize |
|--|------|-----------|
| **Custo** | Zero | 1 chamada LLM extra |
| **Escopo** | Thread (1 conversa) | Thread (1 conversa) |
| **Contexto** | Últimos N turnos | Resumo + recentes |
| **Latência** | Zero | +1-2s |
| **Melhor para** | FAQ, conversas curtas | Suporte longo |

## Agente com Tools

```python
# agent.py
import os

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.base import BaseCheckpointSaver
from pydantic import SecretStr

from whatsapp_langchain.agents.middleware import get_context_middleware

from .prompts import SYSTEM_PROMPT

load_dotenv()


@tool
def consultar_estoque(produto: str) -> str:
    """Consulta o estoque de um produto."""
    # Sua lógica aqui
    return f"{produto}: 42 unidades disponíveis"


def build_graph(checkpointer: BaseCheckpointSaver | None = None):
    """Constrói o agente de vendas com tools."""
    api_key = os.getenv("OPENROUTER_API_KEY")
    secret_key = SecretStr(api_key) if api_key else None

    model = ChatOpenAI(
        model=os.getenv("OPENROUTER_MODEL", "openai/gpt-oss-120b"),
        api_key=secret_key,
        base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
    )

    middleware = get_context_middleware()

    return create_agent(
        model=model,
        tools=[consultar_estoque],
        system_prompt=SYSTEM_PROMPT,
        middleware=middleware,
        checkpointer=checkpointer,
    )
```

## Boas Práticas

- **Um agente por caso de uso** — `rhawk_assistant`, `vendas`, `suporte`, etc
- **Prompts em `prompts.py`** — Separados do código do agente
- **Use `create_agent()`** — Não construa `StateGraph` manualmente a menos que precise de um fluxo não-linear
- **Use `get_context_middleware()`** — Configuração centralizada via `.env`
- **Sem dependências externas** — O agente não deve importar de `server/` ou `worker/`
- **Teste no Studio primeiro** — `make dev` antes de tudo
