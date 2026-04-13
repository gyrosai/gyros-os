"""Serviço OAuth provider-agnostic — persistência + refresh de tokens.

A camada que fala com o banco. Zero conhecimento de qual provider é
(Google, Microsoft, etc): quem souber das peculiaridades do provider
passa um `refresh_fn` como callable injetado em `refresh_if_needed`.

Padrões do projeto seguidos:
- psycopg3 (`async with pool.connection() as conn`, placeholders `%s`).
- `get_pool()` interno em cada função, não como parâmetro.
- Commit explícito.
- Log estruturado via structlog, sempre sem tokens (nem plaintext nem
  ciphertext — ver crypto.py).

A pegadinha principal mora em `save_credentials`: o Google não devolve
`refresh_token` em TODO fluxo de consent. Se a gente sobrescrever o
refresh_token existente com NULL num refresh subsequente, quebra toda
a capacidade de renovar o access_token no futuro. O UPSERT usa
`COALESCE(EXCLUDED.refresh_token_encrypted, oauth_credentials.refresh_token_encrypted)`
pra preservar o valor anterior quando o novo vem NULL.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime
from uuid import UUID

import structlog

from gyros_os.oauth.crypto import decrypt, encrypt
from gyros_os.oauth.models import OAuthCredentials, RefreshResult
from gyros_os.shared.db import get_pool

logger = structlog.get_logger()


# Tipo do callable injetado em `refresh_if_needed`. O caller (ex:
# providers/google.py) passa a função real que sabe falar com o token
# endpoint do provider. O shape do retorno (RefreshResult) é o boundary
# entre service provider-agnostic e providers/* provider-specific.
RefreshFn = Callable[..., Awaitable[RefreshResult]]


_SELECT_COLUMNS = """
    id, organization_id, user_id, provider, provider_user_id, scopes,
    access_token_encrypted, refresh_token_encrypted, token_type,
    expires_at, created_at, updated_at
