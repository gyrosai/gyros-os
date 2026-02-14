"""Testes da ferramenta save_memory."""

from whatsapp_langchain.agents.tools.memory import save_memory


class TestSaveMemoryTool:
    """Testes para a tool save_memory."""

    def test_tool_has_correct_name(self):
        """Verifica que a tool tem o nome correto."""
        assert save_memory.name == "save_memory"

    def test_tool_has_description(self):
        """Verifica que a tool tem descrição."""
        assert save_memory.description
        desc = save_memory.description.lower()
        assert "salva" in desc or "memória" in desc

    def test_tool_has_memory_parameter(self):
        """Verifica que a tool aceita o parâmetro 'memory'."""
        schema = save_memory.get_input_schema()
        fields = schema.model_fields
        assert "memory" in fields
