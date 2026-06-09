"use client";

/**
 * Flow timeline — "How a matter flows from a client's first message to a
 * signed PDF." A horizontal four-step timeline. A gold pulse travels
 * along the connecting rail, lighting up each step in sequence on a
 * continuous loop. Each step has its own icon and an animated indicator
 * that activates when the pulse passes through it.
 */
import { motion, useReducedMotion } from "framer-motion";
import {
  CheckCircle2,
  FileCheck2,
  MessageCircle,
  Sparkles,
} from "lucide-react";
import * as React from "react";

const EMERALD = "hsl(160 65% 22%)";
const GOLD = "hsl(36 60% 50%)";

export type FlowStep = { title: string; body: string };

const STEP_ICONS = [MessageCircle, Sparkles, FileCheck2, CheckCircle2];

export function FlowTimeline({
  kicker,
  title,
  subtitle,
  steps,
}: {
  kicker: string;
  title: string;
  subtitle: string;
  steps: FlowStep[];
}) {
  const reduceMotion = useReducedMotion();
  // Active step cycles every 1.6 s.
  const [active, setActive] = React.useState(0);

  React.useEffect(() => {
    if (reduceMotion) return;
    const id = setInterval(() => {
      setActive((a) => (a + 1) % steps.length);
    }, 1600);
    return () => clearInterval(id);
  }, [reduceMotion, steps.length]);

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

      <motion.div
        initial={reduceMotion ? false : { opacity: 0, y: 24 }}
        whileInView={reduceMotion ? undefined : { opacity: 1, y: 0 }}
        viewport={{ once: true, margin: "-60px" }}
        transition={{ duration: 0.75, ease: [0.16, 1, 0.3, 1] }}
        className="relative max-w-6xl mx-auto rounded-3xl border border-border/60 bg-card p-6 md:p-10 shadow-[0_18px_60px_-30px_hsl(160_65%_18%/0.32)]"
      >
        {/* Ambient surface gradient */}
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 rounded-3xl opacity-70"
          style={{
            backgroundImage:
              "radial-gradient(140% 90% at 100% 100%, hsl(160 65% 22% / 0.06), transparent 55%)," +
              "radial-gradient(140% 90% at 0% 0%, hsl(36 60% 50% / 0.05), transparent 55%)",
          }}
        />

        <div className="relative">
          {/* Horizontal rail (desktop) */}
          <div className="hidden md:block">
            <FlowRail active={active} total={steps.length} reduceMotion={!!reduceMotion} />
            <div className="mt-8 grid grid-cols-4 gap-6">
              {steps.map((step, i) => (
                <FlowCard
                  key={i}
                  step={step}
                  index={i}
                  active={i === active}
                  done={i < active}
                />
              ))}
            </div>
          </div>

          {/* Stacked layout (mobile) */}
          <div className="md:hidden space-y-4">
            {steps.map((step, i) => (
              <div key={i} className="flex gap-4">
                <FlowDot index={i} active={i === active} done={i < active} />
                <div className="flex-1">
                  <h3 className="text-base font-semibold leading-tight text-foreground">
                    {step.title}
                  </h3>
                  <p className="mt-1.5 text-sm text-muted-foreground leading-relaxed">
                    {step.body}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </motion.div>
    </section>
  );
}

/* ─────────────────────────────────────────────────────────────────────── */

function FlowRail({
  active,
  total,
  reduceMotion,
}: {
  active: number;
  total: number;
  reduceMotion: boolean;
}) {
  // The rail itself: dotted emerald line + a moving gold "head" that
  // tracks the active step.
  const positions = Array.from(
    { length: total },
    (_, i) => `${(i / (total - 1)) * 100}%`,
  );

  return (
    <div className="relative h-14">
      {/* Dotted rail */}
      <div
        aria-hidden
        className="absolute inset-x-6 top-1/2 -translate-y-1/2 h-px"
        style={{
          backgroundImage:
            "linear-gradient(90deg, hsl(160 65% 22% / 0.30) 0 6px, transparent 6px 14px)",
          backgroundSize: "14px 1px",
        }}
      />

      {/* Gold "fill" rail that grows up to the active step */}
      <motion.div
        aria-hidden
        className="absolute start-6 top-1/2 -translate-y-1/2 h-[2px] rounded-full"
        style={{
          backgroundImage:
            "linear-gradient(90deg, hsl(160 65% 22%), hsl(36 60% 50%))",
          width: `calc(${(active / (total - 1)) * 100}% - 24px * ${active / (total - 1) * 0})`,
        }}
        animate={{
          width: `${(active / (total - 1)) * 96}%`,
        }}
        transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
      />

      {/* Step dots */}
      {positions.map((left, i) => {
        const isActive = i === active;
        const isDone = i < active;
        return (
          <div
            key={i}
            className="absolute top-1/2 -translate-x-1/2 -translate-y-1/2 rtl:translate-x-1/2"
            style={{ left }}
          >
            <FlowDot index={i} active={isActive} done={isDone} />
          </div>
        );
      })}

      {/* Moving gold pulse riding the rail */}
      {!reduceMotion && (
        <motion.div
          aria-hidden
          className="absolute top-1/2 -translate-x-1/2 -translate-y-1/2 rtl:translate-x-1/2 h-3 w-3 rounded-full"
          style={{
            background:
              "radial-gradient(closest-side, hsl(36 70% 60%), transparent 70%)",
          }}
          animate={{
            left: positions[active],
          }}
          transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
        />
      )}
    </div>
  );
}

function FlowDot({
  index,
  active,
  done,
}: {
  index: number;
  active: boolean;
  done: boolean;
}) {
  const Icon = STEP_ICONS[index] ?? CheckCircle2;
  const filled = active || done;
  return (
    <div className="relative grid place-items-center">
      {active && (
        <motion.span
          aria-hidden
          className="absolute h-10 w-10 rounded-full"
          style={{
            background:
              "radial-gradient(closest-side, hsl(36 70% 60% / 0.30), transparent 70%)",
          }}
          animate={{ scale: [0.9, 1.15, 0.9], opacity: [0.6, 1, 0.6] }}
          transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
        />
      )}
      <span
        className={
          filled
            ? "relative inline-grid h-9 w-9 place-items-center rounded-full bg-primary text-primary-foreground shadow-[0_8px_24px_-8px_hsl(160_65%_18%/0.6)] ring-2 ring-accent/30"
            : "relative inline-grid h-9 w-9 place-items-center rounded-full bg-muted text-muted-foreground ring-1 ring-border/70"
        }
      >
        <Icon className="h-4 w-4" strokeWidth={2.4} />
      </span>
    </div>
  );
}

function FlowCard({
  step,
  index,
  active,
  done,
}: {
  step: FlowStep;
  index: number;
  active: boolean;
  done: boolean;
}) {
  return (
    <div
      className={
        active
          ? "relative rounded-2xl border border-accent/35 bg-accent/5 p-5 transition-all duration-500"
          : done
          ? "relative rounded-2xl border border-primary/20 bg-primary/[0.03] p-5 transition-all duration-500"
          : "relative rounded-2xl border border-border/60 bg-card p-5 transition-all duration-500"
      }
    >
      <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-accent mb-2">
        0{index + 1}
      </div>
      <h3 className="text-base md:text-lg font-semibold leading-tight text-foreground">
        {step.title}
      </h3>
      <p className="mt-2 text-sm text-muted-foreground leading-relaxed">
        {step.body}
      </p>
    </div>
  );
}
