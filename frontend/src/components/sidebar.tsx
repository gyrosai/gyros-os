"use client";

/**
 * Sidebar G4-OS — duas peças:
 *   1. IconBar (52px): ícones de navegação sobre o cinza base
 *   2. SessionsPanel (252px): card branco flutuante com threads
 */

import { useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { signOut } from "@/lib/auth-client";
import { studioConfig } from "@/lib/runtime-config";

/* ── SVG Icons (inline, com stroke-linecap/linejoin round) ── */

function ChatIcon({ active }: { active?: boolean }) {
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke={active ? "#444" : "#888"}
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
    </svg>
  );
}

function KbIcon({ active }: { active?: boolean }) {
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke={active ? "#444" : "#888"}
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z" />
      <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z" />
    </svg>
  );
}

function DashboardIcon({ active }: { active?: boolean }) {
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke={active ? "#444" : "#888"}
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <rect x="3" y="3" width="7" height="7" />
      <rect x="14" y="3" width="7" height="7" />
      <rect x="14" y="14" width="7" height="7" />
      <rect x="3" y="14" width="7" height="7" />
    </svg>
  );
}

function SettingsIcon({ active }: { active?: boolean }) {
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke={active ? "#444" : "#888"}
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
    </svg>
  );
}

/* ── Icon button wrapper ── */

function IconButton({
  href,
  active,
  children,
}: {
  href: string;
  active: boolean;
  children: React.ReactNode;
}) {
  return (
    <Link
      href={href}
      style={{
        width: "38px",
        height: "38px",
        borderRadius: "10px",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: active ? "rgba(0,0,0,0.07)" : "transparent",
        transition: "background 150ms",
      }}
      onMouseEnter={(e) => {
        if (!active) e.currentTarget.style.background = "rgba(0,0,0,0.05)";
      }}
      onMouseLeave={(e) => {
        if (!active) e.currentTarget.style.background = "transparent";
      }}
    >
      {children}
    </Link>
  );
}

/* ── IconBar (52px) ── */

export function IconBar() {
  const pathname = usePathname();
  const router = useRouter();
  const [signingOut, setSigningOut] = useState(false);

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
      router.push("/login");
      router.refresh();
      setSigningOut(false);
    }
  }

  const brandColor =
    studioConfig.brand.kind === "solid"
      ? studioConfig.brand.color
      : studioConfig.brand.to;

  return (
    <nav
      style={{
        width: "52px",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        paddingTop: "12px",
        paddingBottom: "12px",
        gap: "4px",
        flexShrink: 0,
      }}
    >
      {/* Primary nav: Chat, KB */}
      {studioConfig.features.has("chat") && (
        <IconButton href="/chat" active={isActive("/chat") || isActive("/")}>
          <ChatIcon active={isActive("/chat") || isActive("/")} />
        </IconButton>
      )}
      {studioConfig.features.has("kb") && (
        <IconButton href="/kb" active={isActive("/kb")}>
          <KbIcon active={isActive("/kb")} />
        </IconButton>
      )}

      {/* Separator + internal nav */}
      {showInternal && (
        <>
          <div
            style={{
              width: "24px",
              height: "1px",
              background: "rgba(0,0,0,0.1)",
              margin: "4px 0",
            }}
          />
          <IconButton href="/dashboard" active={isActive("/dashboard")}>
            <DashboardIcon active={isActive("/dashboard")} />
          </IconButton>
          <IconButton href="/settings" active={isActive("/settings")}>
            <SettingsIcon active={isActive("/settings")} />
          </IconButton>
        </>
      )}

      {/* Spacer */}
      <div style={{ flex: 1 }} />

      {/* Avatar */}
      <button
        type="button"
        onClick={handleSignOut}
        disabled={signingOut}
        style={{
          width: "32px",
          height: "32px",
          borderRadius: "50%",
          background: brandColor,
          color: "#fff",
          fontSize: "13px",
          fontWeight: 600,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          border: "none",
          cursor: "pointer",
          opacity: signingOut ? 0.5 : 1,
          transition: "opacity 150ms",
        }}
        title="Sair"
      >
        U
      </button>
    </nav>
  );
}

/* ── SessionsPanel (252px card branco) ── */

import { useCallback, useEffect } from "react";
import { type ChatThread, listThreads } from "@/lib/api-client";

function groupByDate(
  threads: ChatThread[],
): { label: string; threads: ChatThread[] }[] {
  const groups: Record<string, ChatThread[]> = {};
  const order: string[] = [];
  const now = new Date();
  const today = now.toDateString();
  const yesterday = new Date(now.getTime() - 86400000).toDateString();

  for (const t of threads) {
    const d = new Date(t.updated_at || t.created_at || "");
    let label: string;
    if (d.toDateString() === today) label = "Hoje";
    else if (d.toDateString() === yesterday) label = "Ontem";
    else
      label = d.toLocaleDateString("pt-BR", {
        day: "numeric",
        month: "short",
      });

    if (!groups[label]) {
      groups[label] = [];
      order.push(label);
    }
    groups[label].push(t);
  }

  return order.map((label) => ({ label, threads: groups[label] }));
}

