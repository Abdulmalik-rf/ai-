"use client";

/**
 * Animated SVG illustrations *exclusive to the /features page* — six
 * fresh compositions, none of which are reused on the home page or
 * anywhere else. They share a 96×96 viewBox and the brand emerald
 * (#0F4C3A primary, #3a7d65 soft) + warm-gold (#B5853C primary, #d4a85a
 * soft) palette.
 *
 * Each icon idles continuously; the `active` prop amplifies the
 * animation when the parent card is hovered.
 */
import { motion } from "framer-motion";

const EMERALD = "hsl(160 65% 22%)";
const EMERALD_SOFT = "hsl(160 60% 35%)";
const GOLD = "hsl(36 60% 50%)";
const GOLD_SOFT = "hsl(36 70% 65%)";

type Props = { active?: boolean };

/* ─────────────────────────────────────────────────────────────────────── */
/* 1. Grounded research — Citation web.                                    */
/*    A central card surrounded by orbiting "source nodes" connected by   */
/*    dashed threads; the threads pulse outward continuously.              */
/* ─────────────────────────────────────────────────────────────────────── */
export function CitationWebIcon({ active }: Props) {
  const sources = [
    { x: 14, y: 26 },
    { x: 82, y: 22 },
    { x: 12, y: 70 },
    { x: 84, y: 74 },
  ];
  return (
    <svg viewBox="0 0 96 96" className="h-full w-full" aria-hidden>
      <defs>
        <linearGradient id="cw-card" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor="white" stopOpacity="0.95" />
          <stop offset="100%" stopColor="white" stopOpacity="0.6" />
        </linearGradient>
      </defs>

      {/* Threads + travelling pulses */}
      {sources.map((s, i) => (
        <g key={i}>
          <line
            x1="48"
            y1="48"
            x2={s.x}
            y2={s.y}
            stroke={EMERALD}
            strokeOpacity="0.30"
            strokeWidth="0.8"
            strokeDasharray="3 3"
          />
          <motion.circle
            r="1.6"
            fill={GOLD}
            initial={false}
            animate={{
              cx: [48, s.x],
              cy: [48, s.y],
              opacity: [0, 1, 0],
            }}
            transition={{
              duration: active ? 1.6 : 2.6,
              delay: i * 0.35,
              repeat: Infinity,
              ease: "easeOut",
            }}
          />
        </g>
      ))}

      {/* Source nodes — small leaf-shapes */}
      {sources.map((s, i) => (
        <g key={`leaf-${i}`}>
          <circle cx={s.x} cy={s.y} r="6" fill={EMERALD} fillOpacity="0.10" />
          <path
            d={`M ${s.x - 3} ${s.y} q 3 -4 6 0 q -3 4 -6 0 z`}
            fill={EMERALD}
            fillOpacity="0.55"
          />
        </g>
      ))}

      {/* Central card */}
      <motion.g
        initial={false}
        animate={{ scale: active ? [1, 1.05, 1] : 1 }}
        transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
        style={{ originX: "48px", originY: "48px" }}
      >
        <rect
          x="30"
          y="34"
          width="36"
          height="28"
          rx="3"
          fill="url(#cw-card)"
          stroke={EMERALD}
          strokeOpacity="0.4"
          strokeWidth="1.1"
        />
        <rect
          x="34"
          y="38"
          width="20"
          height="2"
          rx="1"
          fill={GOLD}
          fillOpacity="0.65"
        />
        <rect
          x="34"
          y="43"
          width="26"
          height="1.6"
          rx="0.8"
          fill={EMERALD}
          fillOpacity="0.5"
        />
        <rect
          x="34"
          y="47"
          width="22"
          height="1.6"
          rx="0.8"
          fill={EMERALD}
          fillOpacity="0.35"
        />
        <rect
          x="34"
          y="51"
          width="18"
          height="1.6"
          rx="0.8"
          fill={EMERALD}
          fillOpacity="0.35"
        />
        <rect
          x="34"
          y="56"
          width="14"
          height="3"
          rx="1.4"
          fill={GOLD}
          fillOpacity="0.3"
        />
      </motion.g>
    </svg>
  );
}

