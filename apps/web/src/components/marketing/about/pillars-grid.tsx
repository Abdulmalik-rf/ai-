"use client";

/**
 * "What sets us apart" — one premium box, two columns.
 *
 *   ┌──────────────────────────────────────────────────────────────┐
 *   │  [Wide motion-graphic banner          ] │  THREE PILLARS     │
 *   │  showing the three pillar concepts    │                      │
 *   │  (mission target / team / commitment  │  ⬢ Our mission       │
 *   │  shield) unified into one composition │     short body…      │
 *   │                                       │                      │
 *   │                                       │  ⬢ Our team          │
 *   │                                       │     short body…      │
 *   │                                       │                      │
 *   │                                       │  ⬢ Our commitment    │
 *   │                                       │     short body…      │
 *   └──────────────────────────────────────────────────────────────┘
 *
 * Premium chrome matches the homepage feature rows:
 *   • cursor-tracking gold spotlight on hover
 *   • animated top border-glow sweep on hover
 *   • gold corner ornament
 *   • soft hover lift + box-shadow lift
 *   • ambient emerald + gold gradient washes inside the surface
 */
import { motion, useReducedMotion } from "framer-motion";
import * as React from "react";

import { cn } from "@/lib/utils";

import {
  PILLAR_ICON_BY_KEY,
  type PillarIconKey,
} from "./pillar-icons";

export type Pillar = {
  key: PillarIconKey;
  title: string;
  body: string;
};

const EMERALD = "hsl(160 65% 22%)";
const EMERALD_SOFT = "hsl(160 60% 35%)";
const GOLD = "hsl(36 60% 50%)";
const GOLD_SOFT = "hsl(36 70% 65%)";

export function PillarsGrid({
  heading,
  items,
}: {
  heading: string;
  items: Pillar[];
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
    <section className="container py-20 md:py-24">
      <div className="max-w-2xl mx-auto text-center mb-12 space-y-3">
        <h2 className="text-3xl md:text-4xl font-bold tracking-tight">
          {heading}
        </h2>
        <div className="mx-auto gold-rule" />
      </div>

      <motion.div
        ref={ref}
        onMouseMove={onMouseMove}
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
        initial={reduceMotion ? false : { opacity: 0, y: 28 }}
        whileInView={reduceMotion ? undefined : { opacity: 1, y: 0 }}
        viewport={{ once: true, margin: "-80px" }}
        transition={{ duration: 0.75, ease: [0.16, 1, 0.3, 1] }}
        className={cn(
          "group relative overflow-hidden rounded-3xl border bg-card max-w-6xl mx-auto",
          "border-border/60",
          "shadow-[0_18px_60px_-30px_hsl(160_65%_18%/0.32)]",
          "transition-[box-shadow,border-color] duration-500 ease-out",
          "hover:border-accent/40 hover:shadow-[0_28px_80px_-30px_hsl(160_65%_18%/0.5)]",
        )}
      >
        {/* ─── Layer 1: ambient gradient on the card surface ─── */}
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 opacity-70"
          style={{
            backgroundImage:
              "radial-gradient(140% 90% at 100% 100%, hsl(160 65% 22% / 0.07), transparent 55%)," +
              "radial-gradient(140% 90% at 0% 0%, hsl(36 60% 50% / 0.06), transparent 55%)",
          }}
        />

        {/* ─── Layer 2: cursor-tracking gold spotlight on hover ─── */}
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 opacity-0 transition-opacity duration-500 group-hover:opacity-100"
          style={{
            background: `radial-gradient(480px circle at ${pos.x}% ${pos.y}%, hsl(36 70% 60% / 0.16), transparent 55%)`,
          }}
        />

        {/* ─── Layer 3: animated top-border sweep on hover ─── */}
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

        {/* ─── Layer 4: gold corner ornament ─── */}
        <div
          aria-hidden
          className="pointer-events-none absolute end-5 top-5 h-7 w-7 opacity-60 transition-opacity duration-500 group-hover:opacity-100"
        >
          <svg viewBox="0 0 24 24" className="h-full w-full">
            <path
              d="M2 2 L22 2 L22 8 M22 2 L14 10"
              stroke={GOLD}
              strokeWidth="1.2"
              fill="none"
              strokeLinecap="round"
            />
          </svg>
        </div>

        {/* ─── Content: two columns ─── */}
        <div className="relative grid items-center gap-8 md:gap-12 p-6 md:p-10 md:grid-cols-[1.05fr_1fr]">
          {/* Motion-graphic banner */}
          <div
            className={cn(
              "relative aspect-[4/3] overflow-hidden rounded-2xl",
              "bg-gradient-to-br from-primary/[0.05] via-transparent to-accent/[0.06]",
              "ring-1 ring-inset ring-border/60",
              "transition-shadow duration-500 group-hover:ring-accent/30",
            )}
          >
            <PillarsBanner active={hovered} reduceMotion={!!reduceMotion} />
          </div>

          {/* Pillars list */}
          <div className="relative">
            <div className="mb-5 inline-flex items-center gap-2">
              <span className="inline-flex h-7 w-7 items-center justify-center rounded-full border border-accent/40 bg-accent/10 text-[11px] font-bold text-accent">
                3
              </span>
              <span className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                {heading}
              </span>
            </div>

            <ul className="space-y-6 md:space-y-7">
              {items.map((pillar) => {
                const Icon = PILLAR_ICON_BY_KEY[pillar.key];
                return (
                  <li key={pillar.key} className="flex gap-4">
                    <div
                      className={cn(
                        "shrink-0 grid place-items-center h-14 w-14 rounded-xl",
                        "bg-gradient-to-br from-primary/[0.08] to-accent/[0.07]",
                        "ring-1 ring-inset ring-border/60",
                      )}
                    >
                      <div className="h-10 w-10">
                        <Icon />
                      </div>
                    </div>
                    <div>
                      <h3 className="text-lg md:text-xl font-semibold leading-tight tracking-tight text-foreground">
                        {pillar.title}
                      </h3>
                      <p className="mt-1.5 text-sm md:text-[0.95rem] text-muted-foreground leading-relaxed">
                        {pillar.body}
                      </p>
                    </div>
                  </li>
                );
              })}
            </ul>
          </div>
        </div>
      </motion.div>
    </section>
  );
}

