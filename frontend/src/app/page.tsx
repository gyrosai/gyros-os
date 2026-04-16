import { studioConfig } from "@/lib/runtime-config";
import { requireSession } from "@/lib/session";
import { HomeChatInput } from "@/components/home-chat-input";

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

      <HomeChatInput
        agentName={studioConfig.agentName}
        brandColor={brandColor}
        suggestions={suggestions}
      />
    </div>
  );
}
