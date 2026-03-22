/**
 * Catch-all route para o Better Auth.
 *
 * Todas as chamadas de autenticação (login, logout, sessão, etc.)
 * passam por /api/auth/* e são tratadas pelo Better Auth.
 */
import { auth } from "@/lib/auth";
import { ensureFrontendRuntimeConfig } from "@/lib/runtime-config";
import { toNextJsHandler } from "better-auth/next-js";

const handlers = toNextJsHandler(auth);

export async function GET(request: Request) {
  ensureFrontendRuntimeConfig();
  return handlers.GET(request);
}

export async function POST(request: Request) {
  ensureFrontendRuntimeConfig();
  return handlers.POST(request);
}
