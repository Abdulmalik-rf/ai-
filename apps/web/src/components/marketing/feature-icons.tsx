"use client";

/**
 * Bespoke animated SVG illustrations for the marketing feature cards.
 *
 * Each icon exposes the same prop surface:
 *   - `active`: the parent card is hovered, so amplify the animation.
 *
 * All icons share a 96×96 viewBox, the brand emerald primary stroke
 * (#0F4C3A) and the warm-gold accent (#B5853C), with `currentColor`
 * fallbacks where appropriate so the icons inherit theme tints.
 *
 * Animations are loop-based and idle on their own; hover boosts amplitude
 * and shortens duration for a "comes alive" feel without ever being
 * distracting. We respect `prefers-reduced-motion` via the parent.
 */
import { motion } from "framer-motion";

const EMERALD = "hsl(160 65% 22%)";
const EMERALD_SOFT = "hsl(160 60% 35%)";
const GOLD = "hsl(36 60% 50%)";
const GOLD_SOFT = "hsl(36 70% 65%)";

type IconProps = { active?: boolean };

/* -------------------------------------------------------------------------- */
/* 1. Grounded legal research — magnifying glass scanning a document with     */
/*    citation pings rising from the page.                                     */
/* -------------------------------------------------------------------------- */
export function ResearchIcon({ active }: IconProps) {
  return (
    <svg viewBox="0 0 96 96" className="h-full w-full" aria-hidden>
      <defs>
        <linearGradient id="rag-doc" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor="white" stopOpacity="0.9" />
          <stop offset="100%" stopColor="white" stopOpacity="0.6" />
        </linearGradient>
        <radialGradient id="rag-lens" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor={GOLD_SOFT} stopOpacity="0.45" />
          <stop offset="70%" stopColor={GOLD} stopOpacity="0.05" />
          <stop offset="100%" stopColor={GOLD} stopOpacity="0" />
        </radialGradient>
      </defs>

      {/* Document */}
      <motion.g
        initial={false}
        animate={{ y: active ? -1 : 0 }}
        transition={{ duration: 0.4, ease: "easeOut" }}
      >
        <rect
          x="14"
          y="16"
          width="54"
          height="64"
          rx="6"
          fill="url(#rag-doc)"
          stroke={EMERALD}
          strokeOpacity="0.35"
          strokeWidth="1.2"
        />
        {/* Page lines — they "fill in" left-to-right on hover */}
        {[28, 36, 44, 52, 60, 68].map((y, i) => (
          <motion.rect
            key={y}
            x="22"
            y={y - 2}
            height="2.6"
            rx="1.3"
            fill={EMERALD}
            fillOpacity={i === 2 ? 0.55 : 0.22}
            initial={false}
            animate={{ width: active ? 38 - (i % 2) * 6 : 26 - (i % 2) * 4 }}
            transition={{ duration: 0.55, delay: i * 0.05, ease: "easeOut" }}
          />
        ))}
        {/* Highlighted citation row */}
        <motion.rect
          x="20"
          y="42"
          width="42"
          height="6"
          rx="2"
          fill={GOLD}
          fillOpacity="0.18"
          initial={false}
          animate={{ opacity: active ? 1 : 0.55 }}
          transition={{ duration: 0.4 }}
        />
      </motion.g>

      {/* Citation pings rising up */}
      {[0, 1, 2].map((i) => (
        <motion.circle
          key={i}
          cx={28 + i * 12}
          cy={20}
          r="1.6"
          fill={GOLD}
          initial={{ opacity: 0, y: 0 }}
          animate={{
            opacity: [0, 0.9, 0],
            y: [0, -10, -18],
          }}
          transition={{
            duration: 2,
            repeat: Infinity,
            delay: i * 0.6,
            ease: "easeOut",
          }}
        />
      ))}

      {/* Magnifying glass — idle drift; on hover, pull in tighter */}
      <motion.g
        initial={false}
        animate={
          active
            ? { x: 0, y: 0, rotate: -4 }
            : { x: [0, 4, 0, -2, 0], y: [0, 2, 4, 2, 0], rotate: [0, 2, 0, -2, 0] }
        }
        transition={
          active
            ? { duration: 0.4, ease: "easeOut" }
            : { duration: 6, repeat: Infinity, ease: "easeInOut" }
        }
        style={{ originX: 0.65, originY: 0.6 }}
      >
        <circle cx="64" cy="58" r="14" fill="url(#rag-lens)" />
        <circle
          cx="64"
          cy="58"
          r="14"
          fill="none"
          stroke={EMERALD}
          strokeWidth="2.5"
        />
        <circle
          cx="64"
          cy="58"
          r="10.5"
          fill="none"
          stroke={GOLD}
          strokeOpacity="0.45"
          strokeWidth="0.8"
        />
        <line
          x1="74"
          y1="69"
          x2="84"
          y2="80"
          stroke={EMERALD}
          strokeWidth="3.2"
          strokeLinecap="round"
        />
      </motion.g>
    </svg>
  );
}

