"""Rota de health check.

Verifica se o servidor e o banco de dados estão operacionais.

Uso:
    curl http://localhost:8000/health
    # {"status": "ok"}
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from whatsapp_langchain.shared.db import check_db_health

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> JSONResponse:
    """Verifica saúde do serviço.

    Testa conectividade com o banco de dados via SELECT 1.

    Returns:
        {"status": "ok"} com HTTP 200, ou {"status": "unhealthy"} com HTTP 503.
    """
    is_healthy = await check_db_health()

    if not is_healthy:
        return JSONResponse(
            content={"status": "unhealthy"},
            status_code=503,
        )

    return JSONResponse(content={"status": "ok"})
