"""
Cria usuário no Better Auth diretamente no banco.
Uso: DATABASE_URL=... python scripts/create_user.py <email> <password> <name>
"""
import sys
import os
import uuid
from datetime import datetime, timezone

try:
    import psycopg
except ImportError:
    print("Instale psycopg: pip install psycopg[binary]")
    sys.exit(1)


def hash_password(password: str) -> str:
    """Hash compatível com Better Auth (bcrypt)."""
    import bcrypt

    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def main():
    if len(sys.argv) < 4:
        print("Uso: python scripts/create_user.py <email> <password> <name>")
        sys.exit(1)

    email = sys.argv[1]
    password = sys.argv[2]
    name = sys.argv[3]

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL não setada")
        sys.exit(1)

    user_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    hashed = hash_password(password)

    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            # Verifica se já existe
            cur.execute('SELECT id FROM auth."user" WHERE email = %s', (email,))
            if cur.fetchone():
                print(f"Usuário {email} já existe. Pulando.")
                return

            # Cria o usuário
            cur.execute(
                '''
                INSERT INTO auth."user" (id, email, name, "emailVerified", "createdAt", "updatedAt")
                VALUES (%s, %s, %s, true, %s, %s)
                ''',
                (user_id, email, name, now, now),
            )

            # Cria a entrada de account (email/password)
            account_id = str(uuid.uuid4())
            cur.execute(
                '''
                INSERT INTO auth.account (id, "accountId", "providerId", "userId", password, "createdAt", "updatedAt")
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ''',
                (account_id, user_id, "credential", user_id, hashed, now, now),
            )

            conn.commit()

    print(f"Usuário criado: {name} <{email}> (id: {user_id})")


if __name__ == "__main__":
    main()
