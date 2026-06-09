"use client";

/**
 * Closing CTA panel for the marketing landing page.
 *
 * A wide dark obsidian panel that sits on the cream marketing canvas,
 * mirroring the dashboard mockups used in the feature rows so the page
 * lands on a confident, branded note instead of a flat centered card.
 *
 *   ┌───────────────────────────────────────────────────────────────┐
 *   │  ✦ gold orb top-end · dotted constellation overlay ✦          │
 *   │                                                                │
 *   │   READY WHEN YOU ARE  ← gold kicker                            │
 *   │                                                                │
 *   │   Give your firm an AI-native                                  │
 *   │   operating system                                             │
 *   │                                                                │
 *   │   One bilingual workspace, grounded in Saudi law.              │
 *   │                                                                │
 *   │   [ Start free trial → ]   [ Book a demo ]                     │
 *   │                                                                │
 *   │   ✓ 14-day trial · ✓ No card · ✓ KSA-resident · ✓ Cancel anyt. │
 *   └───────────────────────────────────────────────────────────────┘
 *
 *   • Soft animated gold orbs in the corners breathe in/out.
 *   • A faint constellation grid covers the panel (matches the
 *     conversation/feature mockups for visual continuity).
 *   • Big bold white headline · gold underline · subdued body.
 *   • Dual CTA: primary gold button (high contrast on dark) +
 *     secondary outlined white button.
 *   • Trust-strip chips below — sets expectations / reduces friction.
 *   • Honors `prefers-reduced-motion` for the orb breathing.
 */
import { motion, useReducedMotion } from "framer-motion";
import {
  ArrowRight,
  CalendarCheck2,
  Check,
  CreditCard,
  MapPin,
  ShieldCheck,
  type LucideIcon,
} from "lucide-react";
import { Link } from "@/i18n/routing";

import { cn } from "@/lib/utils";

export type MarketingCTAStrings = {
  kicker: string;
  title: string;
  subtitle: string;
  primary: string;
  secondary: string;
  trust: {
    trial: string;
    noCard: string;
    ksa: string;
    cancel: string;
  };
};