/* -------------------------------------------------------------------------- */
/* 2. Document drafting — fountain pen drawing animated strokes.              */
/* -------------------------------------------------------------------------- */
export function DraftingIcon({ active }: IconProps) {
  return (
    <svg viewBox="0 0 96 96" className="h-full w-full" aria-hidden>
      <defs>
        <linearGradient id="draft-paper" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor="white" stopOpacity="0.95" />
          <stop offset="100%" stopColor="white" stopOpacity="0.55" />
        </linearGradient>
        <linearGradient id="draft-pen" x1="0" x2="1" y1="0" y2="1">
          <stop offset="0%" stopColor={GOLD_SOFT} />
          <stop offset="100%" stopColor={GOLD} />
        </linearGradient>
      </defs>

      {/* Paper */}
      <rect
        x="12"
        y="14"
        width="60"
        height="68"
        rx="6"
        fill="url(#draft-paper)"
        stroke={EMERALD}
        strokeOpacity="0.28"
        strokeWidth="1.2"
      />

      {/* Pre-existing faint guide lines */}
      {[28, 38, 48, 58, 68].map((y) => (
        <line
          key={y}
          x1="20"
          y1={y}
          x2="64"
          y2={y}
          stroke={EMERALD}
          strokeOpacity="0.08"
          strokeWidth="1"
        />
      ))}

      {/* Drawn ink lines that animate length */}
      {[
        { y: 28, w: 36 },
        { y: 38, w: 44 },
        { y: 48, w: 30 },
      ].map((line, i) => (
        <motion.line
          key={line.y}
          x1="20"
          y1={line.y}
          x2={20 + line.w}
          y2={line.y}
          stroke={EMERALD}
          strokeOpacity="0.7"
          strokeWidth="1.8"
          strokeLinecap="round"
          initial={false}
          animate={{ pathLength: active ? 1 : 0.7 }}
          transition={{ duration: 1.1, delay: i * 0.18, ease: "easeOut" }}
          style={{ pathLength: active ? 1 : undefined }}
        />
      ))}

      {/* Active line being written */}
      <motion.line
        x1="20"
        y1="58"
        x2="56"
        y2="58"
        stroke={EMERALD}
        strokeWidth="1.8"
        strokeLinecap="round"
        initial={{ pathLength: 0 }}
        animate={{ pathLength: [0, 1, 1, 0] }}
        transition={{
          duration: active ? 2.4 : 4,
          repeat: Infinity,
          times: [0, 0.5, 0.7, 1],
          ease: "easeInOut",
        }}
      />

      {/* Fountain pen — moves along the active line */}
      <motion.g
        animate={{
          x: active ? [0, 36, 36, 0] : [0, 36, 36, 0],
          y: 0,
        }}
        transition={{
          duration: active ? 2.4 : 4,
          repeat: Infinity,
          times: [0, 0.5, 0.7, 1],
          ease: "easeInOut",
        }}
      >
        {/* Barrel */}
        <rect
          x="46"
          y="32"
          width="34"
          height="9"
          rx="2"
          fill="url(#draft-pen)"
          transform="rotate(35 56 56)"
        />
        {/* Nib */}
        <polygon
          points="20,57 26,52 26,62"
          fill={EMERALD}
          transform="rotate(35 56 56)"
        />
        {/* Highlight */}
        <rect
          x="48"
          y="33"
          width="30"
          height="2"
          rx="1"
          fill="white"
          opacity="0.6"
          transform="rotate(35 56 56)"
        />
      </motion.g>
    </svg>
  );
}

