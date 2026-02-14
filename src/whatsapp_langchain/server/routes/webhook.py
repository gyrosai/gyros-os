"""Webhook do Twilio — processamento assíncrono via fila.

Recebe mensagens do Twilio, valida, aplica rate limit, e coloca na fila
para processamento pelo Worker. Retorna 200 imediatamente (TwiML vazio).

Fluxo: Twilio -> POST /webhook/twilio -> Fila (PostgreSQL) -> Worker

Uso:
    curl -X POST ".../webhook/twilio?agent=rhawk_assistant" \
         -d "MessageSid=SM123&From=whatsapp:+5511..."
"""

import structlog
from fastapi import APIRouter, Depends, Query, Request, Response

from whatsapp_langchain.agents.loader import AgentNotFoundError, list_agents
from whatsapp_langchain.server.dependencies import (
    check_rate_limit,
    validate_twilio_signature,
)
from whatsapp_langchain.shared.config import settings
from whatsapp_langchain.shared.db import get_pool
from whatsapp_langchain.shared.queue import enqueue_or_buffer

logger = structlog.get_logger()

router = APIRouter(tags=["webhook"])

# TwiML vazio — indica ao Twilio que recebemos a mensagem
EMPTY_TWIML = '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'


@router.post("/webhook/twilio")
async def webhook_twilio(
    request: Request,
    agent: str = Query(
        description="ID do agente para processar a mensagem",
    ),
    _signature: None = Depends(validate_twilio_signature),
) -> Response:
    """Recebe webhook do Twilio e enfileira para processamento.

    O Worker vai consumir a mensagem da fila, executar o agente,
    e salvar a resposta no banco. O envio via Twilio será na Fase 4.

    Args:
        request: Request com form data do Twilio.
        agent: ID do agente (query param).

    Returns:
        TwiML vazio com status 200.
    """
    # Verifica se o agente existe
    available_agents = list_agents()
    if agent not in available_agents:
        raise AgentNotFoundError(agent)

    # Parse do form data do Twilio
    form = await request.form()

    # Extrai campos como string (form data do Twilio é sempre texto)
    phone_number = str(form.get("From", "")).replace("whatsapp:", "")
    body = str(form.get("Body", ""))
    to_number = str(form.get("To", "")).replace("whatsapp:", "")
    message_sid = str(form.get("MessageSid", ""))

    # Mídia (imagem, áudio)
    num_media = int(str(form.get("NumMedia", "0")))
    media_url: str | None = str(form.get("MediaUrl0")) if num_media > 0 else None
    media_type: str | None = (
        str(form.get("MediaContentType0")) if num_media > 0 else None
    )

    # Rate limit
    await check_rate_limit(phone_number)

    # Enfileira a mensagem
    pool = await get_pool()
    result = await enqueue_or_buffer(
        pool=pool,
        phone_number=phone_number,
        agent_id=agent,
        body=body,
        media_url=media_url,
        media_type=media_type,
        to_number=to_number,
        message_id=message_sid,
        buffer_seconds=settings.message_buffer_seconds,
    )

    logger.info(
        "webhook_twilio_received",
        phone=phone_number,
        agent_id=agent,
        message_id=result.message_id,
        buffered=result.is_buffered,
    )

    return Response(content=EMPTY_TWIML, media_type="application/xml")
