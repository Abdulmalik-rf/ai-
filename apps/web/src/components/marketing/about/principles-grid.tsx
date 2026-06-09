"use client";

/**
 * Two visually distinct grids:
 *
 *   • `variant="principles"` — three tall cards, each with a numbered
 *     badge, an oversized icon plate at the top, a big title and body
 *     paragraph. Premium chrome (cursor spotlight, top-border sheen on
 *     hover, gold corner ornament, hover lift).
 *
 *   • `variant="values"` — four cards in a 2×2 grid. Horizontal layout
 *     (icon plate on the leading edge, text on the trailing edge) so it
 *     visually contrasts with the principles section above it.
 *
 * Both variants pull the same chrome (built once in `<PremiumCard>` below)
 * but lay out the inner content differently.
 */
import { motion, useReducedMotion } from "framer-motion";
import {
  BookOpenCheck,
  Eye,
  Lock,
  MapPin,
  Scale,
  ShieldCheck,
  Sparkles,
  type LucideIcon,
} from "lucide-react";
import * as React from "react";

import { cn } from "@/lib/utils";

type Item = {
  key: string;
  title: string;
  body: string;
};

type Variant = "values" | "principles";

const VALUE_ICONS: Record<string, LucideIcon> = {
  trust: Eye,
  privacy: Lock,
  saudi: MapPin,
  speed: Sparkles,
};

const PRINCIPLE_ICONS: Record<string, LucideIcon> = {
  grounded: BookOpenCheck,
  lawyerLed: Scale,
  compliant: ShieldCheck,
};

export function PrinciplesGrid({
  heading,
  items,
  variant,
}: {
  heading: string;
  items: Item[];
  variant: Variant;
}) {
  const isValues = variant === "values";

  return (
    <section className="container py-20 md:py-24">
      <div className="max-w-2xl mx-auto text-center mb-12 space-y-3">
        <motion.h2
          initial={{ opacity: 0, y: 12 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-60px" }}
          transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
          className="text-3xl md:text-4xl font-bold tracking-tight"
        >
          {heading}
        </motion.h2>
        <div className="mx-auto gold-rule" />
      </div>

      {isValues ? (
        <ValuesGrid items={items} />
      ) : (
        <PrinciplesRow items={items} />
      )}
    </section>
  );
}

/* ─── Principles: 3 tall cards in a row ─────────────────────────────────── */

function PrinciplesRow({ items }: { items: Item[] }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-6xl mx-auto">
      {items.map((it, i) => (
        <PrincipleCard key={it.key} item={it} index={i} />
      ))}
    </div>
  );
}

function PrincipleCard({ item, index }: { item: Item; index: number }) {
  const Icon = PRINCIPLE_ICONS[item.key];

  return (
    <PremiumCard delay={index * 0.08} className="p-7 md:p-8">
      {/* Number badge — corner */}
      <div className="absolute end-7 top-7 inline-flex h-7 w-7 items-center justify-center rounded-full border border-accent/40 bg-accent/10 text-[11px] font-bold text-accent">
        0{index + 1}
      </div>

      {/* Oversized icon plate */}
      <div
        className={cn(
          "relative grid place-items-center h-20 w-20 rounded-2xl mb-6",
          "bg-gradient-to-br from-primary/[0.10] via-transparent to-accent/[0.10]",
          "ring-1 ring-inset ring-border/60",
          "text-primary transition-colors duration-300",
          "group-hover:ring-accent/40 group-hover:text-accent",
        )}
      >
        {Icon && <Icon className="h-9 w-9" strokeWidth={1.6} />}
      </div>

      <h3 className="text-xl md:text-2xl font-semibold leading-tight tracking-tight text-foreground transition-colors duration-300 group-hover:text-accent">
        {item.title}
      </h3>

      <p className="mt-3 text-[0.95rem] md:text-base leading-relaxed text-muted-foreground">
        {item.body}
      </p>

      {/* Gold rule at the bottom for finish */}
      <div
        aria-hidden
        className="mt-6 h-px w-12 transition-all duration-500 group-hover:w-20"
        style={{
          backgroundImage:
            "linear-gradient(90deg, hsl(36 60% 50%), transparent)",
        }}
      />
    </PremiumCard>
  );
}

/* ─── Values: 2×2 grid with horizontal cards ─────────────────────────────── */

function ValuesGrid({ items }: { items: Item[] }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-5 max-w-5xl mx-auto">
      {items.map((it, i) => (
        <ValueCard key={it.key} item={it} index={i} />
      ))}
    </div>
  );
}

