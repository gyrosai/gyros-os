"""FastAPI dependencies para validação e rate limiting.

Dependencies são injetadas automaticamente nas rotas via Depends().
Centralizar aqui mantém as rotas limpas e focadas na lógica de negócio.

Uso:
    from whatsapp_langchain.server.dependencies import check_rate_limit

    @router.post("/webhook/twilio")
    async def webhook(rate_limit: None = Depends(check_rate_limit)):
        ...
"""

import time
from collections import defaultdict

import structlog
from fastapi import HTTPException, Request

from whatsapp_langchain.shared.config import settings

logger = structlog.get_logger()

# Sliding window de requisições por telefone: {phone: [timestamps]}
request_history: dict[str, list[float]] = defaultdict(list)


async def validate_twilio_signature(request: Request) -> None:
    """Valida a assinatura X-Twilio-Signature do webhook.

    Só valida quando VALIDATE_TWILIO_SIGNATURE=true. Em desenvolvimento,
    essa validação é desabilitada por padrão.

    Nota: a validação completa requer o SDK do Twilio (Fase 4).
    Por ora, apenas verifica se o header existe quando habilitado.

    Raises:
        HTTPException 403: Se a assinatura é inválida.
    """
    if not settings.validate_twilio_signature:
        return

    signature = request.headers.get("X-Twilio-Signature")
    if not signature:
        logger.warning("twilio_signature_missing")
        raise HTTPException(status_code=403, detail="Missing Twilio signature")

    # Validação completa será implementada na Fase 4 com twilio SDK
    # Por ora, apenas verifica presença do header
    logger.debug("twilio_signature_present")


async def check_rate_limit(phone_number: str) -> None:
    """Verifica rate limit por número de telefone.

    Usa sliding window de 1 hora. Remove timestamps antigos e compara
    a quantidade de requisições com o limite configurado.

    Args:
        phone_number: Número de telefone do remetente.

    Raises:
        HTTPException 429: Se o limite foi atingido.
    """
    now = time.time()
    one_hour_ago = now - 3600

    # Remove timestamps antigos
    timestamps = request_history[phone_number]
    request_history[phone_number] = [t for t in timestamps if t > one_hour_ago]

    if len(request_history[phone_number]) >= settings.rate_limit_per_hour:
        logger.warning(
            "rate_limit_exceeded",
            phone=phone_number,
            count=len(request_history[phone_number]),
            limit=settings.rate_limit_per_hour,
        )
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Try again later.",
        )

    # Registra nova requisição
    request_history[phone_number].append(now)
