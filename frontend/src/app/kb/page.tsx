import { requireSession } from "@/lib/session";

export const dynamic = "force-dynamic";

export default async function KbPage() {
  await requireSession();

  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] text-center px-6">
      <h1 className="text-2xl font-semibold mb-2">Base de Conhecimento</h1>
      <p className="text-muted-foreground max-w-md">
        Em breve. Esta tela vai permitir adicionar documentos que serão usados
        pelo agente nas conversas.
      </p>
    </div>
  );
}
