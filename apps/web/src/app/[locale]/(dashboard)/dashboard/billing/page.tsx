import { getTranslations, getLocale } from "next-intl/server";
import { Suspense } from "react";

import { api } from "@/lib/api";
import { getAccessToken } from "@/lib/session";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { BillingActions } from "@/components/dashboard/billing-actions";

interface Sub {
  id: string;
  plan_id: string;
  status: string;
  provider: string;
  current_period_end: string | null;
}

interface Plan {
  id: string;
  tier: "basic" | "pro" | "enterprise";
  name_en: string;
  name_ar: string;
  price_monthly_sar: number;
  price_monthly_usd: number;
  monthly_messages_limit: number;
  monthly_documents_limit: number;
  monthly_contracts_limit: number;
  seats_limit: number;
}

export default async function BillingPage() {
  const t = await getTranslations("dashboard.billing");

  return (
    <div className="container py-8 space-y-6">
      <header>
        <h1 className="text-3xl font-bold tracking-tight">{t("title")}</h1>
      </header>
      <Suspense fallback={<BillingSkeleton />}>
        <BillingPanels />
      </Suspense>
    </div>
  );
}

async function BillingPanels() {
  const [token, t, locale] = await Promise.all([
    getAccessToken(),
    getTranslations("dashboard.billing"),
    getLocale(),
  ]);

  const [subRes, plansRes] = await Promise.allSettled([
    api<Sub | null>("/v1/subscriptions/me", { token }),
    api<Plan[]>("/v1/plans"),
  ]);
  const sub = subRes.status === "fulfilled" ? subRes.value : null;
  const plans = plansRes.status === "fulfilled" ? plansRes.value ?? [] : [];
  const current = plans.find((p) => p.id === sub?.plan_id);

  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle>{t("currentPlan")}</CardTitle>
        </CardHeader>
        <CardContent>
          {sub && current ? (
            <div className="space-y-2">
              <div className="text-2xl font-bold">
                {locale === "ar" ? current.name_ar : current.name_en}
              </div>
              <Badge variant="success">{sub.status}</Badge>
              <div className="text-sm text-muted-foreground">
                {current.price_monthly_sar} SAR / month · {current.seats_limit}{" "}
                seats
              </div>
            </div>
          ) : (
            <div className="text-muted-foreground">No active subscription.</div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t("upgradePlan")}</CardTitle>
        </CardHeader>
        <CardContent>
          <BillingActions plans={plans} hasSubscription={!!sub} />
        </CardContent>
      </Card>
    </>
  );
}

function BillingSkeleton() {
  return (
    <div className="space-y-4 animate-pulse">
      <div className="rounded-lg border bg-card h-32" />
      <div className="rounded-lg border bg-card h-48" />
    </div>
  );
}
