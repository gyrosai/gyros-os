# Frontend Admin Panel

Painel administrativo em Next.js para operacao do projeto `whatsapp-langchain`.

## Desenvolvimento local

Para iterar no frontend, nao e necessario subir a stack inteira.

### Requisitos minimos

- PostgreSQL local via `make db`
- arquivo `frontend/.env.local`
- API local apenas se voce quiser navegar alem do login

### 1. Configurar `frontend/.env.local`

Exemplo minimo:

```bash
INTERNAL_API_URL=http://localhost:8000
INTERNAL_SERVICE_TOKEN=dev-token-local
DATABASE_URL=postgresql://postgres:postgres@localhost:5433/gyros_os
BETTER_AUTH_SECRET=dev-secret-local-1234567890
BETTER_AUTH_URL=http://localhost:3000
ENVIRONMENT=development
ADMIN_EMAIL=admin@localhost
ADMIN_PASSWORD=troque-esta-senha
```

Observacoes:

- `INTERNAL_SERVICE_TOKEN` pode ser qualquer valor nao-vazio em desenvolvimento
- `BETTER_AUTH_SECRET` tambem pode ser qualquer valor nao-vazio em desenvolvimento
- se `auth."user"` estiver vazio, o primeiro acesso ao `/login` cria o admin
  usando `ADMIN_EMAIL` e `ADMIN_PASSWORD`
- depois do primeiro login, troque a senha em `/settings`
- esse arquivo e usado apenas por `npm run dev`
- Docker Compose e ambientes publicados usam env vars do proprio servico

### 2. Revisar apenas a tela de login

```bash
cd ..
make db
cd frontend
npm run dev
```

Abra [http://localhost:3000/login](http://localhost:3000/login).

O banco precisa estar de pe porque o login e o bootstrap do admin usam Better
Auth + PostgreSQL diretamente.

### 3. Revisar o painel completo

Se voce quiser abrir dashboard, agentes, fila e conversas, suba tambem a API:

```bash
cd ..
make db
make migrate   # necessario apenas em banco novo ou apos reset
INTERNAL_SERVICE_TOKEN=dev-token-local make api
```

Em outro terminal:

```bash
cd frontend
npm run dev
```

Nesse modo:

- `db` e obrigatorio
- `api` e obrigatoria para paginas que consultam `/api/*`
- `worker` nao e necessario para revisao visual

## Configurando uma instância (Forma C)

Cada deploy usa env vars pra customizar nome, agente, cor e features. Todas
opcionais — defaults são da instância Gyros Studio.

**Frontend (precisam do prefixo `NEXT_PUBLIC_` pra chegar no browser):**

| Variável | Default | Descrição |
|---|---|---|
| `NEXT_PUBLIC_STUDIO_NAME` | `Gyros Studio` | Nome exibido no header e `<title>` |
| `NEXT_PUBLIC_AGENT_NAME` | `Lyra` | Nome do agente referenciado nas telas |
| `NEXT_PUBLIC_STUDIO_BRAND` | `gradient:135deg,#9333EA,#7E22CE` | Cor de marca. Formatos: `solid:#HEX` ou `gradient:ANGdeg,#HEX,#HEX` |
| `NEXT_PUBLIC_FEATURES_ENABLED` | `kb,chat,internal` | CSV de features ativas |

**Backend** (em `src/gyros_os/shared/config.py`, via `settings.*`):
`STUDIO_NAME`, `AGENT_NAME`, `STUDIO_BRAND`, `FEATURES_ENABLED`.

### Feature flags

- `kb` — exibe Base de Conhecimento no menu e home
- `chat` — exibe Chat com o agente no menu e home
- `internal` — exibe a navegação operacional (Dashboard, Fila WhatsApp,
  Reuniões, Agentes, Settings). Desabilitado em instâncias-cliente pra
  evitar ruído operacional.

### Exemplo: instância Curadoria CIMI360

```env
NEXT_PUBLIC_STUDIO_NAME=Curadoria CIMI360
NEXT_PUBLIC_AGENT_NAME=Curadora
NEXT_PUBLIC_STUDIO_BRAND=solid:#1F2937
NEXT_PUBLIC_FEATURES_ENABLED=kb,chat
STUDIO_NAME=Curadoria CIMI360
AGENT_NAME=Curadora
FEATURES_ENABLED=kb,chat
```

### Exemplo: instância Gyros (default)

Sem env vars, app inicia como Gyros Studio com Lyra, gradient roxo e
navegação operacional visível.

### Fonte por instância

Se `STUDIO_NAME` contém "Gyros", usa Plus Jakarta Sans. Caso contrário,
Inter (neutro premium). Muda automaticamente por build.

## Build

```bash
npm run build
```

## Integracao com Docker

Use Docker Compose para validar a stack integrada, nao como fluxo principal de
iteracao visual do frontend.

Na stack Docker, as variaveis do frontend sao definidas no proprio servico
`frontend` do `docker-compose.yml`.

## Referencias

- [Primeiros Passos](/Users/ronnald/Documents/code/pro/whatsapp-langchain/docs/GETTING_STARTED.md)
- [Deploy](/Users/ronnald/Documents/code/pro/whatsapp-langchain/docs/DEPLOY.md)
- [Railway](/Users/ronnald/Documents/code/pro/whatsapp-langchain/docs/RAILWAY.md)
