"""Provider Google — tudo que é específico do Google OAuth2 mora aqui.

O `oauth/service.py` nunca importa este módulo diretamente; quem
importa é quem conhece Google (rotas do OAuth, helper de Calendar
client, Fatia 3.3+). Isso mantém o `service.py` provider-agnostic.

Pontos importantes:
- `build_authorization_url` usa `access_type=offline` + `prompt=consent`
  hardcoded. Não é configurável. É o que garante que cada autorização
  devolva `refresh_token`, evitando o caso degenerado de ficar com
  access_token mas sem capacidade de renovar.
- Cliente OAuth é montado em memória a partir das env vars; nunca
  lemos um `client_secret.json` do disco (defesa contra vazamento
  tipo o que rolou hoje).
- `exchange_code_for_tokens` descobre o email via userinfo endpoint
  (não via id_token — nosso scope `calendar.events` não inclui
  `openid`, então o id_token não viria). Se userinfo falhar, seguimos
  com `email=None`, porque ele é auditoria e não chave.
- Zero retry defensivo nesta fatia. Refresh proativo em `is_expired`
  cobre 99% dos casos; 401 em runtime = revogação externa = re-auth
  humana (cenário raro, Fatia 3.3 se mostrar valor).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import structlog
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import Resource, build
from oauthlib.oauth2.rfc6749.errors import OAuth2Error
from pydantic import BaseModel, ConfigDict

from gyros_os.oauth import service
from gyros_os.oauth.models import OAuthCredentials, RefreshResult
from gyros_os.shared.config import settings

logger = structlog.get_logger()

# Endpoints oficiais — hardcoded porque são constantes do Google desde
# sempre e trocar de endpoint quebraria o mundo todo, não só a gente.
_AUTH_URI = "https://accounts.google.com/o/oauth2/auth"
_TOKEN_URI = "https://oauth2.googleapis.com/token"
_USERINFO_URI = "https://www.googleapis.com/oauth2/v2/userinfo"


# ---------- Exceções ----------


class GoogleCredentialsNotFound(Exception):
    """Nenhuma credencial Google persistida para este user_id."""

    def __init__(self, user_id: str) -> None:
        super().__init__(
            f"nenhuma credencial Google para user_id={user_id} — "
            f"rode o fluxo de autorização em /oauth/google/start"
        )
        self.user_id = user_id


# ---------- Modelo de resposta do Google ----------


class GoogleTokenResponse(BaseModel):
    """Resposta normalizada de um token exchange ou refresh do Google.

    `refresh_token` é `None` na esmagadora maioria dos refreshes — o
    Google só devolve novo refresh_token em raras condições. Ver
    COMMENT da coluna `refresh_token_encrypted` na migration 007 e o
    COALESCE em `service.save_credentials`.
    """

    model_config = ConfigDict(extra="forbid")

    access_token: str
    refresh_token: str | None
    expires_at: datetime
    token_type: str
    scopes: list[str]
    email: str | None


# ---------- Helpers internos ----------


def _client_config() -> dict:
    """Monta o dict que google_auth_oauthlib.Flow espera, em memória."""
    client_id = settings.google_oauth_client_id
    client_secret = (
        settings.google_oauth_client_secret.get_secret_value()
        if settings.google_oauth_client_secret is not None
        else ""
    )
    redirect_uri = settings.google_oauth_redirect_uri

    if not (client_id and client_secret and redirect_uri):
        raise RuntimeError(
            "GOOGLE_OAUTH_CLIENT_ID, GOOGLE_OAUTH_CLIENT_SECRET e "
            "GOOGLE_OAUTH_REDIRECT_URI precisam estar configuradas no .env"
        )

    return {
        "web": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [redirect_uri],
        }
    }


def _scopes_list() -> list[str]:
    raw = settings.google_oauth_scopes
    if not raw:
        raise RuntimeError("GOOGLE_OAUTH_SCOPES não configurado no .env")
    return [s.strip() for s in raw.split() if s.strip()]


def _redirect_uri() -> str:
    """Lê o redirect URI das settings, fail-fast se não configurado."""
    redirect_uri = settings.google_oauth_redirect_uri
    if not redirect_uri:
        raise RuntimeError("GOOGLE_OAUTH_REDIRECT_URI não configurada no .env")
    return redirect_uri


# ---------- API pública ----------


def build_authorization_url(*, state: str) -> str:
    """Constrói a URL de consent do Google para a Fatia 3.2.

    `access_type=offline` + `prompt=consent` são hardcoded — são o que
    garante que TODA autorização devolva `refresh_token`, incluindo as
    subsequentes. Sem isso, a segunda autorização só devolve
    access_token e a gente perde refresh.
    """
    flow = Flow.from_client_config(
        _client_config(),
        scopes=_scopes_list(),
        redirect_uri=_redirect_uri(),
    )
    flow.redirect_uri = _redirect_uri()
    # Desabilita PKCE: este é confidential client (Web application com client_secret),
    # segurança vem do client_secret. PKCE é necessário só pra public clients.
    flow.code_verifier = ""  # type: ignore[attr-defined]
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        prompt="consent",
        include_granted_scopes="true",
        state=state,
    )
    return auth_url


async def _fetch_userinfo(access_token: str) -> str | None:
    """GET /oauth2/v2/userinfo — retorna email ou None em caso de erro.

    Não aborta autorização se userinfo falhar — o email é auditoria,
    não é chave. Log específico pra distinguir de outras falhas.
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                _USERINFO_URI,
                headers={"Authorization": f"Bearer {access_token}"},
            )
        if resp.status_code != 200:
            logger.warning(
                "oauth_userinfo_failed",
                status_code=resp.status_code,
            )
            return None
        data = resp.json()
        email = data.get("email")
        return email if isinstance(email, str) else None
    except httpx.HTTPError as e:
        logger.warning("oauth_userinfo_failed", error=str(e))
        return None


