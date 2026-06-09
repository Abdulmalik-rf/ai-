"use client";

/**
 * Case-integrated memo-review + Najiz final-review workflow.
 *
 * Lives inside the case detail page (not a standalone sidebar section).
 * Flow (matches the product spec):
 *   1. Lawyer pastes / edits the case memo (case context auto-filled).
 *   2. Presses "Analyze" → the multi-advisor review agent workflow starts.
 *   3. The outcome (executive summary + advisor cards + revised memo)
 *      renders below.
 *   4. Below the outcome, a "Final Review before Najiz" button appears →
 *      runs the strict 8-check verification gate and shows the verdict.
 *
 * Both reviews are persisted against the case (case_id), so re-opening the
 * case restores the latest run. Work runs server-side in a background task;
 * this component polls until each review's status leaves "running".
 */
import {
  AlertTriangle,
  CheckCircle2,
  Loader2,
  RotateCw,
  ScrollText,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Users2,
  XCircle,
} from "lucide-react";
import { useLocale } from "next-intl";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

type Status = "queued" | "running" | "done" | "failed";
type Assessment = "strong" | "medium" | "weak";

interface AdvisorReport {
  advisor_id: string;
  status: Status;
  assessment: Assessment | null;
  impact_level: "high" | "medium" | "low" | null;
  observations: string[];
  risk_points: string[];
  recommendations: string[];
  extra: Record<string, unknown> | null;
  error: string | null;
}

interface FinalSummary {
  general_assessment?: {
    case_strength?: Assessment;
    memo_strength?: Assessment;
    risk_level?: "low" | "medium" | "high";
    memo_readiness?: "ready" | "ready_with_observations" | "not_ready";
  };
  top_priorities?: string[];
  summary_of_observations?: string[];
  remaining_risks?: string[];
  final_recommendation?: string;
  final_alerts?: string[];
  human_review_points?: string[];
}

interface MemoReview {
  id: string;
  status: Status;
  error: string | null;
  mode: string;
  memo_text: string;
  final_summary: FinalSummary | null;
  revised_memo: string | null;
  advisors: AdvisorReport[];
  created_at: string;
}

interface FinalReview {
  id: string;
  status: Status;
  error: string | null;
  verdict: "ready" | "ready_with_observations" | "not_ready" | null;
  risk_level: "low" | "medium" | "high" | null;
  checks: Record<string, { status: "pass" | "warn" | "fail"; summary: string; findings: FinalFinding[] }> | null;
  critical_errors: FinalCritical[] | null;
  required_modifications: string[] | null;
  human_review_points: string[] | null;
  created_at: string;
}

interface FinalFinding {
  severity: "info" | "warn" | "blocker";
  message: string;
  location?: string;
  quote?: string;
  suggested_fix?: string;
}
interface FinalCritical extends FinalFinding {
  check: string;
}

interface AdvisorMeta {
  id: string;
  name_en: string;
  name_ar: string;
  available: boolean;
}

interface Props {
  caseId: string;
  caseTitle: string;
  caseType: string | null;
  caseFacts: string | null;
}

const CHECK_LABELS: Record<string, { en: string; ar: string }> = {
  basis: { en: "Support / Basis", ar: "الأساس والاستناد" },
  statutes: { en: "Statutes", ar: "النصوص النظامية" },
  facts_names_dates: { en: "Facts / Names / Dates", ar: "الوقائع والأسماء والتواريخ" },
  requests: { en: "Requests", ar: "الطلبات" },
  procedures: { en: "Procedures", ar: "الإجراءات" },
  contradictions: { en: "Contradictions", ar: "التناقضات الداخلية" },
  hallucination: { en: "Hallucination", ar: "المعلومات غير الموثقة" },
  submission_readiness: { en: "Submission readiness", ar: "الجاهزية للتقديم" },
};
const CHECK_ORDER = Object.keys(CHECK_LABELS);

