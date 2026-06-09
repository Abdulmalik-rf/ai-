"use client";

import { useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

interface Plan {
  id: string;
  tier: "basic" | "pro" | "enterprise";
  name_en: string;
  name_ar: string;
  price_monthly_sar: number;
  monthly_messages_limit: number;
  monthly_documents_limit: number;
  monthly_contracts_limit: number;
  seats_limit: number;
}

export function BillingActions({
  plans,
  hasSubscription,
}: {
  plans: Plan[];
  hasSubscription: boolean;
}) {
  const t = useTranslations("dashboard.billing");
  const locale = useLocale();
  const [busy, setBusy] = useState<string | null>(null);

  async function checkout(plan: Plan, provider: "stripe" | "moyasar") {
    setBusy(plan.id);
    try {
      const res = await fetch("/api/v1/subscriptions/checkout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          plan_tier: plan.tier,
          provider,
          success_url: `${window.location.origin}/dashboard/billing?ok=1`,
          cancel_url: `${window.location.origin}/dashboard/billing?cancel=1`,
        }),
      });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      window.location.href = data.checkout_url;
    } catch (err) {
      alert((err as Error).message);
    } finally {
      setBusy(null);
    }
  }

  async function cancel() {
    if (!confirm("Cancel subscription?")) return;
    setBusy("cancel");
    try {
      const res = await fetch("/api/v1/subscriptions/cancel", {
        method: "POST",
      });
      if (!res.ok) throw new Error(await res.text());
      window.location.reload();
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="space-y-4">
      <div className="grid md:grid-cols-3 gap-3">
        {plans.map((plan) => (
          <Card key={plan.id} className="p-4 space-y-2">
            <div className="font-semibold">
              {locale === "ar" ? plan.name_ar : plan.name_en}
            </div>
            <div className="text-2xl font-bold">
              {plan.price_monthly_sar} SAR
            </div>
            <div className="text-xs text-muted-foreground">
              {plan.monthly_messages_limit} messages ·{" "}
              {plan.monthly_documents_limit} docs · {plan.seats_limit} seats
            </div>
            <div className="flex gap-2 pt-2">
              <Button
                size="sm"
                className="flex-1"
                disabled={busy !== null}
                onClick={() => checkout(plan, "stripe")}
              >
                {busy === plan.id && <Loader2 className="h-4 w-4 animate-spin" />}
                Stripe
              </Button>
              <Button
                size="sm"
                variant="outline"
                className="flex-1"
                disabled={busy !== null}
                onClick={() => checkout(plan, "moyasar")}
              >
                Moyasar
              </Button>
            </div>
          </Card>
        ))}
      </div>

      {hasSubscription && (
        <Button variant="destructive" onClick={cancel} disabled={busy !== null}>
          {t("cancelPlan")}
        </Button>
      )}
    </div>
  );
}
