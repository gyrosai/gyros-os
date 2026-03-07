import { ShieldCheck } from "lucide-react";
import { ChangePasswordForm } from "@/components/change-password-form";
import { requireSession } from "@/lib/session";

export default async function SettingsPage() {
  const session = await requireSession();

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <ShieldCheck className="h-6 w-6" />
        <h1 className="text-2xl font-semibold">Seguranca</h1>
      </div>

      <div className="rounded-lg border border-amber-500/40 bg-amber-500/10 p-4 text-sm text-amber-950">
        Em ambientes educacionais, o seed inicial pode usar credenciais padrao.
        Em qualquer ambiente compartilhado ou de producao, altere a senha logo
        no primeiro acesso.
      </div>

      <ChangePasswordForm email={session.user.email} />
    </div>
  );
}
