"use client";

/**
 * Compliance & trust grid — four badge cards in a 2×2 grid. Each card
 * has the same premium chrome as the other section cards.
 */
import { motion, useReducedMotion } from "framer-motion";
import {
  FileCheck2,
  Fingerprint,
  ShieldCheck,
  Workflow,
} from "lucide-react";

import { cn } from "@/lib/utils";

const ICONS = [ShieldCheck, FileCheck2, Fingerprint, Workflow];

export type ComplianceBadge = { title: string; body: string };

export function Compliance({
  kicker,
  title,
  body,
  badges,
}: {
  kicker: string;
  title: string;
  body: string;
  badges: ComplianceBadge[];
}) {
  const reduceMotion = useReducedMotion();

  return (
    <section className="container py-20 md:py-24">
      <div className="max-w-2xl mx-auto text-center mb-10 md:mb-12 space-y-3">
        <div className="text-[11px] uppercase tracking-[0.24em] text-accent font-semibold">
          {kicker}
        </div>
        <h2 className="text-3xl md:text-4xl font-bold tracking-tight">
          {title}
        </h2>
        <div className="mx-auto gold-rule" />
        <p className="text-muted-foreground leading-relaxed">{body}</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-5 md:gap-6 max-w-5xl mx-auto">
        {badges.map((badge, i) => {
          const Icon = ICONS[i] ?? ShieldCheck;
          return (
            <motion.div
              key={badge.title}
              initial={reduceMotion ? false : { opacity: 0, y: 20 }}
              whileInView={reduceMotion ? undefined : { opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-60px" }}
              transition={{
                duration: 0.6,
                delay: i * 0.07,
                ease: [0.16, 1, 0.3, 1],
              }}
              className={cn(
                "relative overflow-hidden rounded-2xl border bg-card p-6 md:p-7",
                "border-border/60",
                "transition-[border-color,box-shadow] duration-500 ease-out",
                "hover:border-accent/40 hover:shadow-[0_18px_48px_-22px_hsl(160_65%_18%/0.45)]",
              )}
            >
              {/* Surface gradient */}
              <div
                aria-hidden
                className="pointer-events-none absolute inset-0 opacity-60"
                style={{
                  backgroundImage:
                    "radial-gradient(120% 80% at 100% 100%, hsl(160 65% 22% / 0.06), transparent 55%)," +
                    "radial-gradient(120% 80% at 0% 0%, hsl(36 60% 50% / 0.05), transparent 55%)",
                }}
              />

              <div className="relative flex gap-4">
                <div
                  className={cn(
                    "shrink-0 grid place-items-center h-14 w-14 rounded-xl",
                    "bg-gradient-to-br from-primary/[0.10] to-accent/[0.08]",
                    "ring-1 ring-inset ring-border/60",
                  )}
                >
                  <Icon className="h-6 w-6 text-primary" strokeWidth={2} />
                </div>
                <div>
                  <h3 className="text-lg md:text-xl font-semibold leading-tight tracking-tight text-foreground">
                    {badge.title}
                  </h3>
                  <p className="mt-1.5 text-sm md:text-[0.95rem] text-muted-foreground leading-relaxed">
                    {badge.body}
                  </p>
                </div>
              </div>
            </motion.div>
          );
        })}
      </div>
    </section>
  );
}
