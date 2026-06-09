"use client";

/**
 * "Deep-dive" section — a single stacked feature row hosting one live
 * product mockup beside a comprehensive text block (kicker · big title ·
 * body paragraph · bulleted checklist · outline CTA).
 *
 * Same chrome as the homepage feature rows, kept consistent on purpose.
 * Two layout variants:
 *   • `mockupSide = "start"` → mockup on the leading edge (left in LTR)
 *   • `mockupSide = "end"`   → mockup on the trailing edge (right in LTR)
 */
import { motion, useReducedMotion } from "framer-motion";
import { ArrowRight, Check } from "lucide-react";
import { Link } from "@/i18n/routing";
import * as React from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

import {
  DraftingStudioPanel,
  MatterStreamPanel,
} from "./live-panels";

const MOCKUPS = {
  workbench: DraftingStudioPanel,
  operations: MatterStreamPanel,
} as const;

export function DeepDive({
  variant,
  index,
  mockupSide,
  locale,
  kicker,
  title,
  body,
  bullets,
  cta,
  ctaHref = "/sign-up",
}: {
  variant: keyof typeof MOCKUPS;
  index: number;
  mockupSide: "start" | "end";
  locale: string;
  kicker: string;
  title: string;
  body: string;
  bullets: string[];
  cta: string;
  ctaHref?: string;
}) {
  const reduceMotion = useReducedMotion();
  const Mockup = MOCKUPS[variant];

  return (
    <section className="container py-14 md:py-20">
      <motion.div
        initial={reduceMotion ? false : { opacity: 0, y: 28 }}
        whileInView={reduceMotion ? undefined : { opacity: 1, y: 0 }}
        viewport={{ once: true, margin: "-80px" }}
        transition={{ duration: 0.75, ease: [0.16, 1, 0.3, 1] }}
        className={cn(
          "relative overflow-hidden rounded-3xl border bg-card max-w-6xl mx-auto",
          "border-border/60",
          "shadow-[0_18px_60px_-30px_hsl(160_65%_18%/0.32)]",
        )}
      >
        {/* Ambient gradient inside the surface */}
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 opacity-70"
          style={{
            backgroundImage:
              "radial-gradient(140% 90% at 100% 100%, hsl(160 65% 22% / 0.06), transparent 55%)," +
              "radial-gradient(140% 90% at 0% 0%, hsl(36 60% 50% / 0.05), transparent 55%)",
          }}
        />

        <div className="relative grid items-center gap-8 md:gap-10 p-6 md:p-10 md:grid-cols-2">
          {/* Mockup */}
          <div className={cn("relative", mockupSide === "end" && "md:order-2")}>
            <Mockup locale={locale} />
          </div>

          {/* Text */}
          <div className="relative">
            <div className="mb-4 inline-flex items-center gap-2">
              <span className="inline-flex h-7 w-7 items-center justify-center rounded-full border border-accent/40 bg-accent/10 text-[11px] font-bold text-accent">
                0{index + 1}
              </span>
              <span className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                {kicker}
              </span>
            </div>

            <h2 className="text-2xl md:text-3xl font-bold leading-tight tracking-tight text-foreground">
              {title}
            </h2>

            <p className="mt-4 text-[0.95rem] md:text-base leading-relaxed text-muted-foreground">
              {body}
            </p>

            <ul className="mt-5 space-y-2.5">
              {bullets.map((b) => (
                <li
                  key={b}
                  className="flex items-start gap-3 text-[0.95rem] text-foreground"
                >
                  <span className="mt-1 inline-flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-primary/12 text-primary">
                    <Check className="h-3 w-3" strokeWidth={3} />
                  </span>
                  <span>{b}</span>
                </li>
              ))}
            </ul>

            <div className="mt-7">
              <Button asChild variant="outline" size="lg" className="group/btn">
                <Link href={ctaHref}>
                  <span>{cta}</span>
                  <ArrowRight className="ms-2 h-4 w-4 transition-transform duration-300 group-hover/btn:translate-x-1 rtl:group-hover/btn:-translate-x-1 rtl:scale-x-[-1]" />
                </Link>
              </Button>
            </div>
          </div>
        </div>
      </motion.div>
    </section>
  );
}
