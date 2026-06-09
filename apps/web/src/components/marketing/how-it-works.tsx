"use client";

/**
 * "How it works" — three-step onboarding flow with premium chrome.
 *
 *   ┌──────────────────────────────────────────────────────────┐
 *   │   KICKER · GET STARTED IN MINUTES                         │
 *   │   Three steps to your firm's private legal AI             │
 *   │                                                           │
 *   │  ┌────────┐ ─ ─ ─ ─ ┌────────┐ ─ ─ ─ ─ ┌────────┐         │
 *   │  │ 01 ⚫   │         │ 02 ⚫   │         │ 03 ⚫   │         │
 *   │  │ [icon] │         │ [icon] │         │ [icon] │         │
 *   │  │ Title  │         │ Title  │         │ Title  │         │
 *   │  │ Body…  │         │ Body…  │         │ Body…  │         │
 *   │  │ chip   │         │ chip   │         │ chip   │         │
 *   │  └────────┘         └────────┘         └────────┘         │
 *   └──────────────────────────────────────────────────────────┘
 *
 *   • Cards stagger-fade upward on scroll-into-view.
 *   • A dashed connector runs behind the cards; a gold pulse travels
 *     left-to-right (LTR) / right-to-left (RTL) along the connector.
 *   • Icon stages tilt subtly on hover, number badge brightens, card
 *     border softens to accent gold.
 *   • Honors `prefers-reduced-motion`.
 */
import { motion, useReducedMotion } from "framer-motion";
import {
  Building2,
  Clock,
  FolderUp,
  Sparkles,
  type LucideIcon,
} from "lucide-react";

import { cn } from "@/lib/utils";

export type HowItWorksStep = {
  id: "1" | "2" | "3";
  title: string;
  body: string;
  meta: string;
};

export type HowItWorksStrings = {
  kicker: string;
  title: string;
  subtitle: string;
  steps: HowItWorksStep[];
};

const ICONS: Record<HowItWorksStep["id"], LucideIcon> = {
  "1": Building2,
  "2": FolderUp,
  "3": Sparkles,
};

