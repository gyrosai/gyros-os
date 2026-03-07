import { QueuePageClient } from "@/components/queue-page-client";
import { requireSession } from "@/lib/session";

export default async function QueuePage() {
  await requireSession();

  return <QueuePageClient />;
}
