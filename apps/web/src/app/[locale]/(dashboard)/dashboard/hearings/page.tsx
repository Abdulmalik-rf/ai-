import { getTranslations } from "next-intl/server";
import { Suspense } from "react";

import { HearingsWorkspace } from "@/components/dashboard/hearings-workspace";
import { api } from "@/lib/api";
import { getAccessToken } from "@/lib/session";

interface Hearing {
  id: string;
  case_id: string;
  scheduled_at: string;
  kind: string;
  status: string;
  duration_minutes: number | null;
  court_name: string | null;
  court_room: string | null;
  judge_name: string | null;
  opposing_counsel: string | null;
  outcome: string | null;
  notes: string | null;
}

interface CaseRef {
  id: string;
  reference: string;
  title: string;
}

export default async function HearingsPage() {
  const t = await getTranslations("dashboard.crm.hearings");

  return (
    <div className="container py-8 space-y-6">
      <header>
        <h1 className="text-3xl font-bold tracking-tight">{t("title")}</h1>
      </header>
      <Suspense fallback={<HearingsSkeleton />}>
        <HearingsBoard />
      </Suspense>
    </div>
  );
}

async function HearingsBoard() {
  const token = await getAccessToken();

  let hearings: Hearing[] = [];
  let cases: CaseRef[] = [];
  try {
    [hearings, cases] = await Promise.all([
      api<Hearing[]>("/v1/hearings?limit=200", { token }),
      api<CaseRef[]>("/v1/cases?limit=200", { token }),
    ]);
  } catch {
    // empty state
  }

  return <HearingsWorkspace initialHearings={hearings} cases={cases} />;
}

function HearingsSkeleton() {
  return (
    <div className="space-y-3 animate-pulse">
      <div className="rounded-lg border bg-card h-12" />
      {Array.from({ length: 5 }).map((_, i) => (
        <div key={i} className="rounded-lg border bg-card h-20" />
      ))}
    </div>
  );
}
