import { Users } from "lucide-react";
import { getTranslations, getLocale } from "next-intl/server";
import { Suspense } from "react";

import { api } from "@/lib/api";
import { getAccessToken } from "@/lib/session";
import { Card } from "@/components/ui/card";
import { ClientsList, type ClientRow } from "@/components/dashboard/clients-list";
import { EmptyState } from "@/components/dashboard/empty-state";
import { NewClientDialog } from "@/components/dashboard/new-client-dialog";

export default async function ClientsPage() {
  const t = await getTranslations("dashboard.clients");

  return (
    <div className="container py-8 space-y-6">
      <header className="flex items-center justify-between gap-4">
        <h1 className="text-3xl font-bold tracking-tight">{t("title")}</h1>
        <NewClientDialog />
      </header>

      <Suspense fallback={<ClientsSkeleton />}>
        <ClientsView />
      </Suspense>
    </div>
  );
}

async function ClientsView() {
  const [token, t, locale] = await Promise.all([
    getAccessToken(),
    getTranslations("dashboard.clients"),
    getLocale(),
  ]);

  let clients: ClientRow[] = [];
  try {
    clients = (await api<ClientRow[]>("/v1/clients?limit=500", { token })) ?? [];
  } catch {
    clients = [];
  }

  if (clients.length === 0) {
    return (
      <EmptyState
        icon={Users}
        title={locale === "ar" ? "لا يوجد عملاء بعد" : "No clients yet"}
        body={
          locale === "ar"
            ? "أضف عميلك الأول لربط القضايا والمستندات والمواعيد به."
            : "Add your first client to link cases, documents, and hearings to them."
        }
      />
    );
  }

  return (
    <ClientsList
      clients={clients}
      isAr={locale === "ar"}
      kindCompany={t("kindCompany")}
      kindPerson={t("kindPerson")}
    />
  );
}

function ClientsSkeleton() {
  return (
    <div className="space-y-3 animate-pulse">
      <div className="h-10 bg-muted/40 rounded-md" />
      <Card className="overflow-hidden">
        <ul className="divide-y divide-border/60">
          {Array.from({ length: 6 }).map((_, i) => (
            <li key={i} className="h-16 bg-muted/30" />
          ))}
        </ul>
      </Card>
    </div>
  );
}
