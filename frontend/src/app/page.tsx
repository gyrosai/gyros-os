import Link from "next/link";
import { studioConfig } from "@/lib/runtime-config";
import { requireSession } from "@/lib/session";

export const dynamic = "force-dynamic";

export default async function HomePage() {
  await requireSession();

  const showChat = studioConfig.features.has("chat");
  const showKb = studioConfig.features.has("kb");

  return (
    <div className="flex flex-col items-center justify-center min-h-[70vh] text-center px-6 max-w-2xl mx-auto">
      <h1 className="text-4xl font-bold mb-4 tracking-tight">
        {studioConfig.name}
      </h1>
      <p className="text-lg text-muted-foreground mb-8">
        Sua plataforma de conhecimento e conversa com {studioConfig.agentName}.
      </p>
      <div className="flex flex-wrap gap-3 justify-center">
        {showChat && (
          <Link
            href="/chat"
            className="brand-bg text-white px-5 py-2.5 rounded-lg font-medium hover:opacity-90 transition"
          >
            Conversar com {studioConfig.agentName}
          </Link>
        )}
        {showKb && (
          <Link
            href="/kb"
            className="border brand-border brand-text px-5 py-2.5 rounded-lg font-medium hover:bg-muted/50 transition"
          >
            Adicionar documentos
          </Link>
        )}
      </div>
    </div>
  );
}
