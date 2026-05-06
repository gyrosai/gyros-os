"""Pipefy GraphQL client — leitura de cards/fases e atualização de campos.

Espelha o padrão de `FirefliesClient`: httpx async, Pydantic para
parsing tolerante, structlog sem secrets. O escopo desta fatia é
deliberadamente mínimo (apenas o que `drive_sync` da Fatia 5.2 vai
consumir): get_card, get_cards_in_phase, update_card_field.

Por que GraphQL "cru" e não um SDK:
- O ecossistema Python pra Pipefy é raso e a API GraphQL é estável.
- Mantemos consistência com Fireflies (mesmo shape de cliente),
  o que reduz superfície cognitiva pra quem mexer depois.
- Pydantic com `extra="allow"` deixa novos campos da API passarem
  sem quebrar parsing — Pipefy adiciona campos com frequência.

Logs:
- Eventos de sucesso/erro têm nomes estáveis (`pipefy_card_fetched`,
  `pipefy_card_field_updated`) pra serem observáveis sem grepar texto.
- O token NUNCA aparece em log — nem prefixo, nem hash. Auth é
  binária (funciona/não funciona); não há ganho em logar fragmentos.
"""

from __future__ import annotations

import time

import httpx
import structlog
from pydantic import BaseModel, ConfigDict, ValidationError

from gyros_os.shared.config import settings

logger = structlog.get_logger()

GRAPHQL_URL = "https://api.pipefy.com/graphql"

# Query principal: traz tudo que `drive_sync` precisa pra decidir o
# que fazer com o card (título, fase atual, todos os campos com label
# legível pra debugging). `field.value` é string serializada — campos
# de seleção múltipla vêm como JSON-string do array; quem usa o helper
# `extract_field` não precisa se preocupar com isso na maioria dos casos.
CARD_QUERY = """
query Card($cardId: ID!) {
  card(id: $cardId) {
    id
    title
    current_phase {
      id
      name
    }
    fields {
      name
      value
      field {
        id
        internal_id
        label
        type
      }
    }
  }
}
"""

# Listagem paginada de cards numa fase. Pegamos só id + title porque
# o caso de uso é "achar quais cards estão na fase X pra processar"
# — quem precisa do detalhe chama `get_card(id)` depois.
PHASE_CARDS_QUERY = """
query PhaseCards($phaseId: ID!, $after: String) {
  phase(id: $phaseId) {
    cards(first: 50, after: $after) {
      pageInfo {
        hasNextPage
        endCursor
      }
      edges {
        node {
          id
          title
        }
      }
    }
  }
}
"""

# Mutation pra atualizar UM campo de UM card. `new_value` é sempre
# lista de strings — para campos single-value, mande lista de 1
# elemento. Decisão da própria API do Pipefy.
UPDATE_CARD_FIELD_MUTATION = """
mutation UpdateCardField(
  $cardId: ID!,
  $fieldId: ID!,
  $newValue: [UndefinedInput!]!
) {
  updateCardField(input: {
    card_id: $cardId,
    field_id: $fieldId,
    new_value: $newValue
  }) {
    success
  }
}
"""


# ---------- Exceções ----------


class PipefyError(Exception):
    """Erro genérico do cliente Pipefy (rede, GraphQL, parsing)."""


class PipefyAuthError(PipefyError):
    """Token inválido/ausente (HTTP 401)."""


class PipefyNotFound(PipefyError):
    """Card/fase não encontrado (HTTP 404 ou null no response)."""


# ---------- Modelos ----------


class PipefyField(BaseModel):
    """Um campo de um card do Pipefy.

    A API retorna o valor "humano" no nível do `field` do card, mas
    os identificadores estáveis (id, internal_id) ficam aninhados em
    `field { ... }`. A gente achata isso em uma estrutura única
    porque é assim que o resto do código vai consumir.
    """

    model_config = ConfigDict(extra="allow")

    name: str
    value: str | None = None
    field_id: str
    internal_id: str
    label: str
    type: str


