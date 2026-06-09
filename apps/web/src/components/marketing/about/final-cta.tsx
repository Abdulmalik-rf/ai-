"use client";

/**
 * Final CTA — premium invitation card.
 *
 * Layout (centred, generous breathing room):
 *   • kicker pill at the top
 *   • brand logo with a soft gold halo
 *   • bold question-style headline
 *   • gold rule
 *   • subtitle paragraph
 *   • primary + secondary CTA buttons
 *   • separator + compliance trust strip
 *
 * Premium chrome (matches the rest of the redesigned About page):
 *   • cursor-tracking gold spotlight on hover
 *   • animated top-border sheen on hover
 *   • gold corner ornaments at both top corners
 *   • ambient emerald + gold corner washes
 *   • soft "constellation" of accent dots in the background
 *   • subtle hover lift on the buttons
 */
import { motion, useReducedMotion } from "framer-motion";
import { ArrowRight } from "lucide-react";
import { Link } from "@/i18n/routing";
import * as React from "react";

import { BrandLogo } from "@/components/brand-logo";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const TRUST_BADGES = ["ZATCA-ready", "PDPL-compliant", "VAT-ready", "Saudi-resident"];

export function FinalCta({
  locale,
  title,
  subtitle,
  primary,
  secondary,
}: {
  locale: string;
  title: string;
  subtitle: string;
  primary: string;
  secondary: string;
}) {
  const reduceMotion = useReducedMotion();
  const ref = React.useRef<HTMLDivElement>(null);
  const [hovered, setHovered] = React.useState(false);
  const [pos, setPos] = React.useState({ x: 50, y: 50 });

  const onMouseMove = React.useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      const el = ref.current;
      if (!el || reduceMotion) return;
      const r = el.getBoundingClientRect();
      setPos({
        x: ((e.clientX - r.left) / r.width) * 100,
        y: ((e.clientY - r.top) / r.height) * 100,
      });
    },
    [reduceMotion],
  );

  return (
    <section className="container py-24">
      <motion.div
        ref={ref}
        onMouseMove={onMouseMove}
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
        initial={reduceMotion ? false : { opacity: 0, y: 28 }}
        whileInView={reduceMotion ? undefined : { opacity: 1, y: 0 }}
        viewport={{ once: true, margin: "-80px" }}
        transition={{ duration: 0.85, ease: [0.16, 1, 0.3, 1] }}
        className={cn(
          "group relative overflow-hidden rounded-3xl border bg-card max-w-4xl mx-auto",
          "border-primary/25",
          "shadow-[0_24px_72px_-30px_hsl(160_65%_18%/0.45)]",
          "transition-[box-shadow,border-color] duration-500 ease-out",
          "hover:border-accent/45 hover:shadow-[0_32px_90px_-30px_hsl(160_65%_18%/0.55)]",
        )}
      >
        {/* ─── ambient corner washes ─── */}
        <div
          aria-hidden
          className="absolute inset-0"
          style={{
            background:
              "radial-gradient(140% 90% at 50% 0%, hsl(160 65% 22% / 0.12), transparent 65%)," +
              "radial-gradient(140% 90% at 50% 100%, hsl(36 60% 50% / 0.10), transparent 65%)",
          }}
        />

        {/* ─── faint constellation dots ─── */}
        <ConstellationDots />

        {/* ─── cursor spotlight on hover ─── */}
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 opacity-0 transition-opacity duration-500 group-hover:opacity-100"
          style={{
            background: `radial-gradient(520px circle at ${pos.x}% ${pos.y}%, hsl(36 70% 60% / 0.18), transparent 55%)`,
          }}
        />

        {/* ─── top + bottom gold rules ─── */}
        <div
          aria-hidden
          className="absolute inset-x-0 top-0 h-px"
          style={{
            backgroundImage:
              "linear-gradient(90deg, transparent, hsl(36 60% 50%), transparent)",
          }}
        />
        <div
          aria-hidden
          className="absolute inset-x-0 bottom-0 h-px"
          style={{
            backgroundImage:
              "linear-gradient(90deg, transparent, hsl(36 60% 50% / 0.5), transparent)",
          }}
        />

        {/* ─── animated top-border sheen on hover ─── */}
        <motion.div
          aria-hidden
          className="pointer-events-none absolute inset-x-0 top-0 h-px"
          initial={false}
          animate={{
            opacity: hovered ? 1 : 0,
            backgroundPosition: hovered ? "200% 0" : "0% 0",
          }}
          transition={{
            opacity: { duration: 0.4 },
            backgroundPosition: { duration: 1.8, ease: "linear" },
          }}
          style={{
            backgroundImage:
              "linear-gradient(90deg, transparent 0%, hsl(36 60% 55%) 50%, transparent 100%)",
            backgroundSize: "200% 100%",
          }}
        />

        {/* ─── gold corner ornaments (both top corners) ─── */}
        <CornerOrnament className="absolute start-5 top-5" flip />
        <CornerOrnament className="absolute end-5 top-5" />

        {/* ─── Content ─── */}
        <div className="relative px-8 py-14 md:px-16 md:py-20 text-center">
          {/* Kicker pill */}
          <div className="flex justify-center mb-7">
            <span className="inline-flex items-center gap-2 rounded-full border border-accent/40 bg-accent/5 text-accent text-[11px] font-semibold uppercase tracking-[0.22em] px-3 py-1">
              <span className="h-1.5 w-1.5 rounded-full bg-accent" />
              {locale === "ar" ? "ابدأ اليوم" : "Get started"}
            </span>
          </div>

          {/* Logo with halo */}
          <div className="flex justify-center mb-6">
            <div className="relative">
              <span
                aria-hidden
                className="absolute inset-0 rounded-full"
                style={{
                  boxShadow:
                    "0 0 0 1px hsl(36 60% 50% / 0.35), 0 0 70px 10px hsl(36 60% 50% / 0.22)",
                }}
              />
              <BrandLogo size={64} locale={locale} />
            </div>
          </div>

          {/* Title */}
          <h3 className="text-3xl md:text-4xl font-bold tracking-tight leading-tight max-w-2xl mx-auto">
            {title}
          </h3>

          {/* Gold rule */}
          <div
            aria-hidden
            className="mx-auto mt-5 h-[2px] w-16 rounded-full"
            style={{
              backgroundImage:
                "linear-gradient(90deg, transparent, hsl(36 60% 50%), transparent)",
            }}
          />

          {/* Subtitle */}
          <p className="text-base md:text-lg text-muted-foreground mt-5 max-w-xl mx-auto leading-relaxed">
            {subtitle}
          </p>

          {/* CTAs */}
          <div className="mt-8 flex flex-col sm:flex-row gap-3 justify-center">
            <Button asChild size="lg" className="shadow-md">
              <Link href="/sign-up">
                {primary}
                <ArrowRight className="rtl:rotate-180" />
              </Link>
            </Button>
            <Button asChild size="lg" variant="outline">
              <Link href="mailto:hello@mostashari.ai">{secondary}</Link>
            </Button>
          </div>

          {/* Separator */}
          <div
            aria-hidden
            className="mx-auto mt-10 h-px max-w-sm"
            style={{
              backgroundImage:
                "linear-gradient(90deg, transparent, hsl(var(--border)), transparent)",
            }}
          />

          {/* Trust strip */}
          <ul className="mt-5 flex flex-wrap justify-center items-center gap-x-5 gap-y-2 text-[11px] uppercase tracking-[0.18em] text-muted-foreground font-semibold">
            {TRUST_BADGES.map((b, i) => (
              <React.Fragment key={b}>
                {i > 0 && (
                  <li
                    aria-hidden
                    className="h-1 w-1 rounded-full bg-accent/60"
                  />
                )}
                <li>{b}</li>
              </React.Fragment>
            ))}
          </ul>
        </div>
      </motion.div>
    </section>
  );
}