/* ─────────────────────────────────────────────────────────────────────── */
/* 2. Document drafting — Quill + ink stream.                              */
/*    A quill icon hovers above a card; gold "ink" drops fall onto the     */
/*    card and fill in lines progressively.                                 */
/* ─────────────────────────────────────────────────────────────────────── */
export function QuillStreamIcon({ active }: Props) {
  return (
    <svg viewBox="0 0 96 96" className="h-full w-full" aria-hidden>
      <defs>
        <linearGradient id="qs-card" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor="white" stopOpacity="0.95" />
          <stop offset="100%" stopColor="white" stopOpacity="0.65" />
        </linearGradient>
        <linearGradient id="qs-quill" x1="0" x2="1" y1="0" y2="1">
          <stop offset="0%" stopColor={GOLD_SOFT} />
          <stop offset="100%" stopColor={GOLD} />
        </linearGradient>
      </defs>

      {/* Card */}
      <rect
        x="18"
        y="46"
        width="60"
        height="38"
        rx="4"
        fill="url(#qs-card)"
        stroke={EMERALD}
        strokeOpacity="0.32"
        strokeWidth="1.1"
      />

      {/* Filling lines — staggered widths */}
      {[
        { y: 56, w: 44 },
        { y: 62, w: 38 },
        { y: 68, w: 32 },
        { y: 74, w: 26 },
      ].map((line, i) => (
        <motion.rect
          key={line.y}
          x="24"
          y={line.y}
          height="2"
          rx="1"
          fill={EMERALD}
          fillOpacity={i === 0 ? 0.55 : 0.3}
          initial={false}
          animate={{ width: active ? line.w : line.w * 0.6 }}
          transition={{ duration: 1.1, delay: i * 0.12, ease: "easeOut" }}
        />
      ))}

      {/* Ink drops falling */}
      {[0, 1, 2].map((i) => (
        <motion.circle
          key={i}
          cx={28 + i * 16}
          r="1.4"
          fill={GOLD}
          initial={false}
          animate={{
            cy: [22, 50],
            opacity: [0, 1, 0],
          }}
          transition={{
            duration: 1.8,
            delay: i * 0.5,
            repeat: Infinity,
            ease: "easeIn",
          }}
        />
      ))}

      {/* Quill */}
      <motion.g
        initial={false}
        animate={{
          rotate: active ? [-4, 2, -4] : [-3, 1, -3],
          y: active ? [0, -1, 0] : [0, -0.5, 0],
        }}
        transition={{
          duration: active ? 2.6 : 4,
          repeat: Infinity,
          ease: "easeInOut",
        }}
        style={{ originX: "58px", originY: "16px" }}
      >
        {/* feather */}
        <path
          d="M 56 8 Q 70 14 72 28 Q 64 26 58 24 Q 50 22 56 8 Z"
          fill="url(#qs-quill)"
          stroke={EMERALD}
          strokeOpacity="0.3"
          strokeWidth="0.6"
        />
        {/* shaft */}
        <line
          x1="60"
          y1="24"
          x2="46"
          y2="42"
          stroke={EMERALD}
          strokeWidth="2"
          strokeLinecap="round"
        />
        {/* nib tip */}
        <circle cx="44" cy="44" r="1.4" fill={GOLD} />
      </motion.g>
    </svg>
  );
}

