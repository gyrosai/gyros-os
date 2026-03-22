import "server-only";

import { auth, authPool } from "@/lib/auth";
import {
  DEFAULT_ADMIN_EMAIL,
  DEFAULT_ADMIN_NAME,
  DEFAULT_ADMIN_PASSWORD,
} from "@/lib/admin-defaults";
import {
  canAutoBootstrapAdmin,
  ensureFrontendRuntimeConfig,
} from "@/lib/runtime-config";

function isAlreadyExistsError(error: unknown): boolean {
  const message = error instanceof Error ? error.message : String(error);
  return (
    message.includes("already") ||
    message.includes("exists") ||
    message.includes("duplicate")
  );
}

export async function ensureDefaultAdmin(): Promise<boolean> {
  if (!canAutoBootstrapAdmin()) {
    return false;
  }

  ensureFrontendRuntimeConfig();

  const tableResult = await authPool.query<{ table_name: string | null }>(
    `SELECT to_regclass('auth."user"') AS table_name`
  );

  const tableName = tableResult.rows[0]?.table_name ?? null;

  if (tableName) {
    const countResult = await authPool.query<{ count: number }>(
      `SELECT COUNT(*)::int AS count FROM auth."user"`
    );

    if ((countResult.rows[0]?.count ?? 0) > 0) {
      return false;
    }
  }

  try {
    const result = await auth.api.signUpEmail({
      body: {
        email: DEFAULT_ADMIN_EMAIL,
        password: DEFAULT_ADMIN_PASSWORD,
        name: DEFAULT_ADMIN_NAME,
      },
    });

    return Boolean(result.user);
  } catch (error) {
    if (isAlreadyExistsError(error)) {
      return false;
    }

    throw error;
  }
}
