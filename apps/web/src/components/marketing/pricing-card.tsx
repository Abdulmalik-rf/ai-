"use client";

/**
 * Single-tier premium pricing card with a Monthly ↔ Yearly toggle.
 *
 * Layout:
 *   ┌──────────────────────────────────┐
 *   │   [ Monthly │ Yearly  -35% ]     │  ← sliding pill toggle
 *   ├──────────────────────────────────┤
 *   │   Plan name                      │
 *   │   Tagline                        │
 *   │                                  │
 *   │   1,849 SAR  /month              │  ← AnimatePresence digit flip
 *   │   Billed monthly · cancel anytime│
 *   │                                  │
 *   │   ✓ Feature 1                    │
 *   │   ✓ Feature 2                    │
 *   │   …                              │
 *   │                                  │
 *   │   [ Start now ]                  │
 *   │                                  │
 *   │   VAT · ZATCA · PDPL fine print  │
 *   └──────────────────────────────────┘
 *
 * The card itself has the same premium ornaments as the feature cards
 * (gold corner glyph, cursor-spotlight, animated top border-glow on hover).
 */

import { motion, AnimatePresence, useReducedMotion } from "framer-motion";
import { Check } from "lucide-react";
import { Link } from "@/i18n/routing";
import * as React from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const MONTHLY_PRICE = 1849;
const YEARLY_PRICE = 14500;
const YEARLY_PER_MONTH_EQUIV = Math.round(YEARLY_PRICE / 12); // 1208

type Period = "monthly" | "yearly";

export type PricingStrings = {
  toggleMonthly: string;
  toggleYearly: string;
  saveBadge: string;
  planName: string;
  planTagline: string;
  perMonth: string;
  perYear: string;
  currency: string;
  billedMonthlyNote: string;
  billedYearlyNote: string;
  yearlyEquivalent: string; // expects "{amount}" placeholder
  ctaStart: string;
  trustNote: string;
  features: {
    research: string;
    drafting: string;
    review: string;
    case: string;
    crm: string;
    whatsapp: string;
    seats: string;
    support: string;
  };
};

export function PricingCard({ strings }: { strings: PricingStrings }) {
  const reduceMotion = useReducedMotion();
  const [period, setPeriod] = React.useState<Period>("yearly");

  // Cursor spotlight
  const cardRef = React.useRef<HTMLDivElement>(null);
  const [pos, setPos] = React.useState({ x: 50, y: 50 });
  const [hovered, setHovered] = React.useState(false);

  const onMouseMove = React.useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      const el = cardRef.current;
      if (!el || reduceMotion) return;
      const r = el.getBoundingClientRect();
      setPos({
        x: ((e.clientX - r.left) / r.width) * 100,
        y: ((e.clientY - r.top) / r.height) * 100,
      });
    },
    [reduceMotion],
  );

  const price = period === "monthly" ? MONTHLY_PRICE : YEARLY_PRICE;
  const periodLabel = period === "monthly" ? strings.perMonth : strings.perYear;
  const billingNote =
    period === "monthly"
      ? strings.billedMonthlyNote
      : strings.billedYearlyNote;

  const features = [
    strings.features.research,
    strings.features.drafting,
    strings.features.review,
    strings.features.case,
    strings.features.crm,
    strings.features.whatsapp,
    strings.features.seats,
    strings.features.support,
  ];

  return (
    <div className="mx-auto max-w-xl">
      <motion.div
        ref={cardRef}
        onMouseMove={onMouseMove}
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
        initial={reduceMotion ? false : { opacity: 0, y: 24 }}
        whileInView={reduceMotion ? undefined : { opacity: 1, y: 0 }}
        viewport={{ once: true, margin: "-60px" }}
        transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
        className={cn(
          "group relative overflow-hidden rounded-3xl border bg-card",
          "border-border/60",
          "shadow-[0_20px_60px_-30px_hsl(160_65%_18%/0.35)]",
          "transition-[box-shadow,border-color] duration-500 ease-out",
          "hover:border-accent/40 hover:shadow-[0_28px_80px_-30px_hsl(160_65%_18%/0.5)]",
        )}
      >
        {/* Ambient gradient — subtle emerald + gold corners */}
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0"
          style={{
            backgroundImage:
              "radial-gradient(120% 80% at 100% 100%, hsl(160 65% 22% / 0.07), transparent 55%)," +
              "radial-gradient(120% 80% at 0% 0%, hsl(36 60% 50% / 0.06), transparent 55%)",
          }}
        />

        {/* Cursor-tracking spotlight */}
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 opacity-0 transition-opacity duration-500 group-hover:opacity-100"
          style={{
            background: `radial-gradient(420px circle at ${pos.x}% ${pos.y}%, hsl(36 70% 60% / 0.16), transparent 55%)`,
          }}
        />

        {/* Top border-glow sweep on hover */}
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
            backgroundPosition: { duration: 1.6, ease: "linear" },
          }}
          style={{
            backgroundImage:
              "linear-gradient(90deg, transparent 0%, hsl(36 60% 55%) 50%, transparent 100%)",
            backgroundSize: "200% 100%",
          }}
        />

        {/* Gold corner ornament — top-end */}
        <div
          aria-hidden
          className="pointer-events-none absolute end-5 top-5 h-6 w-6 opacity-60 transition-opacity duration-500 group-hover:opacity-100"
        >
          <svg viewBox="0 0 24 24" className="h-full w-full">
            <path
              d="M2 2 L22 2 L22 8 M22 2 L14 10"
              stroke="hsl(36 60% 50%)"
              strokeWidth="1.2"
              fill="none"
              strokeLinecap="round"
            />
          </svg>
        </div>

        {/* ─── Content ─── */}
        <div className="relative p-7 md:p-9">
          {/* Toggle */}
          <BillingToggle
            period={period}
            onChange={setPeriod}
            strings={strings}
            reduceMotion={!!reduceMotion}
          />

          {/* Plan header */}
          <div className="mt-8 space-y-1.5">
            <h2 className="text-2xl md:text-3xl font-bold tracking-tight">
              {strings.planName}
            </h2>
            <p className="text-sm text-muted-foreground">
              {strings.planTagline}
            </p>
          </div>

          {/* Price */}
          <div className="mt-6 min-h-[88px]">
            <div className="flex items-baseline gap-2 flex-wrap">
              <AnimatedPrice value={price} reduceMotion={!!reduceMotion} />
              <span className="text-sm font-medium text-muted-foreground">
                {strings.currency}
              </span>
              <span className="text-sm text-muted-foreground">
                {periodLabel}
              </span>
            </div>

            <div className="mt-2 text-xs text-muted-foreground h-4">
              <AnimatePresence mode="wait">
                <motion.span
                  key={period}
                  initial={reduceMotion ? false : { opacity: 0, y: 4 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={reduceMotion ? undefined : { opacity: 0, y: -4 }}
                  transition={{ duration: 0.25 }}
                  className="block"
                >
                  {period === "yearly"
                    ? strings.yearlyEquivalent.replace(
                        "__AMOUNT__",
                        YEARLY_PER_MONTH_EQUIV.toLocaleString(),
                      )
                    : billingNote}
                </motion.span>
              </AnimatePresence>
            </div>
          </div>

          {/* Divider */}
          <div className="my-6 h-px bg-gradient-to-r from-transparent via-border to-transparent" />

          {/* Features */}
          <ul className="space-y-3">
            {features.map((feature, i) => (
              <motion.li
                key={feature}
                initial={reduceMotion ? false : { opacity: 0, x: -6 }}
                whileInView={reduceMotion ? undefined : { opacity: 1, x: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.4, delay: 0.1 + i * 0.04 }}
                className="flex items-start gap-3 text-sm"
              >
                <span className="mt-0.5 grid place-items-center h-5 w-5 rounded-full bg-primary/10 text-primary">
                  <Check className="h-3.5 w-3.5" strokeWidth={2.4} />
                </span>
                <span className="text-foreground">{feature}</span>
              </motion.li>
            ))}
          </ul>

          {/* CTA */}
          <Button asChild size="lg" className="w-full mt-7 shadow-md">
            <Link href="/sign-up">{strings.ctaStart}</Link>
          </Button>

          {/* Trust note */}
          <p className="mt-5 text-[11px] text-muted-foreground text-center">
            {strings.trustNote}
          </p>
        </div>
      </motion.div>
    </div>
  );
}

