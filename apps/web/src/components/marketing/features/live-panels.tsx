"use client";

/**
 * "Live product UI" panels *exclusive to the /features page* — entirely
 * different from the home page's WorkbenchMockup / OperationsMockup.
 *
 *   • DraftingStudioPanel — a live document editor: word-by-word
 *     typewriter into a paragraph, citation chips that highlight as
 *     relevant text appears, a side suggestions stack, auto-save status.
 *
 *   • MatterStreamPanel — a live activity feed of matters: events stream
 *     into the top of the list (intake opened, deadline approaching,
 *     contract signed, etc.) and the older ones scroll down and dim.
 *
 * Both run phase-driven state machines on a loop so they read as the
 * actual product working in real time, not a one-off animation.
 */
import { AnimatePresence, motion } from "framer-motion";
import {
  AlertCircle,
  CalendarClock,
  CheckCircle2,
  FileSignature,
  Inbox,
  MessageSquare,
  Quote,
  Save,
  ScrollText,
  Sparkles,
} from "lucide-react";
import * as React from "react";

/* ────────────────────────────────────────────────────────────────────────── */
/*  Phase-cycle helper                                                         */
/* ────────────────────────────────────────────────────────────────────────── */

function usePhase(totalPhases: number, intervalMs: number) {
  const [phase, setPhase] = React.useState(0);
  React.useEffect(() => {
    const id = setInterval(() => {
      setPhase((p) => (p + 1) % totalPhases);
    }, intervalMs);
    return () => clearInterval(id);
  }, [totalPhases, intervalMs]);
  return phase;
}

/* ============================================================================
   DraftingStudioPanel — live drafting session
   ============================================================================

   Phases (0…5, each 1.6s):
     0  empty editor, cursor blinking
     1  first sentence typewritten in
     2  second sentence (with [ Art. 9 ] inline citation chip) appears
     3  third sentence + a green check ("clause approved") appears in margin
     4  amber "missing definition" pill appears in margin
     5  hold — "saved · v3" badge in footer · then resets
============================================================================ */

const DRAFTING_SENTENCES_EN = [
  "This Agreement is entered into by and between the Parties under the laws of the Kingdom of Saudi Arabia.",
  "Confidential Information shall remain confidential for a period of twenty-four (24) months from disclosure.",
  "Neither Party may circumvent the other by engaging directly with introduced counterparties.",
];

const DRAFTING_SENTENCES_AR = [
  "تُبرَم هذه الاتفاقية بين الطرفين وفقًا لأنظمة المملكة العربية السعودية.",
  "تظل المعلومات السرية محميةً لمدة أربعة وعشرين (٢٤) شهرًا من تاريخ الإفصاح.",
  "لا يجوز لأي طرف الالتفاف على الآخر بالتعاقد مع الجهات التي تم تقديمها.",
];

