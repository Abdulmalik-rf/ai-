"use client";

/**
 * "Live product UI" mockups for the marketing feature rows.
 *
 * Both panels run a phase-driven state machine on a loop, so the panels
 * read as the actual product working in real time — risk items are
 * analysed one after another, citation cards swap, the chat fills in
 * client → agent → reply, and the workflow steps tick green as they
 * complete. Then the loop restarts.
 *
 * Loop cadence is ~1.4 s per phase. The whole sequence resets cleanly so
 * the panels look like a continuously running dashboard rather than a
 * one-off animation that finishes and goes dead.
 */
import { AnimatePresence, motion } from "framer-motion";
import { Check, FileText, MessageCircle, Search, Sparkles } from "lucide-react";
import * as React from "react";

import { BrandLogo } from "@/components/brand-logo";

/* ────────────────────────────────────────────────────────────────────────── */
/*  Phase cycle helper                                                        */
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

/* ────────────────────────────────────────────────────────────────────────── */
/*  WorkbenchMockup — live legal-AI dashboard                                 */
/*                                                                            */
/*  Phases (0…5, each 1.4s):                                                   */
/*    0  fresh start — citation card visible, no items yet                     */
/*    1  item 1 lands ✓  Termination clause valid                              */
/*    2  item 2 lands ⚠  Non-compete scope too broad                           */
/*    3  item 3 lands ✓  Confidentiality compliant                             */
/*    4  item 4 lands ⚠  Missing governing-law clause                          */
/*    5  hold — "run complete", then reset to 0                                */
/* ────────────────────────────────────────────────────────────────────────── */

type RiskItem = { label: string; variant: "ok" | "warn" };