/* -------------------------------------------------------------------------- */

function BillingToggle({
  period,
  onChange,
  strings,
  reduceMotion,
}: {
  period: Period;
  onChange: (p: Period) => void;
  strings: PricingStrings;
  reduceMotion: boolean;
}) {
  return (
    <div className="flex items-center justify-center">
      <div className="relative inline-flex items-center rounded-full border border-border/70 bg-background/60 p-1 shadow-inner">
        <ToggleOption
          active={period === "monthly"}
          onClick={() => onChange("monthly")}
          reduceMotion={reduceMotion}
        >
          {strings.toggleMonthly}
        </ToggleOption>
        <ToggleOption
          active={period === "yearly"}
          onClick={() => onChange("yearly")}
          reduceMotion={reduceMotion}
          trailing={
            <span className="ms-2 inline-flex items-center rounded-full bg-accent/15 text-accent text-[10px] font-semibold px-1.5 py-0.5 leading-none">
              {strings.saveBadge}
            </span>
          }
        >
          {strings.toggleYearly}
        </ToggleOption>
      </div>
    </div>
  );
}

function ToggleOption({
  active,
  onClick,
  children,
  trailing,
  reduceMotion,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
  trailing?: React.ReactNode;
  reduceMotion: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "relative z-10 inline-flex items-center rounded-full px-4 py-1.5 text-sm font-medium",
        "transition-colors duration-300",
        active ? "text-primary-foreground" : "text-foreground/70 hover:text-foreground",
      )}
    >
      {/* Sliding indicator — shared layoutId so the same pill smoothly
          glides between the two options. */}
      {active && (
        <motion.span
          layoutId="billingToggleIndicator"
          aria-hidden
          className="absolute inset-0 rounded-full bg-primary shadow-sm"
          transition={
            reduceMotion
              ? { duration: 0 }
              : { type: "spring", stiffness: 480, damping: 36 }
          }
        />
      )}
      <span className="relative flex items-center">
        {children}
        {trailing}
      </span>
    </button>
  );
}

/* -------------------------------------------------------------------------- */

function AnimatedPrice({
  value,
  reduceMotion,
}: {
  value: number;
  reduceMotion: boolean;
}) {
  // The price flips with a vertical slide + fade when the period changes.
  return (
    <span className="relative inline-block text-5xl md:text-6xl font-bold tracking-tight tabular-nums">
      <AnimatePresence mode="wait" initial={false}>
        <motion.span
          key={value}
          initial={reduceMotion ? false : { y: 16, opacity: 0, filter: "blur(4px)" }}
          animate={{ y: 0, opacity: 1, filter: "blur(0px)" }}
          exit={reduceMotion ? undefined : { y: -16, opacity: 0, filter: "blur(4px)" }}
          transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
          className="inline-block"
        >
          {value.toLocaleString()}
        </motion.span>
      </AnimatePresence>
    </span>
  );
}
