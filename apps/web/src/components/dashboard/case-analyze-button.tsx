"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Brain, Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";

export function CaseAnalyzeButton({
  caseId,
  locale,
}: {
  caseId: string;
  locale: string;
}) {
  const t = useTranslations("dashboard.cases");
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  async function run() {
    setLoading(true);
    try {
      const res = await fetch(`/api/v1/cases/${caseId}/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ locale }),
      });
      if (!res.ok) throw new Error(await res.text());
      router.refresh();
    } catch (err) {
      alert((err as Error).message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <Button variant="outline" size="sm" onClick={run} disabled={loading}>
      {loading ? (
        <Loader2 className="h-4 w-4 animate-spin" />
      ) : (
        <Brain className="h-4 w-4" />
      )}
      {t("analyze")}
    </Button>
  );
}
