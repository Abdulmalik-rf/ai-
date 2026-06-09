"use client";

/**
 * Bilingual & Saudi-grounded callout. A premium dark panel (matching the
 * homepage mockup vocabulary) with two animated "AR ↔ EN" tokens
 * crossfading on a loop, plus a horizontal scrolling row of statute
 * chips representing the Saudi statutes Mostashari is grounded in.
 */
import { motion, useReducedMotion } from "framer-motion";
import * as React from "react";

const EMERALD = "hsl(160 65% 22%)";
const GOLD = "hsl(36 60% 50%)";

export function Bilingual({
  kicker,
  title,
  body,
  chips,
}: {
  kicker: string;
  title: string;
  body: string;
  chips: string[];
}) {
  const reduceMotion = useReducedMotion();

  return (
    <section className="container py-20 md:py-24">
      <motion.div
        initial={reduceMotion ? false : { opacity: 0, y: 28 }}
        whileInView={reduceMotion ? undefined : { opacity: 1, y: 0 }}
        viewport={{ once: true, margin: "-60px" }}
        transition={{ duration: 0.75, ease: [0.16, 1, 0.3, 1] }}
        className="relative max-w-6xl mx-auto overflow-hidden rounded-3xl border border-white/[0.08] shadow-[0_30px_80px_-30px_hsl(160_65%_15%/0.5)]"
        style={{
          background:
            "linear-gradient(150deg, hsl(165 30% 9%) 0%, hsl(165 28% 11%) 100%)",
        }}
      >
        {/* faint dot grid */}
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 opacity-[0.07]"
          style={{
            backgroundImage:
              "radial-gradient(circle at 1px 1px, white 1px, transparent 0)",
            backgroundSize: "14px 14px",
          }}
        />
        {/* gold corner glow */}
        <div
          aria-hidden
          className="pointer-events-none absolute -top-20 -end-20 h-64 w-64 rounded-full opacity-30"
          style={{
            background:
              "radial-gradient(closest-side, hsl(36 70% 60% / 0.6), transparent 70%)",
          }}
        />

        <div className="relative grid items-center gap-8 md:gap-10 p-6 md:p-10 md:grid-cols-2">
          {/* Animated bilingual token */}
          <div className="order-2 md:order-1 relative h-56 md:h-64">
            <BilingualToken reduceMotion={!!reduceMotion} />
          </div>

          {/* Copy */}
          <div className="order-1 md:order-2 relative text-white">
            <div className="text-[11px] font-semibold uppercase tracking-[0.22em] text-amber-300 mb-3">
              {kicker}
            </div>
            <h2 className="text-2xl md:text-3xl font-bold leading-tight tracking-tight">
              {title}
            </h2>
            <p className="mt-4 text-[0.95rem] md:text-base leading-relaxed text-white/70">
              {body}
            </p>

            {/* Horizontal chip marquee */}
            <div className="mt-6 relative overflow-hidden">
              <div
                aria-hidden
                className="pointer-events-none absolute inset-y-0 start-0 w-12 z-10"
                style={{
                  background:
                    "linear-gradient(to right, hsl(165 30% 9%), transparent)",
                }}
              />
              <div
                aria-hidden
                className="pointer-events-none absolute inset-y-0 end-0 w-12 z-10"
                style={{
                  background:
                    "linear-gradient(to left, hsl(165 30% 9%), transparent)",
                }}
              />
              <motion.div
                className="flex gap-2 whitespace-nowrap"
                animate={
                  reduceMotion
                    ? undefined
                    : { x: ["0%", "-50%"] }
                }
                transition={{
                  duration: 32,
                  repeat: Infinity,
                  ease: "linear",
                }}
              >
                {[...chips, ...chips].map((chip, i) => (
                  <span
                    key={`${chip}-${i}`}
                    className="inline-flex items-center rounded-full border border-white/15 bg-white/[0.04] px-3 py-1 text-xs font-medium text-white/85"
                  >
                    {chip}
                  </span>
                ))}
              </motion.div>
            </div>
          </div>
        </div>
      </motion.div>
    </section>
  );
}

