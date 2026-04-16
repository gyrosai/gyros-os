"""
Roda todas as migrations SQL em ordem.
Uso: DATABASE_URL=... python scripts/run_migrations.py
"""
import os
import sys
from pathlib import Path
import psycopg


def main():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL not set", file=sys.stderr)
        sys.exit(1)

    migrations_dir = Path(__file__).parent.parent / "db" / "migrations"
    if not migrations_dir.exists():
        print(f"ERROR: {migrations_dir} not found", file=sys.stderr)
        sys.exit(1)

    migrations = sorted(migrations_dir.glob("*.sql"))
    print(f"Found {len(migrations)} migrations")

    with psycopg.connect(db_url) as conn:
        # Cria tabela de controle
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    filename TEXT PRIMARY KEY,
                    applied_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            conn.commit()

        # Aplica cada migration que ainda não foi aplicada
        for migration in migrations:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM schema_migrations WHERE filename = %s",
                    (migration.name,)
                )
                if cur.fetchone():
                    print(f"SKIP {migration.name} (already applied)")
                    continue

                print(f"APPLY {migration.name}")
                sql = migration.read_text()
                cur.execute(sql)
                cur.execute(
                    "INSERT INTO schema_migrations (filename) VALUES (%s)",
                    (migration.name,)
                )
                conn.commit()

    print("All migrations applied.")


if __name__ == "__main__":
    main()
