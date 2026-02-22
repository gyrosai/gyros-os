"""Webhook do Twilio — processamento assíncrono via fila.

Recebe mensagens do Twilio, valida, aplica rate limit, e coloca na fila
para processamento pelo Worker. Retorna 200 imediatamente (TwiML vazio).

Fluxo: Twilio -> POST /webhook/twilio -> Fila (PostgreSQL) -> Worker

Uso:
    curl -X POST ".../webhook/twilio?agent=rhawk_assistant" \
         -d "MessageSid=SM123&From=whatsapp:+5511..."
"""

import structlog
from fastapi import APIRouter, Depends, Form, Query, Response

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
    agent: str = Query(
        description="ID do agente para processar a mensagem",
    ),
    message_sid: str = Form(
        default="",
        alias="MessageSid",
        description="ID da mensagem no Twilio (MessageSid).",
    ),
    from_number: str = Form(
        default="",
        alias="From",
        description="Número remetente no formato whatsapp:+55...",
    ),
    to_number_form: str = Form(
        default="",
        alias="To",
        description="Número de destino no formato whatsapp:+...",
    ),
    body: str = Form(
        default="",
        alias="Body",
        description="Texto da mensagem (pode ser vazio em mensagens de mídia).",
    ),
    num_media_raw: str = Form(
        default="0",
        alias="NumMedia",
        description="Quantidade de mídias anexadas.",
    ),
    media_url_form: str | None = Form(
        default=None,
        alias="MediaUrl0",
        description="URL da primeira mídia (quando NumMedia > 0).",
    ),
    media_type_form: str | None = Form(
        default=None,
        alias="MediaContentType0",
        description="MIME type da primeira mídia.",
    ),
    _signature: None = Depends(validate_twilio_signature),
) -> Response:
    """Recebe webhook do Twilio e enfileira para processamento.

    O Worker vai consumir a mensagem da fila, executar o agente,
    e salvar a resposta no banco. O envio via Twilio será na Fase 4.

    Args:
        agent: ID do agente (query param).

    Returns:
        TwiML vazio com status 200.
    """
    # Verifica se o agente existe
    available_agents = list_agents()
    if agent not in available_agents:
        raise AgentNotFoundError(agent)

    # Sanitização de campos do Twilio recebidos via x-www-form-urlencoded
    phone_number = (from_number or "").replace("whatsapp:", "")
    body = body or ""
    to_number = (to_number_form or "").replace("whatsapp:", "")
    message_sid = message_sid or ""

    # Mídia (imagem, áudio)
    try:
        num_media = int(num_media_raw or "0")
    except ValueError:
        num_media = 0
    media_url = media_url_form.strip() if (num_media > 0 and media_url_form) else None
    media_type = (
        media_type_form.strip() if (num_media > 0 and media_type_form) else None
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
