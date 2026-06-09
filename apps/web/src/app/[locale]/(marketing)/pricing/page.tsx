import { getTranslations } from "next-intl/server";

import {
  PricingCard,
  type PricingStrings,
} from "@/components/marketing/pricing-card";

/**
 * Single-tier pricing page.
 *
 * The product ships as one comprehensive plan with two billing rhythms
 * (monthly @ 1,849 SAR or annual @ 14,500 SAR). The interactive toggle and
 * animated price display live in the `<PricingCard />` client component;
 * this page is a server component that materialises the translated copy
 * and hands it down as plain strings.
 */
export default async function PricingPage() {
  const t = await getTranslations("marketing.pricing");

  const strings: PricingStrings = {
    toggleMonthly: t("toggleMonthly"),
    toggleYearly: t("toggleYearly"),
    saveBadge: t("saveBadge"),
    planName: t("planName"),
    planTagline: t("planTagline"),
    perMonth: t("perMonth"),
    perYear: t("perYear"),
    currency: t("currency"),
    billedMonthlyNote: t("billedMonthlyNote"),
    billedYearlyNote: t("billedYearlyNote"),
    yearlyEquivalent: t("yearlyEquivalent"),
    ctaStart: t("ctaStart"),
    trustNote: t("trustNote"),
    features: {
      research: t("features.research"),
      drafting: t("features.drafting"),
      review: t("features.review"),
      case: t("features.case"),
      crm: t("features.crm"),
      whatsapp: t("features.whatsapp"),
      seats: t("features.seats"),
      support: t("features.support"),
    },
  };

  return (
    <section className="container py-20">
      <div className="max-w-2xl mx-auto text-center mb-12">
        <h1 className="text-4xl md:text-5xl font-bold tracking-tight">
          {t("title")}
        </h1>
        <div className="mx-auto gold-rule mt-4" />
        <p className="mt-4 text-muted-foreground">{t("subtitle")}</p>
      </div>

      <PricingCard strings={strings} />
    </section>
  );
}
