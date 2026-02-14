"""Operações de fila no PostgreSQL.

Módulo compartilhado entre API e Worker para manipular a tabela message_queue.
A API insere mensagens (enqueue), o Worker consome (claim) e
finaliza (mark_done/failed).

O debounce agrupa mensagens rápidas do mesmo remetente: se o usuário
envia 3 mensagens em 2 segundos, elas são concatenadas em uma única
entrada na fila.

Uso:
    from whatsapp_langchain.shared.queue import enqueue_or_buffer

    result = await enqueue_or_buffer(pool, phone="+55...", body="Olá")
    message = await claim_next(pool, lease_seconds=60)
"""

from datetime import UTC, datetime, timedelta

import structlog
from psycopg_pool import AsyncConnectionPool

from whatsapp_langchain.shared.models import EnqueueResult, MessageQueue

logger = structlog.get_logger()


async def enqueue_or_buffer(
    pool: AsyncConnectionPool,
    phone_number: str,
    agent_id: str,
    body: str,
    media_url: str | None = None,
    media_type: str | None = None,
    to_number: str | None = None,
    message_id: str | None = None,
    buffer_seconds: float = 2.0,
) -> EnqueueResult:
    """Insere mensagem na fila ou agrupa com mensagem pendente (debounce).

    Se existe uma mensagem 'queued' do mesmo phone+agent com process_after
    no futuro, concatena o body e reseta o timer. Isso evita que mensagens
    rápidas (ex: "Oi" + "Tudo bem?" em 1s) gerem duas chamadas ao agente.

    Args:
        pool: Pool de conexões do psycopg.
        phone_number: Telefone do remetente (E.164).
        agent_id: ID do agente que vai processar.
        body: Texto da mensagem.
        media_url: URL de mídia anexada (opcional).
        media_type: MIME type da mídia (opcional).
        to_number: Número destinatário (opcional).
        message_id: ID externo da mensagem, ex: Twilio MessageSid (opcional).
        buffer_seconds: Segundos de debounce. Default: 2.0.

    Returns:
        EnqueueResult com message_id e se foi buffered.
    """
    thread_id = f"{phone_number}:{agent_id}"
    process_after = datetime.now(UTC) + timedelta(seconds=buffer_seconds)

    async with pool.connection() as conn:
        # Tenta encontrar mensagem existente para debounce
        cursor = await conn.execute(
            """
            SELECT id, incoming_message
            FROM message_queue
            WHERE phone_number = %s
              AND agent_id = %s
              AND status = 'queued'
              AND process_after > NOW()
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (phone_number, agent_id),
        )
        existing = await cursor.fetchone()

        if existing:
            # Debounce: concatena mensagem e reseta timer
            existing_id, existing_body = existing
            new_body = f"{existing_body}\n{body}"

            await conn.execute(
                """
                UPDATE message_queue
                SET incoming_message = %s,
                    process_after = %s,
                    media_url = COALESCE(%s, media_url),
                    media_type = COALESCE(%s, media_type),
                    updated_at = NOW()
                WHERE id = %s
                """,
                (new_body, process_after, media_url, media_type, existing_id),
            )
            await conn.commit()

            logger.info(
                "message_buffered",
                message_id=existing_id,
                phone=phone_number,
                agent_id=agent_id,
            )
            return EnqueueResult(message_id=existing_id, is_buffered=True)

        # Nova mensagem na fila
        cursor = await conn.execute(
            """
            INSERT INTO message_queue
                (message_id, phone_number, to_number, agent_id, thread_id,
                 incoming_message, media_url, media_type, process_after)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                message_id,
                phone_number,
                to_number,
                agent_id,
                thread_id,
                body,
                media_url,
                media_type,
                process_after,
            ),
        )
        row = await cursor.fetchone()
        assert row is not None
        new_id = row[0]
        await conn.commit()

        logger.info(
            "message_enqueued",
            message_id=new_id,
            phone=phone_number,
            agent_id=agent_id,
        )
        return EnqueueResult(message_id=new_id, is_buffered=False)