/* ─── decorations ───────────────────────────────────────────────────────── */

function CornerOrnament({
  className,
  flip,
}: {
  className?: string;
  flip?: boolean;
}) {
  return (
    <div
      aria-hidden
      className={cn(
        "pointer-events-none h-6 w-6 opacity-55 transition-opacity duration-500 group-hover:opacity-100",
        className,
      )}
    >
      <svg
        viewBox="0 0 24 24"
        className="h-full w-full"
        style={flip ? { transform: "scaleX(-1)" } : undefined}
      >
        <path
          d="M2 2 L22 2 L22 8 M22 2 L14 10"
          stroke="hsl(36 60% 50%)"
          strokeWidth="1.2"
          fill="none"
          strokeLinecap="round"
        />
      </svg>
    </div>
  );
}

function ConstellationDots() {
  // Deterministic dot field so SSR + client match exactly.
  const dots = React.useMemo(() => {
    const out: { x: number; y: number; r: number; gold: boolean }[] = [];
    let seed = 11;
    const rand = () => {
      seed = (seed * 9301 + 49297) % 233280;
      return seed / 233280;
    };
    for (let i = 0; i < 22; i++) {
      out.push({
        x: rand() * 100,
        y: rand() * 100,
        r: rand() * 1.2 + 0.6,
        gold: rand() > 0.5,
      });
    }
    return out;
  }, []);

  return (
    <div aria-hidden className="pointer-events-none absolute inset-0">
      {dots.map((d, i) => (
        <span
          key={i}
          className="absolute rounded-full"
          style={{
            left: `${d.x}%`,
            top: `${d.y}%`,
            width: `${d.r * 2}px`,
            height: `${d.r * 2}px`,
            background: d.gold
              ? "hsl(36 60% 50% / 0.45)"
              : "hsl(160 65% 22% / 0.32)",
            boxShadow: d.gold
              ? "0 0 6px hsl(36 60% 60% / 0.35)"
              : "0 0 5px hsl(160 65% 35% / 0.30)",
          }}
        />
      ))}
    </div>
  );
}
