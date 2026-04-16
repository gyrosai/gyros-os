# Gyros OS

Sistema operacional interno da Gyros AI Solutions, construído sobre o harness whatsapp-langchain do Ronnald Hawk.

## O que foi adicionado (Week 1 — Foundation)

- **Migration 005**: tabelas `organizations`, `kb_docs`, `kb_chunks` (com `vector(1536)` + HNSW), `event_queue`
- **Módulo `rag/`**: `ingest_text()` idempotente (chunking semântico 512 tok / 50 overlap) + `retrieve()` por similaridade coseno via pgvector
- **Cliente `integrations/fireflies/`**: client GraphQL tipado para buscar transcrições completas (falas, participantes, summary)
- **Webhook `POST /webhook/fireflies`**: valida HMAC-SHA256 opcional, normaliza eventos, enfileira em `event_queue`
- **Event worker paralelo**: segundo loop `asyncio` no mesmo processo do message worker, consome `event_queue` com `FOR UPDATE SKIP LOCKED`
- **Handler `fireflies.transcription_completed`**: busca transcrição na API Fireflies, formata texto com timestamps e participantes, ingere via RAG

## O que NÃO foi adicionado (e por quê)

| Feature | Motivo |
|---------|--------|
| Captura Rápida (voice notes → KB) | Depende de refinamento do pipeline de áudio — planejado para Fatia 2 |
| Scheduler (agenda → lembretes) | Requer integração GCal + lógica de cron — Fatia 3 |
| Proposta (geração automática) | Precisa de templates e aprovação HITL — Fatia 3-4 |
| HITL (human-in-the-loop) | Infraestrutura de aprovação depende do frontend admin — Fatia 4 |

Todas essas features usam a mesma `event_queue` e o mesmo event worker já implementados.

## Como rodar localmente

1. Siga o setup base em [GETTING_STARTED.md](GETTING_STARTED.md) (`make setup` + `cp .env.example .env`)
2. Configure as variáveis adicionais no `.env` (ver seção abaixo)
3. Suba os serviços: `make up` (PostgreSQL com pgvector + API + Worker)
4. As migrations rodam automaticamente no boot — verifique que as tabelas `kb_docs`, `kb_chunks` e `event_queue` existem
5. Configure o webhook `POST https://<seu-dominio>/webhook/fireflies` no painel do Fireflies.ai

## Variáveis de ambiente novas

| Variável | Obrigatória | Uso |
|----------|-------------|-----|
| `FIREFLIES_API_KEY` | Sim (para Fireflies) | Autenticação na API GraphQL do Fireflies |
| `FIREFLIES_WEBHOOK_SECRET` | Não (recomendado em prod) | Validação HMAC-SHA256 do header `X-Hub-Signature` |
| `OPENAI_API_KEY` | Sim (para RAG) | Embeddings via `text-embedding-3-small` |

## Teste end-to-end: Fireflies -> RAG

**1. Simule o webhook do Fireflies:**

```bash
curl -X POST http://localhost:8000/webhook/fireflies \
  -H "Content-Type: application/json" \
  -d '{"event": "Transcription completed", "meeting_id": "<MEETING_ID_REAL>", "timestamp": 1700000000000}'
```

Resposta esperada: `{"status": "queued", "event_id": <int>}` com HTTP 202.

> Use um `meeting_id` real da sua conta Fireflies. O handler vai buscar a transcrição via API.

**2. Acompanhe o processamento:**

```sql
-- Evento foi enfileirado?
SELECT id, event_type, status, created_at FROM event_queue ORDER BY id DESC LIMIT 5;

-- Evento foi processado?
SELECT id, status, result, error FROM event_queue WHERE id = <event_id>;
```

**3. Valide a ingestão no RAG:**

```sql
-- Documento criado?
SELECT id, title, source_type, source_ref, chunk_count FROM kb_docs ORDER BY id DESC LIMIT 5;

-- Chunks com embeddings?
SELECT id, doc_id, token_count, length(embedding::text) as emb_len FROM kb_chunks WHERE doc_id = <doc_id>;
```

Se `kb_docs` tem o documento e `kb_chunks` tem chunks com embeddings não-nulos, o fluxo completo está funcionando.