export function MarketingCTA({
  strings,
  signUpHref = "/sign-up",
  bookDemoHref = "/contact",
}: {
  strings: MarketingCTAStrings;
  signUpHref?: string;
  bookDemoHref?: string;
}) {
  const reduceMotion = useReducedMotion();

  const trust: { icon: LucideIcon; label: string }[] = [
    { icon: CalendarCheck2, label: strings.trust.trial },
    { icon: CreditCard, label: strings.trust.noCard },
    { icon: MapPin, label: strings.trust.ksa },
    { icon: ShieldCheck, label: strings.trust.cancel },
  ];

  return (
    <section className="container py-20 md:py-24">
      <motion.div
        initial={reduceMotion ? false : { opacity: 0, y: 28 }}
        whileInView={reduceMotion ? undefined : { opacity: 1, y: 0 }}
        viewport={{ once: true, margin: "-60px" }}
        transition={{ duration: 0.75, ease: [0.16, 1, 0.3, 1] }}
        className={cn(
          "relative mx-auto max-w-5xl overflow-hidden rounded-3xl",
          "border border-white/[0.08]",
          "shadow-[0_40px_120px_-30px_hsl(160_65%_15%/0.55)]",
        )}
        style={{
          background:
            "linear-gradient(150deg, hsl(165 32% 9%) 0%, hsl(165 30% 11%) 60%, hsl(165 28% 12%) 100%)",
        }}
      >
        {/* Faint constellation dot grid (matches the dashboards) */}
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 opacity-[0.08]"
          style={{
            backgroundImage:
              "radial-gradient(circle at 1px 1px, white 1px, transparent 0)",
            backgroundSize: "16px 16px",
          }}
        />

        {/* Animated gold orb · top-end corner */}
        <motion.div
          aria-hidden
          className="pointer-events-none absolute -top-24 -end-24 h-72 w-72 rounded-full"
          style={{
            background:
              "radial-gradient(closest-side, hsl(36 70% 55% / 0.55), transparent 70%)",
          }}
          animate={
            reduceMotion
              ? undefined
              : { scale: [1, 1.12, 1], opacity: [0.7, 1, 0.7] }
          }
          transition={{ duration: 6, repeat: Infinity, ease: "easeInOut" }}
        />

        {/* Animated emerald orb · bottom-start corner */}
        <motion.div
          aria-hidden
          className="pointer-events-none absolute -bottom-32 -start-24 h-80 w-80 rounded-full"
          style={{
            background:
              "radial-gradient(closest-side, hsl(160 70% 35% / 0.45), transparent 70%)",
          }}
          animate={
            reduceMotion
              ? undefined
              : { scale: [1, 1.08, 1], opacity: [0.5, 0.85, 0.5] }
          }
          transition={{
            duration: 7.5,
            repeat: Infinity,
            ease: "easeInOut",
            delay: 1.4,
          }}
        />

        {/* Top hairline · gold sheen */}
        <div
          aria-hidden
          className="pointer-events-none absolute inset-x-0 top-0 h-px"
          style={{
            background:
              "linear-gradient(90deg, transparent 0%, hsl(36 60% 55% / 0.8) 50%, transparent 100%)",
          }}
        />

        {/* ─── Content ─── */}
        <div className="relative px-7 py-12 md:px-14 md:py-16 text-center">
          {/* Kicker */}
          <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-accent/30 bg-accent/10 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-amber-300">
            <span className="relative flex h-1.5 w-1.5">
              <span className="absolute inset-0 animate-ping rounded-full bg-amber-400 opacity-60" />
              <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-amber-400" />
            </span>
            {strings.kicker}
          </div>

          {/* Headline */}
          <h2 className="mx-auto max-w-3xl text-3xl md:text-5xl font-bold tracking-tight text-white leading-[1.15]">
            {strings.title}
          </h2>

          {/* Gold rule */}
          <div className="mx-auto mt-5 h-[2px] w-12 rounded-full bg-gradient-to-r from-amber-400 via-amber-300/70 to-transparent rtl:from-amber-400 rtl:via-amber-300/70 rtl:to-transparent" />

          {/* Subtitle */}
          <p className="mx-auto mt-5 max-w-2xl text-base md:text-lg leading-relaxed text-white/70">
            {strings.subtitle}
          </p>

          {/* Dual CTA */}
          <div className="mt-9 flex flex-col items-center justify-center gap-3 sm:flex-row">
            {/* Primary — gold */}
            <Link
              href={signUpHref}
              className={cn(
                "group inline-flex items-center gap-2 rounded-full",
                "bg-amber-400 hover:bg-amber-300",
                "px-6 py-3 text-sm font-semibold text-emerald-950",
                "shadow-[0_12px_32px_-12px_hsl(36_80%_55%/0.6)]",
                "transition-all duration-300",
                "hover:shadow-[0_18px_44px_-12px_hsl(36_80%_55%/0.8)]",
                "hover:-translate-y-0.5",
              )}
            >
              {strings.primary}
              <ArrowRight className="h-4 w-4 transition-transform duration-300 group-hover:translate-x-1 rtl:group-hover:-translate-x-1 rtl:scale-x-[-1]" />
            </Link>

            {/* Secondary — outlined white */}
            <Link
              href={bookDemoHref}
              className={cn(
                "group inline-flex items-center gap-2 rounded-full",
                "border border-white/25 bg-white/[0.04]",
                "px-6 py-3 text-sm font-semibold text-white",
                "transition-all duration-300",
                "hover:bg-white/[0.10] hover:border-white/45",
              )}
            >
              {strings.secondary}
            </Link>
          </div>

          {/* Trust strip */}
          <ul className="mx-auto mt-8 flex max-w-3xl flex-wrap items-center justify-center gap-x-5 gap-y-2 text-[12px] text-white/70">
            {trust.map(({ icon: Icon, label }) => (
              <li key={label} className="inline-flex items-center gap-1.5">
                <span className="inline-flex h-4 w-4 items-center justify-center rounded-full bg-emerald-500/20 text-emerald-300">
                  <Check className="h-2.5 w-2.5" strokeWidth={3} />
                </span>
                <span className="inline-flex items-center gap-1">
                  <Icon className="h-3 w-3 text-white/40" />
                  {label}
                </span>
              </li>
            ))}
          </ul>
        </div>
      </motion.div>
    </section>
  );
}