/* -------------------------------------------------------------------------- */
/* 3. Contract review — checks + warnings cascading down a document.          */
/* -------------------------------------------------------------------------- */
export function ReviewIcon({ active }: IconProps) {
  const markers = [
    { y: 26, type: "ok" as const },
    { y: 38, type: "warn" as const },
    { y: 50, type: "ok" as const },
    { y: 62, type: "ok" as const },
    { y: 74, type: "warn" as const },
  ];

  return (
    <svg viewBox="0 0 96 96" className="h-full w-full" aria-hidden>
      <defs>
        <linearGradient id="rev-doc" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor="white" stopOpacity="0.95" />
          <stop offset="100%" stopColor="white" stopOpacity="0.55" />
        </linearGradient>
      </defs>

      {/* Document */}
      <rect
        x="20"
        y="12"
        width="56"
        height="72"
        rx="6"
        fill="url(#rev-doc)"
        stroke={EMERALD}
        strokeOpacity="0.3"
        strokeWidth="1.2"
      />

      {/* Lines */}
      {markers.map((m) => (
        <line
          key={m.y}
          x1="38"
          y1={m.y}
          x2="68"
          y2={m.y}
          stroke={EMERALD}
          strokeOpacity={m.type === "ok" ? 0.18 : 0.32}
          strokeWidth="1.6"
        />
      ))}

      {/* Markers cascade in with stagger */}
      {markers.map((m, i) => (
        <motion.g
          key={`${m.y}-marker`}
          initial={false}
          animate={{
            scale: active ? [1, 1.18, 1] : 1,
            opacity: 1,
          }}
          transition={{
            duration: 0.5,
            delay: i * 0.08,
            repeat: active ? Infinity : 0,
            repeatDelay: 1.4,
          }}
          style={{ originX: `30px`, originY: `${m.y}px` }}
        >
          {m.type === "ok" ? (
            <>
              <circle cx="30" cy={m.y} r="5" fill={EMERALD} fillOpacity="0.12" />
              <path
                d={`M27 ${m.y} l2.4 2.4 L33.5 ${m.y - 2.5}`}
                stroke={EMERALD}
                strokeWidth="1.8"
                strokeLinecap="round"
                strokeLinejoin="round"
                fill="none"
              />
            </>
          ) : (
            <>
              <circle cx="30" cy={m.y} r="5" fill={GOLD} fillOpacity="0.18" />
              <line
                x1="30"
                y1={m.y - 2.5}
                x2="30"
                y2={m.y + 0.5}
                stroke={GOLD}
                strokeWidth="1.8"
                strokeLinecap="round"
              />
              <circle cx="30" cy={m.y + 2.6} r="0.9" fill={GOLD} />
            </>
          )}
        </motion.g>
      ))}

      {/* Sliding scan beam */}
      <motion.rect
        x="20"
        y="12"
        width="56"
        height="3"
        fill={GOLD}
        fillOpacity="0.35"
        initial={false}
        animate={{ y: active ? [12, 80, 12] : [12, 80, 12] }}
        transition={{
          duration: active ? 2.2 : 4.5,
          repeat: Infinity,
          ease: "easeInOut",
        }}
      />
    </svg>
  );
}

/* -------------------------------------------------------------------------- */
/* 4. Case analysis — scales of justice, with weights tilting + data ticks.   */
/* -------------------------------------------------------------------------- */
export function CaseIcon({ active }: IconProps) {
  return (
    <svg viewBox="0 0 96 96" className="h-full w-full" aria-hidden>
      <defs>
        <linearGradient id="case-pan" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor={GOLD_SOFT} />
          <stop offset="100%" stopColor={GOLD} />
        </linearGradient>
      </defs>

      {/* Stand */}
      <rect x="44" y="20" width="8" height="56" rx="2" fill={EMERALD} />
      <rect x="32" y="76" width="32" height="6" rx="2" fill={EMERALD} />

      {/* Cross-beam */}
      <motion.g
        animate={{ rotate: active ? [0, -6, 4, 0] : [0, 3, -3, 0] }}
        transition={{
          duration: active ? 2.6 : 5,
          repeat: Infinity,
          ease: "easeInOut",
        }}
        style={{ originX: "48px", originY: "26px" }}
      >
        <rect x="14" y="24" width="68" height="3.5" rx="1.5" fill={EMERALD} />
        {/* Strings */}
        <line x1="22" y1="27" x2="22" y2="44" stroke={EMERALD} strokeWidth="1.4" />
        <line x1="74" y1="27" x2="74" y2="44" stroke={EMERALD} strokeWidth="1.4" />

        {/* Left pan + chip */}
        <ellipse cx="22" cy="46" rx="11" ry="3.5" fill="url(#case-pan)" />
        <motion.rect
          x="17"
          y="40"
          width="10"
          height="4"
          rx="1"
          fill={EMERALD}
          animate={{ scaleY: active ? [1, 0.7, 1] : 1 }}
          transition={{ duration: 1.2, repeat: Infinity }}
          style={{ originY: "44px" }}
        />

        {/* Right pan + chip */}
        <ellipse cx="74" cy="46" rx="11" ry="3.5" fill="url(#case-pan)" />
        <motion.rect
          x="69"
          y="40"
          width="10"
          height="4"
          rx="1"
          fill={EMERALD}
          animate={{ scaleY: active ? [1, 1.3, 1] : 1 }}
          transition={{ duration: 1.2, repeat: Infinity, delay: 0.4 }}
          style={{ originY: "44px" }}
        />
      </motion.g>

      {/* Pivot ornament */}
      <circle cx="48" cy="22" r="4" fill={GOLD} />

      {/* Floating data ticks */}
      {[0, 1, 2].map((i) => (
        <motion.circle
          key={i}
          cx={20 + i * 28}
          cy={12}
          r="1.4"
          fill={GOLD}
          initial={{ opacity: 0 }}
          animate={{ opacity: [0, 1, 0], cy: [12, 6, 4] }}
          transition={{
            duration: 2,
            delay: i * 0.5,
            repeat: Infinity,
            ease: "easeOut",
          }}
        />
      ))}
    </svg>
  );
}

