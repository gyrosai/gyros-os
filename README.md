# WhatsApp LangChain

Template educacional e production-ready para criar agentes de IA no WhatsApp usando LangGraph.

## O que é?

Um sistema completo que conecta agentes de IA ao WhatsApp. Você define o comportamento do agente usando LangGraph, e a infraestrutura cuida do resto: receber mensagens, processar com IA, e responder automaticamente.

## Arquitetura

![Arquitetura](docs/architecture.png)

```
Usuário (WhatsApp)
       │
       ▼
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Twilio     │────▶│     API      │────▶│ PostgreSQL  │
│  (Provider)  │     │  (FastAPI)   │     │  (Fila +    │
└─────────────┘     └──────────────┘     │ Checkpointer)│
                                          └──────┬───────┘
                                                 │
┌─────────────┐     ┌──────────────┐             │
│   Twilio     │◀───│   Worker     │◀────────────┘
│  (Resposta)  │    │  (LangGraph) │
└─────────────┘     └──────────────┘

┌──────────────┐
│  Admin Panel │───▶ API (métricas, conversas, fila)
│  (Next.js)   │
└──────────────┘
```

**Por que 3 serviços?**

- **API** recebe a mensagem e enfileira. Responde em milissegundos.
- **Worker** processa com IA. Pode demorar segundos — sem bloquear a API.
- **Frontend** monitora tudo via Admin Panel.

Isso garante que nenhuma mensagem é perdida, mesmo sob alta carga.

## Quick Start

```bash
# 1. Clone e configure
git clone <repo-url>
cd whatsapp-langchain
make setup
cp .env.example .env   # Edite com suas chaves

# 2. Desenvolva o agente
make dev               # Abre o LangGraph Studio

# 3. Rode a infraestrutura
make up                # API + Worker + DB (Docker)
make frontend          # Admin Panel
```

## Estrutura do Projeto

```
whatsapp-langchain/
├── src/whatsapp_langchain/
│   ├── agents/                # Agentes de IA
│   │   ├── catalog/           # Um diretório por agente
│   │   │   └── assistant/     # Agente padrão
│   │   └── middleware/        # Trim, Summarize e Semantic Memory
│   ├── server/                # API (FastAPI)
│   │   ├── routes/            # Endpoints
│   │   └── services/          # Queue, Rate Limit
│   ├── worker/                # Processamento (LangGraph)
│   └── shared/                # Config, DB, Models, Logs
├── frontend/                  # Admin Panel (Next.js)
├── stress/                    # Testes de stress (Locust)
├── langgraph.json             # Registry de agentes
├── docker-compose.yml         # Dev local
├── Makefile                   # Comandos úteis
└── docs/                      # Documentação
```

## Documentação

| Documento | Descrição |
|-----------|-----------|
| [Primeiros Passos](docs/GETTING_STARTED.md) | Como rodar o projeto |
| [Arquitetura](docs/ARCHITECTURE.md) | Como o sistema funciona |
| [Criando Agentes](docs/ADDING_AGENTS.md) | Como criar novos agentes |
| [Deploy](docs/DEPLOY.md) | Como colocar em produção |

## Pré-requisitos

- Python 3.12+
- Node.js 20+
- Docker e Docker Compose
- Conta [OpenRouter](https://openrouter.ai/) (LLM)
- Conta [Twilio](https://www.twilio.com/) com número WhatsApp (para produção)

## Comandos

```bash
make setup          # Cria .venv e instala dependências
make dev            # LangGraph Studio (desenvolvimento de agentes)
make db             # Sobe apenas o PostgreSQL
make api            # Roda a API localmente
make worker         # Roda o Worker localmente
make frontend       # Roda o Admin Panel
make up             # Sobe tudo com Docker
make down           # Derruba tudo
make logs           # Logs de todos os serviços
```

## Licença

[TOPHAWKS Community License](LICENSE) — Uso restrito a membros da comunidade [TOPHAWKS](https://www.rhawk.pro/comunidade).