function ValueCard({ item, index }: { item: Item; index: number }) {
  const Icon = VALUE_ICONS[item.key];

  return (
    <PremiumCard delay={index * 0.07} className="p-6 md:p-7">
      <div className="flex items-start gap-5">
        {/* Icon plate */}
        <div
          className={cn(
            "shrink-0 grid place-items-center h-16 w-16 rounded-2xl",
            "bg-gradient-to-br from-primary/[0.10] via-transparent to-accent/[0.10]",
            "ring-1 ring-inset ring-border/60",
            "text-primary transition-colors duration-300",
            "group-hover:ring-accent/40 group-hover:text-accent",
          )}
        >
          {Icon && <Icon className="h-7 w-7" strokeWidth={1.6} />}
        </div>

        {/* Text */}
        <div className="min-w-0">
          <div className="inline-flex items-center gap-2 mb-2">
            <span className="text-[10px] font-bold uppercase tracking-[0.22em] text-accent tabular-nums">
              0{index + 1}
            </span>
            <span className="h-px w-6 bg-accent/40" />
          </div>
          <h3 className="text-lg md:text-xl font-semibold leading-tight tracking-tight text-foreground transition-colors duration-300 group-hover:text-accent">
            {item.title}
          </h3>
          <p className="mt-2 text-sm md:text-[0.95rem] text-muted-foreground leading-relaxed">
            {item.body}
          </p>
        </div>
      </div>
    </PremiumCard>
  );
}

/* ─── Premium card chrome (shared) ───────────────────────────────────────── */

function PremiumCard({
  children,
  delay,
  className,
}: {
  children: React.ReactNode;
  delay: number;
  className?: string;
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
    <motion.div
      ref={ref}
      onMouseMove={onMouseMove}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      initial={reduceMotion ? false : { opacity: 0, y: 22 }}
      whileInView={reduceMotion ? undefined : { opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-60px" }}
      whileHover={reduceMotion ? undefined : { y: -4 }}
      transition={{
        duration: 0.7,
        delay,
        ease: [0.16, 1, 0.3, 1],
      }}
      className={cn(
        "group relative overflow-hidden rounded-2xl border bg-card",
        "border-border/60",
        "shadow-[0_14px_44px_-26px_hsl(160_65%_18%/0.32)]",
        "transition-[box-shadow,border-color] duration-500 ease-out",
        "hover:border-accent/40 hover:shadow-[0_22px_60px_-26px_hsl(160_65%_18%/0.45)]",
        className,
      )}
    >
      {/* ambient corner gradients */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 opacity-70"
        style={{
          backgroundImage:
            "radial-gradient(120% 80% at 100% 100%, hsl(160 65% 22% / 0.06), transparent 55%)," +
            "radial-gradient(120% 80% at 0% 0%, hsl(36 60% 50% / 0.05), transparent 55%)",
        }}
      />

      {/* cursor spotlight on hover */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 opacity-0 transition-opacity duration-500 group-hover:opacity-100"
        style={{
          background: `radial-gradient(360px circle at ${pos.x}% ${pos.y}%, hsl(36 70% 60% / 0.18), transparent 55%)`,
        }}
      />

      {/* top border sheen on hover */}
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

      {/* gold corner ornament (top-end) */}
      <div
        aria-hidden
        className="pointer-events-none absolute end-4 top-4 h-5 w-5 opacity-50 transition-opacity duration-500 group-hover:opacity-100"
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

      <div className="relative">{children}</div>
    </motion.div>
  );
}
