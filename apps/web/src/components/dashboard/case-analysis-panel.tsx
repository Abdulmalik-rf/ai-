"use client";

/**
 * One panel for the case-AI workflow: trigger button, loading state,
 * error states (AI down vs. other), and the rendered analysis when one
 * exists. Replaces the standalone CaseAnalyzeButton + CaseAiAnalysis
 * components which had no shared state and surfaced errors as alert().
 *
 * Initial analysis is server-rendered (passed as `initialAnalysis`), so
 * the panel hydrates with whatever was previously persisted on
 * `cases.ai_analysis`. After re-analyzing we update local state AND
 * router.refresh() so future visits see the new copy.
 */
import {
  AlertTriangle,
  BookText,
  Brain,
  Clock,
  Loader2,
  RotateCw,
  Scale,
  Sparkles,
} from "lucide-react";
import { useLocale } from "next-intl";
import { useState } from "react";

import { useRouter } from "@/i18n/routing";
import { AiProgress } from "@/components/dashboard/ai-progress";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

export type CaseAnalysis = {
  summary?: string;
  legal_issues?: string[];
  suggested_strategy?: string[];
  relevant_laws?: string[];
  risk_assessment?: string;
  generated_at?: string;
};

interface ErrorState {
  kind: "ai" | "other";
  msg: string;
}