export function DraftingStudioPanel({ locale }: { locale: string }) {
  const isAr = locale === "ar";
  const sentences = isAr ? DRAFTING_SENTENCES_AR : DRAFTING_SENTENCES_EN;
  const phase = usePhase(6, 1600);

  // How many sentences are fully visible
  const completed = Math.min(phase, sentences.length);
  // Whether we're currently "typing" the next sentence (between phase ticks)
  const typing = phase > 0 && phase <= sentences.length;
  // Active sentence index (the one being typed)
  const typingIndex = completed;

  // Margin annotations land after sentence 2 (phase ≥ 3) and sentence 3 (phase ≥ 4)
  const annotations = [
    { showAt: 3, variant: "ok" as const, text: isAr ? "بند مقبول" : "Clause approved" },
    { showAt: 4, variant: "warn" as const, text: isAr ? "تعريف ناقص" : "Definition missing" },
  ];

  return (
    <DarkPanel>
      <DarkHeader>
        <div className="flex items-center gap-2 text-xs text-white/70">
          <FileSignature className="h-3.5 w-3.5 text-amber-300" />
          <span className="font-medium text-white/85">
            NDA-Acme.<span className="text-amber-300">v3</span>.docx
          </span>
        </div>
        <div className="flex items-center gap-2 text-[10px] text-white/45">
          <span className="inline-flex items-center gap-1">
            <span className="relative flex h-1.5 w-1.5">
              <span className="absolute inset-0 animate-ping rounded-full bg-emerald-400 opacity-60" />
              <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-emerald-400" />
            </span>
            <span className="text-emerald-300 font-medium">
              {isAr ? "تحرير" : "Editing"}
            </span>
          </span>
        </div>
      </DarkHeader>

      <div className="grid grid-cols-[minmax(0,2.2fr)_minmax(0,1fr)] gap-3 px-4 py-4">
        {/* Document editor */}
        <div className="rounded-xl border border-white/[0.08] bg-black/40 p-3.5">
          <div className="text-[9px] uppercase tracking-widest text-white/40 mb-2.5">
            {isAr ? "النص الحالي" : "Live draft"}
          </div>

          <div className="space-y-2.5 min-h-[140px]">
            {sentences.map((sentence, i) => {
              if (i < completed) {
                return <Sentence key={i} text={sentence} index={i} isAr={isAr} />;
              }
              if (i === typingIndex && typing) {
                return (
                  <TypingSentence
                    key={`typing-${phase}`}
                    text={sentence}
                    durationMs={1500}
                    isAr={isAr}
                  />
                );
              }
              return null;
            })}

            {/* Caret on idle (phase 0) */}
            {phase === 0 && (
              <div className="flex items-center gap-1 text-white/30 text-[11px]">
                <span className="inline-block w-[2px] h-3 bg-amber-300 align-middle animate-pulse" />
              </div>
            )}
          </div>
        </div>

        {/* Margin annotations */}
        <div className="rounded-xl border border-white/[0.08] bg-black/40 p-3 flex flex-col">
          <div className="text-[9px] uppercase tracking-widest text-white/40 mb-2.5">
            {isAr ? "ملاحظات الذكاء" : "AI margin"}
          </div>

          <div className="space-y-2 flex-1">
            <AnimatePresence initial={false}>
              {annotations
                .filter((a) => phase >= a.showAt)
                .map((a) => (
                  <Annotation
                    key={a.text}
                    variant={a.variant}
                    text={a.text}
                  />
                ))}
            </AnimatePresence>

            {phase >= 5 && (
              <motion.div
                initial={{ opacity: 0, y: -4 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4 }}
                className="rounded-md border border-emerald-400/30 bg-emerald-500/[0.08] px-2 py-1.5"
              >
                <div className="flex items-center gap-1.5">
                  <Sparkles className="h-3 w-3 text-emerald-300" />
                  <span className="text-[10px] font-medium text-emerald-200">
                    {isAr ? "ملخص جاهز" : "Summary ready"}
                  </span>
                </div>
              </motion.div>
            )}
          </div>
        </div>
      </div>

      <DarkFooter>
        <FooterStat
          icon={<Save className="h-3 w-3" />}
          label={isAr ? "حُفظ" : "Saved"}
          value={phase >= 5 ? (isAr ? "نسخة ٣" : "v3") : isAr ? "تلقائي" : "auto"}
        />
        <FooterStat
          icon={<Quote className="h-3 w-3" />}
          label={isAr ? "استشهادات" : "Citations"}
          value={String(Math.min(2, Math.max(0, phase - 1)))}
        />
        <FooterStat
          icon={<ScrollText className="h-3 w-3" />}
          label={isAr ? "كلمات" : "Words"}
          value={String(40 + completed * 24 + (typing ? 10 : 0))}
        />
      </DarkFooter>
    </DarkPanel>
  );
}

/* ----- Drafting helpers ----- */

function Sentence({
  text,
  index,
  isAr,
}: {
  text: string;
  index: number;
  isAr: boolean;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className="text-[11px] leading-relaxed text-white/85"
    >
      {/* Render the sentence; injecting an inline citation chip for the
          second sentence (the one about confidentiality). */}
      {index === 1 ? (
        <>
          {text}
          <InlineCite label={isAr ? "م. ٩" : "Art. 9"} />
        </>
      ) : (
        text
      )}
    </motion.div>
  );
}

