"use client";

/**
 * Sidebar G4-style — duas zonas verticais:
 *   1. Header (nome do studio)
 *   2. CTA "Nova conversa" + nav primária (kb, chat) — gated por features
 *   3. Área de threads (placeholder nesta fatia — Fatia 4.3 popula)
 *   4. Nav secundária (operacional, gated por feature "internal")
 *   5. Rodapé com logout
 */

import { useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  MessageSquare,
  BookOpen,
  LayoutDashboard,
  ListOrdered,
  Video,
  Bot,
  ShieldCheck,
  LogOut,
  Menu,
  X,
  Plus,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { signOut } from "@/lib/auth-client";
import { studioConfig } from "@/lib/runtime-config";
import { cn } from "@/lib/utils";

type NavItem = {
  href: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
};

const PRIMARY_NAV: Array<NavItem & { feature: string }> = [
  { href: "/chat", label: "Chat", icon: MessageSquare, feature: "chat" },
  { href: "/kb", label: "Base de Conhecimento", icon: BookOpen, feature: "kb" },
];

const INTERNAL_NAV: NavItem[] = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/queue", label: "Fila WhatsApp", icon: ListOrdered },
  { href: "/chats", label: "Reuniões", icon: Video },
  { href: "/agents", label: "Agentes", icon: Bot },
  { href: "/settings", label: "Settings", icon: ShieldCheck },
];

export function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [signingOut, setSigningOut] = useState(false);

  const primaryItems = PRIMARY_NAV.filter((item) =>
    studioConfig.features.has(item.feature)
  );
  const showInternal = studioConfig.features.has("internal");

  function isActive(href: string): boolean {
    if (href === "/") return pathname === "/";
    return pathname === href || pathname.startsWith(`${href}/`);
  }

  async function handleSignOut() {
    setSigningOut(true);
    try {
      await signOut();
    } finally {
      setOpen(false);
      router.push("/login");
      router.refresh();
      setSigningOut(false);
    }
  }

  function handleNewConversation() {
    // TODO: nova conversa — Fatia 4.3
    console.log("TODO: nova conversa — Fatia 4.3");
  }

  return (
    <>
      <Button
        variant="ghost"
        size="icon"
        className="fixed top-4 left-4 z-50 md:hidden"
        onClick={() => setOpen(!open)}
      >
        {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
      </Button>

      {open && (
        <div
          className="fixed inset-0 z-40 bg-black/40 backdrop-blur-sm md:hidden"
          onClick={() => setOpen(false)}
        />
      )}

      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-40 flex w-[260px] flex-col border-r bg-muted/30 transition-transform md:translate-x-0",
          open ? "translate-x-0" : "-translate-x-full"
        )}
      >
        {/* Header — texto-only, tipografia protagonista */}
        <div className="px-4 py-5 border-b">
          <h1 className="text-base font-semibold tracking-tight">
            {studioConfig.name}
          </h1>
        </div>

        {/* CTA + nav primária */}
        <div className="px-3 pt-4 pb-2 space-y-4">
          <button
            type="button"
            onClick={handleNewConversation}
            className="brand-bg flex w-full items-center justify-center gap-2 rounded-lg px-3 py-2.5 text-sm font-medium text-white transition hover:opacity-90"
          >
            <Plus className="h-4 w-4" />
            Nova conversa
          </button>

          {primaryItems.length > 0 && (
            <nav className="space-y-0.5">
              {primaryItems.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={() => setOpen(false)}
                  className={cn(
                    "flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors",
                    isActive(item.href)
                      ? "bg-muted brand-text font-medium"
                      : "text-foreground/70 hover:bg-muted/60 hover:text-foreground"
                  )}
                >
                  <item.icon className="h-4 w-4" />
                  {item.label}
                </Link>
              ))}
            </nav>
          )}
        </div>

        {/* Threads — placeholder 4.0, populado na 4.3 */}
        <div className="flex-1 overflow-y-auto px-4 py-4">
          <p className="text-[11px] uppercase tracking-wider text-muted-foreground mb-2">
            Conversas
          </p>
          <p className="text-xs italic text-muted-foreground/70">
            Em breve — suas conversas com {studioConfig.agentName} aparecerão
            aqui.
          </p>
        </div>

        {/* Nav secundária (operacional) */}
        {showInternal && (
          <nav className="px-3 py-3 border-t space-y-0.5">
            {INTERNAL_NAV.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => setOpen(false)}
                className={cn(
                  "flex items-center gap-3 rounded-lg px-3 py-2 text-xs transition-colors",
                  isActive(item.href)
                    ? "bg-muted text-foreground font-medium"
                    : "text-muted-foreground hover:bg-muted/60 hover:text-foreground"
                )}
              >
                <item.icon className="h-3.5 w-3.5" />
                {item.label}
              </Link>
            ))}
          </nav>
        )}

        {/* Rodapé: logout */}
        <div className="px-3 py-3 border-t">
          <button
            type="button"
            onClick={handleSignOut}
            disabled={signingOut}
            className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-muted/60 hover:text-foreground disabled:opacity-50"
          >
            <LogOut className="h-4 w-4" />
            {signingOut ? "Saindo..." : "Sair"}
          </button>
        </div>
      </aside>
    </>
  );
}
