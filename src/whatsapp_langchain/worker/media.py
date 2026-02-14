"""Processamento de mídia (imagens e áudio).

Transforma mídias recebidas pelo WhatsApp em conteúdo que o LLM entende:
- Imagens → base64 para visão multimodal
- Áudio → transcrição via modelo multimodal (OpenRouter)

Tudo via OpenRouter — sem dependência de APIs separadas (Whisper, etc).

Nota: o download de mídia do Twilio usa httpx com Basic Auth
(account_sid:auth_token). O SDK Twilio será integrado na Fase 4.

Uso:
    from whatsapp_langchain.worker.media import build_human_message

    message = await build_human_message("Olá", media_url="...", media_type="image/jpeg")
"""

import base64

import httpx
import structlog
from langchain_core.messages import HumanMessage

from whatsapp_langchain.shared.config import settings

logger = structlog.get_logger()


async def download_media(
    url: str,
    account_sid: str = "",
    auth_token: str = "",
) -> bytes:
    """Faz download de mídia do Twilio.

    Usa httpx com Basic Auth (account_sid:auth_token).

    Args:
        url: URL da mídia no Twilio.
        account_sid: SID da conta Twilio.
        auth_token: Token de autenticação Twilio.

    Returns:
        Bytes do arquivo de mídia.
    """
    auth = (account_sid, auth_token) if account_sid else None

    async with httpx.AsyncClient() as client:
        response = await client.get(url, auth=auth, follow_redirects=True)
        response.raise_for_status()
        return response.content


def process_image(media_bytes: bytes) -> str:
    """Converte imagem para base64 para visão multimodal.

    Args:
        media_bytes: Bytes da imagem.

    Returns:
        String base64 da imagem.
    """
    return base64.b64encode(media_bytes).decode("utf-8")


async def process_audio(media_bytes: bytes) -> str:
    """Transcreve áudio via modelo multimodal (OpenRouter).

    Envia o áudio como input_audio no chat completions e pede
    transcrição. Usa o mesmo modelo e API key do agente principal.

    Args:
        media_bytes: Bytes do áudio.

    Returns:
        Texto transcrito.
    """
    api_key = settings.openrouter_api_key
    if not api_key:
        logger.error("audio_transcription_no_api_key")
        return "[Áudio recebido, transcrição não disponível]"

    audio_b64 = base64.b64encode(media_bytes).decode("utf-8")

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{settings.openrouter_base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key.get_secret_value()}",
            },
            json={
                "model": settings.openrouter_model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": (
                                    "Transcreva este áudio fielmente "
                                    "em português. Retorne apenas "
                                    "a transcrição, sem comentários."
                                ),
                            },
                            {
                                "type": "input_audio",
                                "input_audio": {
                                    "data": audio_b64,
                                    "format": "ogg",
                                },
                            },
                        ],
                    }
                ],
            },
            timeout=30.0,
        )
        response.raise_for_status()
        result = response.json()
        return result["choices"][0]["message"]["content"]


async def build_human_message(
    body: str,
    media_url: str | None = None,
    media_type: str | None = None,
) -> HumanMessage:
    """Constrói HumanMessage com suporte a mídia.

    Dependendo do tipo de mídia:
    - Imagem: adiciona como conteúdo multimodal (base64)
    - Áudio: transcreve e adiciona o texto
    - Sem mídia: mensagem de texto simples

    Args:
        body: Texto da mensagem.
        media_url: URL da mídia (opcional).
        media_type: MIME type da mídia (opcional).

    Returns:
        HumanMessage pronta para o agente.
    """
    # Sem mídia: mensagem simples
    if not media_url or not media_type:
        return HumanMessage(content=body)

    # Imagem: visão multimodal
    if media_type.startswith("image/") and settings.media_image_enabled:
        try:
            media_bytes = await download_media(media_url)
            image_b64 = process_image(media_bytes)
            content = [
                {"type": "text", "text": body or "O que você vê nesta imagem?"},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{media_type};base64,{image_b64}",
                    },
                },
            ]
            return HumanMessage(content=content)
        except Exception as e:
            logger.error("image_processing_failed", error=str(e))
            return HumanMessage(content=f"{body}\n[Imagem recebida, erro: {e}]")

    # Áudio: transcrição via modelo multimodal
    if media_type.startswith("audio/") and settings.media_audio_enabled:
        try:
            media_bytes = await download_media(media_url)
            transcription = await process_audio(media_bytes)
            prefix = f"{body}\n" if body else ""
            return HumanMessage(
                content=f"{prefix}[Transcrição de áudio]: {transcription}"
            )
        except Exception as e:
            logger.error("audio_processing_failed", error=str(e))
            return HumanMessage(
                content=f"{body}\n[Áudio recebido, mas transcrição falhou: {e}]"
            )

    # Tipo de mídia não suportado
    return HumanMessage(content=f"{body}\n[Mídia recebida: {media_type}]")
