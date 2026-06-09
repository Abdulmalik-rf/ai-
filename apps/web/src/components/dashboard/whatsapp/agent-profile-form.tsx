"use client";

import { Loader2, Save } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

const ALL_DOMAINS = [
  "commercial",
  "labor",
  "family",
  "criminal",
  "real_estate",
  "administrative",
  "ip",
  "corporate",
  "banking",
  "other",
] as const;

type Domain = (typeof ALL_DOMAINS)[number];

export interface AgentProfile {
  firm_display_name?: string | null;
  welcome_message_ar?: string | null;
  welcome_message_en?: string | null;
  firm_specialties?: string | null;
  consultation_offer?: string | null;
  tone_guidelines?: string | null;
  custom_instructions?: string | null;
  timezone?: string;
  enabled_domains?: string[];
  is_enabled?: boolean;
}

export function AgentProfileForm({ initial }: { initial: AgentProfile }) {
  const t = useTranslations("dashboard.whatsapp.behavior");
  const tDom = useTranslations("dashboard.whatsapp.domainNames");
  const tWa = useTranslations("dashboard.whatsapp");

  const [profile, setProfile] = useState<AgentProfile>({
    timezone: "Asia/Riyadh",
    enabled_domains: [],
    is_enabled: true,
    ...initial,
  });
  const [busy, setBusy] = useState(false);
  const [savedAt, setSavedAt] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const set = <K extends keyof AgentProfile>(k: K, v: AgentProfile[K]) =>
    setProfile((p) => ({ ...p, [k]: v }));

  const toggleDomain = (d: Domain) => {
    const cur = new Set(profile.enabled_domains ?? []);
    if (cur.has(d)) cur.delete(d);
    else cur.add(d);
    set("enabled_domains", Array.from(cur));
  };

  async function save() {
    setError(null);
    setBusy(true);
    try {
      const res = await fetch("/api/v1/whatsapp/agent-profile", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(profile),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        throw new Error(body?.detail || `${res.status}`);
      }
      const data = (await res.json()) as AgentProfile;
      setProfile((p) => ({ ...p, ...data }));
      setSavedAt(Date.now());
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  const enabledDomains = new Set(profile.enabled_domains ?? []);
  const recentlySaved = savedAt && Date.now() - savedAt < 4000;

  return (
    <section className="rounded-2xl border border-border/60 bg-card p-6 shadow-sm space-y-6">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">{t("title")}</h2>
          <p className="mt-1 text-sm text-muted-foreground">{t("subtitle")}</p>
        </div>
        <label className="flex items-center gap-2 cursor-pointer select-none shrink-0">
          <span className="text-sm text-muted-foreground">
            {profile.is_enabled
              ? tWa("masterEnabled")
              : tWa("masterEnabled")}
          </span>
          <span
            role="switch"
            aria-checked={!!profile.is_enabled}
            onClick={() => set("is_enabled", !profile.is_enabled)}
            className={cn(
              "relative h-6 w-11 rounded-full transition-colors",
              profile.is_enabled ? "bg-primary" : "bg-muted"
            )}
          >
            <span
              className={cn(
                "absolute top-0.5 h-5 w-5 rounded-full bg-background shadow transition-transform",
                profile.is_enabled
                  ? "start-[1.5rem]"
                  : "start-0.5"
              )}
            />
          </span>
        </label>
      </div>

      {!profile.is_enabled && (
        <div className="rounded-xl border border-amber-500/40 bg-amber-500/10 p-3 text-sm text-amber-700 dark:text-amber-300">
          {tWa("masterDisabled")}
        </div>
      )}

      <Field
        label={t("firmDisplayName.label")}
        help={t("firmDisplayName.help")}
      >
        <Input
          value={profile.firm_display_name ?? ""}
          onChange={(e) => set("firm_display_name", e.target.value)}
          placeholder={t("firmDisplayName.placeholder")}
        />
      </Field>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Field label={t("welcomeAr.label")} help={t("welcomeAr.help")}>
          <Textarea
            dir="rtl"
            rows={3}
            value={profile.welcome_message_ar ?? ""}
            onChange={(e) => set("welcome_message_ar", e.target.value)}
            placeholder={t("welcomeAr.placeholder")}
          />
        </Field>
        <Field label={t("welcomeEn.label")} help={t("welcomeEn.help")}>
          <Textarea
            dir="ltr"
            rows={3}
            value={profile.welcome_message_en ?? ""}
            onChange={(e) => set("welcome_message_en", e.target.value)}
            placeholder={t("welcomeEn.placeholder")}
          />
        </Field>
      </div>

      <Field label={t("specialties.label")} help={t("specialties.help")}>
        <Textarea
          rows={3}
          value={profile.firm_specialties ?? ""}
          onChange={(e) => set("firm_specialties", e.target.value)}
          placeholder={t("specialties.placeholder")}
        />
      </Field>

      <Field
        label={t("consultationOffer.label")}
        help={t("consultationOffer.help")}
      >
        <Textarea
          rows={3}
          value={profile.consultation_offer ?? ""}
          onChange={(e) => set("consultation_offer", e.target.value)}
          placeholder={t("consultationOffer.placeholder")}
        />
      </Field>

      <Field label={t("tone.label")} help={t("tone.help")}>
        <Textarea
          rows={3}
          value={profile.tone_guidelines ?? ""}
          onChange={(e) => set("tone_guidelines", e.target.value)}
          placeholder={t("tone.placeholder")}
        />
      </Field>

      <Field label={t("domains.label")} help={t("domains.help")}>
        <div className="flex flex-wrap gap-2">
          {ALL_DOMAINS.map((d) => {
            const active = enabledDomains.has(d);
            return (
              <button
                key={d}
                type="button"
                onClick={() => toggleDomain(d)}
                className={cn(
                  "rounded-full border px-3 py-1 text-sm transition-colors",
                  active
                    ? "border-primary bg-primary/10 text-primary"
                    : "border-border text-muted-foreground hover:bg-muted"
                )}
              >
                {tDom(d)}
              </button>
            );
          })}
        </div>
      </Field>

      <Field label={t("custom.label")} help={t("custom.help")}>
        <Textarea
          rows={5}
          value={profile.custom_instructions ?? ""}
          onChange={(e) => set("custom_instructions", e.target.value)}
          placeholder={t("custom.placeholder")}
        />
      </Field>

      <Field label={t("timezone.label")}>
        <Input
          value={profile.timezone ?? ""}
          onChange={(e) => set("timezone", e.target.value)}
          placeholder={t("timezone.placeholder")}
          className="max-w-xs"
        />
      </Field>

      <div className="flex items-center justify-end gap-3 pt-2">
        {error && <span className="text-sm text-destructive">{error}</span>}
        {recentlySaved && (
          <span className="text-sm text-emerald-600 dark:text-emerald-400">
            {t("saved")}
          </span>
        )}
        <Button onClick={save} disabled={busy} className="gap-2">
          {busy ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Save className="h-4 w-4" />
          )}
          {busy ? t("saving") : t("save")}
        </Button>
      </div>
    </section>
  );
}

function Field({
  label,
  help,
  children,
}: {
  label: string;
  help?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block space-y-1.5">
      <span className="text-sm font-medium text-foreground">{label}</span>
      {children}
      {help && <span className="block text-xs text-muted-foreground">{help}</span>}
    </label>
  );
}
