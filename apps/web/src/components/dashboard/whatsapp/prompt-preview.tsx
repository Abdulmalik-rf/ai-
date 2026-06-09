"use client";

import { ChevronDown, ChevronUp, Loader2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export function PromptPreview() {
  const t = useTranslations("dashboard.whatsapp.preview");
  const [open, setOpen] = useState(false);
  const [locale, setLocale] = useState<"ar" | "en">("ar");
  const [text, setText] = useState<string>("");
  const [loading, setLoading] = useState(false);

  async function load(next: "ar" | "en") {
    setLocale(next);
    setLoading(true);
    try {
      const res = await fetch(
        `/api/v1/whatsapp/agent-profile/preview-prompt?locale=${next}`
      );
      if (!res.ok) {
        setText(await res.text());
        return;
      }
      const data = (await res.json()) as { instructions: string };
      setText(data.instructions);
    } finally {
      setLoading(false);
    }
  }

  async function toggle() {
    if (!open) {
      await load(locale);
    }
    setOpen((v) => !v);
  }

  return (
    <section className="rounded-2xl border border-border/60 bg-card p-6 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">{t("title")}</h2>
          <p className="mt-1 text-sm text-muted-foreground">{t("subtitle")}</p>
        </div>
        <Button onClick={toggle} variant="outline" className="gap-2 shrink-0">
          {open ? (
            <ChevronUp className="h-4 w-4" />
          ) : (
            <ChevronDown className="h-4 w-4" />
          )}
          {open ? t("hideButton") : t("showButton")}
        </Button>
      </div>

      {open && (
        <div className="mt-5 space-y-3">
          <div className="inline-flex rounded-full border border-border bg-background p-1 text-xs">
            <button
              type="button"
              onClick={() => load("ar")}
              className={cn(
                "rounded-full px-3 py-1 transition-colors",
                locale === "ar"
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              {t("localeAr")}
            </button>
            <button
              type="button"
              onClick={() => load("en")}
              className={cn(
                "rounded-full px-3 py-1 transition-colors",
                locale === "en"
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              {t("localeEn")}
            </button>
          </div>

          <pre
            dir={locale === "ar" ? "rtl" : "ltr"}
            className="max-h-[460px] overflow-auto rounded-xl border border-border/60 bg-muted/30 p-4 text-xs leading-relaxed whitespace-pre-wrap"
          >
            {loading ? (
              <span className="inline-flex items-center gap-2 text-muted-foreground">
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                {t("loading")}
              </span>
            ) : (
              text
            )}
          </pre>
        </div>
      )}
    </section>
  );
}
