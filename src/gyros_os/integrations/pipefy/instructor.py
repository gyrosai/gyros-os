"""Modelo `InstructorInfo` — dados extraídos de um card CIMI360 Curadoria.

Constrói-se a partir de um `CardData` do `PipefyClient`, lendo cada
campo via `extract_field` (helper estático da Fatia 5.1) usando os
internal_ids do `CIMI360_2026_FIELD_IDS`.

POR QUÊ Pydantic e não dict: o consumidor (drive_sync) lê 15 campos
opcionais. Pydantic dá schema explícito + defaults seguros (campos
faltantes viram string vazia em vez de KeyError) + serializa direto pro
`event_queue.result` quando incluído em `SyncResult`.
"""

from __future__ import annotations

import json

import structlog
from pydantic import BaseModel, Field

from gyros_os.integrations.pipefy.client import CardData, PipefyClient
from gyros_os.integrations.pipefy.field_mapping import CIMI360_2026_FIELD_IDS

logger = structlog.get_logger()


def _parse_json_array(value: str | None) -> list[str]:
    """Parser tolerante para JSON array string do Pipefy.

    Multi-select e attachments do Pipefy chegam como string JSON-serializada
    (`'["a","b"]'`). Strings vazias, None ou JSON inválido viram lista
    vazia silenciosamente — handler upstream loga o caso, drive_sync
    segue com `foto_url=""`.
    """
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(parsed, list):
        return []
    return [str(x) for x in parsed if x is not None and str(x).strip()]


class InstructorInfo(BaseModel):
    """Dados extraídos de um card do pipe CIMI360 Curadoria.

    Campos texto vêm stripped. `categoria_oficina` é JSON array no Pipefy
    (multi-select); aqui virou `list[str]`. `foto_url` é a primeira URL
    do array de anexos (Pipefy permite múltiplos, mas o template pede 1).
    """

    card_id: str
    card_title: str
    nome: str
    foto_url: str = ""
    minibio: str = ""
    empresa: str = ""
    cargo: str = ""
    cidade: str = ""
    uf: str = ""
    telefone: str = ""
    email: str = ""
    linkedin: str = ""
    instagram: str = ""
    cpf: str = ""
    categoria_oficina: list[str] = Field(default_factory=list)
    tema_oficina: str = ""
    tema_outro: str = ""

    @classmethod
    def from_card(cls, card: CardData) -> "InstructorInfo":
        """Constrói InstructorInfo a partir de um CardData do PipefyClient.

        POR QUÊ fallback nome→title: pessoas às vezes deixam `nome_completo`
        em branco mas preenchem o título do card manualmente; pra não
        criar uma pasta `(sem nome)` no Drive, caímos no título.
        """
        get = lambda key: PipefyClient.extract_field(  # noqa: E731
            card, CIMI360_2026_FIELD_IDS[key]
        )

        nome = (get("nome_completo") or card.title or "").strip()

        foto_arr = _parse_json_array(get("foto"))
        foto_url = foto_arr[0] if foto_arr else ""

        categorias = _parse_json_array(get("categoria_oficina"))

        return cls(
            card_id=card.id,
            card_title=card.title,
            nome=nome,
            foto_url=foto_url,
            minibio=(get("minibio") or "").strip(),
            empresa=(get("empresa") or "").strip(),
            cargo=(get("cargo") or "").strip(),
            cidade=(get("cidade") or "").strip(),
            uf=(get("uf") or "").strip(),
            telefone=(get("telefone") or "").strip(),
            email=(get("email") or "").strip(),
            linkedin=(get("linkedin") or "").strip(),
            instagram=(get("instagram") or "").strip(),
            cpf=(get("cpf") or "").strip(),
            categoria_oficina=[c.strip() for c in categorias if c.strip()],
            tema_oficina=(get("tema_oficina") or "").strip(),
            tema_outro=(get("tema_outro") or "").strip(),
        )