function TypingSentence({
  text,
  durationMs,
  isAr,
}: {
  text: string;
  durationMs: number;
  isAr: boolean;
}) {
  const [shown, setShown] = React.useState(0);
  React.useEffect(() => {
    const step = Math.max(20, Math.floor(durationMs / text.length));
    const id = setInterval(() => {
      setShown((s) => Math.min(s + 1, text.length));
    }, step);
    return () => clearInterval(id);
  }, [text, durationMs]);

  return (
    <div className="text-[11px] leading-relaxed text-white/85">
      <span>{text.slice(0, shown)}</span>
      <span
        aria-hidden
        className="inline-block w-[2px] h-3 align-middle bg-amber-300 ms-0.5 animate-pulse"
      />
      {/* invisible suffix to preserve line height */}
      <span className="text-transparent select-none">
        {text.slice(shown) || (isAr ? "." : ".")}
      </span>
    </div>
  );
}

function InlineCite({ label }: { label: string }) {
  return (
    <motion.span
      initial={{ opacity: 0, scale: 0.7 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ delay: 0.2, type: "spring", stiffness: 360, damping: 24 }}
      className="ms-1 inline-flex items-center gap-1 rounded-md bg-amber-500/20 px-1.5 py-0.5 text-[9px] font-semibold text-amber-200 align-middle"
    >
      <Quote className="h-2.5 w-2.5" />
      {label}
    </motion.span>
  );
}

function Annotation({
  variant,
  text,
}: {
  variant: "ok" | "warn";
  text: string;
}) {
  return (
    <motion.div
      layout
      initial={{ opacity: 0, x: 8, scale: 0.96 }}
      animate={{ opacity: 1, x: 0, scale: 1 }}
      exit={{ opacity: 0, x: 8 }}
      transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
      className={
        variant === "ok"
          ? "flex items-center gap-1.5 rounded-md border border-emerald-400/30 bg-emerald-500/[0.08] px-2 py-1.5"
          : "flex items-center gap-1.5 rounded-md border border-amber-400/30 bg-amber-500/[0.08] px-2 py-1.5"
      }
    >
      {variant === "ok" ? (
        <CheckCircle2 className="h-3 w-3 text-emerald-300" />
      ) : (
        <AlertCircle className="h-3 w-3 text-amber-300" />
      )}
      <span
        className={
          variant === "ok"
            ? "text-[10px] font-medium text-emerald-200"
            : "text-[10px] font-medium text-amber-200"
        }
      >
        {text}
      </span>
    </motion.div>
  );
}

/* ============================================================================
   MatterStreamPanel — live activity feed of matters across the firm.
   ============================================================================

   The panel shows a stream of recent events. A new event lands at the
   top of the list every ~1.6s; the oldest event scrolls off the bottom.
   A subtle pulse indicates "an event was just received".
============================================================================ */

type Severity = "info" | "ok" | "warn";

type MatterEvent = {
  kind: "intake" | "message" | "deadline" | "signed" | "review";
  client: string;
  detail: string;
  time: string;
  severity: Severity;
};

const EVENTS_EN: MatterEvent[] = [
  {
    kind: "intake",
    client: "Acme Co.",
    detail: "new contract review · intake opened",
    time: "just now",
    severity: "info",
  },
  {
    kind: "message",
    client: "Faris Group",
    detail: "client replied on WhatsApp · 2 questions",
    time: "1m ago",
    severity: "info",
  },
  {
    kind: "deadline",
    client: "Nile Partners",
    detail: "response deadline in 6h",
    time: "3m ago",
    severity: "warn",
  },
  {
    kind: "signed",
    client: "Riyadh Holding",
    detail: "NDA-v2 signed · PDF filed",
    time: "8m ago",
    severity: "ok",
  },
  {
    kind: "review",
    client: "Jeddah Logistics",
    detail: "risk review complete · 1 flag",
    time: "12m ago",
    severity: "warn",
  },
  {
    kind: "intake",
    client: "Al-Salam Ltd.",
    detail: "intake qualified · matter opened",
    time: "18m ago",
    severity: "info",
  },
];

