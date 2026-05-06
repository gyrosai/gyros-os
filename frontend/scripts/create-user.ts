/**
 * Script para criar um usuário adicional com email/senha (provider "credential").
 *
 * Espelha exatamente o padrão do bootstrap-admin-core.ts, mas SEM o guard
 * "só cria se zero users". Cria sempre que chamado, idempotente por email
 * (se o email já existir, não duplica — usa unique violation do Postgres).
 *
 * Uso:
 *   npx tsx scripts/create-user.ts <email> <password> "<name>"
 *
 * Variáveis de ambiente necessárias:
 *   DATABASE_URL
 */

import { hashPassword } from "better-auth/crypto";
import { Pool } from "pg";

const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
  options: "-c search_path=auth,public",
});

function isUniqueViolation(error: unknown): boolean {
  return (
    typeof error === "object" &&
    error !== null &&
    "code" in error &&
    (error as { code: string }).code === "23505"
  );
}

async function createUser(email: string, password: string, name: string): Promise<{ created: boolean; userId: string | null }> {
  const client = await pool.connect();

  try {
    await client.query("BEGIN");

    // Verifica se o email já existe — idempotência amigável
    const existing = await client.query<{ id: string }>(
      `SELECT id FROM auth."user" WHERE email = $1`,
      [email]
    );

    if (existing.rows.length > 0) {
      await client.query("ROLLBACK");
      console.log(`Usuário ${email} já existe (id: ${existing.rows[0].id}). Pulando.`);
      return { created: false, userId: existing.rows[0].id };
    }

    const userId = crypto.randomUUID();
    const accountId = crypto.randomUUID();
    const now = new Date();
    const passwordHash = await hashPassword(password);

    await client.query(
      `INSERT INTO auth."user"
        (id, name, email, "emailVerified", image, "createdAt", "updatedAt")
       VALUES ($1, $2, $3, $4, $5, $6, $7)`,
      [userId, name, email, false, null, now, now]
    );

    await client.query(
      `INSERT INTO auth.account
        (
          id,
          "accountId",
          "providerId",
          "userId",
          "accessToken",
          "refreshToken",
          "idToken",
          "accessTokenExpiresAt",
          "refreshTokenExpiresAt",
          password,
          "createdAt",
          "updatedAt"
        )
       VALUES
        ($1, $2, $3, $4, NULL, NULL, NULL, NULL, NULL, $5, $6, $7)`,
      [accountId, userId, "credential", userId, passwordHash, now, now]
    );

    await client.query("COMMIT");
    console.log(`✓ Usuário criado: ${name} <${email}> (id: ${userId})`);
    return { created: true, userId };
  } catch (error) {
    await client.query("ROLLBACK").catch(() => undefined);

    if (isUniqueViolation(error)) {
      console.log(`Usuário ${email} já existe (race condition). Pulando.`);
      return { created: false, userId: null };
    }

    throw error;
  } finally {
    client.release();
  }
}

async function main() {
  const [, , email, password, ...nameParts] = process.argv;
  const name = nameParts.join(" ");

  if (!email || !password || !name) {
    console.error("Uso: npx tsx scripts/create-user.ts <email> <password> \"<name>\"");
    process.exit(1);
  }

  if (!process.env.DATABASE_URL) {
    console.error("ERROR: DATABASE_URL não setada");
    process.exit(1);
  }

  try {
    await createUser(email, password, name);
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : String(error);
    console.error("Erro ao criar user:", message);
    process.exit(1);
  } finally {
    await pool.end();
  }
}

main().then(() => process.exit(0));
