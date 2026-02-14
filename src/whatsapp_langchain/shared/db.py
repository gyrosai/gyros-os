"""Pool de conexões PostgreSQL e utilitários de banco de dados.

Gerencia um pool singleton de conexões assíncronas usando psycopg.
O pool é criado no startup da aplicação (lifespan) e fechado no shutdown.

Uso:
    from whatsapp_langchain.shared.db import get_pool, close_pool, run_migrations

    # No lifespan da aplicação:
    pool = await get_pool()
    await run_migrations(pool)
    # ... app roda ...
    await close_pool()
"""

from pathlib import Path

import structlog
from psycopg import AsyncConnection
from psycopg_pool import AsyncConnectionPool

from whatsapp_langchain.shared.config import settings

logger = structlog.get_logger()

# Singleton do pool de conexões
pool: AsyncConnectionPool | None = None

# Diretório de migrações
MIGRATIONS_DIR = Path(__file__).parents[3] / "db" / "migrations"


async def get_pool() -> AsyncConnectionPool:
    """Retorna o pool de conexões, criando se necessário.

    O pool é singleton — chamadas subsequentes retornam a mesma instância.

    Returns:
        Pool de conexões assíncronas do psycopg.
    """
    global pool
    if pool is None:
        pool = AsyncConnectionPool(
            conninfo=settings.database_url,
            min_size=2,
            max_size=10,
            open=False,
        )
        await pool.open()
        db_host = settings.database_url.split("@")[-1]
        logger.info("db_pool_created", database_url=db_host)
    return pool


async def close_pool() -> None:
    """Fecha o pool de conexões.

    Chamado no shutdown da aplicação para liberar recursos.
    """
    global pool
    if pool is not None:
        await pool.close()
        pool = None
        logger.info("db_pool_closed")


async def run_migrations(db_pool: AsyncConnectionPool) -> None:
    """Aplica migrações SQL pendentes ao banco de dados.

    Lê arquivos de db/migrations/ e aplica os que ainda não foram
    registrados na tabela _migrations.

    Args:
        db_pool: Pool de conexões do psycopg.
    """
    async with db_pool.connection() as conn:
        conn: AsyncConnection

        # Garante que a tabela de controle existe
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS _migrations (
                id          SERIAL PRIMARY KEY,
                name        TEXT NOT NULL UNIQUE,
                applied_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        await conn.commit()

        # Busca migrações já aplicadas
        cursor = await conn.execute("SELECT name FROM _migrations ORDER BY name")
        rows = await cursor.fetchall()
        applied = {row[0] for row in rows}

        # Lê e aplica migrações pendentes
        sql_files = sorted(MIGRATIONS_DIR.glob("*.sql"))

        for sql_file in sql_files:
            if sql_file.name in applied:
                logger.debug("migration_already_applied", migration=sql_file.name)
                continue

            logger.info("migration_applying", migration=sql_file.name)
            sql = sql_file.read_text(encoding="utf-8")
            await conn.execute(sql.encode())
            await conn.execute(
                "INSERT INTO _migrations (name) VALUES (%s)",
                (sql_file.name,),
            )
            await conn.commit()
            logger.info("migration_applied", migration=sql_file.name)


async def check_db_health() -> bool:
    """Verifica se o banco de dados está acessível.

    Executa SELECT 1 para confirmar conectividade.

    Returns:
        True se o banco respondeu, False caso contrário.
    """
    try:
        db_pool = await get_pool()
        async with db_pool.connection() as conn:
            await conn.execute("SELECT 1")
        return True
    except Exception as e:
        logger.error("db_health_check_failed", error=str(e))
        return False
