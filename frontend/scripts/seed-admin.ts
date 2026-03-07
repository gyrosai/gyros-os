/**
 * Script para criar o primeiro usuario admin.
 *
 * Em um deploy limpo nao existe usuario — este script cria o admin inicial
 * usando a API do Better Auth diretamente (sem precisar de signup no frontend).
 *
 * Uso:
 *   npx tsx scripts/seed-admin.ts
 *
 * Defaults educacionais:
 *   email: ronnald@rhawk.pro
 *   senha: meuSistema
 *
 * Variaveis de ambiente opcionais:
 *   ADMIN_EMAIL    — sobrescreve o email padrao
 *   ADMIN_PASSWORD — sobrescreve a senha padrao (minimo 8 caracteres)
 *   DATABASE_URL, BETTER_AUTH_SECRET (mesmas do frontend)
 *
 * Opcionais:
 *   ADMIN_NAME — nome de exibicao (default: "Admin")
 *
 * O script e idempotente: se o email ja existe, nao cria duplicata.
 */

import { auth } from "../src/lib/auth";
import {
  DEFAULT_ADMIN_EMAIL,
  DEFAULT_ADMIN_NAME,
  DEFAULT_ADMIN_PASSWORD,
} from "../src/lib/admin-defaults";

const ADMIN_EMAIL: string = process.env.ADMIN_EMAIL || DEFAULT_ADMIN_EMAIL;
const ADMIN_PASSWORD: string =
  process.env.ADMIN_PASSWORD || DEFAULT_ADMIN_PASSWORD;
const ADMIN_NAME: string = process.env.ADMIN_NAME || DEFAULT_ADMIN_NAME;

async function main() {
  console.log(`Criando admin: ${ADMIN_EMAIL}`);

  if (
    ADMIN_EMAIL === DEFAULT_ADMIN_EMAIL &&
    ADMIN_PASSWORD === DEFAULT_ADMIN_PASSWORD
  ) {
    console.log(
      "Usando credenciais padrao do curso. Recomenda-se trocar em ambientes nao educacionais."
    );
  }

  try {
    const result = await auth.api.signUpEmail({
      body: {
        email: ADMIN_EMAIL,
        password: ADMIN_PASSWORD,
        name: ADMIN_NAME,
      },
    });

    if (result.user) {
      console.log(`Admin criado com sucesso: ${result.user.email}`);
    } else {
      console.log("Resultado inesperado:", result);
    }
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : String(error);

    // Better Auth retorna erro se o email ja existe
    if (message.includes("already") || message.includes("exists")) {
      console.log(`Admin ${ADMIN_EMAIL} ja existe — nada a fazer.`);
      return;
    }

    console.error("Erro ao criar admin:", message);
    process.exit(1);
  }
}

main().then(() => process.exit(0));
