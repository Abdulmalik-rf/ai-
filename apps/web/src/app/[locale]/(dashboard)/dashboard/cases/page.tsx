import { Briefcase } from "lucide-react";
import { getTranslations, getLocale } from "next-intl/server";
import { Suspense } from "react";

import { api } from "@/lib/api";
import { getAccessToken } from "@/lib/session";
import { Card } from "@/components/ui/card";
import { CasesList, type CaseRow } from "@/components/dashboard/cases-list";
import { EmptyState } from "@/components/dashboard/empty-state";
import { NewCaseDialog } from "@/components/dashboard/new-case-dialog";

export default async function CasesPage() {
  const t = await getTranslations("dashboard.cases");

  return (
    <div className="container py-8 space-y-6">
      <header className="flex items-center justify-between gap-4">
        <h1 className="text-3xl font-bold tracking-tight">{t("title")}</h1>
        <NewCaseDialog />
      </header>

      <Suspense fallback={<CasesSkeleton />}>
        <CasesView />
      </Suspense>
    </div>
  );
}

async function CasesView() {
  const [token, locale] = await Promise.all([getAccessToken(), getLocale()]);

  let cases: CaseRow[] = [];
  try {
    cases = (await api<CaseRow[]>("/v1/cases?limit=500", { token })) ?? [];
  } catch {
    cases = [];
  }

  if (cases.length === 0) {
    return (
      <EmptyState
        icon={Briefcase}
        title={locale === "ar" ? "لا توجد قضايا بعد" : "No cases yet"}
        body={
          locale === "ar"
            ? "ستظهر هنا القضايا التي تفتحها مع عملائك. أنشئ قضية لبدء العمل."
            : "Cases you open with your clients will appear here. Create one to get started."
        }
      />
    );
  }

  return <CasesList cases={cases} locale={locale} isAr={locale === "ar"} />;
}

function CasesSkeleton() {
  return (
    <div className="space-y-3 animate-pulse">
      <div className="h-10 bg-muted/40 rounded-md" />
      <div className="h-7 bg-muted/30 rounded-md" />
      <Card className="overflow-hidden">
        <ul className="divide-y divide-border/60">
          {Array.from({ length: 4 }).map((_, i) => (
            <li key={i} className="h-20 bg-muted/30" />
          ))}
        </ul>
      </Card>
    </div>
  );
}