/* ─────────────────────────────────────────────────────────────────────── */
/* 3. Contract review — Sliding scanner.                                   */
/*    A document with text rows; a horizontal scanner sweeps top→bottom    */
/*    and each row it touches gets a green or amber severity tag.          */
/* ─────────────────────────────────────────────────────────────────────── */
export function ScannerIcon({ active }: Props) {
  return (
    <svg viewBox="0 0 96 96" className="h-full w-full" aria-hidden>
      <defs>
        <linearGradient id="sc-doc" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor="white" stopOpacity="0.95" />
          <stop offset="100%" stopColor="white" stopOpacity="0.6" />
        </linearGradient>
        <linearGradient id="sc-beam" x1="0" x2="1" y1="0" y2="0">
          <stop offset="0%" stopColor={GOLD} stopOpacity="0" />
          <stop offset="50%" stopColor={GOLD} stopOpacity="0.7" />
          <stop offset="100%" stopColor={GOLD} stopOpacity="0" />
        </linearGradient>
        <clipPath id="sc-doc-clip">
          <rect x="18" y="14" width="60" height="68" rx="5" />
        </clipPath>
      </defs>

      {/* Document */}
      <rect
        x="18"
        y="14"
        width="60"
        height="68"
        rx="5"
        fill="url(#sc-doc)"
        stroke={EMERALD}
        strokeOpacity="0.32"
        strokeWidth="1.1"
      />

      {/* Rows + severity dots */}
      {[
        { y: 24, ok: true },
        { y: 34, ok: false },
        { y: 44, ok: true },
        { y: 54, ok: true },
        { y: 64, ok: false },
        { y: 74, ok: true },
      ].map((row, i) => (
        <g key={row.y}>
          <rect
            x="24"
            y={row.y}
            width={32 + (i % 3) * 6}
            height="2"
            rx="1"
            fill={EMERALD}
            fillOpacity="0.32"
          />
          <motion.circle
            cx="68"
            cy={row.y + 1}
            r="1.6"
            fill={row.ok ? "hsl(140 60% 45%)" : GOLD}
            initial={false}
            animate={{
              opacity: active ? [0.3, 1, 0.3] : [0.5, 0.9, 0.5],
              scale: active ? [1, 1.3, 1] : 1,
            }}
            transition={{
              duration: 2,
              delay: i * 0.2,
              repeat: Infinity,
              ease: "easeInOut",
            }}
          />
        </g>
      ))}

      {/* Sliding scanner beam */}
      <g clipPath="url(#sc-doc-clip)">
        <motion.rect
          x="18"
          width="60"
          height="6"
          fill="url(#sc-beam)"
          initial={false}
          animate={{ y: [14, 82] }}
          transition={{
            duration: active ? 1.8 : 3.2,
            repeat: Infinity,
            ease: "easeInOut",
          }}
        />
      </g>
    </svg>
  );
}

/* ─────────────────────────────────────────────────────────────────────── */
/* 4. Case analysis — Folder unfolding.                                    */
/*    A folder opens and three issue-tag chips lift up from inside it,     */
/*    each labelled with a tiny icon.                                       */
/* ─────────────────────────────────────────────────────────────────────── */
export function FolderTagsIcon({ active }: Props) {
  return (
    <svg viewBox="0 0 96 96" className="h-full w-full" aria-hidden>
      <defs>
        <linearGradient id="ft-folder" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor={EMERALD_SOFT} stopOpacity="0.20" />
          <stop offset="100%" stopColor={EMERALD} stopOpacity="0.36" />
        </linearGradient>
      </defs>

      {/* Folder back */}
      <path
        d="M 14 38 L 14 78 Q 14 82 18 82 L 78 82 Q 82 82 82 78 L 82 42 L 46 42 L 40 36 L 18 36 Q 14 36 14 38 Z"
        fill="url(#ft-folder)"
        stroke={EMERALD}
        strokeOpacity="0.45"
        strokeWidth="1.1"
        strokeLinejoin="round"
      />

      {/* Issue tags lifting up */}
      {[
        { x: 22, label: "law", color: EMERALD },
        { x: 40, label: "fact", color: GOLD },
        { x: 58, label: "risk", color: EMERALD_SOFT },
      ].map((tag, i) => (
        <motion.g
          key={i}
          initial={false}
          animate={{
            y: active ? [-2, -12, -2] : [0, -6, 0],
            opacity: [0.4, 1, 0.4],
          }}
          transition={{
            duration: 3,
            delay: i * 0.45,
            repeat: Infinity,
            ease: "easeInOut",
          }}
        >
          <rect
            x={tag.x}
            y="50"
            width="16"
            height="22"
            rx="2"
            fill="white"
            stroke={tag.color}
            strokeOpacity="0.5"
            strokeWidth="1"
          />
          <circle cx={tag.x + 8} cy="58" r="2.6" fill={tag.color} fillOpacity="0.7" />
          <rect
            x={tag.x + 3}
            y="64"
            width="10"
            height="1.4"
            rx="0.7"
            fill={EMERALD}
            fillOpacity="0.45"
          />
          <rect
            x={tag.x + 3}
            y="67.5"
            width="7"
            height="1.4"
            rx="0.7"
            fill={EMERALD}
            fillOpacity="0.3"
          />
        </motion.g>
      ))}

      {/* Folder tab front */}
      <path
        d="M 14 38 L 40 38 L 46 44 L 82 44 L 82 50 L 14 50 Z"
        fill={EMERALD}
        fillOpacity="0.65"
      />
    </svg>
  );
}