class CardSummary(BaseModel):
    """Resumo de card (id + título) — usado em listagens de fase."""

    model_config = ConfigDict(extra="allow")

    id: str
    title: str


class CardPhase(BaseModel):
    """Fase atual de um card."""

    model_config = ConfigDict(extra="allow")

    id: str
    name: str


class CardData(BaseModel):
    """Card completo do Pipefy, achatado pra consumo direto."""

    model_config = ConfigDict(extra="allow")

    id: str
    title: str
    current_phase: CardPhase
    fields: list[PipefyField] = []


# ---------- Cliente ----------


class PipefyClient:
    """Cliente mínimo da API GraphQL do Pipefy.

    Usa Bearer token vindo das settings. Não tem retry — a Fatia 5.2
    (drive_sync) é idempotente por design, então uma falha transiente
    é resolvida na próxima execução do worker, não numa retry interna.
    """

    def __init__(self, token: str | None = None) -> None:
        # Aceita override via parâmetro pra facilitar testes; em
        # produção, lê do settings. Mesmo padrão do FirefliesClient.
        self._token = token or (
            settings.pipefy_token.get_secret_value()
            if settings.pipefy_token is not None
            else ""
        )

    # ------- Internals -------

    async def _post(self, query: str, variables: dict) -> dict:
        """Executa um POST GraphQL, normalizando erros HTTP/GraphQL.

        Retorna o conteúdo de `data` quando bem-sucedido. Levanta
        `PipefyAuthError`, `PipefyNotFound` ou `PipefyError` conforme
        a categoria do erro. Não inclui o token em nenhum log.
        """
        if not self._token:
            raise PipefyAuthError(
                "PIPEFY_TOKEN não configurado — preencha no .env"
            )

        start = time.monotonic()

        async with httpx.AsyncClient() as http:
            response = await http.post(
                GRAPHQL_URL,
                json={"query": query, "variables": variables},
                headers={
                    "Authorization": f"Bearer {self._token}",
                    "Content-Type": "application/json",
                },
                timeout=30.0,
            )

        latency_ms = round((time.monotonic() - start) * 1000)

        if response.status_code == 401:
            logger.error("pipefy_auth_error", latency_ms=latency_ms)
            raise PipefyAuthError("Token Pipefy inválido")

        if response.status_code == 404:
            logger.warning("pipefy_not_found", latency_ms=latency_ms)
            raise PipefyNotFound("Recurso Pipefy não encontrado")

        response.raise_for_status()

        payload = response.json()

        # GraphQL pode devolver 200 com erros no body. Diferenciamos
        # "não encontrado" de erros gerais inspecionando a mensagem,
        # porque a API não usa códigos de erro estruturados aqui.
        if "errors" in payload:
            error_msg = payload["errors"][0].get("message", "Erro GraphQL")
            logger.error(
                "pipefy_graphql_error",
                error=error_msg,
                latency_ms=latency_ms,
            )
            lower = error_msg.lower()
            if "not found" in lower or "não encontrado" in lower:
                raise PipefyNotFound(error_msg)
            raise PipefyError(error_msg)

        return payload.get("data") or {}

    # ------- API pública -------

    async def get_card(self, card_id: str) -> CardData:
        """Busca um card por id, com fase atual e todos os campos."""
        data = await self._post(CARD_QUERY, {"cardId": card_id})

        raw = data.get("card")
        if raw is None:
            logger.warning("pipefy_card_null", card_id=card_id)
            raise PipefyNotFound(f"Card não encontrado: {card_id}")

        # Achata `field { id, internal_id, label, type }` no nível
        # do PipefyField — ver docstring do modelo.
        flattened_fields = []
        for f in raw.get("fields") or []:
            inner = f.get("field") or {}
            flattened_fields.append(
                {
                    "name": f.get("name"),
                    "value": f.get("value"),
                    "field_id": inner.get("id"),
                    "internal_id": inner.get("internal_id"),
                    "label": inner.get("label"),
                    "type": inner.get("type"),
                }
            )

        try:
            card = CardData(
                id=raw["id"],
                title=raw["title"],
                current_phase=CardPhase(**raw["current_phase"]),
                fields=[PipefyField(**f) for f in flattened_fields],
            )
        except (ValidationError, KeyError) as e:
            logger.error(
                "pipefy_card_validation_failed",
                card_id=card_id,
                error=str(e),
            )
            raise PipefyError(f"Falha ao parsear card {card_id}: {e}") from e

        logger.info(
            "pipefy_card_fetched",
            card_id=card.id,
            title=card.title,
            phase_id=card.current_phase.id,
            num_fields=len(card.fields),
        )
        return card

    async def get_cards_in_phase(self, phase_id: str) -> list[CardSummary]:
        """Lista todos os cards de uma fase, paginando até o fim.

        Pipefy pagina em 50 por página via cursor; a gente percorre
        tudo aqui porque o caso de uso (varrer "Formalização") tem
        cardinalidade baixa (dezenas, não milhares). Se virar gargalo
        depois, vira generator.
        """
        cards: list[CardSummary] = []
        after: str | None = None

        while True:
            data = await self._post(
                PHASE_CARDS_QUERY,
                {"phaseId": phase_id, "after": after},
            )
            phase = data.get("phase")
            if phase is None:
                logger.warning("pipefy_phase_null", phase_id=phase_id)
                raise PipefyNotFound(f"Fase não encontrada: {phase_id}")

            connection = phase.get("cards") or {}
            edges = connection.get("edges") or []
            for edge in edges:
                node = edge.get("node") or {}
                try:
                    cards.append(CardSummary(**node))
                except ValidationError as e:
                    logger.warning(
                        "pipefy_card_summary_skip",
                        phase_id=phase_id,
                        error=str(e),
                    )

            page_info = connection.get("pageInfo") or {}
            if not page_info.get("hasNextPage"):
                break
            after = page_info.get("endCursor")
            if not after:
                # Defesa: hasNextPage=true sem cursor seria bug do Pipefy;
                # paramos aqui pra evitar loop infinito.
                break

        logger.info(
            "pipefy_phase_listed",
            phase_id=phase_id,
            num_cards=len(cards),
        )
        return cards

    async def update_card_field(
        self,
        card_id: str,
        field_id: str,
        new_value: list[str],
    ) -> bool:
        """Atualiza um campo de um card. Retorna True em sucesso.

        `new_value` é lista de strings mesmo para campos single-value
        (decisão da API do Pipefy — passe lista de 1 elemento). O
        método não tenta inferir o tipo de campo: o caller sabe o que
        está atualizando.
        """
        data = await self._post(
            UPDATE_CARD_FIELD_MUTATION,
            {"cardId": card_id, "fieldId": field_id, "newValue": new_value},
        )

        result = data.get("updateCardField") or {}
        success = bool(result.get("success"))

        logger.info(
            "pipefy_card_field_updated",
            card_id=card_id,
            field_id=field_id,
            success=success,
            # Não logamos `new_value` — pode conter PII (link de pasta
            # com dados pessoais do instrutor). Card+field+success já
            # são suficientes pra rastrear o que aconteceu.
        )
        return success

    # ------- Helper utilitário -------

    @staticmethod
    def extract_field(card: CardData, field_id: str) -> str | None:
        """Acha o valor de um campo pelo `field_id` (slug estável).

        Retorna `None` se o campo não existir ou estiver vazio.
        Útil porque a API entrega campos como lista — o lookup
        repetitivo "achar pelo id" é o caso comum em handlers.
        """
        for f in card.fields:
            if f.field_id == field_id:
                return f.value or None
        return None
