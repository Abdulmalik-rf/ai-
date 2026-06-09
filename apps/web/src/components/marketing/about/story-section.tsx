"use client";

/**
 * Story section — scrollytelling.
 *
 * Three chapters of the story (p1, p2, p3). As the reader scrolls
 * through the section, both columns stay sticky in the viewport while
 * the *active chapter index* advances. Whenever it advances:
 *   • the body paragraph fades out and is replaced by the next one;
 *   • the front paper of the stack rises up, rotates, fades, and
 *     drops back to the rear position — while the next paper slides
 *     in from below to become the new front.
 *
 * Implementation: a single `useScroll` on the section root, mapped into
 * a 0|1|2 active index via `useMotionValueEvent`. The page-turn
 * animation lives in an `AnimatePresence` around the front paper.
 */
import {
  AnimatePresence,
  motion,
  useMotionValueEvent,
  useScroll,
} from "framer-motion";
import * as React from "react";

type Chapter = {
  body: string;
  article: string;
};

export function StorySection({
  heading,
  p1,
  p2,
  p3,
}: {
  heading: string;
  p1: string;
  p2: string;
  p3: string;
}) {
  const chapters: Chapter[] = [
    { body: p1, article: "ARTICLE 9" },
    { body: p2, article: "ARTICLE 23" },
    { body: p3, article: "ARTICLE 5" },
  ];

  const sectionRef = React.useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({
    target: sectionRef,
    offset: ["start start", "end end"],
  });

  const [active, setActive] = React.useState(0);
  useMotionValueEvent(scrollYProgress, "change", (p) => {
    const idx = p >= 0.66 ? 2 : p >= 0.33 ? 1 : 0;
    setActive((prev) => (prev !== idx ? idx : prev));
  });

  return (
    <section ref={sectionRef} className="container py-20">
      {/* The grid (not the section) carries the tall height. With
          `lg:h-[260vh]`, both sticky children have ~160vh of vertical
          scroll room to stay pinned in the viewport while the active
          chapter index advances 0 → 1 → 2. */}
      <div className="grid lg:grid-cols-[1.1fr_1fr] gap-10 lg:gap-14 max-w-6xl mx-auto lg:h-[260vh]">
        {/* ─── Text column (sticky, content swaps with chapter) ─── */}
        <div className="lg:sticky lg:top-0 lg:h-screen flex flex-col justify-center">
          <h2 className="text-3xl md:text-4xl font-bold tracking-tight">
            {heading}
          </h2>
          <div
            className="mt-4 h-[2px] w-12"
            style={{
              backgroundImage:
                "linear-gradient(90deg, hsl(36 60% 50%), transparent)",
            }}
          />

          <div className="mt-8 flex items-center gap-3 text-xs uppercase tracking-[0.22em] text-accent font-semibold">
            <span className="tabular-nums">0{active + 1}</span>
            <span className="h-px w-10 bg-accent/30" />
            <span className="text-muted-foreground tabular-nums">
              0{chapters.length}
            </span>
          </div>

          <div className="relative mt-5 min-h-[14rem] md:min-h-[12rem]">
            <AnimatePresence mode="wait">
              <motion.p
                key={active}
                initial={{ opacity: 0, y: 14 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -14 }}
                transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
                className="text-base md:text-lg text-muted-foreground leading-relaxed"
              >
                {chapters[active].body}
              </motion.p>
            </AnimatePresence>
          </div>
        </div>

        {/* ─── Paper stack (sticky, top paper flips per chapter) ─── */}
        <div className="lg:sticky lg:top-0 lg:h-screen flex items-center justify-center">
          <PaperStack chapters={chapters} active={active} />
        </div>
      </div>
    </section>
  );
}

/* ─────────────────────────────────────────────────────────────────────── */

