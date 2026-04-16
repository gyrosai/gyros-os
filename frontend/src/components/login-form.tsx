"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { signIn } from "@/lib/auth-client";
import { Button } from "@/components/ui/button";
import { studioConfig } from "@/lib/runtime-config";

interface LoginFormProps {
  defaultEmail?: string;
  defaultPassword?: string;
  showBootstrapHint?: boolean;
  helperMessage?: string;
}

export function LoginForm({
  defaultEmail = "",
  defaultPassword = "",
  showBootstrapHint = false,
  helperMessage,
}: LoginFormProps) {
  const router = useRouter();
  const [email, setEmail] = useState(defaultEmail);
  const [password, setPassword] = useState(defaultPassword);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setLoading(true);

    const { error: authError } = await signIn.email({
      email,
      password,
      callbackURL: "/",
    });

    if (authError) {
      setError(authError.message || "Erro ao fazer login");
      setLoading(false);
      return;
    }

    router.push("/");
    router.refresh();
  }

  return (
    <div className="flex min-h-screen">
      {/* Painel esquerdo — brand da instância (escondido no mobile) */}
      <div className="brand-bg relative hidden w-[45%] overflow-hidden md:flex md:flex-col md:justify-between">
        {/* Overlay sutil pra dar profundidade tanto em solid quanto em gradient */}
        <div
          className="absolute inset-0"
          style={{
            background:
              "radial-gradient(ellipse at 30% 20%, rgba(255,255,255,0.10), transparent 60%), radial-gradient(ellipse at 80% 80%, rgba(0,0,0,0.15), transparent 50%)",
          }}
        />

        <div className="relative z-10 flex flex-1 flex-col justify-center px-10 lg:px-14">
          <h1 className="mb-4 text-3xl font-semibold tracking-tight text-white lg:text-4xl">
            {studioConfig.name}
          </h1>
          <p className="max-w-sm text-sm leading-relaxed text-white/70">
            Sua plataforma de conhecimento e conversa com {studioConfig.agentName}.
          </p>
        </div>
      </div>

      {/* Painel direito — formulário */}
      <div className="flex flex-1 items-center justify-center px-6 py-12">
        <div className="w-full max-w-sm">
          {/* Título no mobile (painel esquerdo está oculto) */}
          <div className="mb-8 md:hidden">
            <h1 className="text-base font-semibold tracking-tight">
              {studioConfig.name}
            </h1>
          </div>

          <div className="mb-6">
            <h2 className="text-xl font-semibold">Entrar</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Acesse {studioConfig.name}
            </p>
          </div>

          {helperMessage && (
            <div className="mb-4 rounded-lg bg-muted px-4 py-3 text-sm text-muted-foreground">
              {helperMessage}
            </div>
          )}

          {showBootstrapHint && (
            <div className="mb-4 rounded-lg bg-primary/5 border border-primary/10 px-4 py-3 text-sm text-muted-foreground">
              Primeiro admin criado automaticamente a partir de
              <strong> ADMIN_EMAIL</strong> e <strong>ADMIN_PASSWORD</strong>.
              Entre e troque a senha em <strong>/settings</strong>.
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <label htmlFor="email" className="text-sm font-medium">
                Email
              </label>
              <input
                id="email"
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                required
                className="flex h-10 w-full rounded-lg border bg-transparent px-3 py-2 text-sm outline-none transition-colors focus:border-primary focus:ring-2 focus:ring-ring/20"
                placeholder="Digite seu email"
              />
            </div>
            <div className="space-y-2">
              <label htmlFor="password" className="text-sm font-medium">
                Senha
              </label>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                required
                minLength={8}
                className="flex h-10 w-full rounded-lg border bg-transparent px-3 py-2 text-sm outline-none transition-colors focus:border-primary focus:ring-2 focus:ring-ring/20"
                placeholder="Digite sua senha"
              />
            </div>

            {error && (
              <div className="rounded-lg bg-destructive/10 px-4 py-3 text-sm text-destructive">
                {error}
              </div>
            )}

            <Button
              type="submit"
              className="brand-bg w-full h-10 text-white hover:opacity-90"
              disabled={loading}
            >
              {loading ? "Entrando..." : "Entrar"}
            </Button>
          </form>
        </div>
      </div>
    </div>
  );
}