/* ─────────────────────────────────────────────────────────────────────── */
/* 5. Built-in CRM — Card deck.                                            */
/*    A stack of overlapping client cards with status pills; the top card  */
/*    refreshes on a loop and a "new" gold chip lights up.                 */
/* ─────────────────────────────────────────────────────────────────────── */
export function CardDeckIcon({ active }: Props) {
  return (
    <svg viewBox="0 0 96 96" className="h-full w-full" aria-hidden>
      <defs>
        <linearGradient id="cd-card" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor="white" stopOpacity="0.95" />
          <stop offset="100%" stopColor="white" stopOpacity="0.6" />
        </linearGradient>
      </defs>

      {/* Back card (deepest) */}
      <rect
        x="22"
        y="22"
        width="52"
        height="42"
        rx="5"
        fill="white"
        stroke={EMERALD}
        strokeOpacity="0.22"
        strokeWidth="1"
        transform="rotate(-8 48 43)"
      />

      {/* Middle card */}
      <rect
        x="20"
        y="28"
        width="56"
        height="46"
        rx="5"
        fill="white"
        stroke={EMERALD}
        strokeOpacity="0.32"
        strokeWidth="1"
        transform="rotate(-3 48 51)"
      />

      {/* Top card — animates */}
      <motion.g
        initial={false}
        animate={{
          rotate: active ? [0, 1, -1, 0] : [0, 0.5, -0.5, 0],
          y: active ? [0, -2, 0] : 0,
        }}
        transition={{
          duration: 3,
          repeat: Infinity,
          ease: "easeInOut",
        }}
        style={{ originX: "48px", originY: "56px" }}
      >
        <rect
          x="18"
          y="34"
          width="60"
          height="50"
          rx="5"
          fill="url(#cd-card)"
          stroke={EMERALD}
          strokeOpacity="0.42"
          strokeWidth="1.1"
        />
        {/* Avatar circle */}
        <circle cx="28" cy="46" r="5" fill={EMERALD} fillOpacity="0.18" />
        <circle cx="28" cy="45" r="2" fill={EMERALD} />
        <path
          d="M 23 51 Q 28 48 33 51"
          fill={EMERALD}
          fillOpacity="0.55"
        />
        {/* Name line */}
        <rect
          x="38"
          y="42"
          width="24"
          height="2"
          rx="1"
          fill={EMERALD}
          fillOpacity="0.55"
        />
        <rect
          x="38"
          y="47"
          width="18"
          height="1.6"
          rx="0.8"
          fill={EMERALD}
          fillOpacity="0.32"
        />
        {/* Body rows */}
        <rect
          x="24"
          y="60"
          width="48"
          height="1.6"
          rx="0.8"
          fill={EMERALD}
          fillOpacity="0.25"
        />
        <rect
          x="24"
          y="66"
          width="36"
          height="1.6"
          rx="0.8"
          fill={EMERALD}
          fillOpacity="0.25"
        />
        {/* Status pill — pulsing gold */}
        <motion.rect
          x="50"
          y="74"
          width="22"
          height="6"
          rx="3"
          fill={GOLD}
          initial={false}
          animate={{ fillOpacity: active ? [0.4, 0.9, 0.4] : [0.5, 0.8, 0.5] }}
          transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
        />
      </motion.g>
    </svg>
  );
}

