import { ArrowRight } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { Link } from "@/i18n/routing";

import { BrandLogo } from "@/components/brand-logo";
import { ConversationScroll } from "@/components/marketing/conversation-scroll";
import { HowItWorks } from "@/components/marketing/how-it-works";
import { MarketingCTA } from "@/components/marketing/marketing-cta";
import {
  FeatureGrid,
  type FeatureItem,
} from "@/components/marketing/feature-grid";
import { HeroVideo } from "@/components/marketing/hero-video";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ContainerScroll } from "@/components/ui/container-scroll";

export default function LandingPage() {
  const t = useTranslations("marketing");
  const tc = useTranslations("common");
  const locale = useLocale();
  // Two stacked feature rows. Each row has a live-product UI mockup on
  // one side (alternating per row) and a comprehensive text block —
  // kicker pill, big title, paragraph, three-bullet checklist, and a CTA.
  const featureKeys = ["workbench", "operations"] as const;
  const featureItems: FeatureItem[] = featureKeys.map((key) => ({
    key,
    kicker: t(`features.items.${key}.kicker`),
    title: t(`features.items.${key}.title`),
    description: t(`features.items.${key}.description`),
    bullets: [
      t(`features.items.${key}.bullet1`),
      t(`features.items.${key}.bullet2`),
      t(`features.items.${key}.bullet3`),
    ],
    cta: t(`features.items.${key}.cta`),
  }));

  return (
    <>
      {/* ---------- Hero (ContainerScroll: title up top, animated screen below) ---------- */}
      <section>
        <ContainerScroll
          titleComponent={
            // `md:-translate-y-20` lifts the title block 5rem on desktop
            // without affecting the Card (screen) below it — transforms
            // don't change layout flow, so the screen's position is
            // unchanged. Mobile keeps its original placement.
            <div className="space-y-6 px-4 pb-4 md:-translate-y-20">
              <div className="flex justify-center">
                <BrandLogo size={72} locale={locale} />
              </div>

              <div className="space-y-2">
                <Badge
                  variant="outline"
                  className="border-accent/40 text-accent bg-accent/5"
                >
                  {t("hero.badge")}
                </Badge>
                <h1 className="text-4xl md:text-6xl font-bold tracking-tight text-foreground">
                  {locale === "ar" ? (
                    <>
                      <span className="text-primary">مستشاري</span>{" "}
                      <span className="text-accent">AI</span>
                    </>
                  ) : (
                    <>
                      <span className="text-primary">Mostashari</span>{" "}
                      <span className="text-accent">AI</span>
                    </>
                  )}
                </h1>
                <div className="mx-auto gold-rule" />
              </div>

              <p className="text-xl md:text-2xl font-medium text-foreground">
                {tc("tagline")}
              </p>

              <p className="text-base md:text-lg text-muted-foreground leading-relaxed max-w-2xl mx-auto">
                {t("hero.subtitle")}
              </p>

              <div className="flex flex-col sm:flex-row gap-3 justify-center pt-2">
                <Button asChild size="lg" className="shadow-md">
                  <Link href="/sign-up">
                    {t("hero.ctaPrimary")}
                    <ArrowRight className="rtl:rotate-180" />
                  </Link>
                </Button>
                <Button asChild size="lg" variant="outline">
                  <Link href="/#features">{t("hero.ctaSecondary")}</Link>
                </Button>
              </div>
            </div>
          }
        >
          <HeroVideo />
        </ContainerScroll>
      </section>

      {/* ---------- Features ---------- */}
      <section id="features" className="container py-20">
        <div className="max-w-2xl mx-auto text-center mb-14 space-y-3">
          <h2 className="text-3xl md:text-4xl font-bold tracking-tight">
            {t("features.title")}
          </h2>
          <div className="mx-auto gold-rule" />
          <p className="text-muted-foreground">{t("features.subtitle")}</p>
        </div>
        <FeatureGrid items={featureItems} locale={locale} />
      </section>

      {/* ---------- Conversation showcase (scroll-driven) ---------- */}
      <ConversationScroll />

      {/* ---------- How it works ---------- */}
      <HowItWorks
        locale={locale}
        strings={{
          kicker: t("howItWorks.kicker"),
          title: t("howItWorks.title"),
          subtitle: t("howItWorks.subtitle"),
          steps: (["1", "2", "3"] as const).map((id) => ({
            id,
            title: t(`howItWorks.steps.${id}.title`),
            body: t(`howItWorks.steps.${id}.body`),
            meta: t(`howItWorks.steps.${id}.meta`),
          })),
        }}
      />

      {/* ---------- CTA ---------- */}
      <MarketingCTA
        strings={{
          kicker: t("cta.kicker"),
          title: t("cta.title"),
          subtitle: t("cta.subtitle"),
          primary: t("cta.primary"),
          secondary: t("cta.secondary"),
          trust: {
            trial: t("cta.trust.trial"),
            noCard: t("cta.trust.noCard"),
            ksa: t("cta.trust.ksa"),
            cancel: t("cta.trust.cancel"),
          },
        }}
      />
    </>
  );
}
