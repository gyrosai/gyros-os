"""Testes de integração para middlewares de contexto.

Estes testes verificam se as estratégias de gerenciamento de contexto
(trim, summarize, none) funcionam corretamente com o agente real.

Executar com: pytest tests/integration/ -v
"""

import os

import pytest
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from whatsapp_langchain.agents.middleware import get_context_middleware

load_dotenv()


# --- Fixtures ---


@pytest.fixture
def model():
    """Modelo configurado para testes."""
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        pytest.skip("OPENROUTER_API_KEY não configurada")

    return ChatOpenAI(
        model=os.getenv("OPENROUTER_MODEL", "openai/gpt-oss-120b"),
        api_key=SecretStr(api_key),
        base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
    )


# --- Testes do Trim Middleware ---


class TestTrimMiddleware:
    """Testes para a estratégia trim (por turnos)."""

    def test_trim_creates_middleware(self):
        """Verifica que o trim cria o middleware corretamente."""
        middleware = get_context_middleware(strategy="trim", trim_keep_turns=2)

        assert len(middleware) == 1
        assert middleware[0] is not None

    def test_trim_removes_old_turns(self):
        """Invoca o middleware real e verifica remoção de turnos antigos."""
        from langgraph.graph import add_messages

        from whatsapp_langchain.agents.middleware.trim import create_trim_middleware

        # keep_turns=2 → mantém os últimos 2 turnos
        mw = create_trim_middleware(keep_turns=2)

        # 4 turnos: [h1 a1] [h2 a2] [h3 a3] [h4]
        messages = [
            HumanMessage(content="Olá", id="h1"),
            AIMessage(content="Resp 1", id="a1"),
            HumanMessage(content="Msg 2", id="h2"),
            AIMessage(content="Resp 2", id="a2"),
            HumanMessage(content="Msg 3", id="h3"),
            AIMessage(content="Resp 3", id="a3"),
            HumanMessage(content="Msg 4", id="h4"),
        ]

        result = mw.before_model({"messages": messages}, None)

        # Deve remover turnos 1 e 2 (h1, a1, h2, a2 = 4 mensagens)
        assert result is not None
        assert len(result["messages"]) == 4

        # Aplica pelo reducer real — igual ao que o LangGraph faz
        final = add_messages(messages, result["messages"])

        assert len(final) == 3
        assert final[0].content == "Msg 3"
        assert final[1].content == "Resp 3"
        assert final[2].content == "Msg 4"

    def test_trim_with_tool_calls(self):
        """Turno com tool_calls (4+ msgs) conta como 1 turno."""
        from langgraph.graph import add_messages

        from whatsapp_langchain.agents.middleware.trim import create_trim_middleware

        # keep_turns=2 → mantém os últimos 2 turnos
        mw = create_trim_middleware(keep_turns=2)

        # Turno 1: simples (h1, a1)
        # Turno 2: com tool_calls (h2, a2_tool_call, tool_result, a2_final)
        # Turno 3: simples (h3, a3)
        messages = [
            HumanMessage(content="Olá", id="h1"),
            AIMessage(content="Resp 1", id="a1"),
            HumanMessage(content="Consulta estoque", id="h2"),
            AIMessage(
                content="",
                id="a2_call",
                additional_kwargs={
                    "tool_calls": [
                        {
                            "id": "tc1",
                            "function": {
                                "name": "check",
                                "arguments": "{}",
                            },
                        }
                    ],
                },
            ),
            ToolMessage(content="42 unidades", id="t1", tool_call_id="tc1"),
            AIMessage(content="Temos 42 unidades!", id="a2_final"),
            HumanMessage(content="Obrigado", id="h3"),
            AIMessage(content="De nada!", id="a3"),
        ]

        result = mw.before_model({"messages": messages}, None)

        # Deve remover turno 1 (h1, a1 = 2 mensagens)
        assert result is not None
        assert len(result["messages"]) == 2

        # Aplica pelo reducer real
        final = add_messages(messages, result["messages"])

        # Restam turnos 2 e 3 (6 mensagens)
        assert len(final) == 6
        assert final[0].content == "Consulta estoque"  # h2
        assert final[1].id == "a2_call"
        assert final[2].content == "42 unidades"  # tool result
        assert final[3].content == "Temos 42 unidades!"  # a2_final
        assert final[4].content == "Obrigado"  # h3
        assert final[5].content == "De nada!"  # a3

    def test_trim_no_op_when_few_turns(self):
        """Não faz nada quando há turnos suficientes (dentro do limite)."""
        from whatsapp_langchain.agents.middleware.trim import create_trim_middleware

        mw = create_trim_middleware(keep_turns=3)

        # Apenas 2 turnos — abaixo do limite de 3
        messages = [
            HumanMessage(content="Olá", id="h1"),
            AIMessage(content="Resp 1", id="a1"),
            HumanMessage(content="Tudo bem?", id="h2"),
            AIMessage(content="Tudo sim!", id="a2"),
        ]

        result = mw.before_model({"messages": messages}, None)

        assert result is None

    def test_trim_exact_boundary(self):
        """Não faz nada quando o número de turnos é exatamente o limite."""
        from whatsapp_langchain.agents.middleware.trim import create_trim_middleware

        mw = create_trim_middleware(keep_turns=2)

        # Exatamente 2 turnos = limite
        messages = [
            HumanMessage(content="Olá", id="h1"),
            AIMessage(content="Resp 1", id="a1"),
            HumanMessage(content="Msg 2", id="h2"),
            AIMessage(content="Resp 2", id="a2"),
        ]

        result = mw.before_model({"messages": messages}, None)

        assert result is None

    def test_trim_with_agent_integration(self, model):
        """Teste de integração: agente com trim responde corretamente."""
        middleware = get_context_middleware(strategy="trim", trim_keep_turns=2)

        agent = create_agent(
            model=model,
            tools=[],
            system_prompt="Responda de forma breve.",
            middleware=middleware,
        )

        # Primeira mensagem
        result = agent.invoke(
            {"messages": [HumanMessage(content="Olá, meu nome é Carlos.")]},
            config={"configurable": {"thread_id": "test-trim-1"}},
        )

        assert result is not None
        assert "messages" in result


