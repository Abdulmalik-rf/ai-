"use client";

import {
  motion,
  useMotionValue,
  useMotionValueEvent,
  useScroll,
  useTransform,
  type MotionValue,
} from "framer-motion";
import { Check, FileText, Send } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useRef, useState } from "react";

import { BrandLogo } from "@/components/brand-logo";

/**
 * Two-column scrollytelling section.
 *
 * Layout (md+):
 *   ┌─────────────┬──────────────────┐
 *   │  ChatWindow │  feature blurbs  │
 *   │  (sticky,   │  (scroll past)   │
 *   │   leading   │                  │
 *   │   edge)     │                  │
 *   └─────────────┴──────────────────┘
 *
 * The conversation starts EMPTY. As the user scrolls through this section,
 * messages appear progressively in real-time:
 *
 *   • The user's message types itself into the input field (typewriter).
 *   • The send button pulses, the input clears, the bubble flies up.
 *   • The agent's typing dots appear, then the reply slides in.
 *   • Repeat for three turns of conversation, anchored to three blurbs.
 *
 * The conversation completes around 90% scroll, leaving a brief moment of
 * stillness before the next section enters.
 */

type Bubble = {
  from: "user" | "agent";
  key: "msg1" | "msg2" | "msg3" | "msg4" | "msg5" | "msg6";
  preview?: boolean;
  /**
   * Hand-tuned scroll-progress timeline (0 — 1) for each bubble. Both ends
   * sit strictly inside [0, 1] so motion-dom's WAAPI backend doesn't reject
   * the keyframes.
   *
   * • For USER bubbles: `inputStart`/`inputEnd` is the typewriter window
   *   (the message being typed into the input field). `enterStart` is the
   *   moment the bubble actually flies into the chat.
   * • For AGENT bubbles: `typingStart` triggers the bouncing dots; the dots
   *   then fade and the bubble slides in over `enterStart`–`enterEnd`.
   */
  enterStart: number;
  enterEnd: number;
  typingStart?: number;
  inputStart?: number;
  inputEnd?: number;
};

const BUBBLES: Bubble[] = [
  // ─── Phase 1 — "Speak naturally" ─────────────────────────────────────────
  {
    from: "user",
    key: "msg1",
    inputStart: 0.04,
    inputEnd: 0.10,
    enterStart: 0.12,
    enterEnd: 0.16,
  },
  {
    from: "agent",
    key: "msg2",
    typingStart: 0.20,
    enterStart: 0.26,
    enterEnd: 0.32,
  },

  // ─── Phase 2 — "Grounded in Saudi law" ──────────────────────────────────
  {
    from: "user",
    key: "msg3",
    inputStart: 0.38,
    inputEnd: 0.44,
    enterStart: 0.46,
    enterEnd: 0.50,
  },
  {
    from: "agent",
    key: "msg4",
    typingStart: 0.54,
    enterStart: 0.60,
    enterEnd: 0.66,
    preview: true,
  },

  // ─── Phase 3 — "Iterate without losing context" ─────────────────────────
  {
    from: "user",
    key: "msg5",
    inputStart: 0.72,
    inputEnd: 0.78,
    enterStart: 0.80,
    enterEnd: 0.84,
  },
  {
    from: "agent",
    key: "msg6",
    typingStart: 0.86,
    enterStart: 0.90,
    enterEnd: 0.96,
  },
];

// Five marketing blurbs run alongside the chat. The chat itself only has
// three "phases" of conversation (msg1/msg2, msg3/msg4, msg5/msg6) — the
// extra two blurbs ride alongside the trailing portion of the scroll,
// reading like additional capability headlines while the chat sits in
// its completed state.
const BLURB_KEYS = ["blurb1", "blurb2", "blurb3", "blurb4", "blurb5"] as const;

// --- Component ---------------------------------------------------------------

