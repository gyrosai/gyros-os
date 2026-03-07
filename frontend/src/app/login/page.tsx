import { LoginForm } from "@/components/login-form";
import {
  DEFAULT_ADMIN_EMAIL,
  DEFAULT_ADMIN_PASSWORD,
} from "@/lib/admin-defaults";
import { ensureDefaultAdmin } from "@/lib/bootstrap-admin";

export const dynamic = "force-dynamic";

export default async function LoginPage() {
  const bootstrapped = await ensureDefaultAdmin();

  return (
    <LoginForm
      defaultEmail={bootstrapped ? DEFAULT_ADMIN_EMAIL : ""}
      defaultPassword={bootstrapped ? DEFAULT_ADMIN_PASSWORD : ""}
      showBootstrapHint={bootstrapped}
    />
  );
}
