/**
 * Cliente HTTP tipado para consumo client-side (browser).
 *
 * Diferente de api.ts (server-only, usa INTERNAL_SERVICE_TOKEN),
 * este módulo faz requests diretos do browser para a API com
 * credentials: "include" para enviar o cookie Better Auth.
 *
 * Usado pelas telas /kb e /chat (Client Components).
 */

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function apiFetch<T>(
  path: string,
  options?: RequestInit,
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    credentials: "include",
    ...options,
    headers: {
      ...options?.headers,
    },
  });

  if (!res.ok) {
    if (res.status === 401) {
      throw new Error("Not authenticated");
    }
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `API error ${res.status}`);
  }

  return res.json();
}

// ---- KB ----

export interface KBDoc {
  id: string;
  title: string;
  source_type: string;
  file_name: string | null;
  file_size: number | null;
  mime_type: string | null;
  chunk_count: number;
  created_at: string | null;
}

export async function uploadDocument(file: File): Promise<{
  doc_id: string;
  filename: string;
  num_chunks: number;
  status: string;
}> {
  const form = new FormData();
  form.append("file", file);
  return apiFetch("/api/kb/upload", { method: "POST", body: form });
}

export async function listDocuments(): Promise<KBDoc[]> {
  return apiFetch("/api/kb/docs");
}

export async function deleteDocument(docId: string): Promise<void> {
  await apiFetch(`/api/kb/docs/${docId}`, { method: "DELETE" });
}

export async function downloadDocument(docId: string, filename?: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/kb/docs/${docId}/download`, {
    credentials: "include",
  });

  if (!res.ok) {
    if (res.status === 401) {
      throw new Error("Not authenticated");
    }
    throw new Error(`Download failed: ${res.status}`);
  }

  const blob = await res.blob();

  // Use provided filename, fall back to Content-Disposition header
  let resolvedName = filename || "download";
  if (!filename) {
    const disposition = res.headers.get("Content-Disposition");
    if (disposition) {
      const match = disposition.match(/filename="?([^"]+)"?/);
      if (match) resolvedName = match[1];
    }
  }

  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = resolvedName;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// ---- Chat ----

export interface ChatThread {
  id: string;
  title: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export async function sendMessage(
  message: string,
  threadId?: string,
): Promise<{
  reply: string;
  thread_id: string;
  sources: string[];
}> {
  return apiFetch("/api/chat/messages", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, thread_id: threadId }),
  });
}

export async function listThreads(): Promise<ChatThread[]> {
  return apiFetch("/api/chat/threads");
}

export async function getThreadMessages(
  threadId: string,
): Promise<ChatMessage[]> {
  return apiFetch(`/api/chat/threads/${threadId}/messages`);
}