/* -------------------------------------------------------------------------- */
/* 5. Client CRM — node graph; central node pulses, lines flicker.            */
/* -------------------------------------------------------------------------- */
export function CrmIcon({ active }: IconProps) {
  const nodes = [
    { id: "a", x: 20, y: 24 },
    { id: "b", x: 76, y: 22 },
    { id: "c", x: 14, y: 70 },
    { id: "d", x: 82, y: 72 },
    { id: "e", x: 46, y: 78 },
  ];
  const center = { x: 48, y: 46 };

  return (
    <svg viewBox="0 0 96 96" className="h-full w-full" aria-hidden>
      {/* Connections */}
      {nodes.map((n, i) => (
        <motion.line
          key={n.id}
          x1={center.x}
          y1={center.y}
          x2={n.x}
          y2={n.y}
          stroke={EMERALD}
          strokeOpacity="0.35"
          strokeWidth="1"
          initial={false}
          animate={{ strokeOpacity: active ? [0.2, 0.7, 0.2] : [0.15, 0.4, 0.15] }}
          transition={{
            duration: 2,
            delay: i * 0.2,
            repeat: Infinity,
            ease: "easeInOut",
          }}
        />
      ))}

      {/* Travelling pulses */}
      {nodes.map((n, i) => (
        <motion.circle
          key={`pulse-${n.id}`}
          r="1.6"
          fill={GOLD}
          initial={false}
          animate={{
            cx: [center.x, n.x],
            cy: [center.y, n.y],
            opacity: [0, 1, 0],
          }}
          transition={{
            duration: active ? 1.4 : 2.4,
            delay: i * 0.35,
            repeat: Infinity,
            ease: "easeOut",
          }}
        />
      ))}

      {/* Outer nodes (clients) */}
      {nodes.map((n) => (
        <g key={`node-${n.id}`}>
          <circle cx={n.x} cy={n.y} r="6" fill={EMERALD} fillOpacity="0.12" />
          <circle cx={n.x} cy={n.y} r="3.4" fill={EMERALD} />
        </g>
      ))}

      {/* Central node — the firm */}
      <motion.circle
        cx={center.x}
        cy={center.y}
        r="11"
        fill={GOLD}
        fillOpacity="0.18"
        animate={{ scale: active ? [1, 1.18, 1] : [1, 1.08, 1] }}
        transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
        style={{ originX: `${center.x}px`, originY: `${center.y}px` }}
      />
      <circle cx={center.x} cy={center.y} r="6" fill={GOLD} />
      <circle cx={center.x} cy={center.y} r="2.2" fill="white" fillOpacity="0.85" />
    </svg>
  );
}

/* -------------------------------------------------------------------------- */
/* 6. WhatsApp channel — two chat bubbles + typing dots.                      */
/* -------------------------------------------------------------------------- */
export function WhatsappIcon({ active }: IconProps) {
  return (
    <svg viewBox="0 0 96 96" className="h-full w-full" aria-hidden>
      <defs>
        <linearGradient id="wa-bubble1" x1="0" x2="1" y1="0" y2="1">
          <stop offset="0%" stopColor={EMERALD_SOFT} />
          <stop offset="100%" stopColor={EMERALD} />
        </linearGradient>
        <linearGradient id="wa-bubble2" x1="0" x2="1" y1="0" y2="1">
          <stop offset="0%" stopColor={GOLD_SOFT} />
          <stop offset="100%" stopColor={GOLD} />
        </linearGradient>
      </defs>

      {/* Incoming bubble */}
      <motion.g
        initial={false}
        animate={{ y: active ? [0, -1, 0] : 0 }}
        transition={{ duration: 1.6, repeat: Infinity }}
      >
        <path
          d="M14 22 h44 a8 8 0 0 1 8 8 v18 a8 8 0 0 1 -8 8 h-30 l-10 8 v-8 h-4 a8 8 0 0 1 -8 -8 v-18 a8 8 0 0 1 8 -8 z"
          fill="url(#wa-bubble1)"
        />
        <line x1="22" y1="34" x2="50" y2="34" stroke="white" strokeOpacity="0.45" strokeWidth="2" strokeLinecap="round" />
        <line x1="22" y1="42" x2="44" y2="42" stroke="white" strokeOpacity="0.45" strokeWidth="2" strokeLinecap="round" />
      </motion.g>

      {/* Outgoing reply bubble — fades in on hover, pulses gently always */}
      <motion.g
        initial={false}
        animate={{
          opacity: active ? 1 : [0.6, 1, 0.6],
          y: active ? 0 : [0, -1, 0],
        }}
        transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
      >
        <path
          d="M82 60 h-32 a7 7 0 0 1 -7 -7 v-12 a7 7 0 0 1 7 -7 h32 a7 7 0 0 1 7 7 v12 a7 7 0 0 1 -7 7 z"
          fill="url(#wa-bubble2)"
          transform="translate(0 14)"
        />
        {/* Typing dots */}
        {[0, 1, 2].map((i) => (
          <motion.circle
            key={i}
            cx={58 + i * 8}
            cy={62}
            r="2"
            fill="white"
            animate={{
              opacity: [0.3, 1, 0.3],
              cy: [62, 60, 62],
            }}
            transition={{
              duration: 1.1,
              delay: i * 0.18,
              repeat: Infinity,
              ease: "easeInOut",
            }}
          />
        ))}
      </motion.g>
    </svg>
  );
}