/* ─────────────────────────────────────────────────────────────────────── */
/* 6. WhatsApp channel — Reply ribbon.                                     */
/*    A vertical stream of three chat bubbles; the bottom bubble is an     */
/*    outgoing reply that highlights in WhatsApp-green on a loop.          */
/* ─────────────────────────────────────────────────────────────────────── */
export function ReplyRibbonIcon({ active }: Props) {
  const WA_GREEN = "hsl(142 70% 45%)";
  return (
    <svg viewBox="0 0 96 96" className="h-full w-full" aria-hidden>
      <defs>
        <linearGradient id="rr-incoming" x1="0" x2="1" y1="0" y2="1">
          <stop offset="0%" stopColor={EMERALD_SOFT} stopOpacity="0.25" />
          <stop offset="100%" stopColor={EMERALD} stopOpacity="0.45" />
        </linearGradient>
      </defs>

      {/* Incoming bubble 1 (top-left) */}
      <motion.g
        initial={false}
        animate={{ x: active ? [0, -1, 0] : 0 }}
        transition={{ duration: 3, repeat: Infinity }}
      >
        <path
          d="M 14 16 h 38 a 4 4 0 0 1 4 4 v 14 a 4 4 0 0 1 -4 4 h -28 l -6 5 v -5 h -4 a 4 4 0 0 1 -4 -4 v -14 a 4 4 0 0 1 4 -4 z"
          fill="url(#rr-incoming)"
          stroke={EMERALD}
          strokeOpacity="0.5"
          strokeWidth="0.8"
        />
        <line
          x1="20"
          y1="24"
          x2="46"
          y2="24"
          stroke={EMERALD}
          strokeOpacity="0.6"
          strokeWidth="1.4"
          strokeLinecap="round"
        />
        <line
          x1="20"
          y1="30"
          x2="38"
          y2="30"
          stroke={EMERALD}
          strokeOpacity="0.4"
          strokeWidth="1.4"
          strokeLinecap="round"
        />
      </motion.g>

      {/* Outgoing reply bubble (bottom-right, green) — pulses */}
      <motion.g
        initial={false}
        animate={{
          y: active ? [0, -2, 0] : 0,
          opacity: [0.7, 1, 0.7],
        }}
        transition={{ duration: 2.2, repeat: Infinity, ease: "easeInOut" }}
      >
        <path
          d="M 84 50 h -38 a 4 4 0 0 1 -4 -4 v -2 a 4 4 0 0 1 4 -4 h 38 a 4 4 0 0 1 4 4 v 2 a 4 4 0 0 1 -4 4 z"
          fill={WA_GREEN}
          fillOpacity="0.9"
        />
        <path
          d="M 84 76 h -34 l -6 5 v -5 h -4 a 4 4 0 0 1 -4 -4 v -14 a 4 4 0 0 1 4 -4 h 44 a 4 4 0 0 1 4 4 v 14 a 4 4 0 0 1 -4 4 z"
          fill={WA_GREEN}
        />
        {/* Typing dots — three small white circles */}
        {[0, 1, 2].map((i) => (
          <motion.circle
            key={i}
            cx={56 + i * 7}
            cy="69"
            r="1.6"
            fill="white"
            initial={false}
            animate={{ opacity: [0.4, 1, 0.4], cy: [69, 67, 69] }}
            transition={{
              duration: 1,
              delay: i * 0.16,
              repeat: Infinity,
              ease: "easeInOut",
            }}
          />
        ))}
      </motion.g>

      {/* Status check at the very corner */}
      <g transform="translate(78 86)">
        <path
          d="M -4 -1 l 2 2 L 2 -3"
          fill="none"
          stroke={WA_GREEN}
          strokeWidth="1.4"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </g>
    </svg>
  );
}

export const FEATURES_PAGE_ICON_BY_KEY = {
  rag: CitationWebIcon,
  drafting: QuillStreamIcon,
  review: ScannerIcon,
  case: FolderTagsIcon,
  crm: CardDeckIcon,
  whatsapp: ReplyRibbonIcon,
} as const;

export type CapabilityIconKey = keyof typeof FEATURES_PAGE_ICON_BY_KEY;
