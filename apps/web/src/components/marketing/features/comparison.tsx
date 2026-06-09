"use client";

/**
 * Comparison table — "The old way vs. Mostashari".
 * Each row stagger-enters on scroll. The "Mostashari" column has the
 * gold accent treatment; the "old way" column is muted.
 */
import { motion, useReducedMotion } from "framer-motion";
import { Check, X } from "lucide-react";

export type ComparisonRow = {
  feature: string;
  old: string;
  next: string;
};

export function Comparison({
  kicker,
  title,
  rows,
  header,
}: {
  kicker: string;
  title: string;
  rows: ComparisonRow[];
  header: { feature: string; old: string; new: string };
}) {
  const reduceMotion = useReducedMotion();

  return (
    <section className="container py-20 md:py-24">
      <div className="max-w-2xl mx-auto text-center mb-12 space-y-3">
        <div className="text-[11px] uppercase tracking-[0.24em] text-accent font-semibold">
          {kicker}
        </div>
        <h2 className="text-3xl md:text-4xl font-bold tracking-tight">
          {title}
        </h2>
        <div className="mx-auto gold-rule" />
      </div>

      <motion.div
        initial={reduceMotion ? false : { opacity: 0, y: 24 }}
        whileInView={reduceMotion ? undefined : { opacity: 1, y: 0 }}
        viewport={{ once: true, margin: "-60px" }}
        transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
        className="relative max-w-5xl mx-auto rounded-3xl border border-border/60 bg-card shadow-[0_18px_60px_-30px_hsl(160_65%_18%/0.32)] overflow-hidden"
      >
        {/* Gold accent at top */}
        <div
          aria-hidden
          className="pointer-events-none absolute inset-x-0 top-0 h-px"
          style={{
            backgroundImage:
              "linear-gradient(90deg, transparent, hsl(36 60% 50%), transparent)",
          }}
        />

        {/* Header row */}
        <div className="grid grid-cols-[1.2fr_1fr_1fr] md:grid-cols-[1.6fr_1fr_1fr] gap-2 md:gap-4 px-4 md:px-8 py-4 border-b border-border/60 bg-muted/30">
          <div className="text-xs md:text-sm font-semibold uppercase tracking-wider text-muted-foreground">
            {header.feature}
          </div>
          <div className="text-xs md:text-sm font-semibold uppercase tracking-wider text-muted-foreground">
            {header.old}
          </div>
          <div className="text-xs md:text-sm font-semibold uppercase tracking-wider text-accent">
            {header.new}
          </div>
        </div>

        {/* Rows */}
        <ul>
          {rows.map((row, i) => (
            <motion.li
              key={row.feature}
              initial={reduceMotion ? false : { opacity: 0, y: 12 }}
              whileInView={reduceMotion ? undefined : { opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{
                duration: 0.5,
                delay: i * 0.06,
                ease: [0.16, 1, 0.3, 1],
              }}
              className="grid grid-cols-[1.2fr_1fr_1fr] md:grid-cols-[1.6fr_1fr_1fr] gap-2 md:gap-4 px-4 md:px-8 py-4 md:py-5 border-b border-border/40 last:border-b-0 hover:bg-muted/20 transition-colors"
            >
              <div className="text-sm md:text-[0.95rem] font-medium text-foreground">
                {row.feature}
              </div>
              <div className="flex items-center gap-2 text-sm text-muted-foreground line-through decoration-muted-foreground/40">
                <span className="inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-muted text-muted-foreground/70">
                  <X className="h-3 w-3" strokeWidth={2.5} />
                </span>
                <span className="truncate">{row.old}</span>
              </div>
              <div className="flex items-center gap-2 text-sm md:text-[0.95rem] font-medium text-foreground">
                <span className="inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-primary/12 text-primary">
                  <Check className="h-3 w-3" strokeWidth={3} />
                </span>
                <span className="truncate">{row.next}</span>
              </div>
            </motion.li>
          ))}
        </ul>
      </motion.div>
    </section>
  );
}