function PaperStack({
  chapters,
  active,
}: {
  chapters: Chapter[];
  active: number;
}) {
  return (
    <div className="relative aspect-square w-full max-w-md mx-auto">
      {/* Two static back papers — give the stack its depth */}
      <div className="absolute inset-0 -translate-x-[6px] -translate-y-[10px] rotate-[-5deg] opacity-55">
        <BackPaperSvg />
      </div>
      <div className="absolute inset-0 -translate-x-[3px] -translate-y-[5px] rotate-[3deg] opacity-75">
        <BackPaperSvg />
      </div>

      {/* Animated front paper — when the chapter changes, the current
          page rises straight up and fades out; the next page fades in
          softly underneath. No rear-tucking, no rotation. */}
      <AnimatePresence initial={false}>
        <motion.div
          key={active}
          className="absolute inset-0"
          initial={{ y: 24, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          exit={{ y: -160, opacity: 0 }}
          transition={{ duration: 0.55, ease: [0.4, 0, 0.2, 1] }}
        >
          <FrontPaperSvg chapter={chapters[active]} number={active + 1} />
        </motion.div>
      </AnimatePresence>
    </div>
  );
}

/* ─────────────────────────────────────────────────────────────────────── */

function FrontPaperSvg({
  chapter,
  number,
}: {
  chapter: Chapter;
  number: number;
}) {
  return (
    <svg viewBox="0 0 200 200" className="h-full w-full" aria-hidden>
      <defs>
        <linearGradient id={`paper-grad-${number}`} x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor="white" stopOpacity="0.97" />
          <stop offset="100%" stopColor="white" stopOpacity="0.65" />
        </linearGradient>
        <linearGradient id={`paper-edge-${number}`} x1="0" x2="1" y1="0" y2="1">
          <stop offset="0%" stopColor="hsl(160 65% 22%)" stopOpacity="0.38" />
          <stop offset="100%" stopColor="hsl(36 60% 50%)" stopOpacity="0.48" />
        </linearGradient>
      </defs>

      <rect
        x="40"
        y="32"
        width="120"
        height="152"
        rx="8"
        fill={`url(#paper-grad-${number})`}
        stroke={`url(#paper-edge-${number})`}
        strokeWidth="1.2"
      />

      {/* Chapter number — light watermark in the top-end corner */}
      <text
        x="148"
        y="56"
        textAnchor="end"
        fontSize="14"
        fontWeight="700"
        fill="hsl(36 60% 50%)"
        opacity="0.35"
        style={{ fontFeatureSettings: "'tnum'" }}
      >
        {`0${number}`}
      </text>

      {/* Header gold rule */}
      <rect
        x="50"
        y="46"
        width="60"
        height="3"
        rx="1.5"
        fill="hsl(36 60% 50%)"
      />

      {/* Body lines — slightly varied per chapter so each page reads
          as a different document, not a copy. */}
      {linesForChapter(number).map((line, i) => (
        <rect
          key={i}
          x="50"
          y={64 + i * 10}
          width={line}
          height="2"
          rx="1"
          fill="hsl(160 65% 22%)"
          opacity="0.32"
        />
      ))}

      {/* Article badge */}
      <rect
        x="50"
        y="156"
        width="68"
        height="14"
        rx="3"
        fill="hsl(36 60% 50%)"
        opacity="0.14"
      />
      <text
        x="84"
        y="166"
        textAnchor="middle"
        fontSize="6"
        fontWeight="600"
        fill="hsl(36 60% 40%)"
      >
        {chapter.article}
      </text>

      {/* Seal */}
      <g>
        <circle
          cx="144"
          cy="162"
          r="11"
          fill="none"
          stroke="hsl(36 60% 50%)"
          strokeWidth="1.5"
          opacity="0.6"
        />
        <circle cx="144" cy="162" r="6" fill="hsl(36 60% 50%)" opacity="0.18" />
        <path
          d="M140 162 l3 3 l5 -5"
          stroke="hsl(36 60% 40%)"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          fill="none"
        />
      </g>
    </svg>
  );
}

function BackPaperSvg() {
  return (
    <svg viewBox="0 0 200 200" className="h-full w-full" aria-hidden>
      <defs>
        <linearGradient id="back-paper-grad" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor="white" stopOpacity="0.92" />
          <stop offset="100%" stopColor="white" stopOpacity="0.55" />
        </linearGradient>
        <linearGradient id="back-paper-edge" x1="0" x2="1" y1="0" y2="1">
          <stop offset="0%" stopColor="hsl(160 65% 22%)" stopOpacity="0.28" />
          <stop offset="100%" stopColor="hsl(36 60% 50%)" stopOpacity="0.32" />
        </linearGradient>
      </defs>
      <rect
        x="40"
        y="32"
        width="120"
        height="152"
        rx="8"
        fill="url(#back-paper-grad)"
        stroke="url(#back-paper-edge)"
        strokeWidth="0.8"
      />
    </svg>
  );
}

function linesForChapter(n: number): number[] {
  if (n === 1) return [100, 90, 105, 80, 100, 70, 95, 60];
  if (n === 2) return [95, 102, 88, 100, 75, 96, 82, 64];
  return [102, 84, 100, 92, 78, 105, 70, 90];
}
