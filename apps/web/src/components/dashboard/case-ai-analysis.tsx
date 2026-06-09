"use client";

/**
 * Renders the structured AI analysis block stored on `cases.ai_analysis`.
 * Falls back to a "run analysis" call-out when the JSON is empty — that
 * way the user always sees what the AI button will produce.
 */
import { AlertTriangle, BookText, Brain, Scale, Sparkles } from "lucide-react";
import { useLocale } from "next-intl";

import { Card } from "@/components/ui/card";

type AnalysisShape = {
  summary?: string;
  legal_issues?: string[];
  suggested_strategy?: string[];
  relevant_laws?: string[];
  risk_assessment?: string;
  generated_at?: string;
};

export function CaseAiAnalysis({ analysis }: { analysis: AnalysisShape | null }) {
  const locale = useLocale();
  const isAr = locale === "ar";
  const has =
    !!analysis &&
    (analysis.summary ||
      (analysis.legal_issues && analysis.legal_issues.length > 0) ||
      (analysis.suggested_strategy && analysis.suggested_strategy.length > 0) ||
      analysis.risk_assessment);

  if (!has) {
    return (
      <Card className="p-5 border-dashed">
        <div className="flex items-start gap-3">
          <div className="grid h-10 w-10 place-items-center rounded-md bg-primary/10 text-primary shrink-0">
            <Brain className="h-5 w-5" />
          </div>
          <div className="text-sm">
            <div className="font-medium">
              {isAr ? "تحليل القضية بالذكاء الاصطناعي" : "AI case analysis"}
            </div>
            <p className="text-muted-foreground mt-1 max-w-prose">
              {isAr
                ? "اضغط زر التحليل أعلى الصفحة لتوليد ملخص للقضية، القضايا القانونية المُحتملة، خطة عمل مقترحة، الأنظمة ذات الصلة، وتقييم المخاطر."
                : "Use the Analyze button above to generate a case summary, legal issues, a suggested strategy, the relevant Saudi laws, and a risk assessment."}
            </p>
          </div>
        </div>
      </Card>
    );
  }

  return (
    <Card className="p-5 space-y-5">
      <div className="flex items-center gap-2 text-sm font-semibold">
        <Sparkles className="h-4 w-4 text-primary" />
        {isAr ? "تحليل القضية" : "Case analysis"}
      </div>

      {analysis!.summary && (
        <section>
          <SectionHeading
            icon={BookText}
            label={isAr ? "الملخص" : "Summary"}
          />
          <p className="text-sm text-foreground/90 leading-relaxed whitespace-pre-wrap">
            {analysis!.summary}
          </p>
        </section>
      )}

      {analysis!.legal_issues && analysis!.legal_issues.length > 0 && (
        <section>
          <SectionHeading
            icon={Scale}
            label={isAr ? "القضايا القانونية" : "Legal issues"}
          />
          <ul className="list-disc list-inside space-y-1 text-sm">
            {analysis!.legal_issues.map((it, i) => (
              <li key={i}>{it}</li>
            ))}
          </ul>
        </section>
      )}

      {analysis!.suggested_strategy && analysis!.suggested_strategy.length > 0 && (
        <section>
          <SectionHeading
            icon={Sparkles}
            label={isAr ? "الاستراتيجية المقترحة" : "Suggested strategy"}
          />
          <ol className="list-decimal list-inside space-y-1 text-sm">
            {analysis!.suggested_strategy.map((it, i) => (
              <li key={i}>{it}</li>
            ))}
          </ol>
        </section>
      )}

      {analysis!.relevant_laws && analysis!.relevant_laws.length > 0 && (
        <section>
          <SectionHeading
            icon={BookText}
            label={isAr ? "الأنظمة ذات الصلة" : "Relevant laws"}
          />
          <ul className="flex flex-wrap gap-2 text-xs">
            {analysis!.relevant_laws.map((it, i) => (
              <li
                key={i}
                className="rounded-md border border-border/60 bg-muted/40 px-2.5 py-1"
              >
                {it}
              </li>
            ))}
          </ul>
        </section>
      )}

      {analysis!.risk_assessment && (
        <section>
          <SectionHeading
            icon={AlertTriangle}
            label={isAr ? "تقييم المخاطر" : "Risk assessment"}
          />
          <p className="text-sm text-foreground/90 leading-relaxed whitespace-pre-wrap">
            {analysis!.risk_assessment}
          </p>
        </section>
      )}
    </Card>
  );
}

function SectionHeading({
  icon: Icon,
  label,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
}) {
  return (
    <div className="flex items-center gap-2 text-xs uppercase tracking-wider text-muted-foreground mb-2">
      <Icon className="h-3.5 w-3.5" />
      {label}
    </div>
  );
}
