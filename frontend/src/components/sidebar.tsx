"use client";

/**
 * Sidebar de navegação do painel administrativo.
 *
 * Componente client-side para interatividade (estado de abertura no mobile,
 * highlight da rota ativa via usePathname).
 */

import { useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  LayoutDashboard,
  MessageSquare,
  Bot,
  ListOrdered,
  ShieldCheck,
  LogOut,
  Menu,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { signOut } from "@/lib/auth-client";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/chats", label: "Conversas", icon: MessageSquare },
  { href: "/agents", label: "Agentes", icon: Bot },
  { href: "/queue", label: "Fila", icon: ListOrdered },
  { href: "/settings", label: "Seguranca", icon: ShieldCheck },
];

export function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [signingOut, setSigningOut] = useState(false);

  // Verifica se a rota está ativa (match exato para "/" e prefixo para sub-rotas)
  function isActive(href: string): boolean {
    if (href === "/") return pathname === "/";
    return pathname.startsWith(href);
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

  return (
    <>
      {/* Botão mobile — só aparece em telas pequenas */}
      <Button
        variant="ghost"
        size="icon"
        className="fixed top-4 left-4 z-50 md:hidden"
        onClick={() => setOpen(!open)}
      >
        {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
      </Button>

      {/* Overlay mobile */}
      {open && (
        <div
          className="fixed inset-0 z-40 bg-black/50 md:hidden"
          onClick={() => setOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r bg-background transition-transform md:translate-x-0",
          open ? "translate-x-0" : "-translate-x-full"
        )}
      >
        <div className="flex h-14 items-center px-6 font-semibold">
          WhatsApp Admin
        </div>
        <Separator />
        <nav className="flex-1 space-y-1 px-3 py-4">
          {NAV_ITEMS.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              onClick={() => setOpen(false)}
              className={cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors",
                isActive(item.href)
                  ? "bg-accent text-accent-foreground font-medium"
                  : "text-muted-foreground hover:bg-accent/50 hover:text-foreground"
              )}
            >
              <item.icon className="h-4 w-4" />
              {item.label}
            </Link>
          ))}
        </nav>
        <div className="px-3 pb-4">
          <Separator className="mb-3" />
          <Button
            type="button"
            variant="ghost"
            className="w-full justify-start gap-3"
            onClick={handleSignOut}
            disabled={signingOut}
          >
            <LogOut className="h-4 w-4" />
            {signingOut ? "Saindo..." : "Sair"}
          </Button>
        </div>
      </aside>
    </>
  );
}
