# Deploy

Este guia cobre a base de publicação da **Fase 3**:
- API FastAPI exposta para webhook Twilio
- Worker assíncrono com envio outbound real
- PostgreSQL com pgvector

Objetivo: publicar a arquitetura de processamento assíncrono com persistência, memória e canal real via Twilio.

## Escopo desta fase

Incluído:
- webhook Twilio assíncrono (`/webhook/twilio`)
- validação real de assinatura via `X-Twilio-Signature` quando habilitada
- fila em PostgreSQL
- execução de agente no worker
- envio de resposta para WhatsApp via Twilio Messages API
- typing indicator best-effort antes do processamento
- contexto por checkpointer
- memória semântica por store com tools (`save_memory` e `read_memory`)
- rotas administrativas e health check

Ainda não incluído como fechamento operacional:
- frontend/admin panel neste repositório
- deploy específico de plataforma gerenciada (ex: Railway)
- stress testing comparativo e hardening final

## Topologia mínima de produção

- `db`: PostgreSQL (com extensão `vector`)
- `api`: processo HTTP (`uvicorn ...server.main:app`) exposto publicamente para o webhook
- `worker`: processo consumidor (`python -m ...worker.main`) com acesso outbound ao Twilio

A API e o worker devem compartilhar:
- o mesmo banco
- a mesma base de configuração do projeto
- a mesma versão de código

Para setup de sandbox, cloudflared e webhook público, use também [TWILIO.md](TWILIO.md).

## Variáveis obrigatórias

Comuns:
- `DATABASE_URL`
- `OPENROUTER_API_KEY`
- `OPENROUTER_BASE_URL`
- `OPENROUTER_MODEL`

Obrigatórias no worker:
- `TWILIO_ACCOUNT_SID`
- `TWILIO_API_KEY_SID`
- `TWILIO_API_KEY_SECRET`
- `TWILIO_FROM_NUMBER`

Obrigatórias na API quando a validação de assinatura estiver habilitada:
- `TWILIO_AUTH_TOKEN`
- `TWILIO_WEBHOOK_URL`
- `VALIDATE_TWILIO_SIGNATURE=true`

Recomendadas para operação:
- `LOG_JSON=true`
- `CONTEXT_STRATEGY`
- `MESSAGE_BUFFER_SECONDS`
- `POLL_INTERVAL_SECONDS`
- `LEASE_SECONDS`
- `MAX_ATTEMPTS`
- `MEMORY_ENABLED`
- `EMBEDDING_MODEL`
- `EMBEDDING_DIMS`

## Ordem de subida

1. Subir banco PostgreSQL com pgvector.
2. Subir API (aplica migrações no startup).
3. Subir Worker.
4. Verificar `GET /health`.
5. Se o webhook for público, configurar `TWILIO_WEBHOOK_URL` e validação de assinatura na API.
6. Enviar mensagem de teste para `/webhook/twilio`.
7. Acompanhar `/api/metrics` e logs de API/worker.

> Na Fase 3, o worker faz fail-fast se as credenciais outbound do Twilio estiverem ausentes.

## Deploy com Docker (referência)

Os Dockerfiles e `docker-compose.yml` deste repositório representam a base executável da Fase 3.

Build local:

```bash
docker compose build
```

Subida local (modo próximo da produção):

```bash
docker compose up -d
```

Logs:

```bash
docker compose logs -f api worker db
```

## Checklist operacional

- health check responde 200
- request com assinatura inválida retorna 403 quando a validação está habilitada
- `message_queue` recebe mensagens
- worker faz transição `queued -> processing -> done|failed`
- worker tenta `typing` antes do agente nas execuções normais
- resposta outbound chega ao Twilio antes de `mark_done`
- memória semântica persiste em `store` com prefixo `<phone_number>.memories`
- retries acontecem quando há erro transitório
- métricas administrativas retornam dados
- logs estruturados habilitados (`LOG_JSON=true` em produção)

## Hardening recomendado

- mover rate limit HTTP para backend distribuído (Redis ou DB)
- configurar supervisão de processos (restart policy/health probes)
- habilitar `VALIDATE_TWILIO_SIGNATURE=true` quando o webhook estiver exposto publicamente
- proteger ou restringir acesso às rotas administrativas por rede/proxy
- rotacionar segredos do Twilio e do provedor LLM
- adicionar alertas para:
  - crescimento de `queue_size`
  - aumento de `failed`
  - latência média de processamento

## Próxima evolução

Ao avançar para fases seguintes:
- publicar frontend/admin panel
- documentar deploy em plataforma gerenciada
- executar stress testing e hardening final