export function CaseAnalysisPanel({
  caseId,
  initialAnalysis,
}: {
  caseId: string;
  initialAnalysis: CaseAnalysis | null;
}) {
  const locale = useLocale();
  const isAr = locale === "ar";
  const router = useRouter();

  const [analysis, setAnalysis] = useState<CaseAnalysis | null>(initialAnalysis);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<ErrorState | null>(null);
  // Tracks when the user re-runs the analysis in this session, so we can
  // show "Just now" until the page reloads with the server timestamp.
  const [justRanAt, setJustRanAt] = useState<string | null>(null);

  const hasResult = !!(
    analysis &&
    (analysis.summary ||
      (analysis.legal_issues?.length ?? 0) > 0 ||
      (analysis.suggested_strategy?.length ?? 0) > 0 ||
      analysis.risk_assessment)
  );

  async function run() {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/v1/cases/${caseId}/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ locale }),
      });
      if (!res.ok) {
        const text = await res.text();
        let msg = text;
        try {
          const j = JSON.parse(text);
          msg = j?.detail || text;
        } catch {
          /* keep raw */
        }
        const isAi =
          res.status === 502 ||
          String(msg).includes("AI provider") ||
          String(msg).includes("ChatGPT");
        setError({
          kind: isAi ? "ai" : "other",
          msg: msg || `HTTP ${res.status}`,
        });
        return;
      }
      const data = (await res.json()) as CaseAnalysis;
      setAnalysis(data);
      setJustRanAt(new Date().toISOString());
      // Server stashes it on cases.ai_analysis — refresh so subsequent
      // visits hydrate from there.
      router.refresh();
    } catch (err) {
      setError({
        kind: "other",
        msg: (err as Error).message || "Request failed",
      });
    } finally {
      setLoading(false);
    }
  }

  const generatedAt = justRanAt ?? analysis?.generated_at ?? null;

  // --- Render ---------------------------------------------------------------

  return (
    <Card className="overflow-hidden">
      {/* Header — title + action button */}
      <div className="px-5 py-4 flex items-start justify-between gap-3 border-b border-border/40 bg-gradient-to-br from-primary/[0.04] via-transparent to-accent/[0.04]">
        <div className="flex items-start gap-3 min-w-0">
          <div className="grid h-10 w-10 place-items-center rounded-md bg-primary/10 text-primary shrink-0">
            <Brain className="h-5 w-5" />
          </div>
          <div className="min-w-0">
            <div className="font-semibold text-sm flex items-center gap-2">
              {isAr ? "تحليل القضية بالذكاء الاصطناعي" : "AI case analysis"}
              {hasResult && (
                <Badge variant="success" className="text-[10px]">
                  {isAr ? "جاهز" : "Ready"}
                </Badge>
              )}
            </div>
            <p className="text-xs text-muted-foreground mt-0.5 max-w-prose">
              {hasResult
                ? isAr
                  ? "ملخص، قضايا قانونية، استراتيجية مقترحة، أنظمة ذات صلة، وتقييم مخاطر."
                  : "Summary, legal issues, suggested strategy, relevant laws, and risk assessment."
                : isAr
                  ? "وَلِّد ملخصًا ذكيًا للقضية مع تحديد المسائل القانونية واقتراح خطة عمل."
                  : "Generate an AI brief: legal issues, suggested strategy, and risk profile."}
            </p>
            {hasResult && generatedAt && (
              <div className="text-[11px] text-muted-foreground flex items-center gap-1 mt-1">
                <Clock className="h-3 w-3" />
                {isAr ? "آخر تحليل " : "Last analyzed "}
                {formatRelative(generatedAt, isAr)}
              </div>
            )}
          </div>
        </div>
        <Button
          size="sm"
          variant={hasResult ? "outline" : "default"}
          onClick={run}
          disabled={loading}
          className="shrink-0"
        >
          {loading ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : hasResult ? (
            <RotateCw className="h-4 w-4" />
          ) : (
            <Brain className="h-4 w-4" />
          )}
          {loading
            ? isAr
              ? "جارٍ التحليل…"
              : "Analyzing…"
            : hasResult
              ? isAr
                ? "إعادة التحليل"
                : "Re-analyze"
              : isAr
                ? "ابدأ التحليل"
                : "Analyze"}
        </Button>
      </div>

      {/* Body */}
      <div className="p-5">
        {error && (
          <div
            className={
              "rounded-xl border px-4 py-3 flex items-start gap-3 text-sm " +
              (error.kind === "ai"
                ? "border-amber-500/30 bg-amber-500/5"
                : "border-destructive/30 bg-destructive/5")
            }
          >
            <AlertTriangle
              className={
                "h-4 w-4 mt-0.5 shrink-0 " +
                (error.kind === "ai"
                  ? "text-amber-600 dark:text-amber-400"
                  : "text-destructive")
              }
            />
            <div className="min-w-0">
              <div className="font-semibold">
                {error.kind === "ai"
                  ? isAr
                    ? "خدمة الذكاء الاصطناعي معطّلة مؤقتًا"
                    : "AI service temporarily unavailable"
                  : isAr
                    ? "تعذّر التحليل"
                    : "Analysis failed"}
              </div>
              <p className="text-muted-foreground mt-0.5">
                {error.kind === "ai"
                  ? isAr
                    ? "انتهت صلاحية بيانات اعتماد مزود الذكاء الاصطناعي. تواصل مع مسؤول النظام لتحديثها."
                    : "The AI provider's credentials have expired. Ask your admin to refresh them."
                  : error.msg}
              </p>
            </div>
          </div>
        )}

        {!error && loading && !hasResult && (
          <div className="py-6">
            <AiProgress
              estimateSeconds={35}
              stages={
                isAr
                  ? [
                      "يقرأ المساعد ملف القضية…",
                      "يحدّد المسائل القانونية…",
                      "يصوغ الاستراتيجية المقترحة…",
                      "يربط الأنظمة ذات الصلة…",
                      "يُقيّم المخاطر…",
                    ]
                  : [
                      "Reading the case file…",
                      "Identifying legal issues…",
                      "Drafting suggested strategy…",
                      "Linking relevant Saudi laws…",
                      "Assessing risk…",
                    ]
              }
            />
          </div>
        )}

        {!error && !loading && !hasResult && (
          <div className="flex flex-col items-center justify-center py-10 text-center">
            <div className="grid h-12 w-12 place-items-center rounded-2xl bg-primary/10 text-primary mb-3">
              <Sparkles className="h-5 w-5" />
            </div>
            <p className="text-sm text-foreground font-medium">
              {isAr
                ? "لم يُجرَ تحليل بعد."
                : "No analysis yet."}
            </p>
            <p className="text-xs text-muted-foreground mt-1 max-w-md">
              {isAr
                ? "اضغط «ابدأ التحليل» لتوليد ملخص للقضية، القضايا القانونية، خطة عمل مقترحة، الأنظمة ذات الصلة، وتقييم المخاطر."
                : "Tap \"Analyze\" to generate a case brief, legal issues, suggested strategy, relevant Saudi laws, and a risk assessment."}
            </p>
          </div>
        )}

        {hasResult && (
          <div className={"space-y-5 " + (loading ? "opacity-60" : "")}>
            {analysis!.summary && (
              <Section
                icon={BookText}
                label={isAr ? "الملخص" : "Summary"}
              >
                <p className="text-sm text-foreground/90 leading-relaxed whitespace-pre-wrap">
                  {analysis!.summary}
                </p>
              </Section>
            )}

            {(analysis!.legal_issues?.length ?? 0) > 0 && (
              <Section
                icon={Scale}
                label={isAr ? "القضايا القانونية" : "Legal issues"}
              >
                <ul className="list-disc list-inside space-y-1 text-sm text-foreground/90">
                  {analysis!.legal_issues!.map((it, i) => (
                    <li key={i}>{it}</li>
                  ))}
                </ul>
              </Section>
            )}

            {(analysis!.suggested_strategy?.length ?? 0) > 0 && (
              <Section
                icon={Sparkles}
                label={isAr ? "الاستراتيجية المقترحة" : "Suggested strategy"}
              >
                <ol className="list-decimal list-inside space-y-1 text-sm text-foreground/90">
                  {analysis!.suggested_strategy!.map((it, i) => (
                    <li key={i}>{it}</li>
                  ))}
                </ol>
              </Section>
            )}

            {(analysis!.relevant_laws?.length ?? 0) > 0 && (
              <Section
                icon={BookText}
                label={isAr ? "الأنظمة ذات الصلة" : "Relevant laws"}
              >
                <ul className="flex flex-wrap gap-2 text-xs">
                  {analysis!.relevant_laws!.map((it, i) => (
                    <li
                      key={i}
                      className="rounded-md border border-border/60 bg-muted/40 px-2.5 py-1"
                    >
                      {it}
                    </li>
                  ))}
                </ul>
              </Section>
            )}

            {analysis!.risk_assessment && (
              <Section
                icon={AlertTriangle}
                label={isAr ? "تقييم المخاطر" : "Risk assessment"}
              >
                <p className="text-sm text-foreground/90 leading-relaxed whitespace-pre-wrap">
                  {analysis!.risk_assessment}
                </p>
              </Section>
            )}
          </div>
        )}
      </div>
    </Card>
  );
}

function Section({
  icon: Icon,
  label,
  children,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  children: React.ReactNode;
}) {
  return (
    <section>
      <div className="flex items-center gap-2 text-xs uppercase tracking-wider text-muted-foreground mb-2">
        <Icon className="h-3.5 w-3.5" />
        {label}
      </div>
      {children}
    </section>
  );
}

function formatRelative(iso: string, isAr: boolean): string {
  const d = new Date(iso);
  const diff = Date.now() - d.getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 1) return isAr ? "الآن" : "just now";
  if (mins < 60) return isAr ? `قبل ${mins} د` : `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return isAr ? `قبل ${hrs} س` : `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  if (days < 30) return isAr ? `قبل ${days} يوم` : `${days}d ago`;
  return d.toLocaleDateString(isAr ? "ar" : "en");
}
