"use client";

/**
 * Admin-only firm-settings form. PATCHes /api/v1/tenants/me with name,
 * default_locale, vat_number, billing_email, billing_address.
 */
import { Check, Loader2 } from "lucide-react";
import { useLocale } from "next-intl";
import { useRouter } from "next/navigation";
import * as React from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";

interface FirmFormProps {
  initial: {
    name: string;
    subdomain: string;
    default_locale: string;
    vat_number: string | null;
    billing_email: string | null;
    billing_address: string | null;
    dashboard_url: string | null;
  };
}

export function FirmForm({ initial }: FirmFormProps) {
  const router = useRouter();
  const locale = useLocale();
  const isAr = locale === "ar";

  const [submitting, setSubmitting] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [saved, setSaved] = React.useState(false);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    setSubmitting(true);
    setError(null);
    setSaved(false);
    try {
      const body = {
        name: String(fd.get("name") || "").trim(),
        default_locale: String(fd.get("default_locale") || "ar"),
        vat_number: String(fd.get("vat_number") || "").trim() || null,
        billing_email: String(fd.get("billing_email") || "").trim() || null,
        billing_address: String(fd.get("billing_address") || "").trim() || null,
      };
      const res = await fetch("/api/v1/tenants/me", {
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
          /* keep raw text */
        }
        throw new Error(msg || `HTTP ${res.status}`);
      }
      setSaved(true);
      router.refresh();
    } catch (err) {
      setError((err as Error).message || "Failed to save");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="space-y-5">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <Field label={isAr ? "اسم الشركة" : "Firm name"}>
          <Input
            name="name"
            defaultValue={initial.name}
            required
            minLength={2}
            maxLength={200}
          />
        </Field>

        <Field
          label={isAr ? "لغة المؤسسة الافتراضية" : "Default firm locale"}
        >
          <SelectNative
            name="default_locale"
            defaultValue={initial.default_locale}
          >
            <option value="ar">العربية</option>
            <option value="en">English</option>
          </SelectNative>
        </Field>
      </div>

      <Field
        label={isAr ? "النطاق الفرعي" : "Subdomain"}
        hint={
          isAr
            ? "لتغييره استخدم صفحة \"النطاق الفرعي\" المنفصلة (محدود التكرار)."
            : "Change this from the dedicated Subdomain screen (rate-limited)."
        }
      >
        <div className="flex">
          <Input
            value={initial.subdomain}
            disabled
            readOnly
            className="bg-muted/40 rounded-r-none"
          />
          <div className="grid place-items-center px-3 h-10 rounded-r-md border border-l-0 border-input bg-muted/40 text-sm text-muted-foreground">
            {initial.dashboard_url
              ? new URL(initial.dashboard_url).host.split(".").slice(1).join(".")
              : "mostashari.app"}
          </div>
        </div>
      </Field>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <Field label={isAr ? "الرقم الضريبي (VAT)" : "VAT number"}>
          <Input
            name="vat_number"
            defaultValue={initial.vat_number ?? ""}
            maxLength={20}
            placeholder="3xxxxxxxxxxxxx3"
          />
        </Field>
        <Field label={isAr ? "بريد الفواتير" : "Billing email"}>
          <Input
            type="email"
            name="billing_email"
            defaultValue={initial.billing_email ?? ""}
            placeholder={isAr ? "للفواتير والإيصالات" : "For invoices & receipts"}
          />
        </Field>
      </div>

      <Field label={isAr ? "عنوان الفوترة" : "Billing address"}>
        <Textarea
          name="billing_address"
          defaultValue={initial.billing_address ?? ""}
          rows={3}
          maxLength={2000}
          placeholder={
            isAr
              ? "الشارع، الحي، المدينة، الرمز البريدي"
              : "Street, district, city, postal code"
          }
        />
      </Field>

      {error && (
        <div className="rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive">
          {error}
        </div>
      )}

      <div className="flex items-center gap-3 pt-2">
        <Button type="submit" disabled={submitting}>
          {submitting && <Loader2 className="h-4 w-4 animate-spin" />}
          {isAr ? "حفظ بيانات الشركة" : "Save firm details"}
        </Button>
        {saved && !submitting && (
          <span className="inline-flex items-center gap-1.5 text-sm text-emerald-600 dark:text-emerald-400">
            <Check className="h-4 w-4" />
            {isAr ? "تم الحفظ" : "Saved"}
          </span>
        )}
      </div>
    </form>
  );
}

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="text-sm font-medium text-foreground/90 mb-1.5 block">
        {label}
      </span>
      {children}
      {hint && (
        <p className="mt-1.5 text-xs text-muted-foreground">{hint}</p>
      )}
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