# --- Testes do Summarize Middleware ---


class TestSummarizeMiddleware:
    """Testes para a estratégia summarize."""

    def test_summarize_creates_middleware(self):
        """Verifica que o summarize cria o middleware corretamente."""
        middleware = get_context_middleware(
            strategy="summarize",
            summarize_trigger_tokens=100,
            summarize_keep_messages=2,
        )

        assert len(middleware) == 1
        assert middleware[0] is not None

    def test_summarize_with_agent_integration(self, model):
        """Teste de integração: agente com summarize responde corretamente."""
        middleware = get_context_middleware(
            strategy="summarize",
            summarize_trigger_tokens=500,  # Valor baixo para teste
            summarize_keep_messages=2,
        )

        agent = create_agent(
            model=model,
            tools=[],
            system_prompt="Responda de forma breve.",
            middleware=middleware,
        )

        # Primeira mensagem
        result = agent.invoke(
            {"messages": [HumanMessage(content="Olá!")]},
            config={"configurable": {"thread_id": "test-summarize-1"}},
        )

        assert result is not None
        assert "messages" in result


# --- Testes do None (sem middleware) ---


class TestNoneMiddleware:
    """Testes para strategy=none (sem gerenciamento de contexto)."""

    def test_none_returns_empty_list(self):
        """Verifica que strategy=none retorna lista vazia."""
        middleware = get_context_middleware(strategy="none")

        assert middleware == []
        assert len(middleware) == 0

    def test_none_with_agent_integration(self, model):
        """Teste de integração: agente sem middleware responde corretamente."""
        middleware = get_context_middleware(strategy="none")

        agent = create_agent(
            model=model,
            tools=[],
            system_prompt="Responda de forma breve.",
            middleware=middleware,
        )

        result = agent.invoke(
            {"messages": [HumanMessage(content="Olá!")]},
            config={"configurable": {"thread_id": "test-none-1"}},
        )

        assert result is not None
        assert "messages" in result


# --- Testes da Factory ---


class TestGetContextMiddleware:
    """Testes para a factory get_context_middleware()."""

    def test_default_strategy_is_summarize(self):
        """Verifica que o default é summarize quando não há env var."""
        # Salva e limpa a env var
        original = os.environ.pop("CONTEXT_STRATEGY", None)

        try:
            middleware = get_context_middleware()
            # Deve retornar um middleware (summarize)
            assert len(middleware) == 1
        finally:
            # Restaura
            if original:
                os.environ["CONTEXT_STRATEGY"] = original

    def test_override_parameters(self):
        """Verifica que parâmetros override funcionam."""
        middleware = get_context_middleware(
            strategy="trim",
            trim_keep_turns=3,
        )

        assert len(middleware) == 1

    def test_invalid_strategy_returns_empty(self):
        """Verifica que estratégia inválida retorna lista vazia."""
        middleware = get_context_middleware(strategy="invalid_strategy")

        assert middleware == []
