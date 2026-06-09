"use client";

/**
 * Edit-client modal. Pre-filled form that PATCHes /api/v1/clients/{id} with
 * everything the schema exposes: identity, KSA legal IDs (national ID, CR,
 * VAT), contact, address, and CRM funnel fields (status, lead source,
 * referred-by, internal notes).
 */
import { Loader2, Pencil, X } from "lucide-react";
import { useLocale } from "next-intl";
import { useRouter } from "next/navigation";
import * as React from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";

const STATUSES = ["lead", "prospect", "active", "archived"] as const;
const STATUS_LABEL_AR: Record<(typeof STATUSES)[number], string> = {
  lead: "محتمل",
  prospect: "اهتمام",
  active: "نشط",
  archived: "مؤرشف",
};

interface ClientValues {
  name: string;
  kind: string;
  status: string;
  national_id: string | null;
  cr_number: string | null;
  vat_number: string | null;
  email: string | null;
  phone: string | null;
  address: string | null;
  city: string | null;
  lead_source: string | null;
  referred_by: string | null;
  notes: string | null;
}

export function EditClientDialog({
  clientId,
  initial,
}: {
  clientId: string;
  initial: ClientValues;
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
      const body = {
        name: String(fd.get("name") || "").trim(),
        kind: String(fd.get("kind") || "person"),
        status: String(fd.get("status") || "active"),
        national_id: String(fd.get("national_id") || "").trim() || null,
        cr_number: String(fd.get("cr_number") || "").trim() || null,
        vat_number: String(fd.get("vat_number") || "").trim() || null,
        email: String(fd.get("email") || "").trim() || null,
        phone: String(fd.get("phone") || "").trim() || null,
        address: String(fd.get("address") || "").trim() || null,
        city: String(fd.get("city") || "").trim() || null,
        lead_source: String(fd.get("lead_source") || "").trim() || null,
        referred_by: String(fd.get("referred_by") || "").trim() || null,
        notes: String(fd.get("notes") || "").trim() || null,
      };
      const res = await fetch(`/api/v1/clients/${clientId}`, {
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
              ? j.detail.map((d: { msg?: string }) => d.msg ?? "").join("; ")
              : String(j.detail);
          }
        } catch {
          /* keep raw */
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
                {isAr ? "تعديل العميل" : "Edit client"}
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
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <Field label={isAr ? "الاسم" : "Name"}>
                    <Input
                      name="name"
                      required
                      maxLength={200}
                      defaultValue={initial.name}
                    />
                  </Field>
                  <Field label={isAr ? "النوع" : "Type"}>
                    <SelectNative name="kind" defaultValue={initial.kind}>
                      <option value="person">
                        {isAr ? "فرد" : "Person"}
                      </option>
                      <option value="company">
                        {isAr ? "شركة" : "Company"}
                      </option>
                    </SelectNative>
                  </Field>
                </div>
                <Field label={isAr ? "الحالة" : "Status"}>
                  <SelectNative
                    name="status"
                    defaultValue={
                      STATUSES.includes(
                        initial.status as (typeof STATUSES)[number]
                      )
                        ? initial.status
                        : "active"
                    }
                  >
                    {STATUSES.map((s) => (
                      <option key={s} value={s}>
                        {isAr ? STATUS_LABEL_AR[s] : s}
                      </option>
                    ))}
                  </SelectNative>
                </Field>
              </Section>

              <Section title={isAr ? "التواصل" : "Contact"}>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <Field label={isAr ? "البريد الإلكتروني" : "Email"}>
                    <Input
                      type="email"
                      name="email"
                      defaultValue={initial.email ?? ""}
                    />
                  </Field>
                  <Field label={isAr ? "الهاتف" : "Phone"}>
                    <Input
                      name="phone"
                      type="tel"
                      defaultValue={initial.phone ?? ""}
                      dir="ltr"
                    />
                  </Field>
                  <Field label={isAr ? "المدينة" : "City"}>
                    <Input
                      name="city"
                      defaultValue={initial.city ?? ""}
                    />
                  </Field>
                  <Field label={isAr ? "العنوان" : "Address"}>
                    <Input
                      name="address"
                      defaultValue={initial.address ?? ""}
                    />
                  </Field>
                </div>
              </Section>

              <Section
                title={isAr ? "أرقام تعريفية" : "Identifiers"}
              >
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                  <Field label={isAr ? "الهوية الوطنية" : "National ID"}>
                    <Input
                      name="national_id"
                      defaultValue={initial.national_id ?? ""}
                    />
                  </Field>
                  <Field label={isAr ? "السجل التجاري" : "CR number"}>
                    <Input
                      name="cr_number"
                      defaultValue={initial.cr_number ?? ""}
                    />
                  </Field>
                  <Field label={isAr ? "الرقم الضريبي" : "VAT number"}>
                    <Input
                      name="vat_number"
                      defaultValue={initial.vat_number ?? ""}
                    />
                  </Field>
                </div>
              </Section>

              <Section title={isAr ? "المسار التسويقي" : "Funnel"}>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <Field label={isAr ? "مصدر العميل" : "Lead source"}>
                    <Input
                      name="lead_source"
                      defaultValue={initial.lead_source ?? ""}
                      placeholder={
                        isAr ? "إحالة، بحث، واتساب…" : "Referral, search, WhatsApp…"
                      }
                    />
                  </Field>
                  <Field label={isAr ? "أحاله" : "Referred by"}>
                    <Input
                      name="referred_by"
                      defaultValue={initial.referred_by ?? ""}
                    />
                  </Field>
                </div>
              </Section>

              <Field label={isAr ? "ملاحظات داخلية" : "Internal notes"}>
                <Textarea
                  name="notes"
                  rows={3}
                  defaultValue={initial.notes ?? ""}
                />
              </Field>

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
