"use client";

/**
 * Edit-case modal. Mirrors the NewCaseDialog pattern but is pre-filled and
 * targets PATCH /api/v1/cases/{id}. Covers every editable field on the case:
 *
 *   - identity:        title, description
 *   - classification:  domain, status, priority
 *   - linked client:   client_id (select from the firm's clients)
 *   - court / matter:  court_name, court_circuit, court_case_number, judge_name
 *   - other side:      opposing_party_name, opposing_counsel
 *   - dates:           opened_at, closed_at
 *
 * On save it closes the modal and triggers a router refresh so the detail
 * page re-renders with the new values.
 */
import { Loader2, Pencil, X } from "lucide-react";
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

const STATUSES = [
  "intake",
  "open",
  "in_court",
  "settled",
  "closed",
  "archived",
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

const STATUS_LABEL_AR: Record<(typeof STATUSES)[number], string> = {
  intake: "استقبال",
  open: "مفتوحة",
  in_court: "أمام المحكمة",
  settled: "تسوية",
  closed: "مغلقة",
  archived: "مؤرشفة",
};

const PRIORITY_LABEL_AR: Record<(typeof PRIORITIES)[number], string> = {
  low: "منخفضة",
  medium: "متوسطة",
  high: "عالية",
  urgent: "عاجلة",
};

interface CaseValues {
  title: string;
  description: string | null;
  domain: string;
  status: string;
  priority: string;
  client_id: string | null;
  opposing_party_name: string | null;
  opposing_counsel: string | null;
  court_name: string | null;
  court_circuit: string | null;
  court_case_number: string | null;
  judge_name: string | null;
  opened_at: string | null;
  closed_at: string | null;
}

interface ClientOption {
  id: string;
  name: string;
}

export function EditCaseDialog({
  caseId,
  initial,
  clients,
}: {
  caseId: string;
  initial: CaseValues;
  clients: ClientOption[];
}) {
  const router = useRouter();
  const locale = useLocale();
  const isAr = locale === "ar";

  const [open, setOpen] = React.useState(false);
  const [submitting, setSubmitting] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

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
      const body: Record<string, unknown> = {
        title: String(fd.get("title") || "").trim(),
        description: String(fd.get("description") || "").trim() || null,
        domain: String(fd.get("domain") || "other"),
        status: String(fd.get("status") || "intake"),
        priority: String(fd.get("priority") || "medium"),
        client_id: String(fd.get("client_id") || "") || null,
        opposing_party_name:
          String(fd.get("opposing_party_name") || "").trim() || null,
        opposing_counsel:
          String(fd.get("opposing_counsel") || "").trim() || null,
        court_name: String(fd.get("court_name") || "").trim() || null,
        court_circuit: String(fd.get("court_circuit") || "").trim() || null,
        court_case_number:
          String(fd.get("court_case_number") || "").trim() || null,
        judge_name: String(fd.get("judge_name") || "").trim() || null,
        opened_at: String(fd.get("opened_at") || "") || null,
        closed_at: String(fd.get("closed_at") || "") || null,
      };
      const res = await fetch(`/api/v1/cases/${caseId}`, {
        method: "PATCH",
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
              ? j.detail
                  .map((d: { msg?: string }) => d.msg ?? "")
                  .join("; ")
              : String(j.detail);
          }
        } catch {
          /* keep raw text */
        }
        throw new Error(msg || `HTTP ${res.status}`);
      }
      setOpen(false);
      router.refresh();
    } catch (err) {
      setError((err as Error).message || "Failed to save");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      <Button variant="outline" size="sm" onClick={() => setOpen(true)}>
        <Pencil className="h-4 w-4" />
        {isAr ? "تعديل" : "Edit"}
      </Button>

      {open && (
        <div
          className="fixed inset-0 z-50 grid place-items-center bg-black/50 backdrop-blur-sm p-4 overflow-y-auto"
          onClick={() => setOpen(false)}
          role="dialog"
          aria-modal="true"
        >
          <div
            className="relative w-full max-w-2xl rounded-2xl border border-border/60 bg-card shadow-2xl my-8"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between px-6 pt-5 pb-3 sticky top-0 bg-card rounded-t-2xl border-b border-border/40">
              <h2 className="text-xl font-bold tracking-tight">
                {isAr ? "تعديل القضية" : "Edit case"}
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

            <form onSubmit={onSubmit} className="px-6 pb-6 pt-4 space-y-5">
              <Section title={isAr ? "الهوية" : "Identity"}>
                <Field label={isAr ? "العنوان" : "Title"}>
                  <Input
                    name="title"
                    required
                    maxLength={300}
                    defaultValue={initial.title}
                  />
                </Field>
                <Field label={isAr ? "الوصف" : "Description"}>
                  <Textarea
                    name="description"
                    rows={3}
                    defaultValue={initial.description ?? ""}
                  />
                </Field>
              </Section>

              <Section title={isAr ? "التصنيف" : "Classification"}>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                  <Field label={isAr ? "المجال" : "Domain"}>
                    <SelectNative name="domain" defaultValue={initial.domain}>
                      {DOMAINS.map((d) => (
                        <option key={d} value={d}>
                          {isAr ? DOMAIN_LABEL_AR[d] : d.replace("_", " ")}
                        </option>
                      ))}
                    </SelectNative>
                  </Field>
                  <Field label={isAr ? "الحالة" : "Status"}>
                    <SelectNative
                      name="status"
                      defaultValue={
                        STATUSES.includes(initial.status as (typeof STATUSES)[number])
                          ? initial.status
                          : "intake"
                      }
                    >
                      {STATUSES.map((s) => (
                        <option key={s} value={s}>
                          {isAr ? STATUS_LABEL_AR[s] : s.replace("_", " ")}
                        </option>
                      ))}
                    </SelectNative>
                  </Field>
                  <Field label={isAr ? "الأولوية" : "Priority"}>
                    <SelectNative
                      name="priority"
                      defaultValue={
                        PRIORITIES.includes(
                          initial.priority as (typeof PRIORITIES)[number]
                        )
                          ? initial.priority
                          : "medium"
                      }
                    >
                      {PRIORITIES.map((p) => (
                        <option key={p} value={p}>
                          {isAr ? PRIORITY_LABEL_AR[p] : p}
                        </option>
                      ))}
                    </SelectNative>
                  </Field>
                </div>
              </Section>

              <Section title={isAr ? "العميل" : "Client"}>
                <Field label={isAr ? "اربط بعميل" : "Linked client"}>
                  <SelectNative
                    name="client_id"
                    defaultValue={initial.client_id ?? ""}
                  >
                    <option value="">
                      {isAr ? "— بدون عميل مرتبط —" : "— No linked client —"}
                    </option>
                    {clients.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name}
                      </option>
                    ))}
                  </SelectNative>
                </Field>
              </Section>

              <Section title={isAr ? "المحكمة" : "Court"}>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <Field label={isAr ? "اسم المحكمة" : "Court name"}>
                    <Input
                      name="court_name"
                      defaultValue={initial.court_name ?? ""}
                      placeholder={isAr ? "مثل: المحكمة التجارية بالرياض" : "e.g. Commercial Court of Riyadh"}
                    />
                  </Field>
                  <Field label={isAr ? "الدائرة" : "Circuit"}>
                    <Input
                      name="court_circuit"
                      defaultValue={initial.court_circuit ?? ""}
                      placeholder={isAr ? "الدائرة التجارية الثالثة" : "3rd Commercial Circuit"}
                    />
                  </Field>
                  <Field label={isAr ? "رقم القضية في المحكمة" : "Court case number"}>
                    <Input
                      name="court_case_number"
                      defaultValue={initial.court_case_number ?? ""}
                    />
                  </Field>
                  <Field label={isAr ? "القاضي" : "Judge"}>
                    <Input
                      name="judge_name"
                      defaultValue={initial.judge_name ?? ""}
                    />
                  </Field>
                </div>
              </Section>

              <Section title={isAr ? "الخصم" : "Opposing party"}>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <Field label={isAr ? "اسم الخصم" : "Opposing party"}>
                    <Input
                      name="opposing_party_name"
                      defaultValue={initial.opposing_party_name ?? ""}
                    />
                  </Field>
                  <Field label={isAr ? "محامي الخصم" : "Opposing counsel"}>
                    <Input
                      name="opposing_counsel"
                      defaultValue={initial.opposing_counsel ?? ""}
                    />
                  </Field>
                </div>
              </Section>

              <Section title={isAr ? "التواريخ" : "Dates"}>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <Field label={isAr ? "تاريخ الفتح" : "Opened on"}>
                    <Input
                      type="date"
                      name="opened_at"
                      defaultValue={initial.opened_at ?? ""}
                    />
                  </Field>
                  <Field label={isAr ? "تاريخ الإغلاق" : "Closed on"}>
                    <Input
                      type="date"
                      name="closed_at"
                      defaultValue={initial.closed_at ?? ""}
                    />
                  </Field>
                </div>
              </Section>

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
                  {isAr ? "حفظ" : "Save"}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </>
  );
}

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-3">
      <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        {title}
      </div>
      {children}
    </div>
  );
}

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