async def exchange_code_for_tokens(*, code: str) -> GoogleTokenResponse:
    """Troca o `code` do callback pelo par (access_token, refresh_token).

    Também descobre o email da conta via userinfo endpoint (nosso scope
    `calendar.events` não inclui `openid`, então não dá pra decodar
    id_token — userinfo é o caminho simples).
    """
    flow = Flow.from_client_config(
        _client_config(),
        scopes=_scopes_list(),
        redirect_uri=_redirect_uri(),
    )

    # Log defensivo antes do exchange — sem vazar o code completo
    # (prefixo basta pra correlação com o log de oauth_start).
    logger.info(
        "oauth_token_exchange_attempt",
        code_prefix=code[:8],
        code_len=len(code),
        redirect_uri=settings.google_oauth_redirect_uri,
        client_id_prefix=settings.google_oauth_client_id[:12],
    )

    # Síncrono deliberado: fetch_token roda uma vez por autorização,
    # low traffic (só a Camila autorizando a própria agenda em dev).
    # Bloqueia o event loop pela duração da chamada (~500ms-2s), o que
    # é aceitável pro nível de tráfego atual.
    # TODO: quando virar multi-user (v0.2), mover pra run_in_executor
    # pra não bloquear event loop.
    #
    # code_verifier="" desabilita PKCE: este é confidential client
    # (Web application com client_secret), segurança vem do client_secret.
    # PKCE é necessário só pra public clients (mobile/SPA).
    try:
        flow.fetch_token(code=code, code_verifier="")
    except OAuth2Error as exc:
        logger.error(
            "oauth_token_exchange_failed",
            error=exc.error,
            description=getattr(exc, "description", None),
            uri=getattr(exc, "uri", None),
            status_code=getattr(exc, "status_code", None),
        )
        raise

    google_creds: Credentials = flow.credentials  # type: ignore[assignment]

    if google_creds.expiry is None:
        raise RuntimeError("token exchange não devolveu expiry")
    # `google.oauth2.credentials.Credentials.expiry` é naive UTC. Anexa
    # tzinfo explicitamente pra não ter surpresa de comparação depois.
    expires_at = google_creds.expiry.replace(tzinfo=UTC)

    access_token = google_creds.token
    if not access_token:
        raise RuntimeError("token exchange não devolveu access_token")

    email = await _fetch_userinfo(access_token)

    return GoogleTokenResponse(
        access_token=access_token,
        refresh_token=google_creds.refresh_token,
        expires_at=expires_at,
        token_type="Bearer",
        scopes=list(google_creds.scopes or _scopes_list()),
        email=email,
    )