export function SessionsPanel() {
  const pathname = usePathname();
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<"recentes" | "favoritas">(
    "recentes",
  );
  const [threads, setThreads] = useState<ChatThread[]>([]);
  const [activeThreadId, setActiveThreadId] = useState<string | null>(null);

  const fetchThreads = useCallback(async () => {
    try {
      const data = await listThreads();
      setThreads(data);
    } catch {
      // silently fail
    }
  }, []);

  // Fetch threads on mount and when navigating to /chat
  useEffect(() => {
    fetchThreads();
  }, [fetchThreads, pathname]);

  // Listen for thread updates (after sending a message)
  useEffect(() => {
    function handleUpdate() {
      fetchThreads();
    }
    window.addEventListener("threads-updated", handleUpdate);
    return () => window.removeEventListener("threads-updated", handleUpdate);
  }, [fetchThreads]);

  function selectThread(id: string) {
    setActiveThreadId(id);
    if (pathname !== "/chat") {
      router.push(`/chat?thread=${id}`);
    } else {
      window.dispatchEvent(
        new CustomEvent("select-thread", { detail: { threadId: id } }),
      );
    }
  }

  function newSession() {
    setActiveThreadId(null);
    if (pathname !== "/chat") {
      router.push("/chat");
    } else {
      window.dispatchEvent(
        new CustomEvent("select-thread", { detail: { threadId: null } }),
      );
    }
  }

  const grouped = groupByDate(threads);

  return (
    <aside
      style={{
        width: "252px",
        background: "#fff",
        borderRadius: "14px",
        margin: "8px 0 8px 0",
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
        flexShrink: 0,
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: "16px 16px 12px",
        }}
      >
        <h2
          style={{
            fontSize: "14px",
            fontWeight: 600,
            color: "#1a1a1a",
            marginBottom: "12px",
          }}
        >
          {studioConfig.name}
        </h2>

        {/* Botão Nova sessão */}
        <button
          type="button"
          style={{
            width: "100%",
            height: "38px",
            borderRadius: "10px",
            border: "1px solid #ddd",
            background: "#fff",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: "6px",
            fontSize: "13px",
            fontWeight: 500,
            color: "#555",
            cursor: "pointer",
            transition: "background 150ms",
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = "#f8f8f8";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = "#fff";
          }}
          onClick={newSession}
        >
          <span style={{ fontSize: "16px", lineHeight: 1 }}>+</span>
          Nova sessão
        </button>
      </div>

      {/* Tabs */}
      <div
        style={{
          display: "flex",
          gap: "16px",
          padding: "0 16px",
          borderBottom: "1px solid #f0f0f0",
        }}
      >
        {(["recentes", "favoritas"] as const).map((tab) => (
          <button
            key={tab}
            type="button"
            onClick={() => setActiveTab(tab)}
            style={{
              fontSize: "12px",
              fontWeight: 500,
              color: activeTab === tab ? "#555" : "#bbb",
              background: "none",
              border: "none",
              borderBottom:
                activeTab === tab
                  ? "2px solid #555"
                  : "2px solid transparent",
              padding: "8px 0",
              cursor: "pointer",
              textTransform: "capitalize",
              transition: "color 150ms",
            }}
          >
            {tab.charAt(0).toUpperCase() + tab.slice(1)}
          </button>
        ))}
      </div>

      {/* Threads area */}
      <div
        style={{
          flex: 1,
          overflowY: "auto",
          padding: "16px",
        }}
      >
        {activeTab === "recentes" && threads.length === 0 && (
          <p
            style={{
              fontSize: "13px",
              color: "#bbb",
              lineHeight: 1.5,
            }}
          >
            Suas conversas com {studioConfig.agentName} aparecerão aqui.
          </p>
        )}

        {activeTab === "recentes" &&
          grouped.map((group) => (
            <div key={group.label} style={{ marginBottom: "12px" }}>
              <p
                style={{
                  fontSize: "10.5px",
                  textTransform: "uppercase",
                  color: "#ccc",
                  letterSpacing: "0.05em",
                  fontWeight: 500,
                  marginBottom: "6px",
                }}
              >
                {group.label}
              </p>
              {group.threads.map((t) => (
                <button
                  key={t.id}
                  type="button"
                  onClick={() => selectThread(t.id)}
                  style={{
                    display: "block",
                    width: "100%",
                    textAlign: "left",
                    padding: "8px 10px",
                    borderRadius: "8px",
                    border: "none",
                    background:
                      activeThreadId === t.id
                        ? "rgba(0,0,0,0.05)"
                        : "transparent",
                    cursor: "pointer",
                    fontSize: "13px",
                    color: "#444",
                    whiteSpace: "nowrap",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    transition: "background 150ms",
                    marginBottom: "2px",
                  }}
                  onMouseEnter={(e) => {
                    if (activeThreadId !== t.id)
                      e.currentTarget.style.background = "rgba(0,0,0,0.03)";
                  }}
                  onMouseLeave={(e) => {
                    if (activeThreadId !== t.id)
                      e.currentTarget.style.background = "transparent";
                  }}
                >
                  {t.title || "Sem título"}
                </button>
              ))}
            </div>
          ))}

        {activeTab === "favoritas" && (
          <p
            style={{
              fontSize: "13px",
              color: "#bbb",
              lineHeight: 1.5,
            }}
          >
            Favoritas em breve.
          </p>
        )}
      </div>
    </aside>
  );
}