"""


def _row_to_credentials(row: tuple) -> OAuthCredentials:
    """Converte uma linha de `oauth_credentials` em OAuthCredentials
    já decriptada. Nunca é chamada num contexto que loga o retorno."""
    refresh_ct = row[7]
    return OAuthCredentials(
        id=row[0],
        organization_id=row[1],
        user_id=row[2],
        provider=row[3],
        provider_user_id=row[4],
        scopes=list(row[5]) if row[5] is not None else [],
        access_token=decrypt(bytes(row[6])),
        refresh_token=decrypt(bytes(refresh_ct)) if refresh_ct is not None else None,
        token_type=row[8],
        expires_at=row[9],
        created_at=row[10],
        updated_at=row[11],
    )


# ---------- Persistência ----------


async def save_credentials(
    *,
    organization_id: UUID,
    user_id: str,
    provider: str,
    provider_user_id: str | None,
    scopes: list[str],
    access_token: str,
    refresh_token: str | None,
    token_type: str,
    expires_at: datetime,
) -> OAuthCredentials:
    """Upsert de credencial. Criptografa tokens antes de persistir.

    Preserva o `refresh_token_encrypted` existente se o novo vier NULL
    (caso típico do Google em re-autorização sem `prompt=consent`
    forçado). UPSERT num registro novo com refresh_token=None resolve
    para NULL mesmo — que é o comportamento correto (nunca houve um
    refresh_token anterior a preservar).

    Retorna a OAuthCredentials completa já decriptada, relida do row
    retornado pelo RETURNING — uma única roundtrip, sem race entre
    INSERT e SELECT.
    """
    access_ct = encrypt(access_token)
    refresh_ct = encrypt(refresh_token) if refresh_token is not None else None

    sql = f"""
        INSERT INTO oauth_credentials (
            organization_id, user_id, provider, provider_user_id,
            scopes, access_token_encrypted, refresh_token_encrypted,
            token_type, expires_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT ON CONSTRAINT uq_oauth_user_provider DO UPDATE SET
            provider_user_id = EXCLUDED.provider_user_id,
            scopes = EXCLUDED.scopes,
            access_token_encrypted = EXCLUDED.access_token_encrypted,
            refresh_token_encrypted = COALESCE(
                EXCLUDED.refresh_token_encrypted,
                oauth_credentials.refresh_token_encrypted
            ),
            token_type = EXCLUDED.token_type,
            expires_at = EXCLUDED.expires_at,
            updated_at = NOW()
        RETURNING {_SELECT_COLUMNS}
    """

    pool = await get_pool()
    async with pool.connection() as conn:
        cursor = await conn.execute(
            sql,
            (
                str(organization_id),
                user_id,
                provider,
                provider_user_id,
                scopes,
                access_ct,
                refresh_ct,
                token_type,
                expires_at,
            ),
        )
        row = await cursor.fetchone()
        await conn.commit()

    # RETURNING de um UPSERT sempre devolve 1 linha — a assertion é só
    # pra satisfazer o type checker (e falhar alto se algum dia não for).
    assert row is not None, "UPSERT com RETURNING retornou None"
    creds = _row_to_credentials(row)
    logger.info(
        "oauth_credentials_saved",
        user_id=user_id,
        provider=provider,
        provider_user_id=provider_user_id,
        scopes=scopes,
        expires_at=creds.expires_at.isoformat(),
    )
    return creds


async def get_credentials(
    *,
    user_id: str,
    provider: str,
) -> OAuthCredentials | None:
    """Busca credencial pelo par (user_id, provider). Decripta tokens."""
    pool = await get_pool()
    async with pool.connection() as conn:
        cursor = await conn.execute(
            f"""
            SELECT {_SELECT_COLUMNS}
            FROM oauth_credentials
            WHERE user_id = %s AND provider = %s
            """,
            (user_id, provider),
        )
        row = await cursor.fetchone()

    return _row_to_credentials(row) if row else None


# ---------- Refresh ----------


async def refresh_if_needed(
    creds: OAuthCredentials,
    *,
    refresh_fn: RefreshFn,
) -> OAuthCredentials:
    """Refresh proativo: se `creds.is_expired` (margem de 60s), chama
    `refresh_fn` pra obter um novo access_token e persiste via
    `save_credentials`. Senão, retorna `creds` como está.

    `refresh_fn` deve ser uma coroutine que aceita `refresh_token` como
    kwarg e retorna um dict com os campos:
        - access_token (str)
        - expires_at (datetime)
        - token_type (str)
        - scopes (list[str])
        - refresh_token (str | None, opcional — Google raramente devolve)

    Se o refresh falhar, propaga a exceção (não engole). O caller
    decide (ex: endpoint OAuth → 401 com re-auth; worker → HITL).
    """
    if not creds.is_expired:
        return creds

    if creds.refresh_token is None:
        # Sem refresh_token não há como renovar — força re-auth humana.
        raise RuntimeError(
            f"refresh_token ausente para user_id={creds.user_id} "
            f"provider={creds.provider} — re-autorização humana necessária"
        )

    refreshed = await refresh_fn(refresh_token=creds.refresh_token)

    # TODO: quando a 3.2 virar multi-scope, tratar `scope` (string
    # space-sep) do refresh response do Google e validar subset contra
    # scopes originalmente pedidos — o Google pode devolver menos do que
    # você pediu se o usuário desmarcou algo no consent. Por ora só
    # pedimos calendar.events, então fallback pra creds.scopes é seguro.
    new_creds = await save_credentials(
        organization_id=creds.organization_id,
        user_id=creds.user_id,
        provider=creds.provider,
        provider_user_id=creds.provider_user_id,
        scopes=list(refreshed.get("scopes") or creds.scopes),
        access_token=refreshed["access_token"],
        refresh_token=refreshed.get("refresh_token"),
        token_type=refreshed.get("token_type") or creds.token_type,
        expires_at=refreshed["expires_at"],
    )

    logger.info(
        "oauth_token_refreshed",
        user_id=new_creds.user_id,
        provider=new_creds.provider,
        expires_at=new_creds.expires_at.isoformat(),
    )
    return new_creds
