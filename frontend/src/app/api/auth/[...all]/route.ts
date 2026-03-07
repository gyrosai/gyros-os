/**
 * Catch-all route para o Better Auth.
 *
 * Todas as chamadas de autenticação (login, logout, sessão, etc.)
 * passam por /api/auth/* e são tratadas pelo Better Auth.
 */
import { auth } from "@/lib/auth";
import { toNextJsHandler } from "better-auth/next-js";

export const { GET, POST } = toNextJsHandler(auth);