/* -------------------------------------------------------------------------- */
/*  PREMIUM 2-CARD ILLUSTRATIONS                                              */
/*                                                                            */
/*  When the features section is reduced to two large boxes, each card hosts  */
/*  a wide motion-graphic (200×130 viewBox) instead of one of the small       */
/*  96×96 icons above. These are designed as miniature animated scenes —      */
/*  several layered, idling elements that, taken together, communicate the    */
/*  full breadth of the capability described by the box.                       */
/* -------------------------------------------------------------------------- */

/* === Workbench === Research + Drafting + Review + Case analysis combined ===
 * Composition:
 *   • Document at the centre, with text lines that "fill in" over time
 *     (the agent drafting / analysing).
 *   • A gold scan beam sweeps top-to-bottom across the document (review).
 *   • Citation orbs rise from the document edges (research citations).
 *   • A magnifying glass drifts across the doc surface (reading / scanning).
 *   • Bottom-end: tiny scales of justice tilting (case-analysis nod).
 *   • Background: faint dot grid for depth.
 */
export function WorkbenchIcon({ active }: IconProps) {
  return (
    <svg viewBox="0 0 200 130" className="h-full w-full" aria-hidden>
      <defs>
        <linearGradient id="wb-doc" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor="white" stopOpacity="0.95" />
          <stop offset="100%" stopColor="white" stopOpacity="0.55" />
        </linearGradient>
        <linearGradient id="wb-scan" x1="0" x2="1" y1="0" y2="0">
          <stop offset="0%" stopColor={GOLD} stopOpacity="0" />
          <stop offset="50%" stopColor={GOLD} stopOpacity="0.55" />
          <stop offset="100%" stopColor={GOLD} stopOpacity="0" />
        </linearGradient>
        <radialGradient id="wb-lens" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor={GOLD_SOFT} stopOpacity="0.45" />
          <stop offset="70%" stopColor={GOLD} stopOpacity="0.05" />
          <stop offset="100%" stopColor={GOLD} stopOpacity="0" />
        </radialGradient>
        <pattern id="wb-grid" x="0" y="0" width="14" height="14" patternUnits="userSpaceOnUse">
          <circle cx="1" cy="1" r="0.8" fill={EMERALD} fillOpacity="0.10" />
        </pattern>
        <clipPath id="wb-doc-clip">
          <rect x="62" y="14" width="76" height="102" rx="6" />
        </clipPath>
      </defs>

      {/* Background dot grid */}
      <rect x="0" y="0" width="200" height="130" fill="url(#wb-grid)" />

      {/* Decorative connector lines from corners hinting at "everything plugs into one doc" */}
      <g stroke={EMERALD} strokeOpacity="0.12" strokeWidth="0.6" fill="none">
        <path d="M 14 22 L 62 38" />
        <path d="M 186 28 L 138 44" />
        <path d="M 18 110 L 64 92" />
        <path d="M 184 108 L 138 90" />
      </g>

      {/* Tiny scale of justice in the bottom-end corner (case-analysis nod) */}
      <g transform="translate(168 102)">
        <motion.g
          animate={{ rotate: active ? [0, -8, 6, 0] : [0, 4, -4, 0] }}
          transition={{
            duration: active ? 2.6 : 5,
            repeat: Infinity,
            ease: "easeInOut",
          }}
          style={{ originX: "10px", originY: "0px" }}
        >
          <rect x="0" y="-1" width="20" height="2" rx="0.6" fill={EMERALD} />
          <ellipse cx="3" cy="3" rx="3" ry="1" fill={GOLD} />
          <ellipse cx="17" cy="3" rx="3" ry="1" fill={GOLD} />
        </motion.g>
        <rect x="9" y="-1" width="2" height="14" fill={EMERALD} />
        <rect x="6" y="13" width="8" height="2" rx="0.6" fill={EMERALD} />
      </g>

      {/* Tiny magnifying glass on the start side (research nod) */}
      <g transform="translate(28 28)">
        <motion.g
          animate={{
            y: active ? [0, 4, 0] : [0, 2, 0],
            rotate: active ? [-4, 2, -4] : [-2, 1, -2],
          }}
          transition={{
            duration: active ? 3 : 5,
            repeat: Infinity,
            ease: "easeInOut",
          }}
        >
          <circle cx="0" cy="0" r="8" fill="url(#wb-lens)" />
          <circle cx="0" cy="0" r="8" fill="none" stroke={EMERALD} strokeWidth="1.4" />
          <line x1="6" y1="6" x2="12" y2="12" stroke={EMERALD} strokeWidth="1.8" strokeLinecap="round" />
        </motion.g>
      </g>

      {/* === Document === central focal point */}
      <g>
        <rect
          x="62"
          y="14"
          width="76"
          height="102"
          rx="6"
          fill="url(#wb-doc)"
          stroke={EMERALD}
          strokeOpacity="0.32"
          strokeWidth="1.2"
        />

        {/* Title bar */}
        <rect x="70" y="22" width="42" height="3" rx="1.5" fill={EMERALD} fillOpacity="0.45" />
        <rect x="70" y="29" width="28" height="2" rx="1" fill={GOLD} fillOpacity="0.55" />

        {/* Body lines that animate their length — the doc being drafted */}
        {[40, 47, 54, 61, 68, 75, 82, 89, 96, 103].map((y, i) => (
          <motion.rect
            key={y}
            x="70"
            y={y - 1.2}
            height="2"
            rx="1"
            fill={EMERALD}
            fillOpacity={i % 4 === 2 ? 0.55 : 0.22}
            initial={false}
            animate={{
              width: active
                ? 58 - (i % 3) * 8
                : 50 - (i % 3) * 8,
            }}
            transition={{
              duration: 1.0,
              delay: i * 0.04,
              ease: "easeOut",
            }}
          />
        ))}

        {/* Highlighted "citation" line — gold underlay */}
        <motion.rect
          x="68"
          y="65"
          height="6"
          rx="1.5"
          fill={GOLD}
          fillOpacity="0.18"
          initial={false}
          animate={{ width: active ? 56 : 42 }}
          transition={{ duration: 0.5 }}
        />

        {/* Sliding scan beam — clipped to the doc */}
        <g clipPath="url(#wb-doc-clip)">
          <motion.rect
            x="62"
            y="0"
            width="76"
            height="14"
            fill="url(#wb-scan)"
            initial={false}
            animate={{ y: [10, 100, 10] }}
            transition={{
              duration: active ? 2.4 : 4.5,
              repeat: Infinity,
              ease: "easeInOut",
            }}
          />
        </g>
      </g>

      {/* Magnifying glass over the doc — slow drift loop */}
      <motion.g
        initial={false}
        animate={{
          x: active ? [0, 4, -2, 0] : [0, 6, -3, 0],
          y: active ? [0, 14, 28, 0] : [0, 20, 40, 0],
        }}
        transition={{
          duration: active ? 5 : 9,
          repeat: Infinity,
          ease: "easeInOut",
        }}
      >
        <circle cx="118" cy="48" r="11" fill="url(#wb-lens)" />
        <circle cx="118" cy="48" r="11" fill="none" stroke={EMERALD} strokeWidth="1.8" />
        <line x1="126" y1="56" x2="134" y2="64" stroke={EMERALD} strokeWidth="2.4" strokeLinecap="round" />
      </motion.g>

      {/* Citation orbs rising from the doc — staggered loop */}
      {[
        { x: 78, delay: 0 },
        { x: 100, delay: 0.7 },
        { x: 124, delay: 1.4 },
      ].map((o, i) => (
        <motion.g
          key={i}
          initial={false}
          animate={{
            opacity: [0, 1, 0],
            y: [0, -16, -28],
          }}
          transition={{
            duration: 2.4,
            delay: o.delay,
            repeat: Infinity,
            ease: "easeOut",
          }}
        >
          <circle cx={o.x} cy={16} r="2.2" fill={GOLD} />
          <circle cx={o.x} cy={16} r="4" fill={GOLD} fillOpacity="0.18" />
        </motion.g>
      ))}

      {/* Floating "verdict" card on the trailing side — checkmark */}
      <g transform="translate(150 50)">
        <motion.g
          animate={{ y: active ? [0, -3, 0] : [0, -2, 0] }}
          transition={{ duration: 3.4, repeat: Infinity, ease: "easeInOut" }}
        >
          <rect x="0" y="0" width="28" height="20" rx="3" fill="white" stroke={EMERALD} strokeOpacity="0.35" strokeWidth="0.8" />
          <circle cx="7" cy="10" r="3.6" fill={EMERALD} fillOpacity="0.14" />
          <path d="M 5 10 l 1.6 1.6 L 9.4 8.2" stroke={EMERALD} strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" fill="none" />
          <rect x="13" y="7" width="12" height="1.6" rx="0.8" fill={EMERALD} fillOpacity="0.45" />
          <rect x="13" y="11" width="9" height="1.6" rx="0.8" fill={GOLD} fillOpacity="0.55" />
        </motion.g>
      </g>
    </svg>
  );
}

