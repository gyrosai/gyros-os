# Deploy

Este guia resume o deploy da fase atual do projeto e aponta para os
documentos detalhados de operacao.

## Estado atual

Na Fase 4, o projeto ja cobre:
- API FastAPI publica para `POST /webhook/twilio`
- Worker assincrono com envio outbound via Twilio
- Frontend/admin panel em Next.js com Better Auth
- PostgreSQL com pgvector
- deploy de referencia em Railway
- stress testing e leitura de gargalos

## Topologia alvo

```text
Internet -> Frontend (publico)
Internet -> API (publica para /health e /webhook/twilio)
Twilio -> API (webhook inbound)
Frontend -> API (server-side via INTERNAL_API_URL + INTERNAL_SERVICE_TOKEN)
API -> PostgreSQL
Worker -> PostgreSQL
Frontend -> PostgreSQL (schema auth)
Worker -> Twilio (outbound)
```

## Guias detalhados

- [Railway](RAILWAY.md): provisionamento de servicos, rede interna, variaveis e watch paths
- [Twilio](TWILIO.md): credenciais, webhook, assinatura, sandbox e cloudflared
- [Stress Testing](STRESS_TESTING.md): preparo do ambiente e leitura de throughput/latencia

## Variaveis essenciais por servico

### API

- `DATABASE_URL`
- `ENVIRONMENT=production`
- `LOG_JSON=true`
- `OPENROUTER_API_KEY`
- `OPENROUTER_BASE_URL`
- `VALIDATE_TWILIO_SIGNATURE=true`
- `TWILIO_AUTH_TOKEN`
- `TWILIO_WEBHOOK_URL`
- `INTERNAL_SERVICE_TOKEN`
- `MEMORY_ENABLED`, `EMBEDDING_MODEL`, `EMBEDDING_DIMS` quando memoria semantica estiver ativa

### Worker

- `DATABASE_URL`
- `ENVIRONMENT=production`
- `LOG_JSON=true`
- `OPENROUTER_API_KEY`
- `OPENROUTER_BASE_URL`
- `OPENROUTER_MODEL`
- `OPENROUTER_MIDIA_MODEL`
- `TWILIO_OUTBOUND_MODE=real`
- `TWILIO_ACCOUNT_SID`
- `TWILIO_API_KEY_SID`
- `TWILIO_API_KEY_SECRET`
- `TWILIO_FROM_NUMBER`

> Em `TWILIO_OUTBOUND_MODE=real`, o worker encerra no boot se as credenciais
> outbound do Twilio estiverem ausentes.

### Frontend

- `DATABASE_URL`
- `INTERNAL_API_URL`
- `INTERNAL_SERVICE_TOKEN`
- `BETTER_AUTH_SECRET`
- `BETTER_AUTH_URL`

## Fluxo recomendado de publicacao

1. Provisionar `db`, `api`, `worker` e `frontend`.
2. Configurar as variaveis de ambiente por servico.
3. Publicar dominio da API e do Frontend.
4. Configurar o webhook do Twilio apontando para `https://<api>/webhook/twilio?agent=rhawk_assistant`.
5. Fazer o bootstrap do primeiro admin e trocar a senha inicial no painel.
6. Executar smoke tests de API, painel e mensagem real no WhatsApp.

## Checklist de verificacao

- `GET /health` responde `200`
- `/login` renderiza corretamente no Frontend
- request com assinatura invalida retorna `403` quando a validacao esta habilitada
- `message_queue` recebe mensagens e o worker faz `queued -> processing -> done|failed`
- a resposta chega ao WhatsApp antes de `mark_done`
- o Frontend acessa `/api/*` apenas via `INTERNAL_SERVICE_TOKEN`

## Notas operacionais

- Em `ENVIRONMENT=production`, o endpoint `/webhook/sync` fica desabilitado.
- `TWILIO_OUTBOUND_MODE=mock` e util para desenvolvimento local e stress test sem custo real.
- O guia detalhado de Railway fica em [RAILWAY.md](RAILWAY.md); este arquivo e a visao geral.