export function WorkbenchMockup({ locale }: { locale: string }) {
  const isAr = locale === "ar";
  const phase = usePhase(6, 1400);

  const items: RiskItem[] = isAr
    ? [
        { label: "بند الإنهاء صحيح", variant: "ok" },
        { label: "عدم المنافسة واسع جدًا", variant: "warn" },
        { label: "السرية متوافقة", variant: "ok" },
        { label: "نقص قانون الاختصاص", variant: "warn" },
      ]
    : [
        { label: "Termination clause valid", variant: "ok" },
        { label: "Non-compete scope too broad", variant: "warn" },
        { label: "Confidentiality compliant", variant: "ok" },
        { label: "Governing-law clause missing", variant: "warn" },
      ];

  // Number of items currently "landed" (visible with status).
  const completed = Math.min(phase, items.length);
  // Whether we're currently analysing the next item (between phases).
  const analysing = phase > 0 && phase <= items.length;
  // Progress percentage along the 4-item run.
  const progress = Math.min(100, Math.round((completed / items.length) * 100));

  const suggestions = isAr
    ? [
        "بدء التحليل…",
        "تحليل بند عدم المنافسة…",
        "تحليل بند السرية…",
        "اقتراح بند الاختصاص القضائي…",
        "تجهيز ملخص المخاطر…",
        "اكتمل التشغيل · حُفظت v2",
      ]
    : [
        "Starting analysis…",
        "Analysing non-compete clause…",
        "Analysing confidentiality…",
        "Suggesting governing-law clause…",
        "Preparing risk summary…",
        "Run complete · saved as v2",
      ];

  // Citation card cycles between two articles for visual life.
  const cite = phase < 3
    ? {
        article: isAr ? "المادة ٩" : "Article 9",
        law: isAr ? "نظام مكافحة الغش التجاري" : "Anti-Commercial Fraud Law",
        year: isAr ? "١٤٤٢ هـ" : "2020",
        excerpt: isAr
          ? "يُحظر تضمين أي بند تعاقدي يُخالف الأحكام الآمرة ويُعرّض المُتعاقد لخسائر…"
          : "Any contractual clause that conflicts with the mandatory provisions and exposes the contracting party to undue loss is prohibited…",
      }
    : {
        article: isAr ? "المادة ٧٢" : "Article 72",
        law: isAr ? "نظام العمل" : "Labor Law",
        year: isAr ? "١٤٢٦ هـ" : "2005",
        excerpt: isAr
          ? "لا يجوز للعامل الالتزام بعدم منافسة صاحب العمل إلا وفق شروط النطاق الزماني والمكاني…"
          : "An employee may only be bound by a non-compete clause subject to time and territorial scope conditions…",
      };

  return (
    <DarkPanel>
      <PanelHeader>
        <div className="flex items-center gap-2 text-xs text-white/70">
          <LivePill label={isAr ? "متصل" : "LIVE"} />
          <span className="font-medium text-white/85">
            {isAr ? "بحث قانوني" : "Legal research"}
          </span>
        </div>
        <div className="text-[10px] text-white/45">
          {isAr ? "آخر ٧ أيام" : "Last 7 days"}
        </div>
      </PanelHeader>

      {/* Citation card — content cross-fades when it swaps.
          The text region has a fixed height so the card doesn't collapse
          for a frame when the previous citation exits before the next
          enters; the new one slides into reserved space. */}
      <div className="px-4 pt-4 pb-3">
        <div className="rounded-xl border border-amber-500/25 bg-amber-500/[0.06] p-3">
          <div className="relative h-[52px]">
            <AnimatePresence>
              <motion.div
                key={cite.article}
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
                className="absolute inset-0"
              >
                <div className="flex items-center gap-2">
                  <span className="inline-flex items-center gap-1 rounded-md bg-amber-500/20 px-1.5 py-0.5 text-[10px] font-semibold text-amber-300">
                    {cite.article}
                  </span>
                  <span className="truncate text-[11px] text-white/65">
                    {cite.law}
                  </span>
                  <span className="ms-auto text-[10px] text-white/35">
                    {cite.year}
                  </span>
                </div>
                <p className="mt-2 line-clamp-2 text-[11px] leading-relaxed text-white/75">
                  {cite.excerpt}
                </p>
              </motion.div>
            </AnimatePresence>
          </div>
          <div className="mt-2.5 flex items-center gap-2">
            <ChipButton
              icon={<Sparkles className="h-3 w-3" />}
              label={isAr ? "اقتبس" : "Cite"}
              primary
            />
            <ChipButton
              icon={<Search className="h-3 w-3" />}
              label={isAr ? "اعرض المصدر" : "View source"}
            />
          </div>
        </div>
      </div>

      {/* Risk analysis — items land one-by-one */}
      <div className="border-t border-white/5 px-4 py-3">
        <div className="mb-2 flex items-center justify-between">
          <span className="text-[11px] font-semibold text-white/80">
            {isAr
              ? `تحليل المخاطر · ${items.length} بنود`
              : `Risk analysis · ${items.length} items`}
          </span>
          <span className="text-[10px] text-white/40">
            {progress}% {isAr ? "اكتمل" : "done"}
          </span>
        </div>

        {/* Progress bar */}
        <div className="mb-2 h-1 overflow-hidden rounded-full bg-white/[0.06]">
          <motion.div
            className="h-full rounded-full bg-gradient-to-r from-emerald-400 to-amber-300"
            animate={{ width: `${progress}%` }}
            transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
          />
        </div>

        {/*
          Fixed-height container so the panel doesn't grow / shrink as
          items are added — keeps the page layout stable through every
          phase of the loop. Slot height = 5 rows × 30px + 4 × 6px gap.
        */}
        <div className="relative h-[174px]">
          <div className="space-y-1.5">
            {/* Completed items */}
            <AnimatePresence initial={false}>
              {items.slice(0, completed).map((r) => (
                <motion.div
                  key={r.label}
                  layout
                  initial={{ opacity: 0, y: -4, scale: 0.98 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, y: -4 }}
                  transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
                  className="flex items-center gap-2 rounded-md bg-white/[0.03] px-2.5 py-1.5"
                >
                  <StatusDot variant={r.variant} />
                  <span className="flex-1 truncate text-[11px] text-white/80">
                    {r.label}
                  </span>
                  <span
                    className={
                      r.variant === "ok"
                        ? "rounded-full bg-emerald-500/15 px-1.5 py-0.5 text-[9px] font-medium text-emerald-300"
                        : "rounded-full bg-amber-500/15 px-1.5 py-0.5 text-[9px] font-medium text-amber-300"
                    }
                  >
                    {r.variant === "ok"
                      ? isAr ? "سليم" : "OK"
                      : isAr ? "تحقق" : "Review"}
                  </span>
                </motion.div>
              ))}
            </AnimatePresence>

            {/* "Now analysing…" row — shown while a next item is being processed */}
            <AnimatePresence>
              {analysing && completed < items.length && (
                <motion.div
                  key={`analysing-${completed}`}
                  initial={{ opacity: 0, y: -4 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: 4 }}
                  transition={{ duration: 0.3 }}
                  className="flex items-center gap-2 rounded-md border border-dashed border-white/10 px-2.5 py-1.5"
                >
                  <span className="relative inline-flex h-4 w-4 items-center justify-center">
                    <span className="absolute inset-0 animate-ping rounded-full bg-amber-300/30" />
                    <span className="relative h-1.5 w-1.5 rounded-full bg-amber-300" />
                  </span>
                  <span className="flex-1 truncate text-[11px] text-white/55">
                    {items[completed]?.label}
                  </span>
                  <Dots />
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>

        {/* Live suggestion / status line */}
        <div className="mt-2 h-4 overflow-hidden">
          <AnimatePresence mode="wait">
            <motion.div
              key={phase}
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              transition={{ duration: 0.25 }}
              className="text-[10px] text-white/45"
            >
              {suggestions[phase]}
            </motion.div>
          </AnimatePresence>
        </div>
      </div>

      <PanelFooter>
        <Stat label={isAr ? "متوسط الردّ" : "Avg reply"} value="~3.2s" />
        <Stat label={isAr ? "موثَّق" : "Cited"} value="99%" />
        <Stat label={isAr ? "اللغة" : "Lang"} value="AR · EN" />
      </PanelFooter>
    </DarkPanel>
  );
}

/* ────────────────────────────────────────────────────────────────────────── */
/*  OperationsMockup — live chat + workflow                                   */
/*                                                                            */
/*  Phases (0…6, each 1.4s):                                                   */
/*    0  fresh — both panels empty                                             */
/*    1  client message lands in chat                                          */
/*    2  intent detected ✓  + agent typing dots                                */
/*    3  client matched ✓  + agent reply slides in                             */
/*    4  drafting reply (spinner) — chat message tail-of-thread appears        */
/*    5  notify lawyer ✓                                                       */
/*    6  hold — "matter open · escalated", then reset to 0                     */
/* ────────────────────────────────────────────────────────────────────────── */

type StepVariant = "ok" | "warn" | "progress" | "idle";
type WorkflowStep = {
  label: string;
  detail: string;
  icon: React.ReactNode;
};

export function OperationsMockup({ locale }: { locale: string }) {
  const isAr = locale === "ar";
  const phase = usePhase(7, 1400);

  const steps: WorkflowStep[] = isAr
    ? [
        {
          label: "تحديد القصد",
          detail: "مراجعة عقد عمل · 0.97",
          icon: <Sparkles className="h-3 w-3" />,
        },
        {
          label: "مطابقة العميل",
          detail: "Acme Co. · موكِّل قائم",
          icon: <FileText className="h-3 w-3" />,
        },
        {
          label: "صياغة الردّ",
          detail: "ضمن السياق · ~3s",
          icon: <MessageCircle className="h-3 w-3" />,
        },
        {
          label: "إشعار المحامي",
          detail: "تم التصعيد",
          icon: <Check className="h-3 w-3" />,
        },
      ]
    : [
        {
          label: "Intent detected",
          detail: "contract_review · 0.97",
          icon: <Sparkles className="h-3 w-3" />,
        },
        {
          label: "Client matched",
          detail: "Acme Co. · existing client",
          icon: <FileText className="h-3 w-3" />,
        },
        {
          label: "Drafting reply",
          detail: "in-context · ~3s",
          icon: <MessageCircle className="h-3 w-3" />,
        },
        {
          label: "Notify lawyer",
          detail: "escalated",
          icon: <Check className="h-3 w-3" />,
        },
      ];

  // Step variants per phase:
  //   phase 0 → all idle
  //   phase 1 → step 0 progress
  //   phase 2 → step 0 ok, step 1 progress
  //   phase 3 → step 0/1 ok, step 2 progress
  //   phase 4 → step 0/1 ok, step 2 still progress (drafting)
  //   phase 5 → step 0/1/2 ok, step 3 progress
  //   phase 6 → all ok
  const stepVariants: StepVariant[] = [
    phase >= 2 ? "ok" : phase === 1 ? "progress" : "idle",
    phase >= 3 ? "ok" : phase === 2 ? "progress" : "idle",
    phase >= 5 ? "ok" : phase >= 3 ? "progress" : "idle",
    phase >= 6 ? "ok" : phase === 5 ? "progress" : "idle",
  ];

  // Chat content per phase
  const showClientMsg = phase >= 1;
  const showAgentTyping = phase === 2 || phase === 4;
  const showAgentReply = phase >= 3;
  const showFollowupMsg = phase >= 4;

  return (
    <DarkPanel>
      <PanelHeader>
        <div className="flex items-center gap-2 text-xs text-white/70">
          <LivePill label={isAr ? "متصل" : "LIVE"} />
          <span className="font-medium text-white/85">
            {isAr ? "مركز العمليات" : "Operations hub"}
          </span>
        </div>
        <div className="text-[10px] text-white/45">AGENT · 24/7</div>
      </PanelHeader>

      <div className="grid grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)] gap-3 px-4 py-4">
        {/* Phone chat */}
        <div className="rounded-2xl border border-white/10 bg-black/40 p-2.5">
          <div className="flex items-center gap-2 border-b border-white/5 pb-2">
            <BrandLogo size={20} />
            <div className="min-w-0">
              <div className="truncate text-[10px] font-semibold text-white/90">
                Mostashari AI
              </div>
              <div className="truncate text-[9px] text-white/45">
                {isAr ? "متصل · رد تلقائي" : "online · auto-reply"}
              </div>
            </div>
          </div>

          {/*
            Fixed height keeps the phone panel — and therefore the whole
            card — at a stable size across every phase of the loop, even
            when 4 messages are stacked.
          */}
          <div className="h-[160px] space-y-1.5 pt-2">
            <AnimatePresence initial={false}>
              {showClientMsg && (
                <motion.div
                  key="client"
                  initial={{ opacity: 0, y: 8, scale: 0.96 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
                  className="rounded-xl rounded-bl-sm bg-white/10 px-2 py-1.5 text-[10px] text-white/85"
                >
                  {isAr
                    ? "أحتاج مراجعة عقد عمل عاجلًا."
                    : "Need a contract review urgently."}
                </motion.div>
              )}

              {showAgentTyping && !showAgentReply && (
                <motion.div
                  key="typing-1"
                  initial={{ opacity: 0, y: 4 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.25 }}
                  className="w-fit rounded-xl rounded-bl-sm bg-white/10 px-2 py-1.5"
                >
                  <Dots />
                </motion.div>
              )}

              {showAgentReply && (
                <motion.div
                  key="agent-reply"
                  initial={{ opacity: 0, y: 8, scale: 0.96 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
                  className="ms-auto w-fit rounded-xl rounded-br-sm bg-emerald-600/85 px-2 py-1.5 text-[10px] text-white"
                >
                  {isAr
                    ? "أكيد 👋 أرسل العقد وسأبدأ المراجعة فورًا."
                    : "Of course 👋 send the contract and I'll start the review."}
                </motion.div>
              )}

              {showFollowupMsg && (
                <motion.div
                  key="followup"
                  initial={{ opacity: 0, y: 8, scale: 0.96 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
                  className="rounded-xl rounded-bl-sm bg-white/10 px-2 py-1.5 text-[10px] text-white/85"
                >
                  📎 {isAr ? "contract-v1.pdf" : "contract-v1.pdf"}
                </motion.div>
              )}

              {showAgentTyping && showAgentReply && (
                <motion.div
                  key="typing-2"
                  initial={{ opacity: 0, y: 4 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.25 }}
                  className="w-fit rounded-xl rounded-bl-sm bg-white/10 px-2 py-1.5"
                >
                  <Dots />
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>

        {/* Live workflow panel */}
        <div className="rounded-2xl border border-white/10 bg-black/40 p-3">
          <div className="mb-2 flex items-center justify-between">
            <span className="text-[10px] font-semibold text-white/85">
              {isAr ? "سير العمل الحي" : "Live workflow"}
            </span>
            <span className="rounded-full bg-emerald-500/15 px-1.5 py-0.5 text-[9px] font-medium text-emerald-300">
              {phase >= 6
                ? isAr ? "اكتمل" : "Done"
                : isAr ? "تشغيل" : "Running"}
            </span>
          </div>

          <ul className="space-y-1.5">
            {steps.map((s, i) => {
              const v = stepVariants[i];
              return (
                <motion.li
                  key={s.label}
                  layout
                  animate={{
                    opacity: v === "idle" ? 0.45 : 1,
                  }}
                  transition={{ duration: 0.3 }}
                  className="flex items-center gap-2 rounded-md bg-white/[0.03] px-2 py-1.5"
                >
                  <StatusDot variant={v} />
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-[10px] font-medium text-white/85">
                      {s.label}
                    </div>
                    <div className="truncate text-[9px] text-white/45">
                      {v === "idle"
                        ? isAr ? "في الانتظار" : "pending"
                        : s.detail}
                    </div>
                  </div>
                  <span
                    className={
                      v === "ok"
                        ? "text-emerald-300"
                        : v === "progress"
                        ? "text-amber-300"
                        : "text-white/30"
                    }
                  >
                    {s.icon}
                  </span>
                </motion.li>
              );
            })}
          </ul>
        </div>
      </div>

      <PanelFooter>
        <Stat
          label={isAr ? "محادثات/د" : "Convos/min"}
          value={`~${10 + (phase % 4)}`}
        />
        <Stat label={isAr ? "تشغيل" : "Uptime"} value="99.98%" />
        <Stat label={isAr ? "اللغة" : "Lang"} value="AR · EN" />
      </PanelFooter>
    </DarkPanel>
  );
}

/* ────────────────────────────────────────────────────────────────────────── */
/*  Shared atoms                                                              */
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

function PanelHeader({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between border-b border-white/5 bg-black/20 px-4 py-2.5">
      {children}
    </div>
  );
}

function PanelFooter({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-2 border-t border-white/5 bg-black/20 px-4 py-2">
      {children}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline gap-1">
      <span className="text-[9px] uppercase tracking-wider text-white/40">
        {label}
      </span>
      <span className="text-[10px] font-semibold tabular-nums text-white/85">
        {value}
      </span>
    </div>
  );
}

function LivePill({ label }: { label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-500/15 px-2 py-0.5 text-[10px] font-medium text-emerald-300">
      <span className="relative flex h-1.5 w-1.5">
        <span className="absolute inset-0 animate-ping rounded-full bg-emerald-400 opacity-60" />
        <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-emerald-400" />
      </span>
      {label}
    </span>
  );
}

function StatusDot({ variant }: { variant: StepVariant }) {
  if (variant === "ok") {
    return (
      <motion.span
        initial={{ scale: 0.6, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ type: "spring", stiffness: 360, damping: 22 }}
        className="inline-flex h-4 w-4 items-center justify-center rounded-full bg-emerald-500/20"
      >
        <Check className="h-2.5 w-2.5 text-emerald-300" strokeWidth={3} />
      </motion.span>
    );
  }
  if (variant === "warn") {
    return (
      <motion.span
        initial={{ scale: 0.6, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ type: "spring", stiffness: 360, damping: 22 }}
        className="inline-flex h-4 w-4 items-center justify-center rounded-full bg-amber-500/20"
      >
        <span className="h-1.5 w-0.5 rounded-full bg-amber-300" />
      </motion.span>
    );
  }
  if (variant === "progress") {
    return (
      <span className="relative inline-flex h-4 w-4 items-center justify-center">
        <span
          className="absolute inset-0 animate-spin rounded-full"
          style={{
            background:
              "conic-gradient(from 0deg, hsl(36 70% 60%) 0%, transparent 70%)",
            mask: "radial-gradient(closest-side, transparent 60%, black 62%)",
            WebkitMask:
              "radial-gradient(closest-side, transparent 60%, black 62%)",
            animationDuration: "1.4s",
          }}
        />
        <span className="relative h-1 w-1 rounded-full bg-amber-300" />
      </span>
    );
  }
  return (
    <span className="inline-flex h-4 w-4 items-center justify-center rounded-full bg-white/8">
      <span className="h-1.5 w-1.5 rounded-full bg-white/30" />
    </span>
  );
}

function Dots() {
  return (
    <span className="inline-flex items-center gap-0.5">
      {[0, 0.15, 0.3].map((d) => (
        <span
          key={d}
          className="typing-dot inline-block h-1 w-1 rounded-full bg-white/45"
          style={{ animationDelay: `${d}s` }}
        />
      ))}
    </span>
  );
}

function ChipButton({
  icon,
  label,
  primary,
}: {
  icon: React.ReactNode;
  label: string;
  primary?: boolean;
}) {
  return (
    <span
      className={
        primary
          ? "inline-flex items-center gap-1 rounded-md bg-amber-500/85 px-2 py-1 text-[10px] font-semibold text-emerald-950"
          : "inline-flex items-center gap-1 rounded-md border border-white/15 px-2 py-1 text-[10px] font-medium text-white/75"
      }
    >
      {icon}
      {label}
    </span>
  );
}
