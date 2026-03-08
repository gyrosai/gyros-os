# Stress Testing com Locust

Infraestrutura para testes de carga na API WhatsApp LangChain usando [Locust](https://locust.io/).

## O que é stress testing?

Stress testing simula múltiplos usuários enviando mensagens simultaneamente para identificar gargalos, limites de capacidade e comportamento sob pressão. Diferente de testes unitários que validam corretude, testes de carga validam **performance e resiliência**.

## Pré-requisitos

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) instalado
- A API rodando localmente (`make up`) ou em ambiente remoto
- O mesmo `TWILIO_AUTH_TOKEN` configurado na API

## Variáveis de ambiente

| Variável | Obrigatória | Descrição |
|---|---|---|
| `TWILIO_AUTH_TOKEN` | Sim | Token do Twilio (mesmo da API) — usado para assinar requests |
| `TWILIO_WEBHOOK_URL` | Sim | URL base do webhook (ex: `http://localhost:8000`) |

## Como rodar localmente

```bash
cd stress

# Cria ambiente virtual e instala dependências
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt

# Configura as variáveis (use o mesmo token da API)
export TWILIO_AUTH_TOKEN=seu_token_aqui
export TWILIO_WEBHOOK_URL=http://localhost:8000

# Inicia o Locust
locust
```

Acesse a Web UI em **http://localhost:8089** para configurar o número de usuários e iniciar o teste.

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

> **Nota:** Use `host.docker.internal` em vez de `localhost` quando a API roda na máquina host fora do Docker.

Acesse a Web UI em **http://localhost:8089**.

## Cenários de teste

| Cenário | Peso | Descrição |
|---|---|---|
| Mensagem normal | 10 | Frases curtas (3-15 palavras) — simula conversa casual |
| Mensagem longa | 1 | Parágrafos com ~10 frases — testa limites de texto |

## Modo headless (sem Web UI)

Para rodar sem interface gráfica (útil em CI/CD):

```bash
locust --headless -u 10 -r 2 -t 60s \
  -f locustfile.py \
  --host http://localhost:8000
```

- `-u 10`: 10 usuários simultâneos
- `-r 2`: 2 usuários novos por segundo (ramp-up)
- `-t 60s`: durar 60 segundos