/* === Operations === CRM + WhatsApp + client comms unified ====================
 * Composition:
 *   • Firm hub at the centre with a subtle pulse halo.
 *   • Four client nodes orbiting, joined to the hub by dashed lines.
 *   • Three message bubbles travel along the lines toward the hub
 *     (inbound client questions).
 *   • One bubble shows typing dots — agent composing a reply.
 *   • Tiny WhatsApp-green chip on each client node for channel hint.
 *   • A floating "intake" card on the trailing side with a green status dot
 *     suggesting "matter opened, escalated to you".
 */
export function OperationsIcon({ active }: IconProps) {
  // Layout: hub at (100, 65). Clients on four points around it.
  const HUB = { x: 100, y: 65 };
  const clients = [
    { x: 26, y: 32 },
    { x: 178, y: 28 },
    { x: 22, y: 100 },
    { x: 176, y: 102 },
  ];
  const WA_GREEN = "hsl(142 70% 45%)";

  return (
    <svg viewBox="0 0 200 130" className="h-full w-full" aria-hidden>
      <defs>
        <pattern id="op-grid" x="0" y="0" width="14" height="14" patternUnits="userSpaceOnUse">
          <circle cx="1" cy="1" r="0.8" fill={EMERALD} fillOpacity="0.10" />
        </pattern>
        <radialGradient id="op-hub-halo" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor={GOLD_SOFT} stopOpacity="0.5" />
          <stop offset="100%" stopColor={GOLD} stopOpacity="0" />
        </radialGradient>
        <linearGradient id="op-bubble-in" x1="0" x2="1" y1="0" y2="1">
          <stop offset="0%" stopColor={EMERALD_SOFT} />
          <stop offset="100%" stopColor={EMERALD} />
        </linearGradient>
      </defs>

      {/* Background dot grid */}
      <rect x="0" y="0" width="200" height="130" fill="url(#op-grid)" />

      {/* Dashed connection lines from each client → hub */}
      {clients.map((c, i) => (
        <motion.line
          key={i}
          x1={c.x}
          y1={c.y}
          x2={HUB.x}
          y2={HUB.y}
          stroke={EMERALD}
          strokeOpacity="0.45"
          strokeWidth="0.9"
          strokeDasharray="3 3"
          initial={false}
          animate={{
            strokeOpacity: active
              ? [0.25, 0.7, 0.25]
              : [0.2, 0.45, 0.2],
          }}
          transition={{
            duration: 2.6,
            delay: i * 0.3,
            repeat: Infinity,
            ease: "easeInOut",
          }}
        />
      ))}

      {/* Pulses travelling client → hub */}
      {clients.map((c, i) => (
        <motion.circle
          key={`pulse-${i}`}
          r="1.8"
          fill={GOLD}
          initial={false}
          animate={{
            cx: [c.x, HUB.x],
            cy: [c.y, HUB.y],
            opacity: [0, 1, 0],
          }}
          transition={{
            duration: active ? 1.6 : 2.6,
            delay: i * 0.45,
            repeat: Infinity,
            ease: "easeOut",
          }}
        />
      ))}

      {/* Hub halo */}
      <motion.circle
        cx={HUB.x}
        cy={HUB.y}
        r="24"
        fill="url(#op-hub-halo)"
        animate={{ scale: active ? [1, 1.15, 1] : [1, 1.06, 1] }}
        transition={{ duration: 2.4, repeat: Infinity, ease: "easeInOut" }}
        style={{ originX: `${HUB.x}px`, originY: `${HUB.y}px` }}
      />

      {/* Hub disc */}
      <circle cx={HUB.x} cy={HUB.y} r="14" fill={EMERALD} />
      <circle cx={HUB.x} cy={HUB.y} r="14" fill="none" stroke={GOLD} strokeOpacity="0.6" strokeWidth="0.8" />

      {/* CRM glyph inside the hub — a tiny grid of rows */}
      <g>
        <rect x={HUB.x - 7} y={HUB.y - 6} width="14" height="2" rx="0.6" fill="white" fillOpacity="0.9" />
        <rect x={HUB.x - 7} y={HUB.y - 2} width="14" height="2" rx="0.6" fill="white" fillOpacity="0.55" />
        <rect x={HUB.x - 7} y={HUB.y + 2} width="14" height="2" rx="0.6" fill="white" fillOpacity="0.35" />
      </g>

      {/* Client nodes with avatar + WA chip */}
      {clients.map((c, i) => (
        <g key={`node-${i}`}>
          <circle cx={c.x} cy={c.y} r="9" fill="white" stroke={EMERALD} strokeOpacity="0.35" strokeWidth="1.1" />
          <circle cx={c.x} cy={c.y - 2} r="2.6" fill={EMERALD} fillOpacity="0.7" />
          <path d={`M ${c.x - 4} ${c.y + 5} a 4 3 0 0 1 8 0`} fill={EMERALD} fillOpacity="0.45" />
          {/* WhatsApp-green status chip */}
          <circle cx={c.x + 7} cy={c.y - 7} r="2.4" fill={WA_GREEN} stroke="white" strokeWidth="0.8" />
        </g>
      ))}

      {/* === Incoming chat bubble travelling client[0] → hub === */}
      <motion.g
        initial={false}
        animate={{
          x: [clients[0].x - 100, HUB.x - 100 - 12],
          y: [clients[0].y - 65, HUB.y - 65 - 18],
          opacity: [0, 1, 1, 0],
        }}
        transition={{
          duration: active ? 3 : 5,
          times: [0, 0.25, 0.8, 1],
          repeat: Infinity,
          ease: "easeInOut",
        }}
      >
        <g transform="translate(100 65)">
          <path
            d="M 0 0 h 20 a 3 3 0 0 1 3 3 v 7 a 3 3 0 0 1 -3 3 h -16 l -4 4 v -4 a 3 3 0 0 1 -3 -3 v -7 a 3 3 0 0 1 3 -3 z"
            fill="url(#op-bubble-in)"
          />
          <line x1="4" y1="5" x2="18" y2="5" stroke="white" strokeOpacity="0.5" strokeWidth="1" strokeLinecap="round" />
          <line x1="4" y1="9" x2="14" y2="9" stroke="white" strokeOpacity="0.5" strokeWidth="1" strokeLinecap="round" />
        </g>
      </motion.g>

      {/* === Outgoing WhatsApp-green reply bubble travelling hub → client[3] === */}
      <motion.g
        initial={false}
        animate={{
          x: [HUB.x - 100 + 6, clients[3].x - 100 - 18],
          y: [HUB.y - 65 + 6, clients[3].y - 65 - 16],
          opacity: [0, 1, 1, 0],
        }}
        transition={{
          duration: active ? 3 : 5,
          times: [0, 0.2, 0.85, 1],
          delay: active ? 1 : 1.7,
          repeat: Infinity,
          ease: "easeInOut",
        }}
      >
        <g transform="translate(100 65)">
          <path
            d="M 0 0 h 22 a 3 3 0 0 1 3 3 v 7 a 3 3 0 0 1 -3 3 h -18 l -4 4 v -4 a 3 3 0 0 1 -3 -3 v -7 a 3 3 0 0 1 3 -3 z"
            fill={WA_GREEN}
          />
          {/* typing dots */}
          {[0, 1, 2].map((i) => (
            <motion.circle
              key={i}
              cx={6 + i * 5}
              cy={6.5}
              r="1.5"
              fill="white"
              animate={{ opacity: [0.4, 1, 0.4], cy: [6.5, 5.5, 6.5] }}
              transition={{
                duration: 1,
                delay: i * 0.18,
                repeat: Infinity,
                ease: "easeInOut",
              }}
            />
          ))}
        </g>
      </motion.g>

      {/* Trailing "intake card" — a row with green status dot */}
      <g transform="translate(140 14)">
        <motion.g
          animate={{ y: active ? [0, -2, 0] : [0, -1.2, 0] }}
          transition={{ duration: 3.2, repeat: Infinity, ease: "easeInOut" }}
        >
          <rect x="0" y="0" width="48" height="14" rx="3" fill="white" stroke={EMERALD} strokeOpacity="0.32" strokeWidth="0.8" />
          <circle cx="5" cy="7" r="2.4" fill={WA_GREEN} />
          <rect x="11" y="3" width="22" height="2" rx="1" fill={EMERALD} fillOpacity="0.55" />
          <rect x="11" y="7.5" width="32" height="1.6" rx="0.8" fill={EMERALD} fillOpacity="0.30" />
        </motion.g>
      </g>
    </svg>
  );
}

export const FEATURE_ICON_BY_KEY = {
  rag: ResearchIcon,
  drafting: DraftingIcon,
  review: ReviewIcon,
  case: CaseIcon,
  crm: CrmIcon,
  whatsapp: WhatsappIcon,
  workbench: WorkbenchIcon,
  operations: OperationsIcon,
} as const;

export type FeatureIconKey = keyof typeof FEATURE_ICON_BY_KEY;
