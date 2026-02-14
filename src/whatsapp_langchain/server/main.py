"""FastAPI application factory com lifespan.

Entry point do servidor HTTP. Configura logging, banco de dados,
CORS e inclui todos os routers.

Uso:
    uvicorn whatsapp_langchain.server.main:app --reload --port 8000
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from whatsapp_langchain.server.routes.admin import router as admin_router
from whatsapp_langchain.server.routes.health import router as health_router
from whatsapp_langchain.server.routes.webhook import router as webhook_router
from whatsapp_langchain.server.routes.webhook_sync import (
    router as webhook_sync_router,
)
from whatsapp_langchain.shared.config import settings
from whatsapp_langchain.shared.db import close_pool, get_pool, run_migrations
from whatsapp_langchain.shared.observability import setup_logging

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Gerencia o ciclo de vida da aplicação.

    Startup: configura logging, cria pool do banco, aplica migrações.
    Shutdown: fecha pool do banco.
    """
    # Startup
    setup_logging(
        log_level=settings.log_level,
        json_output=settings.log_json,
    )
    logger.info("server_starting", port=settings.port)

    pool = await get_pool()
    await run_migrations(pool)
    logger.info("server_ready")

    yield

    # Shutdown
    await close_pool()
    logger.info("server_stopped")


app = FastAPI(
    title="WhatsApp LangChain API",
    description="API para agentes conversacionais WhatsApp com LangGraph.",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS para o frontend (Next.js)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(health_router)
app.include_router(webhook_router)
app.include_router(webhook_sync_router)
app.include_router(admin_router)