export function ConversationScroll() {
  const t = useTranslations("marketing.conversation");
  const locale = useLocale();
  // The scroll target is the *grid* (chat + blurbs), not the whole section.
  // progress 0 then corresponds to the moment the chat becomes sticky and
  // fully fills the viewport — i.e. the moment the viewer "lands" on the
  // chat — instead of when the heading first peeks above the fold.
  const gridRef = useRef<HTMLDivElement>(null);

  const { scrollYProgress } = useScroll({
    target: gridRef,
    offset: ["start start", "end end"],
  });

  return (
    <section className="container py-20">
      {/* Heading */}
      <div className="text-center mb-14 md:mb-20 space-y-3 max-w-2xl mx-auto">
        <div className="text-xs uppercase tracking-[0.18em] text-accent">
          {t("kicker")}
        </div>
        <h2 className="text-3xl md:text-4xl font-bold tracking-tight">
          {t("title")}
        </h2>
        <div className="mx-auto gold-rule" />
        <p className="text-base text-muted-foreground">{t("subtitle")}</p>
      </div>

      <div
        ref={gridRef}
        className="grid md:grid-cols-2 gap-12 md:gap-12 lg:gap-20 relative"
      >
        {/* Sticky chat — leading edge (right in RTL, left in LTR) */}
        <div className="md:sticky md:top-0 md:h-screen flex md:items-center justify-center">
          <ChatWindow
            scrollYProgress={scrollYProgress}
            t={t}
            locale={locale}
          />
        </div>

        {/* Scrolling marketing copy — trailing edge. Five blurbs run past
            the sticky chat with a tight inter-blurb gap so the eye can
            move through all five capabilities quickly without long empty
            stretches of scroll between them. */}
        <div className="flex flex-col gap-[25vh] md:py-[35vh]">
          {BLURB_KEYS.map((key, i) => (
            <Blurb
              key={key}
              index={i}
              total={BLURB_KEYS.length}
              titleKey={`${key}.title`}
              bodyKey={`${key}.body`}
              progress={scrollYProgress}
              t={t}
            />
          ))}
        </div>
      </div>
    </section>
  );
}

// --- Blurb -------------------------------------------------------------------

function Blurb({
  index,
  total,
  titleKey,
  bodyKey,
  progress,
  t,
}: {
  index: number;
  total: number;
  titleKey: string;
  bodyKey: string;
  progress: MotionValue<number>;
  t: ReturnType<typeof useTranslations>;
}) {
  const start = index / total;
  const end = (index + 1) / total;
  const isFirst = index === 0;
  const isLast = index === total - 1;

  // Fade keypoints. The first blurb has *no* fade-in (it must be fully
  // visible the moment the user lands on the section — there's no
  // "previous blurb" to transition from). The last blurb has *no*
  // fade-out (the section ends with the conversation, so there's nothing
  // to transition to and dimming would just look like a bug). Middle
  // blurbs ramp 0.32 → 1 → 0.32 through their full window.
  const fadeIn = isFirst ? 0 : Math.max(0, start - 0.08);
  const peakStart = isFirst
    ? 0
    : Math.max(fadeIn + 0.001, start + 0.06);
  const peakEnd = isLast
    ? 1
    : Math.min(1, Math.max(peakStart + 0.001, end - 0.06));
  const fadeOut = isLast
    ? 1
    : Math.min(1, Math.max(peakEnd + 0.001, end + 0.08));

  // We compute opacity + translateY in a `useMotionValueEvent` callback
  // and apply them as plain inline styles. Driving these through motion
  // values + `<motion.div style={{...}}>` desynced on motion-dom v12's
  // WAAPI path — the blurb stayed faded even when its window was active.
  // Plain React state + inline style sidesteps that completely.
  const [styleState, setStyleState] = useState<{ opacity: number; ty: number }>(
    () => ({
      // First / last blurbs start (and end) fully visible at their natural
      // position. Middle blurbs start dim + offset and animate in.
      opacity: isFirst ? 1 : 0.32,
      ty: isFirst || isLast ? 0 : 16,
    }),
  );

  useMotionValueEvent(progress, "change", (p) => {
    let op = 0.32;
    if (p >= peakStart && p <= peakEnd) {
      op = 1;
    } else if (p > fadeIn && p < peakStart) {
      const k = (p - fadeIn) / (peakStart - fadeIn);
      op = 0.32 + k * (1 - 0.32);
    } else if (p > peakEnd && p < fadeOut) {
      const k = (p - peakEnd) / (fadeOut - peakEnd);
      op = 1 - k * (1 - 0.32);
    } else if (p >= fadeOut || p <= fadeIn) {
      op = 0.32;
    }

    // Translate-Y drift: 16 → -16 across [start, end], with the first /
    // last blurb pinned at 0 so they don't appear to "drift away" at the
    // section boundaries (where there's no neighbour to transition with).
    let ty = 0;
    if (isFirst || isLast) {
      ty = 0;
    } else if (p <= start) ty = 16;
    else if (p >= end) ty = -16;
    else ty = 16 - ((p - start) / (end - start)) * 32;

    setStyleState((prev) => {
      // Skip noise updates that won't repaint visibly.
      if (
        Math.abs(prev.opacity - op) < 0.005 &&
        Math.abs(prev.ty - ty) < 0.5
      ) {
        return prev;
      }
      return { opacity: op, ty };
    });
  });

  return (
    <div
      style={{
        opacity: styleState.opacity,
        transform: `translateY(${styleState.ty}px)`,
      }}
      className="space-y-4 will-change-[opacity,transform]"
    >
      <div className="flex items-center gap-3 text-xs font-semibold uppercase tracking-[0.2em] text-accent">
        <span className="font-bold">{`0${index + 1}`}</span>
        <span className="h-px flex-1 bg-gradient-to-r from-accent/60 to-transparent rtl:from-accent/60 rtl:to-transparent" />
      </div>
      <h3 className="text-2xl md:text-3xl font-bold tracking-tight">
        {t(titleKey)}
      </h3>
      <p className="text-base md:text-lg text-muted-foreground leading-relaxed">
        {t(bodyKey)}
      </p>
    </div>
  );
}