export function HowItWorks({
  strings,
  locale,
}: {
  strings: HowItWorksStrings;
  locale: string;
}) {
  const reduceMotion = useReducedMotion();
  const isRtl = locale === "ar";

  return (
    <section className="relative">
      {/* Faint emerald separator strokes top + bottom, like the original */}
      <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-primary/15 to-transparent" />
      <div className="absolute inset-x-0 bottom-0 h-px bg-gradient-to-r from-transparent via-primary/15 to-transparent" />

      <div className="container py-20 md:py-24">
        {/* Header */}
        <div className="text-center mb-14 md:mb-16 space-y-3 max-w-2xl mx-auto">
          <div className="text-xs font-semibold uppercase tracking-[0.18em] text-accent">
            {strings.kicker}
          </div>
          <h2 className="text-3xl md:text-4xl font-bold tracking-tight">
            {strings.title}
          </h2>
          <div className="mx-auto gold-rule" />
          <p className="text-base text-muted-foreground">{strings.subtitle}</p>
        </div>

        {/* Stepper */}
        <div className="relative max-w-5xl mx-auto">
          {/* Decorative dashed connector behind the cards (desktop only) */}
          <ConnectorTrack reduceMotion={!!reduceMotion} isRtl={isRtl} />

          <div className="relative grid grid-cols-1 md:grid-cols-3 gap-6 md:gap-8">
            {strings.steps.map((step, i) => (
              <StepCard
                key={step.id}
                step={step}
                index={i}
                reduceMotion={!!reduceMotion}
              />
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

/* -------------------------------------------------------------------------- */

function ConnectorTrack({
  reduceMotion,
  isRtl,
}: {
  reduceMotion: boolean;
  isRtl: boolean;
}) {
  return (
    <div
      aria-hidden
      className="pointer-events-none absolute inset-x-12 top-[68px] hidden md:block"
    >
      {/* Dashed track */}
      <svg
        className="h-px w-full overflow-visible"
        viewBox="0 0 1000 1"
        preserveAspectRatio="none"
      >
        <line
          x1="0"
          y1="0.5"
          x2="1000"
          y2="0.5"
          stroke="hsl(36 60% 50%)"
          strokeOpacity="0.35"
          strokeWidth="1"
          strokeDasharray="6 6"
        />
      </svg>

      {/* Travelling gold pulse */}
      {!reduceMotion && (
        <motion.div
          className="absolute -top-[3px] h-1.5 w-1.5 rounded-full bg-accent shadow-[0_0_12px_2px_hsl(36_70%_60%/0.7)]"
          initial={{ left: isRtl ? "100%" : "0%" }}
          animate={{ left: isRtl ? ["100%", "0%"] : ["0%", "100%"] }}
          transition={{
            duration: 4.5,
            repeat: Infinity,
            ease: "easeInOut",
            repeatDelay: 0.8,
          }}
        />
      )}
    </div>
  );
}

/* -------------------------------------------------------------------------- */

function StepCard({
  step,
  index,
  reduceMotion,
}: {
  step: HowItWorksStep;
  index: number;
  reduceMotion: boolean;
}) {
  const Icon = ICONS[step.id];

  return (
    <motion.div
      initial={reduceMotion ? false : { opacity: 0, y: 24 }}
      whileInView={reduceMotion ? undefined : { opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-60px" }}
      transition={{
        duration: 0.65,
        delay: index * 0.12,
        ease: [0.16, 1, 0.3, 1],
      }}
      whileHover={reduceMotion ? undefined : { y: -4 }}
      className={cn(
        "group relative rounded-2xl border bg-card p-6 md:p-7",
        "border-border/60",
        "shadow-[0_18px_48px_-30px_hsl(160_65%_18%/0.3)]",
        "transition-[box-shadow,border-color] duration-500 ease-out",
        "hover:border-accent/40 hover:shadow-[0_22px_60px_-30px_hsl(160_65%_18%/0.45)]",
      )}
    >
      {/* Ambient soft gradient on the card */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 rounded-2xl opacity-60"
        style={{
          backgroundImage:
            "radial-gradient(110% 70% at 100% 100%, hsl(160 65% 22% / 0.05), transparent 55%)," +
            "radial-gradient(110% 70% at 0% 0%, hsl(36 60% 50% / 0.05), transparent 55%)",
        }}
      />

      {/* Number badge — sits over the connector dot on the track */}
      <div className="relative mb-5 flex items-center justify-between">
        <div className="flex items-center gap-3">
          {/* Big circled number — replaces the connector node visually */}
          <div className="relative">
            <span className="absolute inset-0 rounded-full bg-primary/15 blur-md transition-opacity duration-500 group-hover:bg-accent/25" />
            <span
              className={cn(
                "relative grid h-11 w-11 place-items-center rounded-full",
                "bg-primary text-primary-foreground",
                "text-[13px] font-bold",
                "ring-4 ring-card",
                "transition-all duration-500",
                "group-hover:ring-accent/30 group-hover:bg-primary/90",
              )}
            >
              0{step.id}
            </span>
          </div>
        </div>

        {/* Meta chip — duration / status */}
        <div className="inline-flex items-center gap-1 rounded-full border border-accent/30 bg-accent/8 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-accent">
          <Clock className="h-3 w-3" />
          <span>{step.meta}</span>
        </div>
      </div>

      {/* Icon stage */}
      <div
        className={cn(
          "relative mb-4 inline-flex h-12 w-12 items-center justify-center rounded-xl",
          "bg-gradient-to-br from-primary/[0.10] to-accent/[0.10]",
          "ring-1 ring-inset ring-border/60",
          "transition-all duration-500 group-hover:ring-accent/30",
        )}
      >
        <motion.div
          aria-hidden
          initial={false}
          whileHover={reduceMotion ? undefined : { rotate: -8, scale: 1.05 }}
          transition={{ type: "spring", stiffness: 320, damping: 18 }}
          className="text-primary group-hover:text-accent transition-colors duration-500"
        >
          <Icon className="h-6 w-6" />
        </motion.div>
      </div>

      {/* Title + body */}
      <h3 className="relative text-lg md:text-xl font-bold leading-tight tracking-tight text-foreground transition-colors duration-300 group-hover:text-accent">
        {step.title}
      </h3>
      <p className="relative mt-2.5 text-[0.95rem] leading-relaxed text-muted-foreground">
        {step.body}
      </p>

      {/* Growing gold underline (hover invitation) */}
      <motion.div
        aria-hidden
        className="relative mt-5 h-px origin-start bg-gradient-to-r from-accent/70 to-accent/0"
        initial={false}
        whileHover={reduceMotion ? undefined : { scaleX: 1 }}
        animate={{ scaleX: 0.18 }}
        whileInView={reduceMotion ? undefined : { scaleX: 0.18 }}
        transition={{ duration: 0.45 }}
        style={{ transformOrigin: "left" }}
      />
    </motion.div>
  );
}
