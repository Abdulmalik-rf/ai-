"use client";

/**
 * Calm, static About-page hero.
 *
 * Visual: ambient emerald-and-gold gradient washes + a few decorative dots.
 * No orbital rings, no particle field, no breathing halo, no cursor
 * spotlight — those were noisy and the user found them annoying. The hero
 * now relies on typography and the brand colour palette alone.
 */
import { BrandLogo } from "@/components/brand-logo";

type HeroCanvasProps = {
  locale: string;
  kicker: string;
  title: string;
  subtitle: string;
};

export function HeroCanvas({ locale, kicker, title, subtitle }: HeroCanvasProps) {
  return (
    <section className="relative isolate overflow-hidden">
      {/* Ambient gradient washes — static, no motion */}
      <div
        aria-hidden
        className="absolute inset-0"
        style={{
          background:
            "radial-gradient(ellipse 80% 60% at 50% 0%, hsl(160 65% 22% / 0.10), transparent 70%)," +
            "radial-gradient(ellipse 60% 50% at 100% 100%, hsl(36 60% 50% / 0.06), transparent 65%)," +
            "radial-gradient(ellipse 60% 50% at 0% 100%, hsl(160 60% 35% / 0.04), transparent 65%)",
        }}
      />

      <div className="container relative z-10 py-24 md:py-32">
        <div className="max-w-3xl mx-auto text-center space-y-6">
          <div className="flex justify-center">
            <BrandLogo size={84} locale={locale} />
          </div>

          <div className="flex justify-center">
            <span className="inline-flex items-center gap-2 rounded-full border border-accent/40 bg-accent/5 text-accent text-xs font-semibold uppercase tracking-[0.2em] px-3 py-1">
              <span className="h-1.5 w-1.5 rounded-full bg-accent" />
              {kicker}
            </span>
          </div>

          <h1 className="text-4xl md:text-6xl font-bold tracking-tight leading-tight text-foreground">
            {title}
          </h1>

          <div
            className="mx-auto h-[2px] w-16 rounded-full"
            style={{
              backgroundImage:
                "linear-gradient(90deg, transparent, hsl(36 60% 50%), transparent)",
            }}
          />

          <p className="text-lg md:text-xl text-muted-foreground leading-relaxed max-w-2xl mx-auto">
            {subtitle}
          </p>
        </div>
      </div>

      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 bottom-0 h-16"
        style={{
          background:
            "linear-gradient(to bottom, transparent, hsl(var(--background)))",
        }}
      />
    </section>
  );
}