/* ────────────────────────────────────────────────────────────────────────── */
/* Animated AR ↔ EN token — two stacked language pills swap via crossfade.   */
function BilingualToken({ reduceMotion }: { reduceMotion: boolean }) {
  const [side, setSide] = React.useState(0);
  React.useEffect(() => {
    if (reduceMotion) return;
    const id = setInterval(() => setSide((s) => 1 - s), 2400);
    return () => clearInterval(id);
  }, [reduceMotion]);

  return (
    <div className="relative h-full w-full">
      <svg
        viewBox="0 0 320 240"
        className="absolute inset-0 h-full w-full"
        aria-hidden
      >
        <defs>
          <radialGradient id="bl-glow" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor={GOLD} stopOpacity="0.32" />
            <stop offset="100%" stopColor={GOLD} stopOpacity="0" />
          </radialGradient>
        </defs>
        <circle cx="160" cy="120" r="100" fill="url(#bl-glow)" />

        {/* Connection arrow loop AR ↔ EN */}
        <motion.path
          d="M 88 120 Q 160 60 232 120"
          fill="none"
          stroke={GOLD}
          strokeOpacity="0.4"
          strokeWidth="0.8"
          strokeDasharray="3 4"
          animate={reduceMotion ? undefined : { strokeDashoffset: [0, -14] }}
          transition={{ duration: 1.6, repeat: Infinity, ease: "linear" }}
        />
        <motion.path
          d="M 88 120 Q 160 180 232 120"
          fill="none"
          stroke={EMERALD}
          strokeOpacity="0.55"
          strokeWidth="0.8"
          strokeDasharray="3 4"
          animate={reduceMotion ? undefined : { strokeDashoffset: [0, 14] }}
          transition={{ duration: 1.6, repeat: Infinity, ease: "linear" }}
        />

        {/* Travelling pulses */}
        <motion.circle
          r="2.4"
          fill={GOLD}
          animate={
            reduceMotion
              ? undefined
              : {
                  opacity: [0, 1, 0],
                  offsetDistance: ["0%", "100%"],
                }
          }
          transition={{
            duration: 2.4,
            repeat: Infinity,
            ease: "easeInOut",
          }}
          style={{
            offsetPath: 'path("M 88 120 Q 160 60 232 120")',
          }}
        />
        <motion.circle
          r="2.4"
          fill={EMERALD}
          animate={
            reduceMotion
              ? undefined
              : {
                  opacity: [0, 1, 0],
                  offsetDistance: ["100%", "0%"],
                }
          }
          transition={{
            duration: 2.4,
            repeat: Infinity,
            ease: "easeInOut",
            delay: 1.2,
          }}
          style={{
            offsetPath: 'path("M 88 120 Q 160 180 232 120")',
          }}
        />
      </svg>

      {/* Left pill — Arabic */}
      <motion.div
        className="absolute top-1/2 start-0 -translate-y-1/2 rtl:start-auto rtl:end-0"
        animate={{
          scale: side === 0 ? 1.05 : 0.95,
          opacity: side === 0 ? 1 : 0.55,
        }}
        transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
      >
        <div
          className={
            side === 0
              ? "grid place-items-center h-20 w-20 rounded-2xl bg-amber-500/85 text-emerald-950 shadow-[0_18px_40px_-12px_hsl(36_70%_50%/0.5)] ring-2 ring-amber-300/40"
              : "grid place-items-center h-20 w-20 rounded-2xl bg-white/[0.05] text-white/65 ring-1 ring-white/15"
          }
        >
          <div className="text-center">
            <div className="text-2xl font-bold">AR</div>
            <div className="mt-0.5 text-[9px] uppercase tracking-widest opacity-80">
              عربي
            </div>
          </div>
        </div>
      </motion.div>

      {/* Right pill — English */}
      <motion.div
        className="absolute top-1/2 end-0 -translate-y-1/2 rtl:end-auto rtl:start-0"
        animate={{
          scale: side === 1 ? 1.05 : 0.95,
          opacity: side === 1 ? 1 : 0.55,
        }}
        transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
      >
        <div
          className={
            side === 1
              ? "grid place-items-center h-20 w-20 rounded-2xl bg-emerald-500/85 text-white shadow-[0_18px_40px_-12px_hsl(160_65%_18%/0.6)] ring-2 ring-emerald-300/30"
              : "grid place-items-center h-20 w-20 rounded-2xl bg-white/[0.05] text-white/65 ring-1 ring-white/15"
          }
        >
          <div className="text-center">
            <div className="text-2xl font-bold">EN</div>
            <div className="mt-0.5 text-[9px] uppercase tracking-widest opacity-80">
              English
            </div>
          </div>
        </div>
      </motion.div>
    </div>
  );
}