export function CaseMemoReviewPanel({ caseId, caseTitle, caseType, caseFacts }: Props) {
  const locale = useLocale();
  const isAr = locale === "ar";

  const [memoText, setMemoText] = useState("");
  const [mode, setMode] = useState<"standard" | "deep" | "custom">("deep");
  const [review, setReview] = useState<MemoReview | null>(null);
  const [finalReview, setFinalReview] = useState<FinalReview | null>(null);
  const [advisorMeta, setAdvisorMeta] = useState<Record<string, AdvisorMeta>>({});
  const [starting, setStarting] = useState(false);
  const [startingFinal, setStartingFinal] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(true);

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const finalPollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // ── Initial load: advisors catalogue + latest review for this case ──────
  useEffect(() => {
    (async () => {
      try {
        const cat = await fetch("/api/v1/memo-reviews/advisors").then((r) => (r.ok ? r.json() : null));
        if (cat?.advisors) {
          setAdvisorMeta(
            Object.fromEntries((cat.advisors as AdvisorMeta[]).map((a) => [a.id, a]))
          );
        }
      } catch {
        /* ignore */
      }
      try {
        const list = (await fetch(`/api/v1/memo-reviews?case_id=${caseId}&limit=1`).then((r) =>
          r.ok ? r.json() : []
        )) as MemoReview[];
        if (list.length > 0) {
          setReview(list[0]);
          setMemoText(list[0].memo_text);
          setShowForm(false);
        }
      } catch {
        /* ignore */
      }
      try {
        const fl = (await fetch(`/api/v1/final-reviews?case_id=${caseId}&limit=1`).then((r) =>
          r.ok ? r.json() : []
        )) as FinalReview[];
        if (fl.length > 0) setFinalReview(fl[0]);
      } catch {
        /* ignore */
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [caseId]);

  // ── Poll the active memo review while running ───────────────────────────
  const pollReview = useCallback(async (id: string) => {
    const r = await fetch(`/api/v1/memo-reviews/${id}`);
    if (!r.ok) return;
    const data = (await r.json()) as MemoReview;
    setReview(data);
    if (data.status === "done" || data.status === "failed") {
      if (pollRef.current) clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  useEffect(() => {
    if (review && (review.status === "queued" || review.status === "running")) {
      if (!pollRef.current) {
        pollRef.current = setInterval(() => pollReview(review.id), 4000);
      }
    }
    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [review?.id, review?.status, pollReview]);

  // ── Poll the active final review while running ──────────────────────────
  const pollFinal = useCallback(async (id: string) => {
    const r = await fetch(`/api/v1/final-reviews/${id}`);
    if (!r.ok) return;
    const data = (await r.json()) as FinalReview;
    setFinalReview(data);
    if (data.status === "done" || data.status === "failed") {
      if (finalPollRef.current) clearInterval(finalPollRef.current);
      finalPollRef.current = null;
    }
  }, []);

  useEffect(() => {
    if (finalReview && (finalReview.status === "queued" || finalReview.status === "running")) {
      if (!finalPollRef.current) {
        finalPollRef.current = setInterval(() => pollFinal(finalReview.id), 4000);
      }
    }
    return () => {
      if (finalPollRef.current) {
        clearInterval(finalPollRef.current);
        finalPollRef.current = null;
      }
    };
  }, [finalReview?.id, finalReview?.status, pollFinal]);

  // ── Actions ─────────────────────────────────────────────────────────────
  async function startReview() {
    setStarting(true);
    setError(null);
    try {
      const res = await fetch("/api/v1/memo-reviews", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          case_id: caseId,
          case_title: caseTitle,
          case_type: caseType,
          facts: caseFacts,
          memo_text: memoText.trim(),
          mode,
          want_revised_memo: true,
        }),
      });
      if (!res.ok) {
        const d = await res.json().catch(() => ({ detail: "Request failed" }));
        throw new Error((d as { detail?: string }).detail ?? `HTTP ${res.status}`);
      }
      const created = (await res.json()) as MemoReview;
      setReview(created);
      setFinalReview(null); // a new memo review invalidates the old final review
      setShowForm(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setStarting(false);
    }
  }

  async function startFinalReview() {
    if (!review) return;
    setStartingFinal(true);
    setError(null);
    try {
      // Prefer the revised memo (the corrected version) for the final gate;
      // fall back to the original if no revision was produced.
      const memoForCheck = review.revised_memo?.trim() || review.memo_text;
      const res = await fetch("/api/v1/final-reviews", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          case_id: caseId,
          memo_review_id: review.id,
          memo_text: memoForCheck,
          context: { title: caseTitle, case_type: caseType },
        }),
      });
      if (!res.ok) {
        const d = await res.json().catch(() => ({ detail: "Request failed" }));
        throw new Error((d as { detail?: string }).detail ?? `HTTP ${res.status}`);
      }
      setFinalReview((await res.json()) as FinalReview);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setStartingFinal(false);
    }
  }

  const reviewRunning = review?.status === "queued" || review?.status === "running";
  const reviewDone = review?.status === "done";
  const summary = review?.final_summary;

  // ── Render ──────────────────────────────────────────────────────────────
  return (
    <Card className="overflow-hidden">
      {/* Header */}
      <div className="px-5 py-4 flex items-start justify-between gap-3 border-b border-border/40 bg-gradient-to-br from-primary/[0.04] via-transparent to-accent/[0.04]">
        <div className="flex items-start gap-3 min-w-0">
          <div className="grid h-10 w-10 place-items-center rounded-md bg-primary/10 text-primary shrink-0">
            <Users2 className="h-5 w-5" />
          </div>
          <div className="min-w-0">
            <div className="font-semibold text-sm flex items-center gap-2">
              {isAr ? "مراجعة المذكرة متعددة المستشارين" : "Multi-Advisor Memo Review"}
              {reviewDone && (
                <Badge variant="success" className="text-[10px]">
                  {isAr ? "جاهز" : "Ready"}
                </Badge>
              )}
            </div>
            <p className="text-xs text-muted-foreground mt-0.5 max-w-prose">
              {isAr
                ? "تُرسل المذكرة إلى عدة مستشارين قانونيين، كل واحد يراجعها من زاوية، ثم يدمج المدير النهائي النتائج. بعد ذلك يمكنك إجراء المراجعة النهائية قبل التقديم لـ ناجز."
                : "Sends the memo to several specialized advisors — each reviews independently, then a Final Manager merges the reports. Afterward you can run the Najiz final review."}
            </p>
          </div>
        </div>
        {(reviewDone || review?.status === "failed") && (
          <Button size="sm" variant="outline" onClick={() => setShowForm((v) => !v)} className="shrink-0">
            <RotateCw className="h-4 w-4 me-1" />
            {isAr ? "تحليل جديد" : "New analysis"}
          </Button>
        )}
      </div>

      <div className="p-5 space-y-5">
        {error && (
          <div className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {error}
          </div>
        )}

        {/* Input form */}
        {(showForm || (!review && !reviewRunning)) && (
          <div className="space-y-3">
            <div className="space-y-1.5">
              <label className="text-sm font-medium">
                {isAr ? "نص المذكرة" : "Memo text"} *
              </label>
              <Textarea
                value={memoText}
                onChange={(e) => setMemoText(e.target.value)}
                rows={9}
                placeholder={
                  isAr
                    ? "الصق نص المذكرة كاملاً كما هي اليوم — سيقرأها كل مستشار من زاويته."
                    : "Paste the full memo text as it stands today — each advisor reads it from their angle."
                }
              />
              <div className="text-xs text-muted-foreground">{memoText.length} chars</div>
            </div>

            {/* Mode pills */}
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs text-muted-foreground">{isAr ? "النمط:" : "Mode:"}</span>
              {([
                ["standard", isAr ? "احترافية" : "Standard"],
                ["deep", isAr ? "عميقة" : "Deep"],
                ["custom", isAr ? "مخصصة" : "Custom"],
              ] as const).map(([m, label]) => (
                <button
                  key={m}
                  type="button"
                  onClick={() => setMode(m)}
                  className={cn(
                    "px-3 py-1 rounded-full text-xs border transition-colors",
                    mode === m ? "border-primary bg-primary/10 text-primary" : "border-border hover:bg-accent/40"
                  )}
                >
                  {label}
                </button>
              ))}
            </div>

            <Button onClick={startReview} disabled={starting || memoText.trim().length < 20}>
              {starting ? <Loader2 className="h-4 w-4 me-1 animate-spin" /> : <Sparkles className="h-4 w-4 me-1" />}
              {isAr ? "ابدأ التحليل" : "Analyze"}
            </Button>
          </div>
        )}

        {/* Running state */}
        {reviewRunning && (
          <div className="flex flex-col items-center justify-center py-10 text-center">
            <Loader2 className="h-7 w-7 animate-spin text-primary mb-3" />
            <p className="text-sm font-medium">{isAr ? "المستشارون يعملون…" : "Advisors are working…"}</p>
            <p className="text-xs text-muted-foreground mt-1">
              {(review?.advisors.filter((a) => a.status === "done").length ?? 0)} /{" "}
              {review?.advisors.length ?? 0} {isAr ? "اكتمل" : "completed"}
            </p>
          </div>
        )}

        {/* Failure */}
        {review?.status === "failed" && (
          <div className="rounded-md border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm">
            <div className="font-semibold text-destructive">{isAr ? "فشلت المراجعة" : "Review failed"}</div>
            <div className="text-xs text-muted-foreground mt-1 whitespace-pre-wrap">{review.error}</div>
          </div>
        )}

        {/* Executive summary */}
        {reviewDone && summary && (
          <div className="space-y-4">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <Kpi label={isAr ? "قوة القضية" : "Case strength"} value={summary.general_assessment?.case_strength} />
              <Kpi label={isAr ? "قوة المذكرة" : "Memo strength"} value={summary.general_assessment?.memo_strength} />
              <Kpi label={isAr ? "مستوى الخطر" : "Risk level"} value={summary.general_assessment?.risk_level} />
              <Kpi label={isAr ? "الجاهزية" : "Readiness"} value={summary.general_assessment?.memo_readiness?.replace(/_/g, " ")} />
            </div>

            {summary.top_priorities && summary.top_priorities.length > 0 && (
              <div>
                <div className="text-sm font-semibold mb-2">{isAr ? "أهم الأولويات" : "Top priorities"}</div>
                <ol className="space-y-1.5 list-decimal list-inside text-sm">
                  {summary.top_priorities.map((p, i) => <li key={i} className="ps-1">{p}</li>)}
                </ol>
              </div>
            )}

            {summary.final_recommendation && (
              <div className="rounded-md bg-muted/40 px-3 py-2 text-sm">
                <div className="text-xs font-semibold text-muted-foreground mb-1">{isAr ? "التوصية النهائية" : "Final recommendation"}</div>
                {summary.final_recommendation}
              </div>
            )}

            {summary.human_review_points && summary.human_review_points.length > 0 && (
              <div className="rounded-md border border-amber-500/30 bg-amber-500/5 px-3 py-2 text-sm">
                <div className="font-semibold text-amber-700 dark:text-amber-400 mb-1">{isAr ? "يتطلب مراجعة بشرية" : "Requires human review"}</div>
                <ul className="list-disc list-inside text-xs text-amber-900 dark:text-amber-200">
                  {summary.human_review_points.map((s, i) => <li key={i}>{s}</li>)}
                </ul>
              </div>
            )}

            {/* Advisor cards (collapsed by default) */}
            <details className="rounded-lg border border-border bg-card/50">
              <summary className="cursor-pointer px-4 py-2.5 text-sm font-medium">
                {isAr ? `آراء المستشارين (${review!.advisors.length})` : `Advisor opinions (${review!.advisors.length})`}
              </summary>
              <div className="grid gap-3 md:grid-cols-2 p-4 pt-2">
                {review!.advisors.map((a) => (
                  <AdvisorCard key={a.advisor_id} a={a} meta={advisorMeta[a.advisor_id]} isAr={isAr} />
                ))}
              </div>
            </details>

            {/* Revised memo */}
            {review!.revised_memo && (
              <details className="rounded-lg border border-border bg-card/50">
                <summary className="cursor-pointer px-4 py-2.5 text-sm font-medium flex items-center gap-2">
                  <ScrollText className="h-4 w-4" />
                  {isAr ? "النسخة المنقّحة من المذكرة" : "Revised memo"}
                </summary>
                <pre className="whitespace-pre-wrap text-sm leading-relaxed font-sans px-4 pb-4">{review!.revised_memo}</pre>
              </details>
            )}

            {/* ── Final Review gate ─────────────────────────────────────── */}
            <FinalReviewBlock
              isAr={isAr}
              finalReview={finalReview}
              starting={startingFinal}
              onStart={startFinalReview}
            />
          </div>
        )}
      </div>
    </Card>
  );
}

// ─────────────────────────────────────────────────────────────────────────

function FinalReviewBlock({
  isAr,
  finalReview,
  starting,
  onStart,
}: {
  isAr: boolean;
  finalReview: FinalReview | null;
  starting: boolean;
  onStart: () => void;
}) {
  const running = finalReview?.status === "queued" || finalReview?.status === "running";
  const done = finalReview?.status === "done";

  return (
    <div className="mt-2 rounded-xl border-2 border-dashed border-primary/30 p-4 space-y-3">
      <div className="flex items-center gap-2">
        <ShieldCheck className="h-5 w-5 text-primary" />
        <div className="font-semibold text-sm">
          {isAr ? "المراجعة النهائية قبل التقديم لـ ناجز" : "Final Review Before Submission to Najiz"}
        </div>
      </div>
      <p className="text-xs text-muted-foreground">
        {isAr
          ? "بوابة تحقق صارمة تفحص ثمانية معايير (الأساس، النصوص، الوقائع، الطلبات، الإجراءات، التناقضات، المعلومات غير الموثقة، الجاهزية) وتُصدر قراراً نهائياً."
          : "A strict gate running 8 checks (basis, statutes, facts, requests, procedures, contradictions, hallucination, readiness) and issuing a final verdict."}
      </p>

      {!finalReview && (
        <Button onClick={onStart} disabled={starting}>
          {starting ? <Loader2 className="h-4 w-4 me-1 animate-spin" /> : <ShieldCheck className="h-4 w-4 me-1" />}
          {isAr ? "ابدأ المراجعة النهائية" : "Run final review"}
        </Button>
      )}

      {running && (
        <div className="flex items-center gap-2 text-sm text-muted-foreground py-2">
          <Loader2 className="h-4 w-4 animate-spin text-primary" />
          {isAr ? "الفحص جارٍ — ثمانية فحوصات تعمل بالتوازي…" : "Verifying — 8 checks running in parallel…"}
        </div>
      )}

      {finalReview?.status === "failed" && (
        <div className="text-xs text-destructive whitespace-pre-wrap">{finalReview.error}</div>
      )}

      {done && <FinalVerdict fr={finalReview!} isAr={isAr} onRerun={onStart} rerunning={starting} />}
    </div>
  );
}

function FinalVerdict({ fr, isAr, onRerun, rerunning }: { fr: FinalReview; isAr: boolean; onRerun: () => void; rerunning: boolean }) {
  const checks = fr.checks ?? {};
  const sortedIds = CHECK_ORDER.filter((id) => id in checks);

  return (
    <div className="space-y-3">
      {/* Hero verdict */}
      <div
        className={cn(
          "rounded-lg border-2 py-4 text-center",
          fr.verdict === "ready"
            ? "border-emerald-500/40 bg-emerald-500/5"
            : fr.verdict === "ready_with_observations"
            ? "border-amber-500/40 bg-amber-500/5"
            : "border-destructive/40 bg-destructive/5"
        )}
      >
        {fr.verdict === "ready" ? (
          <CheckCircle2 className="h-9 w-9 mx-auto text-emerald-500" />
        ) : fr.verdict === "ready_with_observations" ? (
          <AlertTriangle className="h-9 w-9 mx-auto text-amber-500" />
        ) : (
          <XCircle className="h-9 w-9 mx-auto text-destructive" />
        )}
        <div className="text-lg font-bold mt-1">
          {fr.verdict === "ready"
            ? isAr ? "جاهزة للتقديم لـ ناجز" : "READY FOR NAJIZ"
            : fr.verdict === "ready_with_observations"
            ? isAr ? "جاهزة مع ملاحظات" : "READY WITH OBSERVATIONS"
            : isAr ? "غير جاهزة — لا تُقدّم" : "NOT READY — DO NOT SUBMIT"}
        </div>
        <div className="text-xs text-muted-foreground mt-0.5">
          {isAr ? "مستوى الخطر" : "Risk level"}: <strong>{fr.risk_level ?? "—"}</strong>
        </div>
        <Button size="sm" variant="ghost" onClick={onRerun} disabled={rerunning} className="mt-2">
          <RotateCw className="h-3.5 w-3.5 me-1" />
          {isAr ? "إعادة الفحص" : "Re-check"}
        </Button>
      </div>

      {/* Critical errors */}
      {fr.critical_errors && fr.critical_errors.length > 0 && (
        <div className="rounded-md border border-destructive/40 bg-destructive/5 p-3 space-y-2">
          <div className="text-sm font-semibold text-destructive flex items-center gap-1.5">
            <XCircle className="h-4 w-4" />
            {isAr ? "أخطاء حرجة" : "Critical errors"}
          </div>
          {fr.critical_errors.map((e, i) => (
            <div key={i} className="text-xs border-s-2 border-destructive/30 ps-2">
              <div className="font-medium">{e.message}</div>
              {e.quote && <blockquote className="italic text-muted-foreground mt-0.5">{e.quote}</blockquote>}
              {e.suggested_fix && <div className="text-emerald-700 dark:text-emerald-400 mt-0.5">→ {e.suggested_fix}</div>}
            </div>
          ))}
        </div>
      )}

      {/* Required modifications */}
      {fr.required_modifications && fr.required_modifications.length > 0 && (
        <div>
          <div className="text-sm font-semibold mb-1.5 flex items-center gap-1.5">
            <AlertTriangle className="h-4 w-4 text-amber-500" />
            {isAr ? "تعديلات مطلوبة قبل التقديم" : "Modifications required before submission"}
          </div>
          <ol className="space-y-1 list-decimal list-inside text-sm">
            {fr.required_modifications.map((m, i) => <li key={i}>{m}</li>)}
          </ol>
        </div>
      )}

      {/* 8 checks */}
      <details className="rounded-lg border border-border bg-card/50">
        <summary className="cursor-pointer px-4 py-2.5 text-sm font-medium">{isAr ? "الفحوصات الثمانية" : "The 8 checks"}</summary>
        <div className="px-4 pb-4 space-y-2">
          {sortedIds.map((id) => {
            const c = checks[id];
            const lbl = CHECK_LABELS[id] ?? { en: id, ar: id };
            return (
              <div key={id} className="text-xs flex items-start gap-2 border-s-2 ps-2 border-border">
                {c.status === "pass" ? (
                  <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500 mt-0.5 shrink-0" />
                ) : c.status === "warn" ? (
                  <AlertTriangle className="h-3.5 w-3.5 text-amber-500 mt-0.5 shrink-0" />
                ) : (
                  <ShieldAlert className="h-3.5 w-3.5 text-destructive mt-0.5 shrink-0" />
                )}
                <div>
                  <span className="font-medium">{isAr ? lbl.ar : lbl.en}</span>
                  <span className="text-muted-foreground"> — {c.summary}</span>
                </div>
              </div>
            );
          })}
        </div>
      </details>
    </div>
  );
}

function AdvisorCard({ a, meta, isAr }: { a: AdvisorReport; meta?: AdvisorMeta; isAr: boolean }) {
  const tone = a.assessment === "strong" ? "border-emerald-500/40" : a.assessment === "weak" ? "border-amber-500/40" : "border-border";
  return (
    <div className={cn("rounded-lg border p-3 space-y-2", tone)}>
      <div className="text-sm font-semibold flex items-center gap-1.5">
        {a.status === "done" && <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />}
        {a.status === "running" && <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" />}
        {a.status === "failed" && <ShieldAlert className="h-3.5 w-3.5 text-destructive" />}
        {meta ? (isAr ? meta.name_ar : meta.name_en) : a.advisor_id}
      </div>
      {a.assessment && (
        <div className="flex gap-1.5 text-[10px]">
          <span className="px-1.5 py-0.5 rounded-full bg-muted text-muted-foreground">{isAr ? "التقييم" : "Assessment"}: {a.assessment}</span>
          {a.impact_level && <span className="px-1.5 py-0.5 rounded-full bg-muted text-muted-foreground">{isAr ? "التأثير" : "Impact"}: {a.impact_level}</span>}
        </div>
      )}
      {a.observations.length > 0 && (
        <div>
          <div className="text-[10px] uppercase tracking-wide text-muted-foreground mb-0.5">{isAr ? "ملاحظات" : "Observations"}</div>
          <ul className="text-xs space-y-0.5 list-disc list-inside">{a.observations.map((o, i) => <li key={i}>{o}</li>)}</ul>
        </div>
      )}
      {a.recommendations.length > 0 && (
        <div>
          <div className="text-[10px] uppercase tracking-wide text-emerald-700 dark:text-emerald-400 mb-0.5">{isAr ? "توصيات" : "Recommendations"}</div>
          <ul className="text-xs space-y-0.5 list-disc list-inside text-emerald-900 dark:text-emerald-200">{a.recommendations.map((o, i) => <li key={i}>{o}</li>)}</ul>
        </div>
      )}
      {a.status === "failed" && a.error && <div className="text-xs text-destructive whitespace-pre-wrap">{a.error}</div>}
    </div>
  );
}

function Kpi({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <div className="rounded-md border border-border/60 bg-muted/30 px-3 py-2">
      <div className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className="font-semibold text-sm mt-0.5 capitalize">{value ?? "—"}</div>
    </div>
  );
}
