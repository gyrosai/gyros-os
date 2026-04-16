"use client";

import {
  Suspense,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";
import { useSearchParams } from "next/navigation";
import ReactMarkdown from "react-markdown";
import { Loader2, Paperclip } from "lucide-react";
import {
  type ChatMessage,
  sendMessage,
  getThreadMessages,
  uploadDocument,
} from "@/lib/api-client";
import { studioConfig } from "@/lib/runtime-config";

const ACCEPTED_EXTENSIONS = ".txt,.md,.csv,.pdf,.docx,.xlsx";

const SUGGESTIONS_GYROS = [
  "Resumir um documento",
  "Buscar na base de conhecimento",
  "Preparar pra uma reunião",
];

const SUGGESTIONS_CURADORIA = [
  "STATUS — hoje",
  "REGISTRAR — ata da reunião",
  "DECIDIR — reciclar instrutor X",
];

function getSuggestions(): string[] {
  const name = studioConfig.name.toLowerCase();
  if (name.includes("curadoria")) return SUGGESTIONS_CURADORIA;
  return SUGGESTIONS_GYROS;
}

interface DisplayMessage {
  role: "user" | "assistant";
  content: string;
  sources?: string[];
}

export default function ChatPage() {
  return (
    <Suspense
      fallback={
        <div
          style={{
            flex: 1,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <Loader2 size={24} className="animate-spin" color="#999" />
        </div>
      }
    >
      <ChatContent />
    </Suspense>
  );
}

function ChatContent() {
  const searchParams = useSearchParams();
  const initialThread = searchParams.get("thread");

  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [threadId, setThreadId] = useState<string | null>(initialThread);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [loadingThread, setLoadingThread] = useState(false);
  const [uploadFeedback, setUploadFeedback] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const brandColor =
    studioConfig.brand.kind === "solid"
      ? studioConfig.brand.color
      : studioConfig.brand.to;

  const suggestions = getSuggestions();

  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, sending]);

  // Load thread from URL param
  const loadThread = useCallback(async (id: string) => {
    setLoadingThread(true);
    try {
      const msgs = await getThreadMessages(id);
      setMessages(msgs.map((m) => ({ role: m.role, content: m.content })));
      setThreadId(id);
    } catch {
      // thread not found or error
    } finally {
      setLoadingThread(false);
    }
  }, []);

  useEffect(() => {
    if (initialThread) {
      loadThread(initialThread);
    }
  }, [initialThread, loadThread]);

  // Listen for thread selection events from sidebar
  useEffect(() => {
    function handleSelectThread(e: CustomEvent<{ threadId: string | null }>) {
      const id = e.detail.threadId;
      if (id === null) {
        // New session
        setMessages([]);
        setThreadId(null);
        setInput("");
        return;
      }
      loadThread(id);
    }

    window.addEventListener(
      "select-thread",
      handleSelectThread as EventListener,
    );
    return () => {
      window.removeEventListener(
        "select-thread",
        handleSelectThread as EventListener,
      );
    };
  }, [loadThread]);

  // Auto-resize textarea
  function handleTextareaInput() {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 200) + "px";
  }

  async function handleSend(text?: string) {
    const msg = (text || input).trim();
    if (!msg || sending) return;

    setInput("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }

    // Add user message
    setMessages((prev) => [...prev, { role: "user", content: msg }]);
    setSending(true);

    try {
      const res = await sendMessage(msg, threadId || undefined);
      setThreadId(res.thread_id);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: res.reply,
          sources: res.sources.length > 0 ? res.sources : undefined,
        },
      ]);
      // Notify sidebar to refresh threads
      window.dispatchEvent(new CustomEvent("threads-updated"));
    } catch (err) {
      const errorMsg =
        err instanceof Error ? err.message : "Erro ao enviar mensagem";
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: `Erro: ${errorMsg}` },
      ]);
    } finally {
      setSending(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  async function handleFileUpload(files: FileList | null) {
    if (!files || files.length === 0) return;
    const file = files[0];
    setUploadFeedback(`Enviando ${file.name}...`);
    try {
      await uploadDocument(file);
      setUploadFeedback(`Documento "${file.name}" adicionado à base.`);
      setTimeout(() => setUploadFeedback(null), 4000);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Erro no upload";
      setUploadFeedback(`Erro: ${msg}`);
      setTimeout(() => setUploadFeedback(null), 4000);
    }
  }

  const showGreeting = messages.length === 0 && !loadingThread;

  return (
    <div
      style={{
        flex: 1,
        display: "flex",
        flexDirection: "column",
        background: "#FAFAFA",
      }}
    >
      {/* Header */}
      <div style={{ padding: "14px 20px", textAlign: "center" }}>
        <span style={{ fontSize: "13px", fontWeight: 500, color: "#aaa" }}>
          {studioConfig.name}
        </span>
      </div>

      {/* Messages area */}
      <div
        style={{
          flex: 1,
          overflowY: "auto",
          display: "flex",
          flexDirection: "column",
        }}
      >
        {/* Loading thread */}
        {loadingThread && (
          <div
            style={{
              flex: 1,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <Loader2 size={24} className="animate-spin" color="#999" />
          </div>
        )}

        {/* Greeting — new conversation */}
        {showGreeting && (
          <div
            style={{
              flex: 1,
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              padding: "0 32px",
              textAlign: "center",
            }}
          >
            <h1
              style={{
                fontSize: "24px",
                fontWeight: 600,
                color: "#1a1a1a",
                letterSpacing: "-0.03em",
                marginBottom: "8px",
              }}
            >
              O que podemos fazer hoje?
            </h1>
            <p
              style={{
                fontSize: "15px",
                color: "#999",
                marginBottom: "24px",
              }}
            >
              {studioConfig.agentName} pode ajudar com sua base de conhecimento.
            </p>
            <div
              style={{
                display: "flex",
                gap: "8px",
                flexWrap: "wrap",
                justifyContent: "center",
                maxWidth: "480px",
              }}
            >
              {suggestions.map((text) => (
                <button
                  key={text}
                  type="button"
                  className="suggestion-pill"
                  onClick={() => handleSend(text)}
                >
                  {text}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Messages */}
        {!showGreeting && !loadingThread && (
          <div
            style={{
              maxWidth: "720px",
              width: "100%",
              margin: "0 auto",
              padding: "16px 24px",
            }}
          >
            {messages.map((msg, i) => (
              <div
                key={i}
                style={{
                  padding: "16px 0",
                  borderBottom:
                    i < messages.length - 1 ? "1px solid #f5f5f5" : "none",
                }}
              >
                <p
                  style={{
                    fontSize: "12px",
                    fontWeight: 600,
                    color: "#999",
                    marginBottom: "6px",
                  }}
                >
                  {msg.role === "user" ? "Você" : studioConfig.agentName}
                </p>
                {msg.role === "assistant" ? (
                  <div className="prose-chat">
                    <ReactMarkdown>{msg.content}</ReactMarkdown>
                  </div>
                ) : (
                  <p style={{ fontSize: "15px", color: "#1a1a1a", lineHeight: 1.6 }}>
                    {msg.content}
                  </p>
                )}
                {msg.sources && msg.sources.length > 0 && (
                  <p
                    style={{
                      fontSize: "12px",
                      color: "#999",
                      marginTop: "8px",
                    }}
                  >
                    Fontes: {msg.sources.join(", ")}
                  </p>
                )}
              </div>
            ))}

            {/* Thinking indicator */}
            {sending && (
              <div style={{ padding: "16px 0" }}>
                <p
                  style={{
                    fontSize: "12px",
                    fontWeight: 600,
                    color: "#999",
                    marginBottom: "6px",
                  }}
                >
                  {studioConfig.agentName}
                </p>
                <p
                  style={{
                    fontSize: "13px",
                    color: "#999",
                    fontStyle: "italic",
                  }}
                >
                  Pensando...
                </p>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Upload feedback */}
      {uploadFeedback && (
        <div
          style={{
            padding: "6px 24px",
            fontSize: "13px",
            color: uploadFeedback.startsWith("Erro") ? "#dc2626" : "#16a34a",
            textAlign: "center",
          }}
        >
          {uploadFeedback}
        </div>
      )}

      {/* Input area */}
      <div style={{ padding: "8px 20px 4px", width: "100%" }}>
        <div className="chat-input-box">
          <textarea
            ref={textareaRef}
            rows={3}
            placeholder={`Escreva sua mensagem pra ${studioConfig.agentName}...`}
            className="chat-input-textarea"
            value={input}
            onChange={(e) => {
              setInput(e.target.value);
              handleTextareaInput();
            }}
            onKeyDown={handleKeyDown}
            disabled={sending}
          />
          <div className="chat-input-toolbar">
            {/* Clip — file upload */}
            <button
              type="button"
              className="chat-toolbar-btn"
              onClick={() => fileInputRef.current?.click()}
              title="Adicionar documento à base"
            >
              <Paperclip size={18} color="#888" />
            </button>
            <input
              ref={fileInputRef}
              type="file"
              accept={ACCEPTED_EXTENSIONS}
              style={{ display: "none" }}
              onChange={(e) => {
                handleFileUpload(e.target.files);
                e.target.value = "";
              }}
            />

            <div style={{ flex: 1 }} />

            {/* Send button */}
            <button
              type="button"
              className="chat-send-btn"
              style={{ background: brandColor }}
              disabled={sending || !input.trim()}
              onClick={() => handleSend()}
            >
              {sending ? (
                <Loader2 size={14} className="animate-spin" color="#fff" />
              ) : (
                <>
                  Enviar
                  <svg
                    width="14"
                    height="14"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="#fff"
                    strokeWidth="2.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <line x1="5" y1="12" x2="19" y2="12" />
                    <polyline points="12 5 19 12 12 19" />
                  </svg>
                </>
              )}
            </button>
          </div>
        </div>
      </div>
      <p className="chat-hint">IA pode cometer erros. Verifique as respostas.</p>
    </div>
  );
}
