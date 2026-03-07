# Stress Testing com Locust

Infraestrutura para testes de carga na API WhatsApp LangChain usando [Locust](https://locust.io/).

## O que e stress testing?

Stress testing simula multiplos usuarios enviando mensagens simultaneamente para identificar gargalos, limites de capacidade e comportamento sob pressao. Diferente de testes unitarios que validam corretude, testes de carga validam **performance e resiliencia**.

## Pre-requisitos

- Python 3.12+
- A API rodando localmente (`make up`) ou em ambiente remoto
- O mesmo `TWILIO_AUTH_TOKEN` configurado na API

## Variaveis de ambiente

| Variavel | Obrigatoria | Descricao |
|---|---|---|
| `TWILIO_AUTH_TOKEN` | Sim | Token do Twilio (mesmo da API) — usado para assinar requests |
| `TWILIO_WEBHOOK_URL` | Sim | URL base do webhook (ex: `http://localhost:8000`) |

## Como rodar localmente

```bash
cd stress
pip install -r requirements.txt

# Configura as variaveis (use o mesmo token da API)
export TWILIO_AUTH_TOKEN=seu_token_aqui
export TWILIO_WEBHOOK_URL=http://localhost:8000

# Inicia o Locust
locust
```

Acesse a Web UI em **http://localhost:8089** para configurar o numero de usuarios e iniciar o teste.

## Como rodar via Docker

```bash
cd stress

# Build da imagem
docker build -t whatsapp-stress .

# Roda o container
docker run -p 8089:8089 \
  -e TWILIO_AUTH_TOKEN=seu_token_aqui \
  -e TWILIO_WEBHOOK_URL=http://host.docker.internal:8000 \
  whatsapp-stress
```

> **Nota:** Use `host.docker.internal` em vez de `localhost` quando a API roda na maquina host fora do Docker.

Acesse a Web UI em **http://localhost:8089**.

## Cenarios de teste

| Cenario | Peso | Descricao |
|---|---|---|
| Mensagem normal | 10 | Frases curtas (3-15 palavras) — simula conversa casual |
| Mensagem longa | 1 | Paragrafos com ~10 frases — testa limites de texto |

## Modo headless (sem Web UI)

Para rodar sem interface grafica (util em CI/CD):

```bash
locust --headless -u 10 -r 2 -t 60s \
  -f locustfile.py \
  --host http://localhost:8000
```

- `-u 10`: 10 usuarios simultaneos
- `-r 2`: 2 usuarios novos por segundo (ramp-up)
- `-t 60s`: durar 60 segundos