const EVENTS_AR: MatterEvent[] = [
  {
    kind: "intake",
    client: "Acme Co.",
    detail: "مراجعة عقد جديدة · فُتح ملف",
    time: "الآن",
    severity: "info",
  },
  {
    kind: "message",
    client: "مجموعة فارس",
    detail: "ردّ العميل على واتساب · سؤالان",
    time: "قبل ١د",
    severity: "info",
  },
  {
    kind: "deadline",
    client: "النيل للمحاماة",
    detail: "موعد الردّ خلال ٦ ساعات",
    time: "قبل ٣د",
    severity: "warn",
  },
  {
    kind: "signed",
    client: "الرياض القابضة",
    detail: "تم توقيع NDA · أُرشف الملف",
    time: "قبل ٨د",
    severity: "ok",
  },
  {
    kind: "review",
    client: "جدة للخدمات اللوجستية",
    detail: "اكتملت مراجعة المخاطر · علامة",
    time: "قبل ١٢د",
    severity: "warn",
  },
  {
    kind: "intake",
    client: "السلام المحدودة",
    detail: "تأهيل · فُتح ملف القضية",
    time: "قبل ١٨د",
    severity: "info",
  },
];

const EVENT_ICONS = {
  intake: Inbox,
  message: MessageSquare,
  deadline: CalendarClock,
  signed: FileSignature,
  review: CheckCircle2,
} as const;

export function MatterStreamPanel({ locale }: { locale: string }) {
  const isAr = locale === "ar";
  const baseEvents = isAr ? EVENTS_AR : EVENTS_EN;
  // We keep a "head index" that advances every tick; the top 5 events
  // shown are derived from rotating the array starting at the head.
  const phase = usePhase(baseEvents.length, 1600);

  const visible = React.useMemo(() => {
    const out: MatterEvent[] = [];
    for (let i = 0; i < 5; i++) {
      out.push(baseEvents[(phase + i) % baseEvents.length]);
    }
    return out;
  }, [phase, baseEvents]);

  // Aggregate stats — tick subtly with the phase
  const todayCount = 12 + (phase % 4);
  const openCount = 7 + ((phase + 1) % 3);

  return (
    <DarkPanel>
      <DarkHeader>
        <div className="flex items-center gap-2 text-xs text-white/70">
          <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-500/15 px-2 py-0.5 text-[10px] font-medium text-emerald-300">
            <span className="relative flex h-1.5 w-1.5">
              <span className="absolute inset-0 animate-ping rounded-full bg-emerald-400 opacity-60" />
              <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-emerald-400" />
            </span>
            {isAr ? "متصل" : "LIVE"}
          </span>
          <span className="font-medium text-white/85">
            {isAr ? "تدفّق القضايا" : "Matter stream"}
          </span>
        </div>
        <div className="text-[10px] text-white/45">
          {isAr ? "اليوم" : "Today"}
        </div>
      </DarkHeader>

      <div className="px-4 py-4">
        {/* Fixed height + `overflow-hidden` keeps the panel a stable size
            while items animate in/out. `popLayout` removes the exiting row
            from the layout flow immediately so its space doesn't briefly
            push the container taller. Stable keys (by client) mean only the
            single new/old event animates per tick — the other 4 just shift
            via the `layout` prop. */}
        <ul className="relative h-[218px] space-y-1.5 overflow-hidden">
          <AnimatePresence initial={false} mode="popLayout">
            {visible.map((event, idx) => (
              <EventRow key={event.client} event={event} rank={idx} />
            ))}
          </AnimatePresence>
        </ul>
      </div>

      <DarkFooter>
        <FooterStat
          icon={<Inbox className="h-3 w-3" />}
          label={isAr ? "اليوم" : "Today"}
          value={String(todayCount)}
        />
        <FooterStat
          icon={<CheckCircle2 className="h-3 w-3" />}
          label={isAr ? "مفتوحة" : "Open"}
          value={String(openCount)}
        />
        <FooterStat
          icon={<CalendarClock className="h-3 w-3" />}
          label={isAr ? "اليوم" : "Due"}
          value="3"
        />
      </DarkFooter>
    </DarkPanel>
  );
}