async def refresh_access_token(*, refresh_token: str) -> RefreshResult:
    """POST /token com grant_type=refresh_token.

    Retorna `RefreshResult` (TypedDict definido em `oauth/models.py`) —
    é o contrato de boundary entre providers provider-specific e o
    service provider-agnostic. O service não importa tipos do Google;
    qualquer provider futuro só precisa implementar esse mesmo shape.

    Note que o Google quase nunca devolve `refresh_token` novo no
    response de refresh — ele assume que o caller já tem o original
    persistido. Por isso `refresh_token` no RefreshResult retornado
    aqui é tipicamente None, e o `service.refresh_if_needed` faz
    fallback pro valor existente via COALESCE no UPSERT.
    """
    client_id = settings.google_oauth_client_id
    client_secret = (
        settings.google_oauth_client_secret.get_secret_value()
        if settings.google_oauth_client_secret is not None
        else ""
    )
    if not (client_id and client_secret):
        raise RuntimeError(
            "GOOGLE_OAUTH_CLIENT_ID e GOOGLE_OAUTH_CLIENT_SECRET "
            "precisam estar configuradas no .env"
        )

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            _TOKEN_URI,
            data={
                "grant_type": "refresh_token",
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    if resp.status_code != 200:
        # Não logamos o body — pode conter error_description com
        # pedaços do refresh_token em alguns casos patológicos.
        logger.warning("oauth_refresh_failed", status_code=resp.status_code)
        raise RuntimeError(f"refresh_token falhou no Google: HTTP {resp.status_code}")

    data = resp.json()

    access_token = data.get("access_token")
    if not access_token:
        raise RuntimeError("refresh response do Google sem access_token")

    expires_in = data.get("expires_in")
    if not expires_in:
        raise RuntimeError("refresh response do Google sem expires_in")

    expires_at = datetime.now(UTC) + timedelta(seconds=int(expires_in))

    # Google às vezes devolve `scope` (singular, string space-separated)
    # no refresh response. Quase nunca devolve `refresh_token` novo.
    raw_scope = data.get("scope")
    scopes_list = (
        raw_scope.split() if isinstance(raw_scope, str) and raw_scope else None
    )

    logger.info(
        "oauth_token_refreshed",
        provider="google",
        expires_at=expires_at.isoformat(),
    )

    return RefreshResult(
        access_token=access_token,
        expires_at=expires_at,
        token_type=data.get("token_type") or "Bearer",
        refresh_token=data.get("refresh_token"),  # quase sempre None
        scopes=scopes_list,  # pode ser None — service faz fallback
    )


async def get_google_calendar_client(*, user_id: str) -> Resource:
    """Helper público — Fatia 3.3 vai chamar isso no executor.

    Passo a passo:
    1. Busca credencial no banco.
    2. Refresh proativo se expirado (margem de 60s).
    3. Monta `google.oauth2.credentials.Credentials` do SDK.
    4. `googleapiclient.discovery.build("calendar", "v3", ...)`.
    """
    creds = await service.get_credentials(user_id=user_id, provider="google")
    if creds is None:
        raise GoogleCredentialsNotFound(user_id)

    creds = await service.refresh_if_needed(
        creds,
        refresh_fn=refresh_access_token,
    )

    google_creds = _build_google_credentials(creds)

    return build(
        "calendar",
        "v3",
        credentials=google_creds,
        cache_discovery=False,
    )


async def get_google_drive_client(*, user_id: str) -> Resource:
    """Helper público — cliente Drive autenticado.

    Espelha `get_google_calendar_client` mas constrói cliente Drive.
    Mesma garantia de refresh proativo: busca credencial, refresha se
    perto de expirar, e devolve um Resource pronto pra uso. Requer
    que o scope `drive` (ou `drive.readonly`/`drive.file`) esteja
    incluído em `GOOGLE_OAUTH_SCOPES` no momento da autorização.
    """
    creds = await service.get_credentials(user_id=user_id, provider="google")
    if creds is None:
        raise GoogleCredentialsNotFound(user_id)

    creds = await service.refresh_if_needed(
        creds,
        refresh_fn=refresh_access_token,
    )

    google_creds = _build_google_credentials(creds)

    return build(
        "drive",
        "v3",
        credentials=google_creds,
        cache_discovery=False,
    )


def _build_google_credentials(creds: OAuthCredentials) -> Credentials:
    """Converte nossa OAuthCredentials no Credentials do SDK do Google.

    Lê client_id e client_secret das settings — o SDK precisa deles
    pra fazer refresh interno se o token expirar durante uso (a gente
    já fez refresh proativo antes, mas o SDK também faz refresh sob
    demanda em alguns code paths).
    """
    client_id = settings.google_oauth_client_id
    client_secret = (
        settings.google_oauth_client_secret.get_secret_value()
        if settings.google_oauth_client_secret is not None
        else ""
    )

    return Credentials(
        token=creds.access_token,
        refresh_token=creds.refresh_token,
        token_uri=_TOKEN_URI,
        client_id=client_id,
        client_secret=client_secret,
        scopes=creds.scopes,
    )
