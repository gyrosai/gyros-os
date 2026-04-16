"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";
import { sendMessage } from "@/lib/api-client";

interface HomeChatInputProps {
  agentName: string;
  brandColor: string;
  suggestions: string[];
}

export function HomeChatInput({
  agentName,
  brandColor,
  suggestions,
}: HomeChatInputProps) {
  const router = useRouter();
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  async function handleSend(text?: string) {
    const msg = (text || input).trim();
    if (!msg || sending) return;

    setSending(true);
    try {
      const res = await sendMessage(msg);
      router.push(`/chat?thread=${res.thread_id}`);
    } catch {
      setSending(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  return (
    <>
      {/* Greeting area — centered */}
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
          {agentName} pode ajudar com sua base de conhecimento.
        </p>

        {/* Suggestion pills */}
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
              disabled={sending}
              onClick={() => handleSend(text)}
            >
              {text}
            </button>
          ))}
        </div>
      </div>

      {/* Input area — anchored at bottom */}
      <div style={{ padding: "8px 20px 4px", width: "100%" }}>
        <div className="chat-input-box">
          <textarea
            ref={textareaRef}
            rows={3}
            placeholder={`Escreva sua mensagem pra ${agentName}...`}
            className="chat-input-textarea"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={sending}
          />
          {/* Toolbar */}
          <div className="chat-input-toolbar">
            <button type="button" className="chat-toolbar-btn">
              <svg
                width="18"
                height="18"
                viewBox="0 0 24 24"
                fill="none"
                stroke="#888"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48" />
              </svg>
            </button>
            <div style={{ flex: 1 }} />
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
    </>
  );
}