/* ─────────────────────────────────────────────────────────────────────── */
/* Wide motion-graphic banner: three pillar concepts unified in one
   composition. Subtle idle animation only — no looping firework noise. */
function PillarsBanner({
  active,
  reduceMotion,
}: {
  active: boolean;
  reduceMotion: boolean;
}) {
  return (
    <svg
      viewBox="0 0 240 180"
      className="absolute inset-0 h-full w-full"
      aria-hidden
    >
      <defs>
        <radialGradient id="pillars-glow" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor={GOLD_SOFT} stopOpacity="0.32" />
          <stop offset="100%" stopColor={GOLD} stopOpacity="0" />
        </radialGradient>
        <linearGradient id="pillars-shield" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor={EMERALD_SOFT} stopOpacity="0.20" />
          <stop offset="100%" stopColor={EMERALD} stopOpacity="0.32" />
        </linearGradient>
      </defs>

      {/* central halo */}
      <circle cx="120" cy="92" r="78" fill="url(#pillars-glow)" />

      {/* faint dot grid backdrop */}
      <g opacity="0.55">
        {[30, 90, 150, 210].map((cx) =>
          [30, 70, 110, 150].map((cy) => (
            <circle key={`${cx}-${cy}`} cx={cx} cy={cy} r="0.8" fill={EMERALD} fillOpacity="0.18" />
          )),
        )}
      </g>

      {/* gold connecting lines between the three nodes */}
      <path
        d="M 52 118 Q 120 38 188 118"
        fill="none"
        stroke={GOLD}
        strokeWidth="0.6"
        strokeDasharray="2 3"
        opacity="0.38"
      />
      <line
        x1="62"
        y1="118"
        x2="178"
        y2="118"
        stroke={GOLD}
        strokeOpacity="0.32"
        strokeWidth="0.5"
        strokeDasharray="2 3"
      />

      {/* ─── Left node: target (mission) ─── */}
      <g transform="translate(52 118)">
        <circle r="22" fill="none" stroke={EMERALD} strokeOpacity="0.20" strokeWidth="0.8" />
        <circle r="14" fill="none" stroke={EMERALD} strokeOpacity="0.40" strokeWidth="1.1" />
        <circle r="6" fill={EMERALD} />
        <motion.circle
          r="3"
          fill={GOLD}
          animate={
            reduceMotion || !active
              ? undefined
              : { opacity: [0.6, 1, 0.6] }
          }
          transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
        />
        {/* crosshair ticks */}
        {[
          [0, -24, 0, -28],
          [0, 24, 0, 28],
          [-24, 0, -28, 0],
          [24, 0, 28, 0],
        ].map(([x1, y1, x2, y2], i) => (
          <line
            key={i}
            x1={x1}
            y1={y1}
            x2={x2}
            y2={y2}
            stroke={EMERALD}
            strokeWidth="1.2"
            strokeLinecap="round"
            strokeOpacity="0.55"
          />
        ))}
      </g>

      {/* ─── Top centre node: team (three figures around a centre) ─── */}
      <g transform="translate(120 50)">
        <circle r="20" fill={GOLD} fillOpacity="0.10" />
        <circle r="6" fill={GOLD} />
        {[0, 120, 240].map((angle) => {
          const rad = (angle * Math.PI) / 180;
          const cx = Math.cos(rad) * 22;
          const cy = Math.sin(rad) * 22;
          return (
            <g key={angle}>
              <line
                x1="0"
                y1="0"
                x2={cx * 0.7}
                y2={cy * 0.7}
                stroke={GOLD}
                strokeOpacity="0.25"
                strokeWidth="0.6"
              />
              <circle cx={cx} cy={cy - 2} r="3" fill={EMERALD} />
              <path
                d={`M ${cx - 4} ${cy + 5} Q ${cx} ${cy} ${cx + 4} ${cy + 5}`}
                stroke={EMERALD}
                strokeWidth="1.8"
                strokeLinecap="round"
                fill="none"
              />
            </g>
          );
        })}
      </g>

      {/* ─── Right node: shield (commitment) ─── */}
      <g transform="translate(188 118)">
        <path
          d="M -18 -22 L 18 -22 L 18 4 Q 18 20 0 30 Q -18 20 -18 4 Z"
          fill="url(#pillars-shield)"
          stroke={EMERALD}
          strokeWidth="1.4"
          strokeLinejoin="round"
        />
        <path
          d="M -8 2 L -2 8 L 10 -6"
          fill="none"
          stroke={GOLD}
          strokeWidth="2.2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </g>

      {/* subtle floating accents */}
      <circle cx="90" cy="60" r="1.6" fill={GOLD} opacity="0.55" />
      <circle cx="150" cy="138" r="1.4" fill={EMERALD} opacity="0.50" />
      <circle cx="170" cy="48" r="1.2" fill={GOLD} opacity="0.55" />
      <circle cx="74" cy="150" r="1.2" fill={EMERALD} opacity="0.40" />
    </svg>
  );
}
