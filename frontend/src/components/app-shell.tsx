"use client";

/**
 * Shell da aplicação — layout em 3 colunas estilo G4 OS:
 *   1. Barra de ícones (52px) — sem background, sobre o cinza base
 *   2. Painel de sessões (252px) — card branco flutuante
 *   3. Área principal — card branco flutuante
 *
 * Na rota /login, renderiza apenas o conteúdo (full viewport).
 */

import { usePathname } from "next/navigation";
import { IconBar } from "@/components/sidebar";
import { SessionsPanel } from "@/components/sidebar";

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isLogin = pathname === "/login";

  if (isLogin) {
    return <>{children}</>;
  }

  return (
    <div
      style={{
        display: "flex",
        height: "100vh",
        background: "#F0F0EE",
      }}
    >
      {/* Barra de ícones: 52px, sem bg, sobre o cinza */}
      <IconBar />

      {/* Painel de sessões: card branco flutuante */}
      <SessionsPanel />

      {/* Main: card branco flutuante */}
      <main
        style={{
          flex: 1,
          background: "#fff",
          borderRadius: "14px",
          margin: "8px",
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
        }}
      >
        {children}
      </main>
    </div>
  );
}
