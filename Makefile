.PHONY: help dev setup db migrate api worker frontend up down logs lint format format-check fix typecheck check ci test test-x test-v clean

# Cores para output
CYAN := \033[36m
RESET := \033[0m

##@ Geral
help: ## Mostra esta mensagem de ajuda
	@awk 'BEGIN {FS = ":.*##"; printf "\nUso:\n  make $(CYAN)<comando>$(RESET)\n"} /^[a-zA-Z_-]+:.*?##/ { printf "  $(CYAN)%-15s$(RESET) %s\n", $$1, $$2 } /^##@/ { printf "\n%s\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

##@ Setup
setup: ## Cria .venv e instala dependências
	uv venv
	uv pip install -e ".[dev]"

##@ Desenvolvimento
dev: ## Inicia LangGraph Studio (desenvolvimento de agentes)
	uv run langgraph dev

db: ## Inicia apenas o PostgreSQL (com pgvector)
	docker compose up -d db

migrate: ## Aplica migrações pendentes no banco
	uv run python db/migrate.py

api: ## Roda a API localmente (fora do Docker)
	uv run uvicorn whatsapp_langchain.server.main:app --reload --port 8000

worker: ## Roda o Worker localmente (fora do Docker)
	uv run python -m whatsapp_langchain.worker.main

frontend: ## Roda o Admin Panel (Next.js)
	cd frontend && npm run dev

##@ Docker
up: ## Inicia todos os serviços (API + Worker + DB)
	docker compose up -d

down: ## Para todos os serviços
	docker compose down

logs: ## Mostra logs de todos os serviços
	docker compose logs -f

##@ Qualidade de Código
# Estes comandos verificam estilo e tipos, NÃO lógica.
# Para testar lógica, use: make test
#
# Fluxo típico:
#   make fix && make format   # Corrige e formata
#   make check                # Verifica se está tudo ok
#   git commit

lint: ## Encontra problemas (imports, sintaxe) — não altera arquivos
	uv run ruff check .

format: ## Formata código — ALTERA arquivos
	uv run ruff format .

format-check: ## Verifica se está formatado — não altera (para CI)
	uv run ruff format --check .

fix: ## Corrige problemas automaticamente — ALTERA arquivos
	uv run ruff check --fix .

typecheck: ## Verifica tipos estáticos (pyright) — não altera arquivos
	uv run pyright src/

check: ## Verifica tudo (lint + format + types) — não altera arquivos
	uv run ruff check . && uv run ruff format --check . && uv run pyright src/

ci: ## CI/CD: verifica tudo + roda testes — não altera arquivos
	uv run ruff check . && uv run ruff format --check . && uv run pyright src/ && uv run pytest

##@ Testes
test: ## Roda todos os testes
	uv run pytest

test-x: ## Roda testes, para no primeiro erro
	uv run pytest -x

test-v: ## Roda testes com output verboso
	uv run pytest -v

##@ Limpeza
clean: ## Remove arquivos de cache do Python
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
