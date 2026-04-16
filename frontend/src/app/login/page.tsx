import { LoginForm } from "@/components/login-form";
import { ensureFrontendRuntimeConfig } from "@/lib/runtime-config";

export const dynamic = "force-dynamic";

export default async function LoginPage() {
  ensureFrontendRuntimeConfig();

  return <LoginForm />;
}
