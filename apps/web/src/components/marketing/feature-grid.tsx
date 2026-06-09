"use client";

/**
 * Premium feature section — Emergize-style stacked rows.
 *
 * Each capability gets its own full-width row. Inside the row:
 *
 *   ┌──────────────────────────────────────────────────────────────┐
 *   │  [Live product UI panel]   │   01  KICKER                    │
 *   │                            │                                 │
 *   │  (dark dashboard mockup    │   Big bold title                │
 *   │   with realistic data,     │                                 │
 *   │   animated indicators,     │   Comprehensive description     │
 *   │   typing dots, etc.)       │   paragraph that explains the   │
 *   │                            │   capability in detail.         │
 *   │                            │                                 │
 *   │                            │   ✓ Bullet 1                    │
 *   │                            │   ✓ Bullet 2                    │
 *   │                            │   ✓ Bullet 3                    │
 *   │                            │                                 │
 *   │                            │   [ Explore →  ]                │
 *   └──────────────────────────────────────────────────────────────┘
 *
 * Rows alternate sides: even rows put the mockup on the leading edge,
 * odd rows put it on the trailing edge — creating a visual rhythm down
 * the page. We honour `prefers-reduced-motion` for entrance animation.
 */
import { motion, useReducedMotion } from "framer-motion";
import { ArrowRight, Check } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

import {
  OperationsMockup,
  WorkbenchMockup,
} from "./feature-mockups";

export type FeatureKey = "workbench" | "operations";

export type FeatureItem = {
  key: FeatureKey;
  kicker: string;
  title: string;
  description: string;
  bullets: [string, string, string];
  cta: string;
};

const MOCKUPS: Record<FeatureKey, (p: { locale: string }) => React.ReactNode> = {
  workbench: WorkbenchMockup,
  operations: OperationsMockup,
};

export function FeatureGrid({
  items,
  locale,
}: {
  items: FeatureItem[];
  locale: string;
}) {
  return (
    <div className="space-y-8 md:space-y-10 max-w-6xl mx-auto">
      {items.map((item, i) => (
        <FeatureRow key={item.key} item={item} index={i} locale={locale} />
      ))}
    </div>
  );
}

function FeatureRow({
  item,
  index,
  locale,
}: {
  item: FeatureItem;
  index: number;
  locale: string;
}) {
  const reduceMotion = useReducedMotion();
  const Mockup = MOCKUPS[item.key];
  // Alternate which side the mockup sits on. CSS Grid respects `dir="rtl"`
  // automatically (col 1 = visually right in RTL), so the same parity rule
  // works in both languages: even rows put the mockup on the leading edge
  // (left in LTR / right in RTL), odd rows put it on the trailing edge.
  const swap = index % 2 === 1;

  return (
    <motion.div
      initial={reduceMotion ? false : { opacity: 0, y: 32 }}
      whileInView={reduceMotion ? undefined : { opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-80px" }}
      transition={{
        duration: 0.75,
        delay: index * 0.08,
        ease: [0.16, 1, 0.3, 1],
      }}
      className={cn(
        "relative overflow-hidden rounded-3xl border bg-card",
        "border-border/60",
        "shadow-[0_18px_60px_-30px_hsl(160_65%_18%/0.32)]",
      )}
    >
      {/* Subtle ambient gradient on the card surface */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 opacity-70"
        style={{
          backgroundImage:
            "radial-gradient(140% 90% at 100% 100%, hsl(160 65% 22% / 0.06), transparent 55%)," +
            "radial-gradient(140% 90% at 0% 0%, hsl(36 60% 50% / 0.05), transparent 55%)",
        }}
      />

      <div
        className={cn(
          "relative grid items-center gap-8 md:gap-10 p-6 md:p-10",
          "md:grid-cols-2",
        )}
      >
        {/* ─── Mockup half ─── */}
        <div className={cn("relative", swap && "md:order-2")}>
          <Mockup locale={locale} />
        </div>

        {/* ─── Text half ─── */}
        <div className="relative">
          {/* Number + kicker pill */}
          <div className="mb-4 inline-flex items-center gap-2">
            <span className="inline-flex h-7 w-7 items-center justify-center rounded-full border border-accent/40 bg-accent/10 text-[11px] font-bold text-accent">
              0{index + 1}
            </span>
            <span className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
              {item.kicker}
            </span>
          </div>

          <h3 className="text-2xl md:text-3xl font-bold leading-tight tracking-tight text-foreground">
            {item.title}
          </h3>

          <p className="mt-4 text-[0.95rem] md:text-base leading-relaxed text-muted-foreground">
            {item.description}
          </p>

          <ul className="mt-5 space-y-2.5">
            {item.bullets.map((b) => (
              <li key={b} className="flex items-start gap-3 text-[0.95rem] text-foreground">
                <span className="mt-1 inline-flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-primary/12 text-primary">
                  <Check className="h-3 w-3" strokeWidth={3} />
                </span>
                <span>{b}</span>
              </li>
            ))}
          </ul>

          <div className="mt-7">
            <Button variant="outline" size="lg" className="group/btn">
              <span>{item.cta}</span>
              <ArrowRight className="ms-2 h-4 w-4 transition-transform duration-300 group-hover/btn:translate-x-1 rtl:group-hover/btn:-translate-x-1 rtl:scale-x-[-1]" />
            </Button>
          </div>
        </div>
      </div>
    </motion.div>
  );
}