function EventRow({ event, rank }: { event: MatterEvent; rank: number }) {
  const Icon = EVENT_ICONS[event.kind];
  const isTop = rank === 0;
  // Older events fade more
  const opacity = 1 - rank * 0.14;

  return (
    <motion.li
      layout
      initial={{ opacity: 0, y: -16, scale: 0.96 }}
      animate={{ opacity, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: 12, scale: 0.96 }}
      transition={{ duration: 0.45, ease: [0.16, 1, 0.3, 1] }}
      className={
        isTop
          ? "relative flex items-center gap-2.5 rounded-md border border-amber-400/30 bg-amber-500/[0.06] px-2.5 py-1.5"
          : "relative flex items-center gap-2.5 rounded-md bg-white/[0.03] px-2.5 py-1.5"
      }
    >
      <span
        className={
          event.severity === "ok"
            ? "inline-grid place-items-center h-6 w-6 rounded-full bg-emerald-500/20 text-emerald-300"
            : event.severity === "warn"
            ? "inline-grid place-items-center h-6 w-6 rounded-full bg-amber-500/20 text-amber-300"
            : "inline-grid place-items-center h-6 w-6 rounded-full bg-white/10 text-white/70"
        }
      >
        <Icon className="h-3 w-3" />
      </span>

      <div className="min-w-0 flex-1">
        <div className="flex items-baseline gap-1.5">
          <span className="truncate text-[11px] font-semibold text-white/90">
            {event.client}
          </span>
          <span className="text-[9px] text-white/40 truncate">
            · {event.detail}
          </span>
        </div>
      </div>

      <span className="text-[9px] text-white/45 shrink-0">{event.time}</span>

      {isTop && (
        <motion.span
          aria-hidden
          initial={{ opacity: 0.6, scale: 0.8 }}
          animate={{ opacity: 0, scale: 1.6 }}
          transition={{ duration: 1.2, repeat: 1 }}
          className="absolute -end-1 top-1/2 -translate-y-1/2 h-2 w-2 rounded-full bg-amber-400/70"
        />
      )}
    </motion.li>
  );
}

/* ────────────────────────────────────────────────────────────────────────── */
/*  Shared dark-panel primitives                                              */
/* ────────────────────────────────────────────────────────────────────────── */

function DarkPanel({ children }: { children: React.ReactNode }) {
  return (
    <div
      className="relative w-full overflow-hidden rounded-2xl border border-white/[0.08] shadow-[0_30px_80px_-30px_hsl(160_65%_15%/0.5)]"
      style={{
        background:
          "linear-gradient(150deg, hsl(165 30% 9%) 0%, hsl(165 28% 11%) 100%)",
      }}
    >
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 opacity-[0.07]"
        style={{
          backgroundImage:
            "radial-gradient(circle at 1px 1px, white 1px, transparent 0)",
          backgroundSize: "14px 14px",
        }}
      />
      <div
        aria-hidden
        className="pointer-events-none absolute -top-12 -end-12 h-40 w-40 rounded-full opacity-30"
        style={{
          background:
            "radial-gradient(closest-side, hsl(36 70% 60% / 0.5), transparent 70%)",
        }}
      />
      <div className="relative">{children}</div>
    </div>
  );
}

function DarkHeader({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between border-b border-white/5 bg-black/20 px-4 py-2.5">
      {children}
    </div>
  );
}

function DarkFooter({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3 border-t border-white/5 bg-black/20 px-4 py-2.5">
      {children}
    </div>
  );
}

function FooterStat({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div className="flex items-center gap-1.5 text-[10px]">
      <span className="text-white/45">{icon}</span>
      <span className="text-white/40 uppercase tracking-wider text-[9px]">
        {label}
      </span>
      <span className="font-semibold tabular-nums text-white/85">{value}</span>
    </div>
  );
}
