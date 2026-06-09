"use client";

/**
 * Capability constellation — six premium cards arranged in a grid, each
 * with a continuously-idling animated SVG icon. Reuses the same hover
 * chrome as the homepage feature rows: cursor spotlight, top border
 * sweep, gold corner ornament, soft hover lift.
 */
import { motion, useReducedMotion } from "framer-motion";
import * as React from "react";

import { cn } from "@/lib/utils";

import {
  FEATURES_PAGE_ICON_BY_KEY,
  type CapabilityIconKey,
} from "./capability-icons";

type ItemKey = CapabilityIconKey;

const ICONS = FEATURES_PAGE_ICON_BY_KEY;

export type ConstellationItem = {
  key: ItemKey;
  title: string;
  body: string;
};

export function Constellation({
  kicker,
  title,
  subtitle,
  items,
}: {
  kicker: string;
  title: string;
  subtitle: string;
  items: ConstellationItem[];
}) {
  return (
    <section className="container py-20 md:py-24">
      <div className="max-w-2xl mx-auto text-center mb-12 md:mb-14 space-y-3">
        <div className="text-[11px] uppercase tracking-[0.24em] text-accent font-semibold">
          {kicker}
        </div>
        <h2 className="text-3xl md:text-4xl font-bold tracking-tight">
          {title}
        </h2>
        <div className="mx-auto gold-rule" />
        <p className="text-muted-foreground leading-relaxed">{subtitle}</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5 md:gap-6 max-w-6xl mx-auto">
        {items.map((item, i) => (
          <CapabilityCard key={item.key} item={item} index={i} />
        ))}
      </div>
    </section>
  );
}

function CapabilityCard({
  item,
  index,
}: {
  item: ConstellationItem;
  index: number;
}) {
  const reduceMotion = useReducedMotion();
  const Icon = ICONS[item.key];
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
      initial={reduceMotion ? false : { opacity: 0, y: 24 }}
      whileInView={reduceMotion ? undefined : { opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-60px" }}
      transition={{
        duration: 0.6,
        delay: index * 0.06,
        ease: [0.16, 1, 0.3, 1],
      }}
      whileHover={reduceMotion ? undefined : { y: -4 }}
      className={cn(
        "group relative overflow-hidden rounded-2xl border bg-card",
        "border-border/60",
        "transition-[box-shadow,border-color] duration-500 ease-out",
        "hover:border-accent/40 hover:shadow-[0_18px_48px_-22px_hsl(160_65%_18%/0.45)]",
      )}
    >
      {/* Layer 1 — ambient gradient on the surface */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 opacity-60"
        style={{
          backgroundImage:
            "radial-gradient(120% 80% at 100% 100%, hsl(160 65% 22% / 0.06), transparent 55%)," +
            "radial-gradient(120% 80% at 0% 0%, hsl(36 60% 50% / 0.05), transparent 55%)",
        }}
      />

      {/* Layer 2 — cursor-tracking spotlight */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 opacity-0 transition-opacity duration-500 group-hover:opacity-100"
        style={{
          background: `radial-gradient(360px circle at ${pos.x}% ${pos.y}%, hsl(36 70% 60% / 0.16), transparent 55%)`,
        }}
      />

      {/* Layer 3 — top border-glow sweep on hover */}
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

      {/* Layer 4 — gold corner ornament */}
      <div
        aria-hidden
        className="pointer-events-none absolute end-4 top-4 h-6 w-6 opacity-50 transition-opacity duration-500 group-hover:opacity-100"
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

      {/* Content */}
      <div className="relative p-6 md:p-7">
        <div
          className={cn(
            "relative mb-5 flex h-24 w-24 items-center justify-center overflow-hidden rounded-xl",
            "bg-gradient-to-br from-primary/[0.06] via-transparent to-accent/[0.08]",
            "ring-1 ring-inset ring-border/60",
            "transition-all duration-500 group-hover:ring-accent/30",
          )}
        >
          <div className="relative h-16 w-16">
            <Icon active={hovered} />
          </div>
        </div>

        <h3
          className={cn(
            "text-lg md:text-xl font-semibold leading-tight tracking-tight",
            "text-foreground transition-colors duration-300",
            "group-hover:text-accent",
          )}
        >
          {item.title}
        </h3>

        <p className="mt-3 text-[0.95rem] leading-relaxed text-muted-foreground">
          {item.body}
        </p>

        {/* Growing gold underline on hover */}
        <motion.div
          aria-hidden
          className="mt-6 h-px origin-start bg-gradient-to-r from-accent/70 to-accent/0"
          initial={false}
          animate={{ scaleX: hovered ? 1 : 0.18 }}
          transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
          style={{ transformOrigin: "left" }}
        />
      </div>
    </motion.div>
  );
}
