# Stress Testing

## Por que testar carga?

Testes unitarios validam que cada funcao faz o que deveria. Testes de carga validam que o **sistema inteiro** sobrevive quando muitos usuarios chegam ao mesmo tempo.

Sem testes de carga, voce so descobre gargalos em producao — quando ja e tarde demais. Com eles, voce pode:

- Encontrar o ponto de ruptura antes que os usuarios encontrem
- Validar que a arquitetura assincrona (fila + worker) realmente escala melhor que processamento sincrono
- Medir latencias reais sob pressao (p50, p95, p99)
- Garantir que rate limiting, debounce e backpressure funcionam como esperado

**Diferenca fundamental:**

| Aspecto | Teste unitario | Teste de carga |
|---------|---------------|----------------|
| Escopo | Uma funcao/modulo | Sistema completo |
| Objetivo | Corretude logica | Performance e estabilidade |
| Duracao | Milissegundos | Minutos |
| Dependencias | Mockadas | Reais (DB, API, LLM) |

## Cenarios disponiveis

O `locustfile.py` define tres classes de usuarios virtuais, cada uma simulando um padrao de uso diferente:

| Cenario | Classe | Endpoint | Peso | Wait Time | Assinatura |
|---------|--------|----------|------|-----------|------------|
| Webhook Async | `TwilioWebhookUser` | `/webhook/twilio` | 10 (normal) / 1 (longo) | 1-3s | Sim (HMAC-SHA1) |
| Webhook Sync | `SyncWebhookUser` | `/webhook/sync` | 1 | 3-10s | Nao |
| Burst | `BurstUser` | `/webhook/twilio` | 1 | 5-15s (entre rajadas) | Sim |

### Webhook Async (TwilioWebhookUser)

Cenario principal. Simula usuarios enviando mensagens pelo webhook do Twilio com assinatura HMAC-SHA1 valida. A API enfileira a mensagem e retorna `200` imediatamente — o worker processa depois.

### Webhook Sync (SyncWebhookUser)

Cenario de comparacao. O endpoint `/webhook/sync` processa a mensagem inline e so retorna quando a IA responde. **Nao use em producao** — existe apenas para demonstrar a diferenca de throughput entre arquiteturas sync e async.

### Burst (BurstUser)

Simula rajadas de 5-20 mensagens com intervalo de 0.1-0.5s entre elas (como um usuario colando varias linhas). Estressa rate limiting, crescimento de fila e estabilidade do banco sob muitas escritas simultaneas.

## Como executar

### Localmente (sem Docker)

```bash
cd /caminho/para/whatsapp-langchain/stress
pip install -r requirements.txt
export TWILIO_AUTH_TOKEN=seu_token
export TWILIO_WEBHOOK_URL=http://localhost:8000
locust
```

Acesse http://localhost:8089 para a interface web do Locust.

### Via Docker Compose (profile testing)

O servico `stress` esta configurado com o profile `testing`, entao nao sobe junto com os servicos principais. Para inicia-lo:

```bash
docker compose --profile testing up stress
```

Isso sobe o Locust apontando para o servico `api` via rede interna do Compose. Acesse http://localhost:8089.

> **Nota:** As variaveis `TWILIO_AUTH_TOKEN` e `TWILIO_WEBHOOK_URL` ja estao configuradas no `docker-compose.yml`. O token vem do `.env` (ou usa `test-token` como fallback).

### Modo headless (CI/CD)

Para rodar sem interface grafica (util em pipelines de CI):

```bash
locust --headless -u 50 -r 5 -t 120s -f locustfile.py --host http://localhost:8000
```

Parametros:
- `-u 50`: 50 usuarios simultaneos
- `-r 5`: ramp-up de 5 usuarios por segundo
- `-t 120s`: duracao total de 120 segundos
- `--host`: URL base da API

### Contra o Railway (stack real)

Para testar contra o ambiente de producao no Railway:

```bash
export TWILIO_AUTH_TOKEN=token_producao
export TWILIO_WEBHOOK_URL=https://api-domain.up.railway.app
locust --host https://api-domain.up.railway.app
```

> **Cuidado:** Isso gera trafego real no seu ambiente de producao. Use com moderacao para nao estourar cotas de LLM ou rate limits do Twilio.

## Cenarios recomendados

| Cenario | Usuarios | Ramp-up | Duracao | Objetivo |
|---------|----------|---------|---------|----------|
| Baseline | 10 | 2/s | 60s | Validar funcionamento basico |
| Normal | 50 | 5/s | 120s | Carga tipica de operacao |
| Pico | 200 | 10/s | 300s | Simular horario de pico |
| Stress | 500 | 20/s | 300s | Encontrar ponto de ruptura |

Comece pelo **Baseline** para garantir que tudo funciona, depois escale gradualmente. Se o Baseline ja mostra erros, corrija antes de ir para cenarios maiores.

## Interpretando resultados

### Metricas-chave

- **RPS (Requests per Second)**: throughput da API — quantas requisicoes ela consegue processar por segundo
- **p50/p95/p99 latencia**: tempo de resposta em percentis. p50 = mediana, p95 = "quase todo mundo", p99 = piores casos
- **Taxa de erros**: percentual de respostas 4xx/5xx. Em operacao normal, deve ser proximo de 0%
- **Queue drain rate**: velocidade com que o worker processa a fila. Se a fila so cresce, o worker esta mais lento que a entrada

### Comparacao Async vs Sync (exercicio educacional)

Rode 100 usuarios por 5 minutos em cada cenario e compare as metricas:

| Metrica | Async (esperado) | Sync (esperado) |
|---------|------------------|-----------------|
| RPS | 100+ | 5-10 |
| p50 latencia | <50ms | 5-30s |
| p99 latencia | <200ms | timeout |
| Taxa de erros | ~0% | alta |

**Conclusao**: A fila assincrona permite throughput 10-20x maior com latencias consistentes. O endpoint async retorna imediatamente apos enfileirar, enquanto o sync bloqueia ate o LLM responder — o que causa timeouts sob carga.

## Identificando gargalos

Quando os resultados nao estao bons, use esta tabela para diagnosticar:

| Sintoma | Causa provavel | O que verificar |
|---------|---------------|-----------------|
| Latencia alta no enqueue | API lenta | Conexao com o banco de dados, pool size |
| Fila cresce sem drenar | Worker lento | Rate limit do LLM, quantidade de workers |
| Erros de conexao | DB saturado | `pool_size` no PostgreSQL, conexoes abertas |
| Erros 429 do OpenRouter | LLM throttled | Ajustar `LLM_RATE_LIMIT_*` no `.env` |
| Erros 403 no webhook | Assinatura invalida | `TWILIO_AUTH_TOKEN` correto e consistente |

## Contextos de uso

1. **Educacional local**: compare sync vs async com a stack Docker completa. Rode o cenario Baseline nos dois endpoints e observe a diferenca dramatica de throughput e latencia. Este e o melhor exercicio para entender *por que* filas assincronas existem.

2. **Validacao operacional**: rode o cenario async com assinatura valida contra o Railway real antes de ir para producao. Valide que o sistema aguenta a carga esperada sem acumular backlog na fila.
