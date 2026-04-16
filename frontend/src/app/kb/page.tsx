"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  FileText,
  FileSpreadsheet,
  Upload,
  MoreVertical,
  Download,
  Trash2,
  Loader2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  type KBDoc,
  listDocuments,
  uploadDocument,
  deleteDocument,
  downloadDocument,
} from "@/lib/api-client";
import { studioConfig } from "@/lib/runtime-config";

const ACCEPTED_EXTENSIONS = ".txt,.md,.csv,.pdf,.docx";

function fileIcon(fileName: string | null) {
  const ext = (fileName || "").split(".").pop()?.toLowerCase();
  if (ext === "csv") return <FileSpreadsheet size={20} className="text-muted-foreground" />;
  return <FileText size={20} className="text-muted-foreground" />;
}

function relativeDate(iso: string | null): string {
  if (!iso) return "";
  const date = new Date(iso);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMin = Math.floor(diffMs / 60000);
  const diffH = Math.floor(diffMs / 3600000);
  const diffD = Math.floor(diffMs / 86400000);

  if (diffMin < 1) return "agora";
  if (diffMin < 60) return `há ${diffMin}min`;
  if (diffH < 24) return `há ${diffH}h`;
  if (diffD === 1) return "ontem";
  return date.toLocaleDateString("pt-BR", { day: "numeric", month: "short" });
}

