import { Suspense } from "react";

import { api } from "@/lib/api";
import { getAccessToken } from "@/lib/session";
import { DraftingStudio } from "@/components/dashboard/drafting-studio";

interface Template {
  id: string;
  title_en: string;
  title_ar: string;
  kind: string;
  is_global: boolean;
  variables: { name: string; label_en: string; label_ar: string; type: string }[];
}

export default function DraftingPage() {
  return (
    <Suspense fallback={<DraftingSkeleton />}>
      <DraftingView />
    </Suspense>
  );
}

async function DraftingView() {
  const token = await getAccessToken();
  let templates: Template[] = [];
  try {
    templates = (await api<Template[]>("/v1/templates", { token })) ?? [];
  } catch {
    templates = [];
  }
  return <DraftingStudio templates={templates} />;
}

function DraftingSkeleton() {
  return (
    <div className="container py-8 space-y-6 animate-pulse">
      <div className="rounded-lg border bg-card h-12 w-1/3" />
      <div className="rounded-lg border bg-card h-96" />
    </div>
  );
}
