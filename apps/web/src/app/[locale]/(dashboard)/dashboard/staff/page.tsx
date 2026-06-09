import { getTranslations } from "next-intl/server";
import { Suspense } from "react";

import { StaffWorkspace } from "@/components/dashboard/staff-workspace";
import { api } from "@/lib/api";
import { getAccessToken } from "@/lib/session";

interface StaffMember {
  id: string;
  full_name: string;
  email: string;
  role: string;
  locale: string;
  phone_number: string | null;
  is_active: boolean;
  created_at: string;
}

export default async function StaffPage() {
  const t = await getTranslations("dashboard.crm.staff");

  return (
    <div className="container py-8 space-y-6">
      <header className="space-y-1">
        <h1 className="text-3xl font-bold tracking-tight">{t("title")}</h1>
        <p className="text-sm text-muted-foreground max-w-2xl">
          {t("subtitle")}
        </p>
      </header>
      <Suspense fallback={<StaffSkeleton />}>
        <StaffList />
      </Suspense>
    </div>
  );
}

async function StaffList() {
  const token = await getAccessToken();

  let staff: StaffMember[] = [];
  try {
    staff = await api<StaffMember[]>("/v1/team/users", { token });
  } catch {
    // first run / unauthenticated — fall back to an empty list
  }

  return <StaffWorkspace initialStaff={staff} />;
}

function StaffSkeleton() {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 animate-pulse">
      {Array.from({ length: 3 }).map((_, i) => (
        <div key={i} className="rounded-lg border bg-card h-48" />
      ))}
    </div>
  );
}
