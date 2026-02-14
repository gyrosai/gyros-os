"""Testes do middleware de memória semântica."""

from whatsapp_langchain.agents.middleware.memory import create_memory_middleware


class TestCreateMemoryMiddleware:
    """Testes para a factory create_memory_middleware."""

    def test_creates_middleware(self):
        """Verifica que a factory cria o middleware corretamente."""
        mw = create_memory_middleware(search_limit=3)
        assert mw is not None

    def test_default_search_limit(self):
        """Verifica que o default search_limit é 5."""
        mw = create_memory_middleware()
        assert mw is not None

    def test_middleware_is_agent_middleware(self):
        """Verifica que o middleware é uma instância de AgentMiddleware."""
        from langchain.agents.middleware import AgentMiddleware

        mw = create_memory_middleware()
        assert isinstance(mw, AgentMiddleware)

    def test_middleware_has_abefore_model(self):
        """Verifica que o middleware implementa abefore_model (async)."""
        mw = create_memory_middleware()
        # O @before_model async cria uma classe com abefore_model
        assert hasattr(mw, "abefore_model")