function formatSize(bytes: number | null): string {
  if (!bytes) return "";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

interface UploadingFile {
  name: string;
  status: "uploading" | "done" | "error";
  error?: string;
}

export default function KbPage() {
  const [docs, setDocs] = useState<KBDoc[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState<UploadingFile[]>([]);
  const [dragging, setDragging] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<KBDoc | null>(null);
  const [deleting, setDeleting] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const fetchDocs = useCallback(async () => {
    try {
      const data = await listDocuments();
      setDocs(data);
    } catch {
      // silently fail — user sees empty state
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDocs();
  }, [fetchDocs]);

  async function handleFiles(files: FileList | File[]) {
    const fileArray = Array.from(files);
    if (fileArray.length === 0) return;

    const newUploading: UploadingFile[] = fileArray.map((f) => ({
      name: f.name,
      status: "uploading" as const,
    }));
    setUploading((prev) => [...prev, ...newUploading]);

    await Promise.all(
      fileArray.map(async (file, idx) => {
        try {
          await uploadDocument(file);
          setUploading((prev) =>
            prev.map((u, i) =>
              i === prev.length - fileArray.length + idx
                ? { ...u, status: "done" as const }
                : u,
            ),
          );
        } catch (err) {
          const msg = err instanceof Error ? err.message : "Erro no upload";
          setUploading((prev) =>
            prev.map((u, i) =>
              i === prev.length - fileArray.length + idx
                ? { ...u, status: "error" as const, error: msg }
                : u,
            ),
          );
        }
      }),
    );

    // Refresh list and clear done uploads after a short delay
    await fetchDocs();
    setTimeout(() => {
      setUploading((prev) => prev.filter((u) => u.status === "error"));
    }, 2000);
  }

  async function handleDelete() {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await deleteDocument(deleteTarget.id);
      setDocs((prev) => prev.filter((d) => d.id !== deleteTarget.id));
      setDeleteTarget(null);
    } catch {
      // keep dialog open on error
    } finally {
      setDeleting(false);
    }
  }

  const brandColor =
    studioConfig.brand.kind === "solid"
      ? studioConfig.brand.color
      : studioConfig.brand.to;

  return (
    <div
      style={{ flex: 1, display: "flex", flexDirection: "column" }}
      onDragOver={(e) => {
        e.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragging(false);
        handleFiles(e.dataTransfer.files);
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: "20px 24px 16px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <h1 style={{ fontSize: "20px", fontWeight: 600, color: "#1a1a1a" }}>
          Base de Conhecimento
        </h1>
        <Button
          onClick={() => fileInputRef.current?.click()}
          style={{
            background: brandColor,
            borderRadius: "20px",
            gap: "6px",
          }}
        >
          <Upload size={16} />
          Upload
        </Button>
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept={ACCEPTED_EXTENSIONS}
          style={{ display: "none" }}
          onChange={(e) => {
            if (e.target.files) handleFiles(e.target.files);
            e.target.value = "";
          }}
        />
      </div>

      {/* Upload progress */}
      {uploading.length > 0 && (
        <div style={{ padding: "0 24px 8px", display: "flex", flexDirection: "column", gap: "4px" }}>
          {uploading.map((u, i) => (
            <div
              key={`${u.name}-${i}`}
              style={{
                fontSize: "13px",
                display: "flex",
                alignItems: "center",
                gap: "8px",
                color: u.status === "error" ? "#dc2626" : "#666",
              }}
            >
              {u.status === "uploading" && <Loader2 size={14} className="animate-spin" />}
              {u.status === "done" && <span style={{ color: "#16a34a" }}>&#10003;</span>}
              {u.status === "error" && <span>&#10007;</span>}
              <span>{u.name}</span>
              {u.error && (
                <span style={{ fontSize: "12px", color: "#dc2626" }}>
                  — {u.error}
                </span>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Content area */}
      <div
        style={{
          flex: 1,
          padding: "0 24px 24px",
          overflowY: "auto",
          border: dragging ? "2px dashed" : "2px solid transparent",
          borderColor: dragging ? brandColor : "transparent",
          borderRadius: "8px",
          margin: "0 8px",
          transition: "border-color 200ms",
        }}
      >
        {/* Loading skeleton */}
        {loading && (
          <div style={{ display: "flex", flexDirection: "column", gap: "12px", paddingTop: "8px" }}>
            {[1, 2, 3].map((n) => (
              <Skeleton key={n} className="h-14 w-full" />
            ))}
          </div>
        )}

        {/* Empty state */}
        {!loading && docs.length === 0 && uploading.length === 0 && (
          <div
            style={{
              flex: 1,
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              textAlign: "center",
              padding: "64px 0",
            }}
          >
            <Upload size={48} color="#ccc" strokeWidth={1.5} />
            <h2
              style={{
                fontSize: "17px",
                fontWeight: 600,
                color: "#1a1a1a",
                marginTop: "16px",
                marginBottom: "6px",
              }}
            >
              Nenhum documento ainda
            </h2>
            <p style={{ fontSize: "14px", color: "#999", maxWidth: "320px" }}>
              Arraste arquivos aqui ou clique em Upload pra começar.
              {" "}{studioConfig.agentName} vai usar esses documentos nas conversas.
            </p>
          </div>
        )}

        {/* Document list */}
        {!loading && docs.length > 0 && (
          <div style={{ display: "flex", flexDirection: "column" }}>
            {docs.map((doc) => (
              <div
                key={doc.id}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "12px",
                  padding: "14px 0",
                  borderBottom: "1px solid #f0f0f0",
                }}
              >
                {fileIcon(doc.file_name)}
                <div style={{ flex: 1, minWidth: 0 }}>
                  <p
                    style={{
                      fontSize: "14px",
                      fontWeight: 500,
                      color: "#1a1a1a",
                      whiteSpace: "nowrap",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                    }}
                  >
                    {doc.file_name || doc.title}
                  </p>
                  <p style={{ fontSize: "12px", color: "#999", marginTop: "2px" }}>
                    {formatSize(doc.file_size)}
                    {doc.file_size ? " · " : ""}
                    {relativeDate(doc.created_at)}
                  </p>
                </div>
                <Badge variant="secondary" style={{ fontSize: "11px", flexShrink: 0 }}>
                  {doc.chunk_count} chunk{doc.chunk_count !== 1 ? "s" : ""}
                </Badge>
                <DropdownMenu>
                  <DropdownMenuTrigger
                    style={{
                      background: "none",
                      border: "none",
                      cursor: "pointer",
                      padding: "4px",
                      borderRadius: "6px",
                      display: "flex",
                    }}
                  >
                    <MoreVertical size={16} color="#999" />
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    <DropdownMenuItem onClick={() => downloadDocument(doc.id)}>
                      <Download size={14} style={{ marginRight: "8px" }} />
                      Download original
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      onClick={() => setDeleteTarget(doc)}
                      className="text-red-600 focus:text-red-600"
                    >
                      <Trash2 size={14} style={{ marginRight: "8px" }} />
                      Excluir
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Delete confirmation dialog */}
      <Dialog open={!!deleteTarget} onOpenChange={(open) => !open && setDeleteTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Excluir documento</DialogTitle>
            <DialogDescription>
              Tem certeza que deseja excluir &quot;{deleteTarget?.file_name || deleteTarget?.title}&quot;?
              Essa ação não pode ser desfeita.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteTarget(null)} disabled={deleting}>
              Cancelar
            </Button>
            <Button variant="destructive" onClick={handleDelete} disabled={deleting}>
              {deleting ? <Loader2 size={14} className="animate-spin" /> : "Excluir"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