async def claim_next(
    pool: AsyncConnectionPool,
    lease_seconds: int = 60,
) -> MessageQueue | None:
    """Busca e reserva a próxima mensagem pronta para processamento.

    Usa FOR UPDATE SKIP LOCKED para concorrência segura entre múltiplos workers.
    Só retorna mensagens com process_after <= NOW() (debounce concluído) e
    dentro do limite de tentativas.

    Args:
        pool: Pool de conexões do psycopg.
        lease_seconds: Segundos de lock para o worker processar.

    Returns:
        MessageQueue se houver mensagem disponível, None caso contrário.
    """
    lease_until = datetime.now(UTC) + timedelta(seconds=lease_seconds)

    async with pool.connection() as conn:
        cursor = await conn.execute(
            """
            UPDATE message_queue
            SET status = 'processing',
                lease_until = %s,
                attempts = attempts + 1,
                updated_at = NOW()
            WHERE id = (
                SELECT id FROM message_queue
                WHERE status = 'queued'
                  AND process_after <= NOW()
                  AND attempts < max_attempts
                ORDER BY created_at ASC
                LIMIT 1
                FOR UPDATE SKIP LOCKED
            )
            RETURNING id, message_id, phone_number, to_number, agent_id, thread_id,
                      incoming_message, media_url, media_type, status,
                      process_after, attempts, max_attempts, lease_until,
                      response, error, created_at, updated_at, processed_at
            """,
            (lease_until,),
        )
        row = await cursor.fetchone()
        await conn.commit()

        if row is None:
            return None

        message = MessageQueue(
            id=row[0],
            message_id=row[1],
            phone_number=row[2],
            to_number=row[3],
            agent_id=row[4],
            thread_id=row[5],
            incoming_message=row[6],
            media_url=row[7],
            media_type=row[8],
            status=row[9],
            process_after=row[10],
            attempts=row[11],
            max_attempts=row[12],
            lease_until=row[13],
            response=row[14],
            error=row[15],
            created_at=row[16],
            updated_at=row[17],
            processed_at=row[18],
        )

        logger.info(
            "message_claimed",
            message_id=message.id,
            phone=message.phone_number,
            agent_id=message.agent_id,
            attempt=message.attempts,
        )
        return message


async def mark_done(
    pool: AsyncConnectionPool,
    message_id: int,
    response: str,
) -> None:
    """Marca mensagem como processada com sucesso.

    Args:
        pool: Pool de conexões do psycopg.
        message_id: ID da mensagem na fila.
        response: Resposta gerada pelo agente.
    """
    async with pool.connection() as conn:
        await conn.execute(
            """
            UPDATE message_queue
            SET status = 'done',
                response = %s,
                processed_at = NOW(),
                updated_at = NOW()
            WHERE id = %s
            """,
            (response, message_id),
        )
        await conn.commit()

    logger.info("message_done", message_id=message_id)


async def mark_failed(
    pool: AsyncConnectionPool,
    message_id: int,
    error: str,
) -> None:
    """Marca mensagem como falha.

    Se ainda tem tentativas restantes, volta para 'queued' para retry.
    Caso contrário, marca como 'failed' definitivamente.

    Args:
        pool: Pool de conexões do psycopg.
        message_id: ID da mensagem na fila.
        error: Descrição do erro.
    """
    async with pool.connection() as conn:
        # Verifica se ainda tem tentativas
        cursor = await conn.execute(
            "SELECT attempts, max_attempts FROM message_queue WHERE id = %s",
            (message_id,),
        )
        row = await cursor.fetchone()

        if row and row[0] < row[1]:
            # Ainda tem tentativas: volta para a fila com backoff progressivo
            # Cada tentativa espera attempts * 5s antes de ser reprocessada
            backoff_seconds = row[0] * 5
            await conn.execute(
                """
                UPDATE message_queue
                SET status = 'queued',
                    error = %s,
                    lease_until = NULL,
                    process_after = NOW() + make_interval(secs => %s),
                    updated_at = NOW()
                WHERE id = %s
                """,
                (error, backoff_seconds, message_id),
            )
            logger.warning(
                "message_retry",
                message_id=message_id,
                attempt=row[0],
                max_attempts=row[1],
                backoff_seconds=backoff_seconds,
                error=error,
            )
        else:
            # Sem tentativas: falha definitiva
            await conn.execute(
                """
                UPDATE message_queue
                SET status = 'failed',
                    error = %s,
                    processed_at = NOW(),
                    updated_at = NOW()
                WHERE id = %s
                """,
                (error, message_id),
            )
            logger.error(
                "message_failed",
                message_id=message_id,
                error=error,
            )

        await conn.commit()


async def upsert_conversation(
    pool: AsyncConnectionPool,
    phone_number: str,
    agent_id: str,
    last_message: str,
) -> None:
    """Atualiza ou cria registro de conversa.

    Usado após cada mensagem processada para manter o histórico
    de conversas atualizado (para o painel admin).

    Args:
        pool: Pool de conexões do psycopg.
        phone_number: Telefone do remetente.
        agent_id: ID do agente.
        last_message: Última mensagem processada.
    """
    thread_id = f"{phone_number}:{agent_id}"

    async with pool.connection() as conn:
        await conn.execute(
            """
            INSERT INTO conversations (
                phone_number, agent_id, thread_id,
                last_message, last_message_at, message_count)
            VALUES (%s, %s, %s, %s, NOW(), 1)
            ON CONFLICT (phone_number, agent_id) DO UPDATE SET
                last_message = EXCLUDED.last_message,
                last_message_at = NOW(),
                message_count = conversations.message_count + 1,
                updated_at = NOW()
            """,
            (phone_number, agent_id, thread_id, last_message),
        )
        await conn.commit()
