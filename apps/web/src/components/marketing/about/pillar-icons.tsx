"use client";

/**
 * Static, calm pillar icons for the About page.
 *
 * Earlier versions had radiating rings, orbiting figures, and looping
 * draw-ins — too busy. These are still bespoke (not stock lucide icons),
 * still in the brand palette, but they don't move on their own. The
 * `active` prop is accepted for API compatibility with the parent grid
 * but isn't used.
 */

const EMERALD = "hsl(160 65% 22%)";
const EMERALD_SOFT = "hsl(160 60% 35%)";
const GOLD = "hsl(36 60% 50%)";
const GOLD_SOFT = "hsl(36 70% 65%)";

type IconProps = { active?: boolean };

/* 1. Mission — concentric rings + crosshair (static) */
export function MissionIcon(_: IconProps) {
  return (
    <svg viewBox="0 0 96 96" className="h-full w-full" aria-hidden>
      <defs>
        <radialGradient id="mission-glow" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor={GOLD_SOFT} stopOpacity="0.35" />
          <stop offset="100%" stopColor={GOLD} stopOpacity="0" />
        </radialGradient>
      </defs>
      <circle cx="48" cy="48" r="22" fill="url(#mission-glow)" />
      <circle cx="48" cy="48" r="22" fill="none" stroke={GOLD} strokeOpacity="0.35" strokeWidth="1" />
      <circle cx="48" cy="48" r="14" fill="none" stroke={GOLD} strokeOpacity="0.55" strokeWidth="1" />
      <g stroke={EMERALD} strokeWidth="1.5" strokeLinecap="round">
        <line x1="48" y1="14" x2="48" y2="24" />
        <line x1="48" y1="72" x2="48" y2="82" />
        <line x1="14" y1="48" x2="24" y2="48" />
        <line x1="72" y1="48" x2="82" y2="48" />
      </g>
      <circle cx="48" cy="48" r="8" fill="none" stroke={EMERALD} strokeWidth="1.8" />
      <circle cx="48" cy="48" r="3.5" fill={EMERALD} />
    </svg>
  );
}

/* 2. Team — three figures connected to a center node (static) */
export function TeamIcon(_: IconProps) {
  const figures = [0, 120, 240];
  return (
    <svg viewBox="0 0 96 96" className="h-full w-full" aria-hidden>
      <defs>
        <radialGradient id="team-center" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor={GOLD} stopOpacity="0.40" />
          <stop offset="100%" stopColor={GOLD} stopOpacity="0" />
        </radialGradient>
      </defs>
      <circle cx="48" cy="48" r="28" fill="none" stroke={EMERALD} strokeOpacity="0.16" strokeWidth="1" strokeDasharray="2 4" />
      <circle cx="48" cy="48" r="14" fill="url(#team-center)" />
      {figures.map((angle) => {
        const rad = (angle * Math.PI) / 180;
        const cx = 48 + Math.cos(rad) * 28;
        const cy = 48 + Math.sin(rad) * 28;
        return (
          <g key={angle}>
            <line x1={cx} y1={cy} x2="48" y2="48" stroke={GOLD} strokeOpacity="0.22" strokeWidth="1" />
            <circle cx={cx} cy={cy - 4} r="3" fill={EMERALD} />
            <path d={`M ${cx - 5} ${cy + 6} Q ${cx} ${cy - 1} ${cx + 5} ${cy + 6}`} fill="none" stroke={EMERALD} strokeWidth="2" strokeLinecap="round" />
          </g>
        );
      })}
      <circle cx="48" cy="48" r="5" fill={GOLD} />
    </svg>
  );
}

/* 3. Commitment — shield with a static check (no draw-in loop) */
export function CommitmentIcon(_: IconProps) {
  return (
    <svg viewBox="0 0 96 96" className="h-full w-full" aria-hidden>
      <defs>
        <linearGradient id="shield-fill" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor={EMERALD_SOFT} stopOpacity="0.18" />
          <stop offset="100%" stopColor={EMERALD} stopOpacity="0.30" />
        </linearGradient>
        <radialGradient id="shield-glow" cx="50%" cy="40%" r="60%">
          <stop offset="0%" stopColor={GOLD_SOFT} stopOpacity="0.25" />
          <stop offset="100%" stopColor={GOLD} stopOpacity="0" />
        </radialGradient>
      </defs>
      <circle cx="48" cy="44" r="34" fill="url(#shield-glow)" />
      <path
        d="M48 12 L74 22 L74 50 Q74 70 48 84 Q22 70 22 50 L22 22 Z"
        fill="url(#shield-fill)"
        stroke={EMERALD}
        strokeWidth="2"
        strokeLinejoin="round"
      />
      <path
        d="M34 50 L44 60 L62 38"
        fill="none"
        stroke={GOLD}
        strokeWidth="3"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export const PILLAR_ICON_BY_KEY = {
  mission: MissionIcon,
  team: TeamIcon,
  commitment: CommitmentIcon,
} as const;

export type PillarIconKey = keyof typeof PILLAR_ICON_BY_KEY;
