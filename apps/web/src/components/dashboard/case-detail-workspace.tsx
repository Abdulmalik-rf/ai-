"use client";

/**
 * Hearings workspace shown under each case.
 *
 * Previously this rendered a five-tab UI (tasks, hearings, time, notes,
 * activity). The user wanted the page focused on what actually matters for
 * a litigation case: the list of court sessions with their full details
 * inline. So the tabs and their sibling sub-resources are gone; what's left
 * is a hearing-creation card on top and a chronological session feed below
 * — each row spelling out every detail we have on file (court, circuit,
 * room, judge, opposing counsel, kind, status, duration, recorded
 * outcome).
 */
import { useLocale, useTranslations } from "next-intl";
import { useState } from "react";
import {
  Building2,
  Clock,
  Gavel,
  MapPin,
  Pencil,
  Plus,
  Scale,
  ScrollText,
  User,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { VoiceTextarea } from "@/components/dashboard/voice-textarea";

export interface Hearing {
  id: string;
  case_id: string;
  scheduled_at: string;
  kind: string;
  status: string;
  duration_minutes?: number | null;
  court_name: string | null;
  court_circuit?: string | null;
  court_room: string | null;
  judge_name: string | null;
  opposing_counsel?: string | null;
  outcome: string | null;
  notes?: string | null;
  created_at?: string;
}

const HEARING_KINDS = [
  "hearing",
  "mediation",
  "deposition",
  "filing_deadline",
  "response_deadline",
  "settlement",
  "appeal_deadline",
  "expert_meeting",
  "other",
] as const;

const KIND_LABEL_AR: Record<string, string> = {
  hearing: "جلسة",
  mediation: "وساطة",
  deposition: "استجواب",
  filing_deadline: "مهلة إيداع",
  response_deadline: "مهلة رد",
  settlement: "تسوية",
  appeal_deadline: "مهلة استئناف",
  expert_meeting: "اجتماع خبير",
  other: "أخرى",
};

const STATUS_LABEL_AR: Record<string, string> = {
  scheduled: "مجدولة",
  attended: "حضرت",
  postponed: "مؤجلة",
  cancelled: "ملغاة",
  no_show: "تغيب",
};

export function CaseDetailWorkspace(props: {
  caseId: string;
  hearings: Hearing[];
}) {
  const t = useTranslations("dashboard.crm.hearings");
  const tCommon = useTranslations("dashboard.crm.common");
  const locale = useLocale();
  const isAr = locale === "ar";

  const [hearings, setHearings] = useState<Hearing[]>(props.hearings);
  const [showForm, setShowForm] = useState(false);

  async function createHearing(payload: Omit<Hearing, "id" | "case_id" | "status" | "created_at">) {
    const res = await fetch("/api/v1/hearings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        case_id: props.caseId,
        scheduled_at: new Date(payload.scheduled_at).toISOString(),
        kind: payload.kind,
        duration_minutes: payload.duration_minutes ?? null,
        court_name: payload.court_name || null,
        court_circuit: payload.court_circuit || null,
        court_room: payload.court_room || null,
        judge_name: payload.judge_name || null,
        opposing_counsel: payload.opposing_counsel || null,
        notes: payload.notes || null,
      }),
    });
    if (!res.ok) return null;
    const h = (await res.json()) as Hearing;
    setHearings((p) => [h, ...p]);
    setShowForm(false);
    return h;
  }

  async function patchHearing(id: string, patch: Partial<Hearing>) {
    const res = await fetch(`/api/v1/hearings/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(patch),
    });
    if (!res.ok) return;
    const updated = (await res.json()) as Hearing;
    setHearings((p) => p.map((x) => (x.id === id ? updated : x)));
  }

  const sorted = [...hearings].sort(
    (a, b) => new Date(b.scheduled_at).getTime() - new Date(a.scheduled_at).getTime(),
  );
  const upcomingCount = hearings.filter((h) => h.status === "scheduled").length;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h2 className="text-xl font-semibold flex items-center gap-2">
            <Scale className="h-5 w-5 text-primary" />
            {isAr ? "الجلسات" : "Hearings"}
            <span className="text-sm font-normal text-muted-foreground">
              ({hearings.length}
              {upcomingCount > 0 && (
                <> · {isAr ? `${upcomingCount} قادمة` : `${upcomingCount} upcoming`}</>
              )}
              )
            </span>
          </h2>
          <p className="text-sm text-muted-foreground mt-0.5">
            {isAr
              ? "كل الجلسات المسجّلة في هذه القضية، الأحدث في الأعلى."
              : "Every session logged on this case, newest first."}
          </p>
        </div>
        <Button size="sm" onClick={() => setShowForm((v) => !v)}>
          <Plus className="h-4 w-4" />
          {isAr ? "جلسة جديدة" : "New hearing"}
        </Button>
      </div>

      {showForm && (
        <HearingForm
          isAr={isAr}
          tCommon={tCommon}
          mode="create"
          onCancel={() => setShowForm(false)}
          onSubmit={async (values) => {
            await createHearing({
              scheduled_at: values.scheduled_at,
              kind: values.kind,
              duration_minutes: values.duration_minutes,
              court_name: values.court_name,
              court_circuit: values.court_circuit,
              court_room: values.court_room,
              judge_name: values.judge_name,
              opposing_counsel: values.opposing_counsel,
              outcome: null,
              notes: values.notes,
            });
          }}
        />
      )}

      {sorted.length === 0 ? (
        <Card className="border-dashed py-12 text-center text-sm text-muted-foreground">
          {isAr
            ? "لا توجد جلسات بعد. اضغط «جلسة جديدة» لتسجيل أولى الجلسات."
            : "No hearings yet. Tap \"New hearing\" to log the first session."}
        </Card>
      ) : (
        <div className="space-y-3">
          {sorted.map((h) => (
            <HearingCard
              key={h.id}
              hearing={h}
              locale={locale}
              isAr={isAr}
              onPatch={patchHearing}
            />
          ))}
        </div>
      )}
    </div>
  );
}

// ============================================================================
// Creation + edit form (same UI; the `mode` flag controls whether we expose
// the status dropdown — status starts as `scheduled` for new entries and is
// editable once the row exists)
// ============================================================================

const HEARING_STATUSES = [
  "scheduled",
  "attended",
  "postponed",
  "cancelled",
  "no_show",
] as const;

interface HearingFormValues {
  scheduled_at: string;
  kind: string;
  status?: string;
  duration_minutes: number | null;
  court_name: string;
  court_circuit: string;
  court_room: string;
  judge_name: string;
  opposing_counsel: string;
  outcome?: string | null;
  notes: string;
}

/** Convert an ISO string to the local datetime value expected by the
 *  `<input type="datetime-local">` element. */
function toLocalDatetimeInput(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function HearingForm({
  isAr,
  tCommon,
  mode,
  initial,
  onCancel,
  onSubmit,
}: {
  isAr: boolean;
  tCommon: (k: string) => string;
  mode: "create" | "edit";
  /** Existing hearing for edit mode (ignored when creating). */
  initial?: Hearing;
  onCancel: () => void;
  /** In create mode receives the new hearing's full payload; in edit mode
   *  receives only the changed-shape values to PATCH. */
  onSubmit: (values: HearingFormValues) => Promise<unknown>;
}) {
  const [scheduledAt, setScheduledAt] = useState(
    mode === "edit" ? toLocalDatetimeInput(initial?.scheduled_at) : "",
  );
  const [kind, setKind] = useState(initial?.kind ?? "hearing");
  const [status, setStatus] = useState(initial?.status ?? "scheduled");
  const [duration, setDuration] = useState(
    initial?.duration_minutes != null ? String(initial.duration_minutes) : "",
  );
  const [court, setCourt] = useState(initial?.court_name ?? "");
  const [circuit, setCircuit] = useState(initial?.court_circuit ?? "");
  const [room, setRoom] = useState(initial?.court_room ?? "");
  const [judge, setJudge] = useState(initial?.judge_name ?? "");
  const [opposing, setOpposing] = useState(initial?.opposing_counsel ?? "");
  const [notes, setNotes] = useState(initial?.notes ?? "");
  const [pending, setPending] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!scheduledAt) return;
    setPending(true);
    const payload: HearingFormValues = {
      scheduled_at: scheduledAt,
      kind,
      duration_minutes: duration ? Number(duration) : null,
      court_name: court,
      court_circuit: circuit,
      court_room: room,
      judge_name: judge,
      opposing_counsel: opposing,
      notes,
    };
    if (mode === "edit") {
      payload.status = status;
      payload.outcome = initial?.outcome ?? null;
    } else {
      payload.outcome = null;
    }
    await onSubmit(payload);
    setPending(false);
  }

  return (
    <Card className="p-5 space-y-4">
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <Field label={isAr ? "تاريخ ووقت الجلسة" : "Scheduled at"}>
            <Input
              type="datetime-local"
              value={scheduledAt}
              onChange={(e) => setScheduledAt(e.target.value)}
              required
            />
          </Field>
          <Field label={isAr ? "نوع الجلسة" : "Kind"}>
            <SelectNative value={kind} onChange={setKind}>
              {HEARING_KINDS.map((k) => (
                <option key={k} value={k}>
                  {isAr ? KIND_LABEL_AR[k] ?? k : k.replace("_", " ")}
                </option>
              ))}
            </SelectNative>
          </Field>
          <Field label={isAr ? "المدة (دقائق)" : "Duration (min)"}>
            <Input
              type="number"
              min="0"
              value={duration}
              onChange={(e) => setDuration(e.target.value)}
              placeholder="60"
            />
          </Field>
        </div>

        {mode === "edit" && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <Field label={isAr ? "حالة الجلسة" : "Status"}>
              <SelectNative value={status} onChange={setStatus}>
                {HEARING_STATUSES.map((s) => (
                  <option key={s} value={s}>
                    {isAr ? STATUS_LABEL_AR[s] ?? s : s.replace("_", " ")}
                  </option>
                ))}
              </SelectNative>
            </Field>
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <Field label={isAr ? "المحكمة" : "Court"}>
            <Input
              value={court}
              onChange={(e) => setCourt(e.target.value)}
              placeholder={isAr ? "المحكمة التجارية بالرياض" : "Commercial Court of Riyadh"}
            />
          </Field>
          <Field label={isAr ? "الدائرة" : "Circuit"}>
            <Input
              value={circuit}
              onChange={(e) => setCircuit(e.target.value)}
              placeholder={isAr ? "الدائرة التجارية الثالثة" : "3rd Commercial Circuit"}
            />
          </Field>
          <Field label={isAr ? "القاعة" : "Court room"}>
            <Input
              value={room}
              onChange={(e) => setRoom(e.target.value)}
              placeholder={isAr ? "قاعة ٢" : "Room 2"}
            />
          </Field>
          <Field label={isAr ? "القاضي" : "Judge"}>
            <Input value={judge} onChange={(e) => setJudge(e.target.value)} />
          </Field>
          <Field label={isAr ? "محامي الخصم" : "Opposing counsel"}>
            <Input value={opposing} onChange={(e) => setOpposing(e.target.value)} />
          </Field>
        </div>

        <Field label={isAr ? "ملاحظات" : "Notes"}>
          <VoiceTextarea
            value={notes}
            onChange={setNotes}
            rows={3}
            placeholder={
              isAr
                ? "ملاحظات داخلية للفريق… (يمكنك الضغط على المايكروفون لإملائها)"
                : "Internal notes for the team… (tap the mic to dictate)"
            }
          />
        </Field>

        <div className="flex justify-end gap-2">
          <Button type="button" variant="outline" size="sm" onClick={onCancel}>
            {tCommon("cancel")}
          </Button>
          <Button type="submit" size="sm" disabled={pending}>
            {mode === "edit"
              ? isAr
                ? "حفظ التعديلات"
                : "Save changes"
              : tCommon("create")}
          </Button>
        </div>
      </form>
    </Card>
  );
}

// ============================================================================
// Detail card per hearing
// ============================================================================

function HearingCard({
  hearing,
  locale,
  isAr,
  onPatch,
}: {
  hearing: Hearing;
  locale: string;
  isAr: boolean;
  onPatch: (id: string, patch: Partial<Hearing>) => Promise<void>;
}) {
  const [editingOutcome, setEditingOutcome] = useState(false);
  const [outcome, setOutcome] = useState(hearing.outcome ?? "");
  // Full-card edit mode: when true the card body is replaced with the
  // same form used for creating new hearings, pre-filled from this row.
  const [editing, setEditing] = useState(false);
  const tCommon = useTranslations("dashboard.crm.common");

  if (editing) {
    return (
      <Card className="overflow-hidden">
        <div className="px-4 pt-4 pb-2 flex items-center justify-between">
          <div className="text-sm font-medium">
            {isAr ? "تعديل الجلسة" : "Edit hearing"}
          </div>
        </div>
        <div className="p-4 pt-0">
          <HearingForm
            isAr={isAr}
            tCommon={tCommon}
            mode="edit"
            initial={hearing}
            onCancel={() => setEditing(false)}
            onSubmit={async (values) => {
              await onPatch(hearing.id, {
                scheduled_at: new Date(values.scheduled_at).toISOString(),
                kind: values.kind,
                status: values.status,
                duration_minutes: values.duration_minutes,
                court_name: values.court_name || null,
                court_circuit: values.court_circuit || null,
                court_room: values.court_room || null,
                judge_name: values.judge_name || null,
                opposing_counsel: values.opposing_counsel || null,
                notes: values.notes || null,
              });
              setEditing(false);
            }}
          />
        </div>
      </Card>
    );
  }

  const date = new Date(hearing.scheduled_at);
  const dateFull = date.toLocaleString(isAr ? "ar-SA" : "en-GB", {
    weekday: "short",
    day: "2-digit",
    month: "long",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
  const dayShort = date.toLocaleDateString(isAr ? "ar-SA" : "en-GB", {
    day: "2-digit",
    month: "short",
  });
  const timeShort = date.toLocaleTimeString(isAr ? "ar-SA" : "en-GB", {
    hour: "2-digit",
    minute: "2-digit",
  });

  const kindLabel = isAr
    ? KIND_LABEL_AR[hearing.kind] ?? hearing.kind
    : hearing.kind.replace("_", " ");
  const statusLabel = isAr
    ? STATUS_LABEL_AR[hearing.status] ?? hearing.status
    : hearing.status;

  const isPast = date.getTime() < Date.now();
  const isUpcoming = hearing.status === "scheduled" && !isPast;

  return (
    <Card className="overflow-hidden">
      <div className="grid grid-cols-[auto_1fr] gap-0">
        {/* Date column */}
        <div
          className={
            "px-4 py-5 grid place-items-center border-e border-border/60 " +
            (isUpcoming
              ? "bg-primary/5"
              : hearing.status === "cancelled"
                ? "bg-muted/40"
                : "bg-muted/20")
          }
        >
          <div className="text-center">
            <div className="text-2xl font-bold tabular-nums leading-tight">
              {dayShort}
            </div>
            <div className="text-xs text-muted-foreground tabular-nums mt-0.5">
              {timeShort}
            </div>
          </div>
        </div>

        {/* Detail column */}
        <div className="p-4 space-y-3">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant={isUpcoming ? "default" : "outline"}>
                {kindLabel}
              </Badge>
              <Badge variant={statusBadgeVariant(hearing.status)}>
                {statusLabel}
              </Badge>
              <span className="text-xs text-muted-foreground">{dateFull}</span>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setEditing(true)}
              className="shrink-0"
            >
              <Pencil className="h-3.5 w-3.5" />
              {isAr ? "تعديل" : "Edit"}
            </Button>
          </div>

          {/* Fact grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-2 text-sm">
            <Fact
              icon={Building2}
              label={isAr ? "المحكمة" : "Court"}
              value={hearing.court_name}
            />
            <Fact
              icon={ScrollText}
              label={isAr ? "الدائرة" : "Circuit"}
              value={hearing.court_circuit ?? null}
            />
            <Fact
              icon={MapPin}
              label={isAr ? "القاعة" : "Court room"}
              value={hearing.court_room}
            />
            <Fact
              icon={Gavel}
              label={isAr ? "القاضي" : "Judge"}
              value={hearing.judge_name}
            />
            <Fact
              icon={User}
              label={isAr ? "محامي الخصم" : "Opposing counsel"}
              value={hearing.opposing_counsel ?? null}
            />
            {hearing.duration_minutes != null && (
              <Fact
                icon={Clock}
                label={isAr ? "المدة" : "Duration"}
                value={`${hearing.duration_minutes} ${isAr ? "د" : "min"}`}
              />
            )}
          </div>

          {hearing.notes && (
            <div className="rounded-md bg-muted/40 px-3 py-2 text-sm text-foreground/90">
              <div className="text-xs text-muted-foreground mb-0.5">
                {isAr ? "ملاحظات" : "Notes"}
              </div>
              <p className="whitespace-pre-wrap">{hearing.notes}</p>
            </div>
          )}

          {/* Outcome — viewable / editable. Voice-enabled so the lawyer
              can dictate what happened in court right after the session. */}
          <div className="pt-1 border-t border-border/40">
            {editingOutcome ? (
              <div className="space-y-2 pt-2">
                <VoiceTextarea
                  value={outcome}
                  onChange={setOutcome}
                  rows={4}
                  placeholder={
                    isAr
                      ? "نتيجة الجلسة، القرارات المتخذة، الموعد التالي… (اضغط المايكروفون للإملاء)"
                      : "Decisions made, what was recorded, next date… (tap the mic to dictate)"
                  }
                />
                <div className="flex justify-end gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      setOutcome(hearing.outcome ?? "");
                      setEditingOutcome(false);
                    }}
                  >
                    {isAr ? "إلغاء" : "Cancel"}
                  </Button>
                  <Button
                    size="sm"
                    onClick={async () => {
                      await onPatch(hearing.id, {
                        outcome: outcome || null,
                        status: outcome ? "attended" : hearing.status,
                      });
                      setEditingOutcome(false);
                    }}
                  >
                    {isAr ? "حفظ النتيجة" : "Save outcome"}
                  </Button>
                </div>
              </div>
            ) : hearing.outcome ? (
              <div className="pt-2">
                <div className="text-xs text-muted-foreground mb-1">
                  {isAr ? "النتيجة" : "Outcome"}
                </div>
                <div className="flex items-start justify-between gap-3">
                  <p className="text-sm whitespace-pre-wrap flex-1">
                    {hearing.outcome}
                  </p>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setEditingOutcome(true)}
                  >
                    {isAr ? "تعديل" : "Edit"}
                  </Button>
                </div>
              </div>
            ) : (
              <div className="pt-2 flex items-center gap-2">
                <span className="text-xs text-muted-foreground">
                  {isAr ? "لم تُسجَّل النتيجة بعد." : "No outcome recorded yet."}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setEditingOutcome(true)}
                >
                  {isAr ? "تسجيل النتيجة" : "Record outcome"}
                </Button>
              </div>
            )}
          </div>
        </div>
      </div>
    </Card>
  );
}

// ============================================================================
// Small helpers
// ============================================================================

function statusBadgeVariant(status: string) {
  switch (status) {
    case "scheduled":
      return "secondary" as const;
    case "attended":
      return "success" as const;
    case "cancelled":
      return "destructive" as const;
    case "postponed":
    case "no_show":
      return "warning" as const;
    default:
      return "outline" as const;
  }
}

function Fact({
  icon: Icon,
  label,
  value,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string | null | undefined;
}) {
  return (
    <div className="flex items-start gap-2">
      <Icon className="h-3.5 w-3.5 text-muted-foreground mt-0.5 shrink-0" />
      <div className="min-w-0">
        <div className="text-xs text-muted-foreground">{label}</div>
        <div className="text-sm font-medium truncate">
          {value || <span className="text-muted-foreground/60">—</span>}
        </div>
      </div>
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
      <span className="text-xs font-medium text-foreground/90 mb-1 block">
        {label}
      </span>
      {children}
    </label>
  );
}

function SelectNative({
  value,
  onChange,
  children,
}: {
  value: string;
  onChange: (v: string) => void;
  children: React.ReactNode;
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="w-full h-10 rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent"
    >
      {children}
    </select>
  );
}
