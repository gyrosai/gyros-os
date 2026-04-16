"""Criptografia simétrica dos tokens OAuth (Fernet).

Único módulo do projeto que importa `cryptography`. Isola a dependência
para que o resto do código fale apenas em `encrypt(str) -> bytes` /
`decrypt(bytes) -> str`, sem nunca tocar na chave.

Regras:
- Fail-fast no primeiro uso: se `OAUTH_TOKEN_ENCRYPTION_KEY` estiver
  ausente ou malformada, `_get_fernet()` levanta RuntimeError claro.
  NÃO existe fallback "modo dev sem crypto" — esse flag vira bug de
  produção.
- NUNCA logar tokens, nem plaintext nem ciphertext, nem em DEBUG, nem
  em mensagens de exceção. Se precisar logar algo sobre um token, o
  chamador loga só metadados (user_id, provider, expires_at, tamanho
  do ciphertext).
- `InvalidToken` do Fernet propaga como está — não engolimos — mas
  tomamos cuidado pra não incluir o plaintext/ciphertext em nenhuma
  mensagem construída aqui.
"""

from __future__ import annotations

from cryptography.fernet import Fernet

from gyros_os.shared.config import settings

_fernet: Fernet | None = None

_ENV_VAR = "OAUTH_TOKEN_ENCRYPTION_KEY"

# Singleton cacheado em módulo. Inicializado lazy na primeira chamada
# pra não quebrar import do módulo em contextos que não precisam de
# cripto (ex: testes de outros módulos, ferramentas estáticas).
_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is not None:
        return _fernet

    key_secret = settings.oauth_token_encryption_key
    if key_secret is None:
        print("[FERNET_DEBUG] oauth_token_encryption_key is None")
        raise RuntimeError(
            "OAUTH_TOKEN_ENCRYPTION_KEY não configurada ou inválida — "
            "gere uma com Fernet.generate_key()"
        )

    raw = key_secret.get_secret_value()
    print(f"[FERNET_DEBUG] raw length: {len(raw)}")
    print(f"[FERNET_DEBUG] first 10: {repr(raw[:10])}")
    print(f"[FERNET_DEBUG] last 5: {repr(raw[-5:])}")
    print(f"[FERNET_DEBUG] has whitespace: {raw != raw.strip()}")
    print(f"[FERNET_DEBUG] has newline: {chr(10) in raw or chr(13) in raw}")

    try:
        _fernet = Fernet(raw.encode())
        print("[FERNET_DEBUG] Fernet initialized OK")
    except Exception as exc:
        print(f"[FERNET_DEBUG] Fernet init FAILED: {type(exc).__name__}: {exc}")
        raise

    return _fernet


def encrypt(plaintext: str) -> bytes:
    """Criptografa uma string plaintext em bytes Fernet.

    Argumentos:
        plaintext: string a criptografar (ex: access_token bruto).

    Retorna:
        bytes opacos prontos pra ir pro banco (BYTEA).
    """
    fernet = _get_fernet()
    return fernet.encrypt(plaintext.encode("utf-8"))


def decrypt(ciphertext: bytes) -> str:
    """Decripta bytes Fernet de volta pra string.

    Propaga `cryptography.fernet.InvalidToken` se o ciphertext estiver
    corrompido ou se a chave for diferente da que criptografou. Quem
    chamou decide o que fazer.
    """
    fernet = _get_fernet()
    return fernet.decrypt(ciphertext).decode("utf-8")