// --- Chat window -------------------------------------------------------------

function ChatWindow({
  scrollYProgress,
  t,
  locale,
}: {
  scrollYProgress: MotionValue<number>;
  t: ReturnType<typeof useTranslations>;
  locale: string;
}) {
  // User-message typewriter schedule, materialised once with the actual text.
  // The input field watches scroll progress and shows whichever message is
  // currently in its typing window.
  const userSchedule = BUBBLES
    .filter((b): b is Bubble & { inputStart: number; inputEnd: number } =>
      b.from === "user" && b.inputStart !== undefined && b.inputEnd !== undefined,
    )
    .map((b) => ({
      text: t(b.key),
      inputStart: b.inputStart,
      inputEnd: b.inputEnd,
      enterStart: b.enterStart,
    }));

  return (
    <div className="w-full max-w-md rounded-3xl border border-border/60 bg-card/85 backdrop-blur-md shadow-2xl overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-3 px-4 py-3 border-b border-border/60 bg-background/40">
        <div className="relative">
          <BrandLogo size={36} />
          <span className="absolute bottom-0 end-0 h-2.5 w-2.5 rounded-full bg-emerald-500 ring-2 ring-card" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-sm font-semibold truncate">{t("header")}</div>
          <div className="text-[11px] text-muted-foreground truncate">
            {t("online")}
          </div>
        </div>
      </div>

      {/* Messages — chat starts empty, fills top-down as the conversation
          unfolds. `justify-start` anchors content to the TOP, so msg1
          appears at the top, msg2 lands beneath it, etc. — exactly the
          way a real chat replay would feel. The container is sized to
          fit all six messages plus the preview card without clipping. */}
      <div className="px-4 pt-3 h-[32rem] overflow-hidden flex flex-col justify-start">
        {BUBBLES.map((b, i) => (
          <BubbleRow
            key={b.key}
            bubble={b}
            isFirst={i === 0}
            progress={scrollYProgress}
            t={t}
            youLabel={t("you")}
            locale={locale}
          />
        ))}
      </div>

      {/* Live input footer — shows the current user message being typed */}
      <ChatInput
        schedule={userSchedule}
        scrollYProgress={scrollYProgress}
        placeholder={locale === "ar" ? "اكتب رسالتك…" : "Type a message…"}
      />
    </div>
  );
}

// --- Single bubble row -------------------------------------------------------

