# Primeiros Passos

## Pré-requisitos

- **Python 3.11+** — [python.org](https://www.python.org/)
- **uv** — [docs.astral.sh/uv](https://docs.astral.sh/uv/) (gerenciador de pacotes)
- **Conta OpenRouter** — [openrouter.ai](https://openrouter.ai/) (chave de API para os modelos)

## 1. Instalando o uv

O **uv** é um gerenciador de pacotes moderno e rápido. Funciona nativamente no Windows, Mac e Linux.

```bash
# Windows (PowerShell)
irm https://astral.sh/uv/install.ps1 | iex

# Mac/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Ou via pip (qualquer OS)
pip install uv
```

## 2. Setup do Projeto

```bash
git clone <repo-url>
cd whatsapp-langchain

# Cria ambiente virtual e instala dependências
make setup
# Ou manualmente:
# uv venv
# uv pip install -e ".[dev]"

# Copia o template de variáveis de ambiente
cp .env.example .env
```

Edite o `.env` com suas credenciais:

```bash
# Obrigatório
OPENROUTER_API_KEY=sk-or-v1-...

# O resto pode ficar com os valores padrão para dev
```

## 3. Desenvolvendo Agentes (LangGraph Studio)

O jeito mais rápido de começar é usando o LangGraph Studio:

```bash
make dev
# Ou manualmente: uv run langgraph dev
```

Isso abre o LangGraph Studio no navegador. Você pode:
- Conversar com o agente `rhawk_assistant`
- Ver o grafo executando em tempo real
- Testar diferentes configurações de middleware

O agente é definido em `src/whatsapp_langchain/agents/catalog/rhawk_assistant/`. Edite os arquivos e veja as mudanças ao vivo:

| Arquivo | Responsabilidade |
|---------|-----------------|
| `agent.py` | Factory `build_graph()` — configura modelo e middleware |
| `graph.py` | Exporta variável `graph` para o LangGraph Studio |
| `prompts.py` | System prompt do agente |

### Configurando o Middleware de Contexto

O `.env` controla a estratégia de gerenciamento de contexto:

```bash
# No .env
CONTEXT_STRATEGY=trim        # trim | summarize | none

# Para trim: mantém os N turnos mais recentes
# Um turno = 1 HumanMessage + todas as respostas (AI, tools, etc)
TRIM_KEEP_TURNS=5

# Para summarize: sumariza quando excede o limite de tokens
SUMMARIZE_TRIGGER_TOKENS=4000
SUMMARIZE_KEEP_MESSAGES=10
SUMMARIZE_MODEL=google/gemini-3-flash-preview
```

Mude `CONTEXT_STRATEGY` e reinicie o LangGraph Studio para testar diferentes estratégias.

## 4. Testes

```bash
make test
# Ou manualmente: uv run pytest
```

Outros comandos úteis:

```bash
make test-x    # Para no primeiro erro
make test-v    # Output verboso
```

> **Nota:** Os testes de integração requerem `OPENROUTER_API_KEY` configurada no `.env`.

## 5. Qualidade de Código

O projeto usa **Ruff** para linting/formatação e **Pyright** para type checking.

```bash
# Encontra problemas
make lint

# Formata código automaticamente
make format

# Corrige problemas automaticamente
make fix

# Verifica tipos estáticos
make typecheck

# Verifica tudo de uma vez (lint + format + types)
make check
```

Fluxo recomendado antes de commitar:

```bash
make fix && make format    # Corrige e formata
make check                 # Verifica se está tudo ok
```

## Troubleshooting

### LangGraph Studio não abre

```
Verifique se o uv está instalado: uv --version
Verifique se as dependências estão instaladas: make setup
Verifique se o langgraph.json está na raiz do projeto
```

### Erro "OPENROUTER_API_KEY not set"

```
Verifique se o .env existe: ls .env
Verifique se a chave está configurada: grep OPENROUTER_API_KEY .env
Gere uma chave em: https://openrouter.ai/keys
```

### Modelo não responde ou retorna erro

```
Verifique se a chave do OpenRouter tem créditos
Verifique o modelo configurado em OPENROUTER_MODEL no .env
Teste com um modelo gratuito: google/gemini-3-flash-preview
```

### Testes falham com "requires API key"

```
Os testes de integração precisam de uma chave válida no .env
Para pular testes de integração: uv run pytest -k "not integration"
```

## Próximos Passos

- [Criando Agentes](ADDING_AGENTS.md) — Crie seu próprio agente com middleware personalizado
- [Arquitetura](ARCHITECTURE.md) — Entenda como o sistema funciona e para onde vai
