"""Modelos Pydantic do módulo OAuth.

`OAuthCredentials` é o objeto que circula DENTRO do código depois de
decriptar os tokens. O que vai pro banco é outra coisa (bytes Fernet em
colunas BYTEA). Esta struct só existe em memória e nunca deve ser
serializada pra log, dump, resposta HTTP, ou qualquer outra saída.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import NotRequired, TypedDict
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class RefreshResult(TypedDict):
    """Shape do retorno de `refresh_fn` injetado em `service.refresh_if_needed`.

    É o contrato de boundary entre o `oauth/service.py` (provider-agnostic)
    e os `oauth/providers/*` (provider-specific). Tipa o dict sem o
    service precisar importar tipos específicos de nenhum provider —
    quando aparecer um segundo provider, ele só precisa implementar
    esse mesmo shape.
    """

    access_token: str
    expires_at: datetime
    token_type: NotRequired[str | None]
    refresh_token: NotRequired[str | None]
    scopes: NotRequired[list[str] | None]


class OAuthCredentials(BaseModel):
    """Credenciais OAuth2 decriptadas de um par (user_id, provider).

    Os campos `access_token` e `refresh_token` são PLAINTEXT nesta
    struct — só existem em memória, nunca vão pra log nem pra banco.
    O que o banco guarda são os mesmos valores criptografados via
    Fernet em colunas BYTEA separadas.
    """

    model_config = ConfigDict(extra="forbid")

    id: int
    organization_id: UUID
    user_id: str
    provider: str
    provider_user_id: str | None
    scopes: list[str]
    access_token: str
    refresh_token: str | None
    token_type: str
    expires_at: datetime
    created_at: datetime
    updated_at: datetime

    @property
    def is_expired(self) -> bool:
        """True se o token expira em menos de 60s (margem anti-race).

        Comparamos `expires_at` contra `now + 60s` para forçar refresh
        proativo e evitar que o token expire no meio de uma chamada ao
        Google. 60s cobre latência de rede, skew de relógio local vs
        servidor do Google, e o próprio tempo da chamada.
        """
        return self.expires_at <= datetime.now(UTC) + timedelta(seconds=60)
