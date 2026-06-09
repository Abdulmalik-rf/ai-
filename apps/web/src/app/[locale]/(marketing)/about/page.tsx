import { getLocale, getTranslations } from "next-intl/server";

import { FinalCta } from "@/components/marketing/about/final-cta";
import { HeroCanvas } from "@/components/marketing/about/hero-canvas";
import { Manifesto } from "@/components/marketing/about/manifesto";
import {
  PillarsGrid,
  type Pillar,
} from "@/components/marketing/about/pillars-grid";
import { PrinciplesGrid } from "@/components/marketing/about/principles-grid";
import { SaudiCallout } from "@/components/marketing/about/saudi-callout";
import { StatsBar, type StatItem } from "@/components/marketing/about/stats-bar";
import { StorySection } from "@/components/marketing/about/story-section";

export default async function AboutPage() {
  const t = await getTranslations("marketing.about");
  const locale = await getLocale();

  // Stats — numeric values + suffixes are stable across locales so we
  // keep them inline; only the labels come from translations. (next-intl
  // surfaces messages as ICU strings, so reading a numeric JSON leaf
  // through `t()` yields NaN — hard-coding avoids the awkward dance.)
  const stats: StatItem[] = [
    { value: 150, suffix: "+", label: t("stats.items.statutes.label") },
    {
      value: 1.8,
      suffix: locale === "ar" ? "ث" : "s",
      label: t("stats.items.response.label"),
      decimals: 1,
    },
    {
      value: 99,
      suffix: locale === "ar" ? "٪" : "%",
      label: t("stats.items.accuracy.label"),
    },
    {
      value: 70,
      suffix: locale === "ar" ? "٪" : "%",
      label: t("stats.items.timeSaved.label"),
    },
  ];

  const pillars: Pillar[] = (["mission", "team", "commitment"] as const).map(
    (key) => ({
      key,
      title: t(`pillars.${key}.title`),
      body: t(`pillars.${key}.body`),
    }),
  );

  const values = (["trust", "privacy", "saudi", "speed"] as const).map(
    (key) => ({
      key,
      title: t(`values.items.${key}.title`),
      body: t(`values.items.${key}.body`),
    }),
  );

  const principles = (["grounded", "lawyerLed", "compliant"] as const).map(
    (key) => ({
      key,
      title: t(`principles.items.${key}.title`),
      body: t(`principles.items.${key}.body`),
    }),
  );

  const saudiCities = (() => {
    try {
      // next-intl exposes array indexes via `.0`, `.1`…
      return [0, 1, 2, 3, 4, 5].map((i) => t(`saudiCallout.cities.${i}`));
    } catch {
      return [];
    }
  })();

  const saudiChips = (() => {
    try {
      return [0, 1, 2, 3, 4, 5].map((i) => t(`saudiCallout.chips.${i}`));
    } catch {
      return [];
    }
  })();

  return (
    <>
      <HeroCanvas
        locale={locale}
        kicker={t("kicker")}
        title={t("title")}
        subtitle={t("subtitle")}
      />

      <div className="-mt-10 md:-mt-12 relative z-10">
        <StatsBar kicker={t("stats.kicker")} items={stats} />
      </div>

      <StorySection
        heading={t("story.title")}
        p1={t("story.p1")}
        p2={t("story.p2")}
        p3={t("story.p3")}
      />

      <PillarsGrid heading={t("pillars.title")} items={pillars} />

      <SaudiCallout
        kicker={t("saudiCallout.kicker")}
        title={t("saudiCallout.title")}
        body={t("saudiCallout.body")}
        chips={saudiChips}
        cityLabels={saudiCities}
        locale={locale}
      />

      <Manifesto
        kicker={t("manifesto.kicker")}
        quote={t("manifesto.quote")}
        attribution={t("manifesto.attribution")}
      />

      <PrinciplesGrid
        heading={t("principles.title")}
        items={principles}
        variant="principles"
      />

      <PrinciplesGrid
        heading={t("values.title")}
        items={values}
        variant="values"
      />

      <FinalCta
        locale={locale}
        title={t("cta.title")}
        subtitle={t("cta.subtitle")}
        primary={t("cta.primary")}
        secondary={t("cta.secondary")}
      />
    </>
  );
}
