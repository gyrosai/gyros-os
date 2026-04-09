"""Integration test for RAG ingest + retrieve.

Requires:
- PostgreSQL running on localhost:5433 with gyros_os database
- OPENAI_API_KEY set in environment or .env
- Migration 005 applied (organizations, kb_docs, kb_chunks tables)

Run with: uv run pytest tests/rag/test_ingest_and_retrieve.py -v
"""

import pytest

from gyros_os.rag import ingest_text, retrieve
from gyros_os.shared.db import get_pool


@pytest.fixture
async def org_id():
    """Get the 'gyros' organization ID from the database."""
    pool = await get_pool()
    async with pool.connection() as conn:
        cursor = await conn.execute(
            "SELECT id FROM organizations WHERE slug = 'gyros'"
        )
        row = await cursor.fetchone()
        assert row is not None, "Organization 'gyros' not found — run migrations first"
        return row[0]


@pytest.fixture
async def cleanup(org_id):
    """Clean up test data after the test."""
    yield
    pool = await get_pool()
    async with pool.connection() as conn:
        await conn.execute(
            """
            DELETE FROM kb_chunks WHERE doc_id IN (
                SELECT id FROM kb_docs
                WHERE organization_id = %s AND source_ref = 'test-ingest-retrieve'
            )
            """,
            (str(org_id),),
        )
        await conn.execute(
            """
            DELETE FROM kb_docs
            WHERE organization_id = %s AND source_ref = 'test-ingest-retrieve'
            """,
            (str(org_id),),
        )
        await conn.commit()


TOPIC_COOKING = """Receitas culinárias são uma arte fascinante que exige dedicação e conhecimento técnico aprofundado. O risoto de cogumelos, por exemplo, demanda paciência e um bom caldo caseiro preparado com ossos de frango e vegetais aromáticos. A técnica de tostagem do arroz arbóreo antes de adicionar o caldo é o segredo fundamental para um risoto cremoso e al dente. Temperos como açafrão-da-terra, tomilho fresco e parmesão ralado na hora completam o sabor de maneira incomparável. Além do risoto, técnicas francesas como o roux, a emulsificação de molhos e a cocção sous-vide revolucionaram a gastronomia moderna. O preparo de massas frescas italianas também requer habilidade manual considerável, desde a hidratação correta da farinha até o ponto exato de cozimento. Chefs renomados dedicam anos ao aperfeiçoamento dessas técnicas antes de se aventurarem em criações autorais. A confeitaria é outro campo que combina precisão científica com criatividade artística, exigindo controle preciso de temperatura e proporções em receitas como o crème brûlée e o soufflé."""

TOPIC_SPACE = """A exploração espacial avançou enormemente nas últimas décadas e representa uma das maiores conquistas da humanidade. A missão Artemis da NASA planeja levar astronautas de volta à Lua até o final desta década, estabelecendo uma base permanente no polo sul lunar. Enquanto isso, a SpaceX de Elon Musk desenvolve o Starship, o maior foguete já construído, projetado para viagens interplanetárias a Marte. Telescópios espaciais como o James Webb, lançado em dezembro de 2021, já revelaram galáxias formadas apenas algumas centenas de milhões de anos após o Big Bang, ampliando dramaticamente nosso entendimento sobre a formação do universo. A Estação Espacial Internacional continua servindo como laboratório orbital, realizando experimentos em microgravidade que beneficiam a medicina e a ciência de materiais na Terra. Empresas privadas como Blue Origin e Rocket Lab estão democratizando o acesso ao espaço, reduzindo custos de lançamento e abrindo caminho para o turismo espacial comercial. Os rovers Perseverance e Curiosity exploram a superfície marciana coletando amostras de solo."""

TOPIC_GARDEN = """Jardinagem é uma atividade terapêutica e sustentável que conecta as pessoas com a natureza e promove bem-estar mental comprovado por estudos científicos. Cultivar ervas aromáticas como manjericão, alecrim, hortelã e sálvia em vasos pequenos é ideal para apartamentos urbanos com espaço limitado. A compostagem doméstica transforma restos orgânicos como cascas de frutas, borra de café e folhas secas em adubo rico em nutrientes para as plantas. A técnica de irrigação por gotejamento economiza até 70% de água em comparação com irrigação convencional, enquanto mantém as plantas consistentemente saudáveis. O cultivo de hortaliças como tomate, alface e cenoura em canteiros elevados permite controle total do solo e facilita a manutenção para pessoas com limitações de mobilidade. Plantas companheiras como tagetes e cravo-de-defunto afastam pragas naturalmente, reduzindo a necessidade de pesticidas. A poda regular de arbustos e árvores frutíferas estimula o crescimento saudável e aumenta a produção de frutos na estação seguinte."""

CONTENT = f"{TOPIC_COOKING}\n\n{TOPIC_SPACE}\n\n{TOPIC_GARDEN}"


@pytest.mark.asyncio
async def test_ingest_and_retrieve_top1_matches_query(org_id, cleanup):
    """Ingest 3-topic doc, query about topic 2, verify top-1 is space-related."""
    result = await ingest_text(
        org_id=org_id,
        source_type="test",
        source_ref="test-ingest-retrieve",
        title="Test document with 3 topics",
        content=CONTENT,
    )

    assert result["num_chunks"] >= 3, f"Expected at least 3 chunks, got {result['num_chunks']}"
    assert result["total_tokens"] > 0

    # Query about space exploration (topic 2)
    results = await retrieve(
        org_id=org_id,
        query="missão espacial Artemis NASA Lua Marte telescópio",
        top_k=3,
    )

    assert len(results) > 0, "Expected at least 1 retrieval result"

    top = results[0]
    space_keywords = ["espacial", "NASA", "Artemis", "Marte", "Lua", "Starship", "Webb", "galáxias", "astronautas", "universo"]
    assert any(
        kw.lower() in top.content.lower() for kw in space_keywords
    ), f"Top-1 chunk should contain space-related content, got: {top.content[:200]}"
