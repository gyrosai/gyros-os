import { studioConfig } from "@/lib/runtime-config";
import { requireSession } from "@/lib/session";

export const dynamic = "force-dynamic";

export default async function ChatPage() {
  await requireSession();

  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] text-center px-6">
      <h1 className="text-2xl font-semibold mb-2">
        Chat com {studioConfig.agentName}
      </h1>
      <p className="text-muted-foreground max-w-md">
        Em breve. Esta tela vai permitir conversar com {studioConfig.agentName}{" "}
        usando sua base de conhecimento.
      </p>
    </div>
  );
}
