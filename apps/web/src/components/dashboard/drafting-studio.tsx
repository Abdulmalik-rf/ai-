"use client";

import { useMemo, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { Loader2, Sparkles } from "lucide-react";

import { AiProgress } from "@/components/dashboard/ai-progress";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";

interface Template {
  id: string;
  title_en: string;
  title_ar: string;
  kind: string;
  variables: { name: string; label_en: string; label_ar: string; type: string }[];
}

export function DraftingStudio({ templates }: { templates: Template[] }) {
  const t = useTranslations("dashboard.drafting");
  const locale = useLocale();
  const isAr = locale === "ar";

  const [templateId, setTemplateId] = useState<string>(templates[0]?.id ?? "");
  const [vars, setVars] = useState<Record<string, string>>({});
  const [instructions, setInstructions] = useState("");
  const [output, setOutput] = useState("");
  const [loading, setLoading] = useState(false);

  const current = useMemo(
    () => templates.find((tt) => tt.id === templateId),
    [templates, templateId]
  );

  async function run() {
    if (!current) return;
    setLoading(true);
    setOutput("");
    try {
      const res = await fetch("/api/v1/drafting", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          template_id: current.id,
          kind: current.kind,
          locale,
          variables: vars,
          instructions: instructions || null,
        }),
      });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setOutput(data.body);
    } catch (err) {
      alert((err as Error).message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="container py-8 space-y-6">
      <header>
        <h1 className="text-3xl font-bold tracking-tight">{t("title")}</h1>
      </header>

      <div className="grid lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle>{t("selectTemplate")}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <select
              value={templateId}
              onChange={(e) => setTemplateId(e.target.value)}
              className="w-full rounded-md border border-input bg-background h-10 px-3 text-sm"
            >
              {templates.map((tt) => (
                <option key={tt.id} value={tt.id}>
                  {locale === "ar" ? tt.title_ar : tt.title_en}
                </option>
              ))}
            </select>

            {current?.variables.map((v) => (
              <div key={v.name} className="space-y-1.5">
                <label className="text-sm font-medium">
                  {locale === "ar" ? v.label_ar : v.label_en}
                </label>
                <Input
                  value={vars[v.name] ?? ""}
                  type={v.type === "date" ? "date" : "text"}
                  onChange={(e) =>
                    setVars((s) => ({ ...s, [v.name]: e.target.value }))
                  }
                />
              </div>
            ))}

            <div className="space-y-1.5">
              <label className="text-sm font-medium">
                {t("customInstructions")}
              </label>
              <Textarea
                value={instructions}
                onChange={(e) => setInstructions(e.target.value)}
                rows={3}
              />
            </div>

            <Button onClick={run} disabled={loading} className="w-full">
              {loading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Sparkles className="h-4 w-4" />
              )}
              {t("title")}
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-6 min-h-[60vh]">
            {loading && !output ? (
              <AiProgress
                estimateSeconds={30}
                stages={
                  isAr
                    ? [
                        "يجهّز المساعد المسودة…",
                        "يصوغ البنية والأقسام…",
                        "يضيف الأسانيد النظامية…",
                        "ينقّح اللغة القانونية…",
                      ]
                    : [
                        "Preparing the draft…",
                        "Structuring sections…",
                        "Adding statutory basis…",
                        "Polishing legal language…",
                      ]
                }
              />
            ) : (
              <pre className="whitespace-pre-wrap text-sm font-mono">{output}</pre>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
