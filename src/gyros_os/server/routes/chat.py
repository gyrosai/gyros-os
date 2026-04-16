"""Rotas REST para o chat com agente studio_assistant.

Envio de mensagens (request/response, sem streaming v0.1),
listagem de threads e histórico de mensagens.

Todas as rotas exigem sessão Better Auth válida.
"""

from uuid import uuid4

import structlog
from fastapi import APIRouter, Depends, HTTPException
from langchain_core.messages import HumanMessage
from pydantic import BaseModel

from gyros_os.agents.loader import load_graph
from gyros_os.server.dependencies import get_current_user
from gyros_os.shared.db import get_pool, open_checkpointer, open_store
from gyros_os.shared.org import get_default_org_id

logger = structlog.get_logger()

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatRequest(BaseModel):
    message: str
    thread_id: str | None = None


class ChatResponse(BaseModel):
    reply: str
    thread_id: str
    sources: list[str] = []


@router.post("/messages")
async def send_message(
    body: ChatRequest,
    user: dict = Depends(get_current_user),
) -> ChatResponse:
    """Envia mensagem e retorna resposta do studio_assistant."""
    pool = await get_pool()
    org_id = await get_default_org_id(pool)

    is_new_thread = body.thread_id is None
    thread_id = body.thread_id or f"studio_{user['user_id']}_{uuid4().hex[:8]}"

    # Registra thread na tabela auxiliar
    if is_new_thread:
        # Usa primeiras palavras da mensagem como título
        title = body.message[:60].strip()
        if len(body.message) > 60:
            title += "..."
        async with pool.connection() as conn:
            await conn.execute(
                """
                INSERT INTO chat_threads (id, user_id, organization_id, title)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING
                """,
                (thread_id, user["user_id"], str(org_id), title),
            )
            await conn.commit()

    # Invoca studio_assistant com checkpointer para persistência
    checkpointer_stack, checkpointer = await open_checkpointer()
    store_stack, store = await open_store()

    try:
        graph = load_graph(
            "studio_assistant",
            checkpointer=checkpointer,
            store=store,
        )

        result = await graph.ainvoke(
            {"messages": [HumanMessage(content=body.message)]},
            config={
                "configurable": {
                    "thread_id": thread_id,
                    "user_id": user["user_id"],
                },
                "recursion_limit": 10,
            },
        )

        reply = result["messages"][-1].content

        # Extrai sources dos tool calls se houver
        sources: list[str] = []
        for msg in result["messages"]:
            if hasattr(msg, "tool_calls"):
                for tc in msg.tool_calls:
                    if tc.get("name") == "search_kb" and isinstance(
                        tc.get("output"), str
                    ):
                        # Parse source titles from output
                        for line in tc["output"].split("\n"):
                            if line.startswith("[Fonte:"):
                                src = line.split("]")[0].replace("[Fonte: ", "")
                                if src and src not in sources:
                                    sources.append(src)
    finally:
        if store_stack is not None:
            await store_stack.aclose()
        await checkpointer_stack.aclose()

    # Atualiza updated_at da thread
    async with pool.connection() as conn:
        await conn.execute(
            "UPDATE chat_threads SET updated_at = NOW() WHERE id = %s",
            (thread_id,),
        )
        await conn.commit()

    logger.info(
        "chat_message_processed",
        thread_id=thread_id,
        user_id=user["user_id"],
        reply_length=len(reply),
    )

    return ChatResponse(reply=reply, thread_id=thread_id, sources=sources)


@router.get("/threads")
async def list_threads(
    user: dict = Depends(get_current_user),
) -> list[dict]:
    """Lista threads de chat do usuário."""
    pool = await get_pool()
    org_id = await get_default_org_id(pool)

    async with pool.connection() as conn:
        cursor = await conn.execute(
            """
            SELECT id, title, created_at, updated_at
            FROM chat_threads
            WHERE user_id = %s AND organization_id = %s
            ORDER BY updated_at DESC
            """,
            (user["user_id"], str(org_id)),
        )
        rows = await cursor.fetchall()

    return [
        {
            "id": r[0],
            "title": r[1],
            "created_at": r[2].isoformat() if r[2] else None,
            "updated_at": r[3].isoformat() if r[3] else None,
        }
        for r in rows
    ]


@router.get("/threads/{thread_id}/messages")
async def get_thread_messages(
    thread_id: str,
    user: dict = Depends(get_current_user),
) -> list[dict]:
    """Retorna histórico de mensagens de uma thread via checkpointer."""
    # Verifica que a thread pertence ao user
    pool = await get_pool()
    async with pool.connection() as conn:
        cursor = await conn.execute(
            "SELECT id FROM chat_threads WHERE id = %s AND user_id = %s",
            (thread_id, user["user_id"]),
        )
        row = await cursor.fetchone()

    if not row:
        raise HTTPException(404, "Thread not found")

    # Carrega estado do checkpointer
    checkpointer_stack, checkpointer = await open_checkpointer()
    try:
        config = {"configurable": {"thread_id": thread_id}}
        state = await checkpointer.aget(config)
    finally:
        await checkpointer_stack.aclose()

    if not state or "channel_values" not in state:
        return []

    messages = state["channel_values"].get("messages", [])

    result = []
    for msg in messages:
        msg_type = getattr(msg, "type", None)
        if msg_type in ("human", "ai") and msg.content:
            result.append(
                {
                    "role": "user" if msg_type == "human" else "assistant",
                    "content": msg.content,
                }
            )

    return result
