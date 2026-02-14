"""Processador de mensagens — orquestra agente e fila.

Responsável por:
1. Construir a HumanMessage (com mídia se houver)
2. Carregar o agente via loader (com checkpointer PostgreSQL)
3. Executar o agente
4. Salvar a resposta no banco (mark_done ou mark_failed)

Uso:
    from whatsapp_langchain.worker.processor import process_message

    await process_message(message, pool)
"""

import structlog
from langchain_openai import OpenAIEmbeddings
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.store.postgres.aio import AsyncPostgresStore
from langgraph.store.postgres.base import PostgresIndexConfig
from psycopg_pool import AsyncConnectionPool
from pydantic import SecretStr

from whatsapp_langchain.agents.loader import load_graph
from whatsapp_langchain.shared.config import settings
from whatsapp_langchain.shared.models import MessageQueue
from whatsapp_langchain.shared.queue import (
    mark_done,
    mark_failed,
    upsert_conversation,
)
from whatsapp_langchain.worker.media import build_human_message

logger = structlog.get_logger()


async def process_message(
    message: MessageQueue,
    pool: AsyncConnectionPool,
) -> None:
    """Processa uma mensagem da fila com o agente apropriado.

    Faz download de mídia se presente, carrega o grafo do agente com
    checkpointer PostgreSQL, executa e salva a resposta.

    Args:
        message: Mensagem a processar (já reservada via claim).
        pool: Pool de conexões do psycopg.
    """
    logger.info(
        "processing_message",
        message_id=message.id,
        phone=message.phone_number,
        agent_id=message.agent_id,
        attempt=message.attempts,
    )

    try:
        # 1. Construir HumanMessage (com mídia se houver)
        human_message = await build_human_message(
            body=message.incoming_message,
            media_url=message.media_url,
            media_type=message.media_type,
        )

        # 2. Carregar agente com checkpointer + store PostgreSQL
        # from_conn_string é async context manager: cria conexão
        # dedicada para cada componente e a fecha ao sair do bloco
        invoke_config = {
            "configurable": {
                "thread_id": message.thread_id,
                "user_id": message.phone_number,
            }
        }

        if settings.memory_enabled:
            # Memória habilitada: cria embeddings + store para memória semântica
            api_key = settings.openrouter_api_key
            secret_key = SecretStr(api_key.get_secret_value()) if api_key else None
            embeddings = OpenAIEmbeddings(
                model=settings.embedding_model,
                base_url=settings.openrouter_base_url,
                api_key=secret_key,
            )

            index_config: PostgresIndexConfig = {
                "embed": embeddings,
                "dims": settings.embedding_dims,
                "fields": ["$"],
            }

            async with (
                AsyncPostgresStore.from_conn_string(
                    settings.database_url,
                    index=index_config,
                ) as store,
                AsyncPostgresSaver.from_conn_string(
                    settings.database_url,
                ) as checkpointer,
            ):
                graph = load_graph(
                    message.agent_id,
                    checkpointer=checkpointer,
                    store=store,
                )

                result = await graph.ainvoke(
                    {"messages": [human_message]},
                    config=invoke_config,
                )
        else:
            # Memória desabilitada: só checkpointer, sem store/embeddings
            logger.info("memory_disabled", message_id=message.id)
            async with AsyncPostgresSaver.from_conn_string(
                settings.database_url,
            ) as checkpointer:
                graph = load_graph(
                    message.agent_id,
                    checkpointer=checkpointer,
                )

                result = await graph.ainvoke(
                    {"messages": [human_message]},
                    config=invoke_config,
                )

        # 4. Extrair resposta
        response_text = result["messages"][-1].content

        # 5. Salvar resultado
        await mark_done(pool, message.id, response_text)
        await upsert_conversation(
            pool,
            phone_number=message.phone_number,
            agent_id=message.agent_id,
            last_message=response_text,
        )

        logger.info(
            "message_processed",
            message_id=message.id,
            phone=message.phone_number,
            agent_id=message.agent_id,
            response_length=len(response_text),
        )

    except Exception as e:
        logger.error(
            "message_processing_error",
            message_id=message.id,
            phone=message.phone_number,
            agent_id=message.agent_id,
            error=str(e),
        )
        await mark_failed(pool, message.id, str(e))
