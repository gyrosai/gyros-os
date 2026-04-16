import { studioConfig } from "@/lib/runtime-config";
import { requireSession } from "@/lib/session";

export const dynamic = "force-dynamic";

export default async function KbPage() {
  await requireSession();

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
          Base de Conhecimento
        </h1>
        <p
          style={{
            fontSize: "15px",
            color: "#999",
          }}
        >
          Adicione documentos pra {studioConfig.agentName} usar nas conversas.
        </p>
      </div>
    </div>
  );
}
