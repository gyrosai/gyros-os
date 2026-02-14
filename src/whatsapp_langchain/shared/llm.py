"""Factory para criação do modelo LLM com rate limiting.

Centraliza a criação do ChatOpenAI com InMemoryRateLimiter do LangChain.
Todos os pontos que criam modelos devem usar esta factory para garantir
controle de custo uniforme.

Uso:
    from whatsapp_langchain.shared.llm import create_chat_model

    model = create_chat_model()                          # default
    model = create_chat_model(model="gpt-4o-mini")       # override modelo
    model = create_chat_model(temperature=0.0)           # determinístico
"""

from langchain_core.rate_limiters import InMemoryRateLimiter
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from whatsapp_langchain.shared.config import settings


def create_chat_model(
    model: str | None = None,
    temperature: float | None = None,
) -> ChatOpenAI:
    """Cria ChatOpenAI configurado com rate limiter.

    O rate limiter usa token bucket: limita requisições por segundo
    com burst para picos controlados. Valores vêm de settings
    (LLM_RATE_LIMIT_REQUESTS_PER_SECOND e LLM_RATE_LIMIT_MAX_BURST).

    Args:
        model: Nome do modelo. Default: settings.openrouter_model.
        temperature: Temperatura. Default: None (usa default do provider).

    Returns:
        ChatOpenAI com rate limiter aplicado.
    """
    api_key = settings.openrouter_api_key
    secret_key = SecretStr(api_key.get_secret_value()) if api_key else None

    rate_limiter = InMemoryRateLimiter(
        requests_per_second=settings.llm_rate_limit_requests_per_second,
        max_bucket_size=settings.llm_rate_limit_max_burst,
    )

    kwargs: dict = {
        "model": model or settings.openrouter_model,
        "api_key": secret_key,
        "base_url": settings.openrouter_base_url,
        "rate_limiter": rate_limiter,
    }
    if temperature is not None:
        kwargs["temperature"] = temperature

    return ChatOpenAI(**kwargs)
