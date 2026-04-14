"""Rotas OAuth — fluxo de autorização Google Calendar.

Expoe apenas dois endpoints nesta fatia (3.2):
- GET /oauth/google/start    — redireciona o browser pro consent do Google
- GET /oauth/google/callback — recebe o code, troca por tokens, persiste

Tudo que escreve no banco vai via `oauth.service`; tudo que fala com
Google vai via `oauth.providers.google`. Esta camada só orquestra e
trata state CSRF.

State CSRF:
- Guardado em dict module-level com TTL de 10 minutos. Suficiente pra
  v0.1 single-process; quando for multi-process, migrar pra Redis ou
  tabela. Não é Redis já porque a primeira coisa que a gente aprendeu
  na 3.1 é "YAGNI até doer".
- Lookup no callback usa `pop()` (atômico), não `get()` + `del` — isso
  previne replay de state válido.
- Tempo é `datetime.now(UTC)` guardado junto, comparado no callback.
  Não misturamos com `time.monotonic()`.
"""

from __future__ import annotations

import base64
import json
import uuid
from datetime import UTC, datetime, timedelta

import structlog
from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse, RedirectResponse

from gyros_os.oauth import service
from gyros_os.oauth.providers import google as google_provider
from gyros_os.shared.db import get_pool
from gyros_os.shared.org import get_default_org_id

logger = structlog.get_logger()

router = APIRouter()


# ---------- State CSRF (in-memory, TTL 10 min) ----------


_STATE_TTL = timedelta(minutes=10)

# {state_token: {"user_id": str, "expires_at": datetime}}
_state_store: dict[str, dict] = {}


def _issue_state(user_id: str) -> str:
    """Gera um state opaco e registra TTL. Formato: base64 de um JSON
    com nonce e timestamp — opaco pro cliente, legível se a gente
    precisar debugar. O que valida é o lookup no dict, não o conteúdo."""
    nonce = str(uuid.uuid4())
    now = datetime.now(UTC)
    payload = {"user_id": user_id, "nonce": nonce, "ts": now.isoformat()}
    token = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
    _state_store[token] = {
        "user_id": user_id,
        "expires_at": now + _STATE_TTL,
    }
    _prune_expired_states(now)
    return token


def _consume_state(token: str) -> str | None:
    """Lookup + remove atomicamente. Retorna user_id ou None se state
    desconhecido ou expirado. Usa pop() pra ser atômico contra replay."""
    entry = _state_store.pop(token, None)
    if entry is None:
        return None
    if entry["expires_at"] < datetime.now(UTC):
        return None
    return entry["user_id"]


def _prune_expired_states(now: datetime) -> None:
    """Limpa entries vencidos — best-effort. Chamado em cada issue pra
    evitar crescimento ilimitado do dict em dev."""
    expired = [k for k, v in _state_store.items() if v["expires_at"] < now]
    for k in expired:
        _state_store.pop(k, None)


# ---------- Helpers de HTML ----------


_HTML_STYLE = (
    "font-family: system-ui, -apple-system, sans-serif; "
    "max-width: 560px; margin: 3rem auto; padding: 0 1rem;"
)


def _html_response(title: str, body: str, status: int = 200) -> HTMLResponse:
    html = (
        "<!doctype html>\n"
        '<html lang="pt-br">\n'
        f'<head><meta charset="utf-8"><title>{title}</title></head>\n'
        f'<body style="{_HTML_STYLE}">\n'
        f"{body}\n"
        "</body>\n"
        "</html>"
    )
    return HTMLResponse(content=html, status_code=status)


# ---------- Endpoints ----------

@router.get("/oauth/google/start")
async def oauth_google_start(
    user_id: str = Query(..., description="Phone number E.164 (ex: +5521981354432)"),
) -> RedirectResponse:
    """Inicia o fluxo OAuth Google pra este user_id. Redireciona pro
    consent do Google com state CSRF embutido.
    
    Convenção do projeto: phone_number sempre em formato E.164 com `+`
    (igual ao que o Twilio webhook usa). Como `+` em query string HTTP é
    interpretado como espaço (RFC 1738 legacy), o caller pode mandar tanto
    `?user_id=+55...` quanto `?user_id=%2B55...` — normalizamos os dois
    pro mesmo formato canônico.
    """
    # Normaliza pra E.164: aceita tanto "+55..." quanto " 55..." (que é o
    # que chega quando o caller mandou "+" sem URL-encoding) quanto "55..."
    # cru, e padroniza pra sempre ter o "+" no começo.
    user_id = user_id.strip()
    if not user_id:
        return _html_response(  # type: ignore[return-value]
            "Erro",
            "<h1>Erro</h1><p>user_id vazio.</p>",
            status=400,
        )
    if not user_id.startswith("+"):
        user_id = "+" + user_id

    state = _issue_state(user_id)
    auth_url = google_provider.build_authorization_url(state=state)

    logger.info(
        "oauth_start",
        user_id=user_id,
        state_prefix=state[:12],
    )
    return RedirectResponse(url=auth_url, status_code=307)

@router.get("/oauth/google/callback")
async def oauth_google_callback(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
) -> HTMLResponse:
    """Callback do Google. Valida state, troca code por tokens,
    persiste, mostra HTML de sucesso."""
    # Caso 1: usuário negou consent (ou outro erro do Google).
    if error:
        logger.info("oauth_callback_denied", error=error)
        return _html_response(
            "Autorização cancelada",
            "<h1>Autorização cancelada</h1>"
            "<p>Volte pro terminal e rode de novo se quiser tentar.</p>"
            f"<p><small>Motivo reportado pelo Google: <code>{error}</code></small></p>",
        )

    # Caso 2: state ou code ausente → malformed request.
    if not state or not code:
        return _html_response(
            "Requisição inválida",
            "<h1>Requisição inválida</h1>"
            "<p>Faltando <code>code</code> ou <code>state</code>.</p>",
            status=400,
        )

    # Caso 3: state desconhecido ou expirado → CSRF / TTL.
    user_id = _consume_state(state)
    if user_id is None:
        logger.warning("oauth_callback_invalid_state", state_prefix=state[:12])
        return _html_response(
            "State inválido ou expirado",
            "<h1>State inválido ou expirado</h1>"
            "<p>Tente de novo abrindo "
            "<code>/oauth/google/start?user_id=...</code>.</p>",
            status=400,
        )

    pool = await get_pool()
    org_id = await get_default_org_id(pool)

    # Troca o code por tokens + descobre email.
    token_response = await google_provider.exchange_code_for_tokens(code=code)

    # Persiste via service (criptografa e upserta).
    creds = await service.save_credentials(
        organization_id=org_id,
        user_id=user_id,
        provider="google",
        provider_user_id=token_response.email,
        scopes=token_response.scopes,
        access_token=token_response.access_token,
        refresh_token=token_response.refresh_token,
        token_type=token_response.token_type,
        expires_at=token_response.expires_at,
    )

    logger.info(
        "oauth_callback_success",
        user_id=user_id,
        provider_user_id=creds.provider_user_id,
        scopes=creds.scopes,
        expires_at=creds.expires_at.isoformat(),
    )

    account = creds.provider_user_id or "desconhecida"
    return _html_response(
        "Autorização concluída",
        "<h1>✅ Autorização concluída</h1>"
        "<p>Você pode fechar essa aba e voltar pro terminal.</p>"
        f"<p>Conta autorizada: <code>{account}</code></p>",
    )
