import { LoginForm } from "@/components/login-form";
import {
  DEFAULT_ADMIN_EMAIL,
  DEFAULT_ADMIN_PASSWORD,
} from "@/lib/admin-defaults";
import { ensureDefaultAdmin } from "@/lib/bootstrap-admin";
import {
  ensureFrontendRuntimeConfig,
  isProductionEnvironment,
} from "@/lib/runtime-config";

export const dynamic = "force-dynamic";

export default async function LoginPage() {
  ensureFrontendRuntimeConfig();

  const production = isProductionEnvironment();
  const bootstrapped = await ensureDefaultAdmin();
  const helperMessage = production
    ? "Em production, o primeiro admin deve ser criado manualmente com o script de seed e credenciais fortes."
    : undefined;

  return (
    <LoginForm
      defaultEmail={bootstrapped ? DEFAULT_ADMIN_EMAIL : ""}
      defaultPassword={bootstrapped ? DEFAULT_ADMIN_PASSWORD : ""}
      showBootstrapHint={bootstrapped}
      helperMessage={helperMessage}
    />
  );
}
