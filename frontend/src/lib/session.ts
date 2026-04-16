/**
 * Validacao de sessao server-side.
 *
 * Centraliza a verificacao real da sessao do Better Auth para uso
 * em Server Components e Route Handlers. Diferente do proxy.ts
 * (que so checa o cookie), aqui fazemos a chamada ao banco para
 * confirmar que a sessao e valida.
 */
import "server-only";

import { headers } from "next/headers";
import { redirect } from "next/navigation";
import { auth } from "@/lib/auth";
import { ensureFrontendRuntimeConfig } from "@/lib/runtime-config";

/**
 * Retorna a sessao validada ou redireciona para /login.
 *
 * Deve ser chamada no inicio de cada Server Component e Route Handler
 * que precisa de autenticacao. Faz a validacao completa (banco de dados),
 * nao apenas checagem de cookie.
 */
export async function requireSession() {
  ensureFrontendRuntimeConfig();

  const h = await headers();

  // Debug: lista todos os cookies que chegaram
  const cookieHeader = h.get("cookie");
  console.log("[SESSION_DEBUG] cookie header:", cookieHeader ? cookieHeader.substring(0, 100) : "EMPTY");
  console.log("[SESSION_DEBUG] has session token:", cookieHeader?.includes("better-auth.session_token") ?? false);

  const session = await auth.api.getSession({ headers: h });
  console.log("[SESSION_DEBUG] session result:", session ? "FOUND" : "NULL");

  if (!session) {
    redirect("/login");
  }

  return session;
}
