"use client";

/**
 * "New client" trigger + modal form. Mirrors NewCaseDialog: button →
 * overlay → form → POST to /api/v1/clients → close + router.refresh().
 */
import { Loader2, Plus, X } from "lucide-react";
import { useLocale } from "next-intl";
import { useRouter } from "next/navigation";
import * as React from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";

export function NewClientDialog() {
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
        email: String(fd.get("email") || "").trim() || null,
        phone: String(fd.get("phone") || "").trim() || null,
        national_id: String(fd.get("national_id") || "").trim() || null,
        cr_number: String(fd.get("cr_number") || "").trim() || null,
        notes: String(fd.get("notes") || "").trim() || null,
      };
      const res = await fetch("/api/v1/clients", {
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
          /* keep raw */
        }
        throw new Error(msg || `HTTP ${res.status}`);
      }
      setOpen(false);
      router.refresh();
    } catch (err) {
      setError((err as Error).message || "Failed to create client");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      <Button onClick={() => setOpen(true)}>
        <Plus className="h-4 w-4" />
        {isAr ? "عميل جديد" : "New client"}
      </Button>

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
                {isAr ? "عميل جديد" : "New client"}
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
              <Field label={isAr ? "الاسم" : "Name"}>
                <Input
                  name="name"
                  required
                  maxLength={200}
                  autoFocus
                  placeholder={
                    isAr ? "اسم الشخص أو الشركة" : "Person or company name"
                  }
                />
              </Field>

              <Field label={isAr ? "النوع" : "Type"}>
                <SelectNative name="kind" defaultValue="person">
                  <option value="person">{isAr ? "فرد" : "Person"}</option>
                  <option value="company">{isAr ? "شركة" : "Company"}</option>
                </SelectNative>
              </Field>

              <div className="grid grid-cols-2 gap-3">
                <Field label={isAr ? "البريد الإلكتروني" : "Email"}>
                  <Input type="email" name="email" />
                </Field>
                <Field label={isAr ? "الهاتف" : "Phone"}>
                  <Input name="phone" />
                </Field>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <Field label={isAr ? "الهوية الوطنية" : "National ID"}>
                  <Input name="national_id" />
                </Field>
                <Field label={isAr ? "السجل التجاري" : "CR number"}>
                  <Input name="cr_number" />
                </Field>
              </div>

              <Field label={isAr ? "ملاحظات" : "Notes"}>
                <Textarea name="notes" rows={2} />
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
                  {isAr ? "إضافة" : "Create"}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </>
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
