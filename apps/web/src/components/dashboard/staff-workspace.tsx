"use client";

import { CheckCircle2, MessageCircle, Plus, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState, useTransition } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

interface StaffMember {
  id: string;
  full_name: string;
  email: string;
  role: string;
  locale: string;
  phone_number: string | null;
  is_active: boolean;
  created_at: string;
}

type Role = "admin" | "lawyer" | "partner" | "paralegal";

const ROLES: Role[] = ["admin", "lawyer", "partner", "paralegal"];

/** Staff workspace.
 *
 * Two responsibilities:
 *   - render the staff list (name, email, role, WhatsApp phone, status)
 *   - host the "add staff member" inline form
 *
 * Phone numbers are first-class: when an admin sets one, the API mirrors
 * the digits into the tenant's WhatsApp allowlist so the AI agent picks
 * them up automatically. The same is true on edit/deactivate. */
export function StaffWorkspace({
  initialStaff,
}: {
  initialStaff: StaffMember[];
}) {
  const t = useTranslations("dashboard.crm.staff");
  const tCommon = useTranslations("dashboard.crm.common");
  const [staff, setStaff] = useState<StaffMember[]>(initialStaff);
  const [showCreate, setShowCreate] = useState(false);
  const [, startTransition] = useTransition();

  function handleCreated(member: StaffMember) {
    setStaff((prev) => [member, ...prev]);
    setShowCreate(false);
  }

  async function updatePhone(id: string, phone: string) {
    const res = await fetch(`/api/v1/team/users/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ phone_number: phone || null }),
    });
    if (res.ok) {
      const updated = (await res.json()) as StaffMember;
      setStaff((prev) => prev.map((p) => (p.id === updated.id ? updated : p)));
    }
  }

  async function deactivate(id: string) {
    const res = await fetch(`/api/v1/team/users/${id}`, { method: "DELETE" });
    if (res.ok) {
      setStaff((prev) =>
        prev.map((p) =>
          p.id === id ? { ...p, is_active: false, phone_number: null } : p,
        ),
      );
    }
  }

  return (
    <>
      <div className="flex justify-end">
        <Button size="sm" onClick={() => setShowCreate(true)}>
          <Plus className="h-4 w-4 me-1" /> {t("new")}
        </Button>
      </div>

      {showCreate && (
        <CreateStaffCard
          onCancel={() => setShowCreate(false)}
          onCreated={(member) =>
            startTransition(() => handleCreated(member))
          }
        />
      )}

      {staff.length === 0 ? (
        <Card className="p-10 text-center text-sm text-muted-foreground">
          {t("empty")}
        </Card>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {staff.map((member) => (
            <StaffCard
              key={member.id}
              member={member}
              onPhoneSave={(phone) => updatePhone(member.id, phone)}
              onDeactivate={() => deactivate(member.id)}
              tDelete={tCommon("delete")}
            />
          ))}
        </div>
      )}
    </>
  );
}

function StaffCard({
  member,
  onPhoneSave,
  onDeactivate,
  tDelete,
}: {
  member: StaffMember;
  onPhoneSave: (phone: string) => void;
  onDeactivate: () => void;
  tDelete: string;
}) {
  const t = useTranslations("dashboard.crm.staff");
  const [editing, setEditing] = useState(false);
  const [phone, setPhone] = useState(member.phone_number ?? "");

  function save() {
    onPhoneSave(phone.trim());
    setEditing(false);
  }

  return (
    <Card className="p-5 flex flex-col gap-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="font-semibold leading-tight truncate">
            {member.full_name}
          </p>
          <p className="text-xs text-muted-foreground truncate">
            {member.email}
          </p>
        </div>
        <Badge
          variant="outline"
          className={cn(
            "text-[10px] uppercase tracking-wider shrink-0",
            member.is_active
              ? "border-emerald-500/40 text-emerald-700 dark:text-emerald-400"
              : "text-muted-foreground",
          )}
        >
          {member.is_active ? t("active") : t("inactive")}
        </Badge>
      </div>

      <div className="flex flex-wrap gap-1.5">
        <Badge variant="outline" className="text-[10px] uppercase">
          {roleLabel(member.role, t)}
        </Badge>
        <Badge variant="outline" className="text-[10px] uppercase">
          {member.locale}
        </Badge>
      </div>

      {/* WhatsApp number row */}
      <div className="rounded-md border bg-muted/30 px-3 py-2 text-sm space-y-2">
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <MessageCircle className="h-3.5 w-3.5" />
          <span>{t("fieldPhone")}</span>
          {member.phone_number ? (
            <span className="ms-auto inline-flex items-center gap-1 text-emerald-700 dark:text-emerald-400 font-medium">
              <CheckCircle2 className="h-3 w-3" />
              {t("phoneSynced")}
            </span>
          ) : (
            <span className="ms-auto text-muted-foreground/80">
              {t("phoneEmpty")}
            </span>
          )}
        </div>
        {editing ? (
          <div className="flex gap-2">
            <Input
              type="tel"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              placeholder="9665XXXXXXXX"
              className="h-8 text-sm"
              autoFocus
            />
            <Button size="sm" onClick={save} className="h-8">
              {t("savePhone")}
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => {
                setEditing(false);
                setPhone(member.phone_number ?? "");
              }}
              className="h-8 w-8 p-0"
              aria-label="Cancel"
            >
              <X className="h-4 w-4" />
            </Button>
          </div>
        ) : (
          <div className="flex items-center gap-2">
            <span className="font-mono text-sm tabular-nums">
              {member.phone_number || "—"}
            </span>
            <button
              type="button"
              onClick={() => setEditing(true)}
              className="ms-auto text-xs text-primary hover:underline"
            >
              {t("edit")}
            </button>
          </div>
        )}
      </div>

      {member.is_active && (
        <button
          type="button"
          onClick={onDeactivate}
          className="text-xs text-destructive hover:underline text-end"
        >
          {t("deactivate")}
        </button>
      )}
    </Card>
  );
}

function CreateStaffCard({
  onCancel,
  onCreated,
}: {
  onCancel: () => void;
  onCreated: (member: StaffMember) => void;
}) {
  const t = useTranslations("dashboard.crm.staff");
  const tCommon = useTranslations("dashboard.crm.common");
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [role, setRole] = useState<Role>("lawyer");
  const [locale, setLocale] = useState("ar");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!fullName.trim() || !email.trim()) return;
    setPending(true);
    setError(null);
    try {
      const res = await fetch("/api/v1/team/staff", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          full_name: fullName.trim(),
          email: email.trim(),
          phone_number: phone.trim() || null,
          role,
          locale,
          is_active: true,
        }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        throw new Error(body?.detail || `HTTP ${res.status}`);
      }
      const member = (await res.json()) as StaffMember;
      onCreated(member);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed");
    } finally {
      setPending(false);
    }
  }

  return (
    <Card className="p-5">
      <form onSubmit={submit} className="space-y-3">
        <h3 className="font-semibold">{t("createTitle")}</h3>
        <Input
          placeholder={t("fieldFullName")}
          value={fullName}
          onChange={(e) => setFullName(e.target.value)}
          required
          autoFocus
        />
        <Input
          type="email"
          placeholder={t("fieldEmail")}
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
        <div className="space-y-1">
          <Input
            type="tel"
            placeholder="9665XXXXXXXX"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
          />
          <p className="text-[11px] text-muted-foreground">
            {t("fieldPhoneHint")}
          </p>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <select
            value={role}
            onChange={(e) => setRole(e.target.value as Role)}
            className="rounded-md border bg-background px-3 py-2 text-sm"
            aria-label={t("fieldRole")}
          >
            {ROLES.map((r) => (
              <option key={r} value={r}>
                {roleLabel(r, t)}
              </option>
            ))}
          </select>
          <select
            value={locale}
            onChange={(e) => setLocale(e.target.value)}
            className="rounded-md border bg-background px-3 py-2 text-sm"
            aria-label={t("fieldLocale")}
          >
            <option value="ar">العربية</option>
            <option value="en">English</option>
          </select>
        </div>
        {error && <p className="text-sm text-destructive">{error}</p>}
        <div className="flex gap-2 justify-end">
          <Button type="button" variant="outline" size="sm" onClick={onCancel}>
            {tCommon("cancel")}
          </Button>
          <Button type="submit" size="sm" disabled={pending}>
            {pending ? "…" : tCommon("create")}
          </Button>
        </div>
      </form>
    </Card>
  );
}

function roleLabel(
  role: string,
  t: ReturnType<typeof useTranslations>,
): string {
  switch (role) {
    case "admin":
      return t("roleAdmin");
    case "lawyer":
      return t("roleLawyer");
    case "partner":
      return t("rolePartner");
    case "paralegal":
      return t("roleParalegal");
    default:
      return role;
  }
}
