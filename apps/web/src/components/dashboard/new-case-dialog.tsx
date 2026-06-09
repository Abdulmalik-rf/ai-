"use client";

/**
 * "New case" trigger + modal form.
 *
 * Renders a button that opens a centered overlay with the case-creation
 * form. POSTs to `/api/v1/cases` (proxied with the http-only access
 * cookie attached server-side). On success, closes the modal and triggers
 * a Next.js router refresh so the cases list re-fetches with the new row.
 */
import { Loader2, Plus, X } from "lucide-react";
import { useLocale } from "next-intl";
import { useRouter } from "next/navigation";
import * as React from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";

const DOMAINS = [
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

const PRIORITIES = ["low", "medium", "high", "urgent"] as const;

const DOMAIN_LABEL_AR: Record<(typeof DOMAINS)[number], string> = {
  commercial: "تجاري",
  labor: "عمل",
  family: "أحوال شخصية",
  criminal: "جنائي",
  real_estate: "عقاري",
  administrative: "إداري",
  ip: "ملكية فكرية",
  corporate: "شركات",
  banking: "مصرفي",
  other: "أخرى",
};

const PRIORITY_LABEL_AR: Record<(typeof PRIORITIES)[number], string> = {
  low: "منخفضة",
  medium: "متوسطة",
  high: "عالية",
  urgent: "عاجلة",
};

interface NewCaseDialogProps {
  /** When provided, the dialog becomes a controlled component and the
   *  built-in trigger button is hidden so the parent can render its own. */
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
}

export function NewCaseDialog({ open: openProp, onOpenChange }: NewCaseDialogProps = {}) {
  const router = useRouter();
  const locale = useLocale();
  const isAr = locale === "ar";

  const controlled = openProp !== undefined;
  const [internalOpen, setInternalOpen] = React.useState(false);
  const open = controlled ? !!openProp : internalOpen;
  const setOpen = React.useCallback(
    (next: boolean) => {
      if (controlled) onOpenChange?.(next);
      else setInternalOpen(next);
    },
    [controlled, onOpenChange],
  );
  const [submitting, setSubmitting] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  // Close on Escape
  React.useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    setSubmitting(true);
    setError(null);
    try {
      const body = {
        reference: String(fd.get("reference") || "").trim(),
        title: String(fd.get("title") || "").trim(),
        description: String(fd.get("description") || "").trim() || null,
        domain: String(fd.get("domain") || "other"),
        priority: String(fd.get("priority") || "medium"),
      };
      const res = await fetch("/api/v1/cases", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const text = await res.text();
        let msg = text;
        try {
          const j = JSON.parse(text);
          if (j?.detail) {
            msg = Array.isArray(j.detail)
              ? j.detail.map((d: { msg?: string }) => d.msg ?? "").join("; ")
              : String(j.detail);
          }
        } catch {
          /* keep msg as raw text */
        }
        throw new Error(msg || `HTTP ${res.status}`);
      }
      setOpen(false);
      router.refresh();
    } catch (err) {
      setError((err as Error).message || "Failed to create case");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      {!controlled && (
        <Button onClick={() => setOpen(true)}>
          <Plus className="h-4 w-4" />
          {isAr ? "قضية جديدة" : "New case"}
        </Button>
      )}

      {open && (
        <div
          className="fixed inset-0 z-50 grid place-items-center bg-black/50 backdrop-blur-sm p-4"
          onClick={() => setOpen(false)}
          role="dialog"
          aria-modal="true"
        >
          <div
            className="relative w-full max-w-lg rounded-2xl border border-border/60 bg-card shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between px-6 pt-5 pb-3">
              <h2 className="text-xl font-bold tracking-tight">
                {isAr ? "قضية جديدة" : "New case"}
              </h2>
              <button
                type="button"
                onClick={() => setOpen(false)}
                className="grid h-8 w-8 place-items-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
                aria-label={isAr ? "إغلاق" : "Close"}
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <form onSubmit={onSubmit} className="px-6 pb-6 space-y-4">
              <Field label={isAr ? "الرقم المرجعي" : "Reference"}>
                <Input
                  name="reference"
                  required
                  maxLength={64}
                  placeholder={isAr ? "مثل: ١٤٤٦-٠٠١" : "e.g. 2026-001"}
                  autoFocus
                />
              </Field>

              <Field label={isAr ? "العنوان" : "Title"}>
                <Input
                  name="title"
                  required
                  maxLength={300}
                  placeholder={
                    isAr
                      ? "وصف قصير للقضية"
                      : "Short description of the case"
                  }
                />
              </Field>

              <Field label={isAr ? "الوصف (اختياري)" : "Description (optional)"}>
                <Textarea name="description" rows={3} />
              </Field>

              <div className="grid grid-cols-2 gap-3">
                <Field label={isAr ? "المجال" : "Domain"}>
                  <SelectNative name="domain" defaultValue="other">
                    {DOMAINS.map((d) => (
                      <option key={d} value={d}>
                        {isAr ? DOMAIN_LABEL_AR[d] : d.replace("_", " ")}
                      </option>
                    ))}
                  </SelectNative>
                </Field>

                <Field label={isAr ? "الأولوية" : "Priority"}>
                  <SelectNative name="priority" defaultValue="medium">
                    {PRIORITIES.map((p) => (
                      <option key={p} value={p}>
                        {isAr ? PRIORITY_LABEL_AR[p] : p}
                      </option>
                    ))}
                  </SelectNative>
                </Field>
              </div>

              {error && (
                <div className="rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive">
                  {error}
                </div>
              )}

              <div className="flex justify-end gap-2 pt-2">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setOpen(false)}
                  disabled={submitting}
                >
                  {isAr ? "إلغاء" : "Cancel"}
                </Button>
                <Button type="submit" disabled={submitting}>
                  {submitting && <Loader2 className="h-4 w-4 animate-spin" />}
                  {isAr ? "إنشاء" : "Create"}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </>
  );
}

/* Tiny helpers */

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="text-sm font-medium text-foreground/90 mb-1.5 block">
        {label}
      </span>
      {children}
    </label>
  );
}

function SelectNative({
  name,
  defaultValue,
  children,
}: {
  name: string;
  defaultValue?: string;
  children: React.ReactNode;
}) {
  return (
    <select
      name={name}
      defaultValue={defaultValue}
      className="w-full h-10 rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent"
    >
      {children}
    </select>
  );
}
