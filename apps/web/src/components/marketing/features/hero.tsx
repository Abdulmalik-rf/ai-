"use client";

/**
 * Features-page hero — premium, animated.
 *
 * Visual: ambient emerald/gold radial washes (matching About-page hero),
 * three subtle orbital arcs in the background that rotate slowly, and
 * a continuously firing "synapse" — small gold pulses travelling along
 * faint emerald connection lines behind the title. Static typography
 * stays the focal point.
 */
import { motion, useReducedMotion } from "framer-motion";

import { BrandLogo } from "@/components/brand-logo";

const EMERALD = "hsl(160 65% 22%)";
const GOLD = "hsl(36 60% 50%)";

type Props = {
  locale: string;
  kicker: string;
  title: string;
  subtitle: string;
};

export function FeaturesHero({ locale, kicker, title, subtitle }: Props) {
  const reduceMotion = useReducedMotion();

  return (
    <section className="relative isolate overflow-hidden">
      {/* Ambient gradient — identical vocabulary to the About hero */}
      <div
        aria-hidden
        className="absolute inset-0"
        style={{
          background:
            "radial-gradient(ellipse 80% 60% at 50% 0%, hsl(160 65% 22% / 0.10), transparent 70%)," +
            "radial-gradient(ellipse 60% 50% at 100% 100%, hsl(36 60% 50% / 0.06), transparent 65%)," +
            "radial-gradient(ellipse 60% 50% at 0% 100%, hsl(160 60% 35% / 0.04), transparent 65%)",
        }}
      />

      {/* Animated background — orbital arcs + synapse pulses */}
      <div className="pointer-events-none absolute inset-0">
        <SynapseField reduceMotion={!!reduceMotion} />
      </div>

      <div className="container relative z-10 py-24 md:py-32">
        <div className="max-w-3xl mx-auto text-center space-y-6">
          <motion.div
            initial={reduceMotion ? false : { opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
            className="flex justify-center"
          >
            <BrandLogo size={84} locale={locale} />
          </motion.div>

          <motion.div
            initial={reduceMotion ? false : { opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{
              duration: 0.7,
              delay: 0.08,
              ease: [0.16, 1, 0.3, 1],
            }}
            className="flex justify-center"
          >
            <span className="inline-flex items-center gap-2 rounded-full border border-accent/40 bg-accent/5 text-accent text-xs font-semibold uppercase tracking-[0.2em] px-3 py-1">
              <span className="relative flex h-1.5 w-1.5">
                <span className="absolute inset-0 animate-ping rounded-full bg-accent opacity-60" />
                <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-accent" />
              </span>
              {kicker}
            </span>
          </motion.div>

          <motion.h1
            initial={reduceMotion ? false : { opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{
              duration: 0.8,
              delay: 0.16,
              ease: [0.16, 1, 0.3, 1],
            }}
            className="text-4xl md:text-6xl font-bold tracking-tight leading-tight text-foreground"
          >
            {title}
          </motion.h1>

          <div
            className="mx-auto h-[2px] w-16 rounded-full"
            style={{
              backgroundImage:
                "linear-gradient(90deg, transparent, hsl(36 60% 50%), transparent)",
            }}
          />

          <motion.p
            initial={reduceMotion ? false : { opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{
              duration: 0.7,
              delay: 0.24,
              ease: [0.16, 1, 0.3, 1],
            }}
            className="text-lg md:text-xl text-muted-foreground leading-relaxed max-w-2xl mx-auto"
          >
            {subtitle}
          </motion.p>
        </div>
      </div>

      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 bottom-0 h-16"
        style={{
          background:
            "linear-gradient(to bottom, transparent, hsl(var(--background)))",
        }}
      />
    </section>
  );
}

/**
 * Synapse field — three slowly-rotating orbital arcs plus four small
 * gold pulses travelling along faint emerald paths. All animations are
 * very low-amplitude so they never compete with the title.
 */
function SynapseField({ reduceMotion }: { reduceMotion: boolean }) {
  return (
    <svg
      viewBox="0 0 1440 720"
      preserveAspectRatio="xMidYMid slice"
      className="absolute inset-0 h-full w-full opacity-[0.55]"
      aria-hidden
    >
      <defs>
        <radialGradient id="hero-glow-center" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor={GOLD} stopOpacity="0.10" />
          <stop offset="100%" stopColor={GOLD} stopOpacity="0" />
        </radialGradient>
        <pattern
          id="hero-dots"
          x="0"
          y="0"
          width="36"
          height="36"
          patternUnits="userSpaceOnUse"
        >
          <circle cx="1" cy="1" r="0.9" fill={EMERALD} fillOpacity="0.18" />
        </pattern>
      </defs>

      <rect x="0" y="0" width="1440" height="720" fill="url(#hero-dots)" />
      <circle cx="720" cy="320" r="280" fill="url(#hero-glow-center)" />

      {/* Three slow orbital rings */}
      {[
        { r: 180, dur: 60, dir: 1 },
        { r: 280, dur: 90, dir: -1 },
        { r: 380, dur: 120, dir: 1 },
      ].map((ring, i) => (
        <motion.g
          key={i}
          style={{ transformOrigin: "720px 320px" }}
          animate={
            reduceMotion
              ? undefined
              : { rotate: ring.dir > 0 ? 360 : -360 }
          }
          transition={{ duration: ring.dur, repeat: Infinity, ease: "linear" }}
        >
          <circle
            cx="720"
            cy="320"
            r={ring.r}
            fill="none"
            stroke={EMERALD}
            strokeOpacity={0.14 - i * 0.025}
            strokeWidth="0.6"
            strokeDasharray="2 7"
          />
          {/* a single bright gold node travelling on the ring */}
          <circle
            cx={720 + ring.r}
            cy="320"
            r={i === 0 ? 2.4 : 1.6}
            fill={GOLD}
            opacity={0.65 - i * 0.12}
          />
        </motion.g>
      ))}

      {/* Connection paths */}
      <g stroke={EMERALD} strokeOpacity="0.18" strokeWidth="0.6" fill="none">
        <path d="M 220 540 Q 520 300 720 320" strokeDasharray="2 6" />
        <path d="M 1220 540 Q 920 300 720 320" strokeDasharray="2 6" />
        <path d="M 220 120 Q 480 240 720 320" strokeDasharray="2 6" />
        <path d="M 1220 120 Q 960 240 720 320" strokeDasharray="2 6" />
      </g>

      {/* Gold pulses travelling along the paths */}
      {[
        { path: "M 220 540 Q 520 300 720 320", delay: 0 },
        { path: "M 1220 540 Q 920 300 720 320", delay: 1.4 },
        { path: "M 220 120 Q 480 240 720 320", delay: 2.8 },
        { path: "M 1220 120 Q 960 240 720 320", delay: 4.2 },
      ].map((p, i) => (
        <motion.circle
          key={i}
          r="2.4"
          fill={GOLD}
          opacity="0"
          animate={
            reduceMotion
              ? undefined
              : {
                  opacity: [0, 1, 0],
                  offsetDistance: ["0%", "100%"],
                }
          }
          transition={{
            duration: 5.6,
            delay: p.delay,
            repeat: Infinity,
            ease: "easeInOut",
          }}
          style={{
            offsetPath: `path("${p.path}")`,
          }}
        />
      ))}
    </svg>
  );
}