function BubbleRow({
  bubble,
  isFirst,
  progress,
  t,
  youLabel,
  locale,
}: {
  bubble: Bubble;
  isFirst: boolean;
  progress: MotionValue<number>;
  t: ReturnType<typeof useTranslations>;
  youLabel: string;
  locale: string;
}) {
  const isUser = bubble.from === "user";
  const { enterStart, enterEnd } = bubble;

  // Typing-dots window. For user bubbles there are no dots, so the
  // "typing" keypoints collapse to micro-deltas just before `enterStart`
  // — this keeps the input array monotonic for motion-dom v12 while
  // contributing zero visible height.
  const hasTyping = bubble.typingStart !== undefined;
  const typingStart = hasTyping ? bubble.typingStart! : enterStart - 0.002;
  const typingPeak = hasTyping
    ? typingStart + Math.max(0.005, (enterStart - typingStart) * 0.35)
    : enterStart - 0.001;

  // The wrapper's height grows in two stages:
  //   • typingStart → typingPeak → enterStart : 0 → ~38px (room for the
  //     agent's bouncing typing dots, agent bubbles only).
  //   • enterStart  → enterEnd               : ~38 → 240 (room for the
  //     full bubble; the 240 ceiling is well above any natural height).
  // For user bubbles the first stage is a no-op (the keypoints sit on
  // top of each other and the value is 0 throughout).
  // We rely *only* on `maxHeight` + `overflow-hidden` to gate visibility —
  // not opacity — because driving opacity in parallel desynced from
  // maxHeight on motion-dom v12's WAAPI path.
  const wrapperMaxHeight = useTransform(
    progress,
    [typingStart, typingPeak, enterStart, enterEnd],
    hasTyping ? [0, 38, 38, 240] : [0, 0, 0, 240],
  );

  // Typing-dots visibility — agent only. We listen to scroll progress and
  // flip a React `boolean` instead of driving the dots' opacity through a
  // motion value. Motion-dom v12 routes opacity through its WAAPI backend,
  // which on this path desyncs from scroll progress (the dots stay painted
  // at full opacity even after their input range has been crossed). A
  // state-driven mount/unmount sidesteps that completely.
  const [typingVisible, setTypingVisible] = useState(false);
  useMotionValueEvent(progress, "change", (p) => {
    if (!hasTyping) return;
    const shouldShow = p >= typingStart && p < enterStart;
    setTypingVisible((prev) => (prev !== shouldShow ? shouldShow : prev));
  });

  return (
    <motion.div
      style={{ maxHeight: wrapperMaxHeight }}
      className="overflow-hidden"
    >
      <div className={isFirst ? "" : "pt-3"}>
        <div
          className={`flex ${
            isUser ? "justify-end" : "justify-start"
          } items-end gap-2`}
        >
          {/* Agent avatar — leading edge */}
          {!isUser && (
            <div className="shrink-0 mb-1">
              <BrandLogo size={22} />
            </div>
          )}

          <div
            className={`flex flex-col ${
              isUser ? "items-end" : "items-start"
            } max-w-[78%]`}
          >
            {/* Typing dots — agent only, conditionally mounted while the
                agent is "typing" the next reply. */}
            {!isUser && typingVisible && (
              <div
                className="rounded-2xl rounded-bl-sm bg-muted/70 px-3 py-2 mb-1"
                aria-hidden
              >
                <span className="inline-flex gap-1 items-center">
                  <Dot delay={0} />
                  <Dot delay={0.15} />
                  <Dot delay={0.3} />
                </span>
              </div>
            )}

            {/* The bubble itself */}
            <div
              className={
                isUser
                  ? "rounded-2xl rounded-br-sm bg-primary text-primary-foreground px-4 py-2 text-sm shadow-sm"
                  : "rounded-2xl rounded-bl-sm bg-muted text-foreground px-4 py-2 text-sm shadow-sm border border-border/40"
              }
            >
              {t(bubble.key)}
              {bubble.from === "agent" && bubble.preview && (
                <PreviewCard
                  title={t("previewTitle")}
                  line={t("previewLine")}
                />
              )}
              <div
                className={`text-[10px] mt-1 ${
                  isUser
                    ? "text-primary-foreground/70"
                    : "text-muted-foreground"
                }`}
              >
                {isUser ? `${youLabel} · ${t("now")}` : t("now")}
              </div>
            </div>
          </div>

          {/* User avatar — trailing edge */}
          {isUser && (
            <div
              className="shrink-0 mb-1 grid place-items-center h-6 w-6 rounded-full bg-accent/20 text-accent text-[10px] font-bold"
              aria-hidden
            >
              {locale === "ar" ? "أ" : "Y"}
            </div>
          )}
        </div>
      </div>
    </motion.div>
  );
}

