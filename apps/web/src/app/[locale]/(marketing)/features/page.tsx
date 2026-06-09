import { getLocale, getTranslations } from "next-intl/server";

import { Bilingual } from "@/components/marketing/features/bilingual";
import {
  Comparison,
  type ComparisonRow,
} from "@/components/marketing/features/comparison";
import {
  Compliance,
  type ComplianceBadge,
} from "@/components/marketing/features/compliance";
import {
  Constellation,
  type ConstellationItem,
} from "@/components/marketing/features/constellation";
import { DeepDive } from "@/components/marketing/features/deep-dive";
import { FeaturesFinalCta } from "@/components/marketing/features/final-cta";
import {
  FlowTimeline,
  type FlowStep,
} from "@/components/marketing/features/flow-timeline";
import { FeaturesHero } from "@/components/marketing/features/hero";

/**
 * Features page — a comprehensive showcase of every Mostashari capability.
 *
 * Sections (top → bottom):
 *   1.  Hero with synapse-field background animation
 *   2.  Six-capability constellation grid
 *   3.  Workbench deep-dive (live mockup + bullets + CTA)
 *   4.  Operations deep-dive (live mockup + bullets + CTA — mirror layout)
 *   5.  Flow timeline (animated 4-step process loop)
 *   6.  Old-way-vs-Mostashari comparison table
 *   7.  Bilingual & Saudi-grounded callout (dark panel with statute chips)
 *   8.  Compliance & trust grid (4 badges)
 *   9.  Final CTA
 */
export default async function FeaturesPage() {
  const t = await getTranslations("marketing.featuresPage");
  const locale = await getLocale();

  // Constellation cards
  const items: ConstellationItem[] = (
    ["rag", "drafting", "review", "case", "crm", "whatsapp"] as const
  ).map((key) => ({
    key,
    title: t(`constellation.items.${key}.title`),
    body: t(`constellation.items.${key}.body`),
  }));

  // Workbench deep-dive bullets
  const workbenchBullets = [0, 1, 2, 3].map((i) => t(`workbench.bullets.${i}`));
  // Operations deep-dive bullets
  const operationsBullets = [0, 1, 2, 3].map((i) =>
    t(`operations.bullets.${i}`),
  );

  // Flow timeline steps
  const flowSteps: FlowStep[] = [0, 1, 2, 3].map((i) => ({
    title: t(`flow.steps.${i}.title`),
    body: t(`flow.steps.${i}.body`),
  }));

  // Comparison rows
  const rows: ComparisonRow[] = [0, 1, 2, 3, 4, 5].map((i) => ({
    feature: t(`compare.rows.${i}.feature`),
    old: t(`compare.rows.${i}.old`),
    next: t(`compare.rows.${i}.new`),
  }));

  // Bilingual chips
  const chips = [0, 1, 2, 3, 4, 5, 6, 7].map((i) => t(`bilingual.chips.${i}`));

  // Compliance badges
  const badges: ComplianceBadge[] = [0, 1, 2, 3].map((i) => ({
    title: t(`compliance.badges.${i}.title`),
    body: t(`compliance.badges.${i}.body`),
  }));

  return (
    <>
      <FeaturesHero
        locale={locale}
        kicker={t("hero.kicker")}
        title={t("hero.title")}
        subtitle={t("hero.subtitle")}
      />

      <Constellation
        kicker={t("constellation.kicker")}
        title={t("constellation.title")}
        subtitle={t("constellation.subtitle")}
        items={items}
      />

      <DeepDive
        variant="workbench"
        index={0}
        mockupSide="start"
        locale={locale}
        kicker={t("workbench.kicker")}
        title={t("workbench.title")}
        body={t("workbench.body")}
        bullets={workbenchBullets}
        cta={t("workbench.cta")}
      />

      <DeepDive
        variant="operations"
        index={1}
        mockupSide="end"
        locale={locale}
        kicker={t("operations.kicker")}
        title={t("operations.title")}
        body={t("operations.body")}
        bullets={operationsBullets}
        cta={t("operations.cta")}
      />

      <FlowTimeline
        kicker={t("flow.kicker")}
        title={t("flow.title")}
        subtitle={t("flow.subtitle")}
        steps={flowSteps}
      />

      <Comparison
        kicker={t("compare.kicker")}
        title={t("compare.title")}
        rows={rows}
        header={{
          feature: t("compare.rowsHeader.feature"),
          old: t("compare.rowsHeader.old"),
          new: t("compare.rowsHeader.new"),
        }}
      />

      <Bilingual
        kicker={t("bilingual.kicker")}
        title={t("bilingual.title")}
        body={t("bilingual.body")}
        chips={chips}
      />

      <Compliance
        kicker={t("compliance.kicker")}
        title={t("compliance.title")}
        body={t("compliance.body")}
        badges={badges}
      />

      <FeaturesFinalCta
        locale={locale}
        kicker={t("cta.kicker")}
        title={t("cta.title")}
        subtitle={t("cta.subtitle")}
        primary={t("cta.primary")}
        secondary={t("cta.secondary")}
      />
    </>
  );
}
