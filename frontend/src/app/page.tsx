import { studioConfig } from "@/lib/runtime-config";
import { requireSession } from "@/lib/session";

export const dynamic = "force-dynamic";

const SUGGESTIONS_GYROS = [
  "Resumir um documento",
  "Buscar na base de conhecimento",
  "Preparar pra uma reunião",
];

const SUGGESTIONS_CURADORIA = [
  "Resumir um documento",
  "Buscar na base de conhecimento",
  "Tirar dúvidas sobre a curadoria",
];

function getSuggestions(): string[] {
  const name = studioConfig.name.toLowerCase();
  if (name.includes("curadoria")) return SUGGESTIONS_CURADORIA;
  return SUGGESTIONS_GYROS;
}

export default async function HomePage() {
  await requireSession();

  const suggestions = getSuggestions();
  const brandColor =
    studioConfig.brand.kind === "solid"
      ? studioConfig.brand.color
      : studioConfig.brand.to;

  return (
    <div
      style={{
        flex: 1,
        display: "flex",
        flexDirection: "column",
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: "12px 20px",
          textAlign: "center",
        }}
      >
        <span
          style={{
            fontSize: "13px",
            fontWeight: 500,
            color: "#aaa",
          }}
        >
          {studioConfig.name}
        </span>
      </div>

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
          {studioConfig.agentName} pode ajudar com sua base de conhecimento.
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
            <button key={text} type="button" className="suggestion-pill">
              {text}
            </button>
          ))}
        </div>
      </div>

      {/* Input area — anchored at bottom */}
      <div style={{ padding: "0 20px 16px", width: "100%" }}>
        <div className="chat-input-box">
          <textarea
            disabled
            rows={3}
            placeholder={`Escreva sua mensagem pra ${studioConfig.agentName}...`}
            className="chat-input-textarea"
          />
          {/* Toolbar */}
          <div className="chat-input-toolbar">
            {/* Clip icon */}
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

            {/* Model/font icon */}
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
                <polyline points="4 7 4 4 20 4 20 7" />
                <line x1="9" y1="20" x2="15" y2="20" />
                <line x1="12" y1="4" x2="12" y2="20" />
              </svg>
            </button>

            {/* Spacer */}
            <div style={{ flex: 1 }} />

            {/* Send button */}
            <button
              type="button"
              disabled
              className="chat-send-btn"
              style={{ background: brandColor }}
            >
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
            </button>
          </div>
        </div>

        {/* Hint */}
        <p className="chat-hint">
          IA pode cometer erros. Verifique as respostas.
        </p>
      </div>
    </div>
  );
}