// --- Live chat input (typewriter + send button pulse) -----------------------

type UserSlot = {
  text: string;
  inputStart: number;
  inputEnd: number;
  enterStart: number;
};

function ChatInput({
  schedule,
  scrollYProgress,
  placeholder,
}: {
  schedule: UserSlot[];
  scrollYProgress: MotionValue<number>;
  placeholder: string;
}) {
  const [typed, setTyped] = useState("");
  const sendPulse = useMotionValue(0); // 0 = idle, 1 = pulsing

  // Watch scroll progress and recompute the input's content.
  useMotionValueEvent(scrollYProgress, "change", (p) => {
    // Find which (if any) user slot we're currently inside.
    const active = schedule.find(
      (s) => p >= s.inputStart && p < s.enterStart,
    );

    if (!active) {
      if (typed !== "") setTyped("");
      return;
    }

    const span = active.inputEnd - active.inputStart;
    const fraction = Math.min(1, Math.max(0, (p - active.inputStart) / span));
    const charCount = Math.floor(active.text.length * fraction);
    const next = active.text.slice(0, charCount);
    if (next !== typed) setTyped(next);
  });

  // Pulse the send button right at each user message's `enterStart`.
  useMotionValueEvent(scrollYProgress, "change", (p) => {
    for (const s of schedule) {
      // tight ±0.004 window catches the cross even at sub-frame scroll deltas
      if (Math.abs(p - s.enterStart) < 0.004) {
        sendPulse.set(1);
        // ramp back down on the next animation frame
        requestAnimationFrame(() => sendPulse.set(0));
      }
    }
  });

  const sendScale = useTransform(sendPulse, [0, 1], [1, 1.18]);
  const sendGlow = useTransform(sendPulse, [0, 1], [0, 0.6]);
  // gentle caret blink while typing
  const isTyping = typed.length > 0;

  return (
    <div className="px-4 py-3 border-t border-border/60 bg-background/40 flex items-center gap-2">
      <div className="flex-1 h-9 rounded-full border border-border/60 bg-background/60 px-4 flex items-center text-xs">
        {isTyping ? (
          <span className="text-foreground truncate">
            {typed}
            <Caret />
          </span>
        ) : (
          <span className="text-muted-foreground truncate">{placeholder}</span>
        )}
      </div>
      <motion.button
        type="button"
        style={{ scale: sendScale }}
        className="relative grid place-items-center h-9 w-9 rounded-full bg-primary text-primary-foreground shadow-md"
        aria-hidden
        tabIndex={-1}
      >
        {/* Soft gold halo on send pulse */}
        <motion.span
          aria-hidden
          style={{
            opacity: sendGlow,
            boxShadow: "0 0 0 6px hsl(36 60% 55% / 0.35)",
          }}
          className="absolute inset-0 rounded-full"
        />
        <Send className="h-4 w-4 rtl:scale-x-[-1] relative" />
      </motion.button>
    </div>
  );
}

// --- Atoms -------------------------------------------------------------------

function Caret() {
  return (
    <span
      aria-hidden
      className="inline-block w-[2px] h-[12px] align-middle bg-primary/70 ms-0.5"
      style={{ animation: "caret-blink 1s steps(1) infinite" }}
    />
  );
}

function Dot({ delay }: { delay: number }) {
  // Plain CSS animation rather than framer-motion `animate` because
  // motion-dom 12.x's WAAPI backend rejects the keyframe offsets when a
  // `delay` is present alongside `repeat: Infinity`.
  return (
    <span
      className="typing-dot h-1.5 w-1.5 rounded-full bg-muted-foreground/70"
      style={{ animationDelay: `${delay}s` }}
    />
  );
}

function PreviewCard({ title, line }: { title: string; line: string }) {
  return (
    <div className="mt-2 rounded-xl border border-accent/40 bg-background/60 p-2.5 flex items-center gap-2.5">
      <div className="grid place-items-center h-8 w-8 rounded-md bg-accent/15 text-accent shrink-0">
        <FileText className="h-4 w-4" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="text-xs font-semibold truncate text-foreground">
          {title}
        </div>
        <div className="text-[10px] text-muted-foreground flex items-center gap-1 truncate">
          <Check className="h-3 w-3 text-emerald-500 shrink-0" />
          {line}
        </div>
      </div>
    </div>
  );
}
