import { getLocale } from "next-intl/server";

import { ConsultationsWorkspace } from "@/components/dashboard/consultations-workspace";
import { api } from "@/lib/api";
import { getAccessToken } from "@/lib/session";

export const dynamic = "force-dynamic";

interface AdvisorMeta {
  id: string;
  name_en: string;
  name_ar: string;
}

export default async function ConsultationsPage() {
  const locale = await getLocale();
  const isAr = locale === "ar";
  const token = await getAccessToken();

  let consultations: unknown[] = [];
  let advisorMeta: Record<string, AdvisorMeta> = {};
  try {
    const [list, catalogue] = await Promise.all([
      api<unknown[]>("/v1/consultations?limit=50", { token }),
      api<{ advisors: AdvisorMeta[] }>("/v1/consultations/advisors", { token }),
    ]);
    consultations = list;
    advisorMeta = Object.fromEntries((catalogue.advisors ?? []).map((a) => [a.id, a]));
  } catch {
    // unauthenticated or first run — render empty state
  }

  return (
    <div className="container max-w-6xl py-6 sm:py-8">
      <ConsultationsWorkspace
        initialConsultations={consultations as never}
        advisorMeta={advisorMeta}
        isAr={isAr}
      />
    </div>
  );
}
