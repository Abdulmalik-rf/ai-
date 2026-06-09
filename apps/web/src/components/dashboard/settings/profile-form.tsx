"use client";

/**
 * Profile self-edit form. PATCHes /api/v1/auth/me with name + locale.
 * On success: toast-style banner and router.refresh() so the new values
 * propagate to the sidebar / header.
 */
import { Check, Loader2 } from "lucide-react";
import { useLocale } from "next-intl";
import { useRouter } from "next/navigation";
import * as React from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

interface ProfileFormProps {
  initial: {
    full_name: string;
    email: string;
    locale: string;
    role: string;
    phone_number: string | null;
  };
}

/** Normalise phone for the API: keep digits only — the bridge stores JIDs
 *  without leading + or whitespace. Empty string → null so the column clears. */
function normalisePhone(raw: string): string | null {
  const digits = raw.replace(/\D+/g, "");
  return digits.length > 0 ? digits : null;
}

export function ProfileForm({ initial }: ProfileFormProps) {
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
        full_name: String(fd.get("full_name") || "").trim(),
        locale: String(fd.get("locale") || "en"),
        phone_number: normalisePhone(String(fd.get("phone_number") || "")),
      };
      const res = await fetch("/api/v1/auth/me", {
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
      <Field label={isAr ? "الاسم الكامل" : "Full name"}>
        <Input
          name="full_name"
          defaultValue={initial.full_name}
          required
          maxLength={200}
        />
      </Field>

      <Field label={isAr ? "البريد الإلكتروني" : "Email"}>
        <Input value={initial.email} disabled readOnly className="bg-muted/40" />
        <p className="mt-1.5 text-xs text-muted-foreground">
          {isAr
            ? "لا يمكن تغيير البريد الإلكتروني من هنا. تواصل مع الدعم."
            : "Your email can't be changed here. Contact support if you need to."}
        </p>
      </Field>

      <Field label={isAr ? "رقم الجوال (واتساب)" : "Mobile number (WhatsApp)"}>
        <Input
          name="phone_number"
          type="tel"
          defaultValue={initial.phone_number ?? ""}
          maxLength={32}
          placeholder="9665XXXXXXXX"
          inputMode="tel"
          dir="ltr"
        />
        <p className="mt-1.5 text-xs text-muted-foreground">
          {isAr
            ? "بصيغة دولية بدون + (مثل 9665XXXXXXXX). عند تعيينه يُضاف تلقائيًا إلى قائمة واتساب المسموح بها للمكتب."
            : "Use the international format without + (e.g. 9665XXXXXXXX). When set, it's auto-added to your firm's WhatsApp allowlist."}
        </p>
      </Field>

      <div className="grid grid-cols-2 gap-3">
        <Field label={isAr ? "لغة الواجهة" : "Interface language"}>
          <SelectNative name="locale" defaultValue={initial.locale}>
            <option value="ar">العربية</option>
            <option value="en">English</option>
          </SelectNative>
        </Field>
        <Field label={isAr ? "الصلاحية" : "Role"}>
          <Input value={roleLabel(initial.role, isAr)} disabled readOnly className="bg-muted/40 capitalize" />
        </Field>
      </div>

      {error && (
        <div className="rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive">
          {error}
        </div>
      )}

      <div className="flex items-center gap-3 pt-2">
        <Button type="submit" disabled={submitting}>
          {submitting && <Loader2 className="h-4 w-4 animate-spin" />}
          {isAr ? "حفظ التغييرات" : "Save changes"}
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

function roleLabel(role: string, isAr: boolean) {
  if (!isAr) return role;
  switch (role) {
    case "admin":
      return "مدير";
    case "lawyer":
      return "محامٍ";
    case "staff":
      return "موظف";
    case "super_admin":
      return "مشرف النظام";
    default:
      return role;
  }
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
