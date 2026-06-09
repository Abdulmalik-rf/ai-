"use client";

import { useTranslations, useLocale } from "next-intl";
import { Plus } from "lucide-react";
import { useMemo, useState } from "react";

import { FilterBar, type ChipGroup } from "@/components/dashboard/filter-bar";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Link } from "@/i18n/routing";
import { formatDate } from "@/lib/utils";

interface Hearing {
  id: string;
  case_id: string;
  scheduled_at: string;
  kind: string;
  status: string;
  duration_minutes: number | null;
  court_name: string | null;
  court_room: string | null;
  judge_name: string | null;
  opposing_counsel: string | null;
  outcome: string | null;
  notes: string | null;
}

interface CaseRef {
  id: string;
  reference: string;
  title: string;
}

const KINDS = [
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

const KIND_LABEL_AR: Record<(typeof KINDS)[number], string> = {
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

function kindLabel(k: string, isAr: boolean): string {
  if (isAr && k in KIND_LABEL_AR) {
    return KIND_LABEL_AR[k as (typeof KINDS)[number]];
  }
  return k.replace("_", " ");
}

function statusLabel(s: string, isAr: boolean): string {
  return isAr ? STATUS_LABEL_AR[s] ?? s : s.replace("_", " ");
}

export function HearingsWorkspace({
  initialHearings,
  cases,
}: {
  initialHearings: Hearing[];
  cases: CaseRef[];
}) {
  const t = useTranslations("dashboard.crm.hearings");
  const tCommon = useTranslations("dashboard.crm.common");
  const locale = useLocale();
  const [hearings, setHearings] = useState<Hearing[]>(initialHearings);
  const [showCreate, setShowCreate] = useState(false);
  const isAr = locale === "ar";

  // Filters
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | "scheduled" | "attended" | "postponed" | "cancelled">("all");
  const [whenFilter, setWhenFilter] = useState<"all" | "upcoming" | "past">("all");

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    const nowMs = Date.now();
    return hearings.filter((h) => {
      if (statusFilter !== "all" && h.status !== statusFilter) return false;
      if (whenFilter === "upcoming" && new Date(h.scheduled_at).getTime() < nowMs) return false;
      if (whenFilter === "past" && new Date(h.scheduled_at).getTime() >= nowMs) return false;
      if (q) {
        const hay = `${h.court_name ?? ""} ${h.judge_name ?? ""} ${h.kind} ${h.notes ?? ""}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }, [hearings, query, statusFilter, whenFilter]);

  const now = Date.now();
  const today = new Date().toISOString().slice(0, 10);
  const todayList = filtered.filter(
    (h) => h.scheduled_at.slice(0, 10) === today
  );
  const upcoming = filtered.filter(
    (h) => new Date(h.scheduled_at).getTime() > now && h.scheduled_at.slice(0, 10) !== today
  );
  const past = filtered.filter(
    (h) => new Date(h.scheduled_at).getTime() < now && h.scheduled_at.slice(0, 10) !== today
  );

  function handleCreated(h: Hearing) {
    setHearings((prev) =>
      [...prev, h].sort(
        (a, b) =>
          new Date(a.scheduled_at).getTime() - new Date(b.scheduled_at).getTime()
      )
    );
    setShowCreate(false);
  }

  const chipGroups: ChipGroup[] = [
    {
      value: whenFilter,
      onChange: (v) => setWhenFilter(v as typeof whenFilter),
      options: [
        { value: "all", label: isAr ? "الكل" : "All" },
        {
          value: "upcoming",
          label: isAr ? "قادمة" : "Upcoming",
          activeClassName: "bg-primary/15 text-primary",
        },
        { value: "past", label: isAr ? "ماضية" : "Past" },
      ],
    },
    {
      value: statusFilter,
      onChange: (v) => setStatusFilter(v as typeof statusFilter),
      options: [
        { value: "all", label: isAr ? "الكل" : "All" },
        {
          value: "scheduled",
          label: isAr ? "مجدولة" : "Scheduled",
          activeClassName: "bg-sky-100 text-sky-900 dark:bg-sky-900/30 dark:text-sky-200",
        },
        {
          value: "attended",
          label: isAr ? "حضرت" : "Attended",
          activeClassName: "bg-emerald-100 text-emerald-900 dark:bg-emerald-900/30 dark:text-emerald-200",
        },
        {
          value: "postponed",
          label: isAr ? "مؤجلة" : "Postponed",
          activeClassName: "bg-amber-100 text-amber-900 dark:bg-amber-900/30 dark:text-amber-200",
        },
        {
          value: "cancelled",
          label: isAr ? "ملغاة" : "Cancelled",
          activeClassName: "bg-red-100 text-red-900 dark:bg-red-900/30 dark:text-red-200",
        },
      ],
    },
  ];

  return (
    <>
      <FilterBar
        query={query}
        onQueryChange={setQuery}
        placeholder={isAr ? "ابحث بالمحكمة أو القاضي…" : "Search court or judge…"}
        chipGroups={chipGroups}
        totalCount={hearings.length}
        filteredCount={filtered.length}
        hasFilters={
          query.trim() !== "" || statusFilter !== "all" || whenFilter !== "all"
        }
        onReset={() => {
          setQuery("");
          setStatusFilter("all");
          setWhenFilter("all");
        }}
        isAr={isAr}
        noun={{ singular: "hearing", plural: isAr ? "جلسات" : "hearings" }}
      />

      <div className="flex justify-end">
        <Button size="sm" onClick={() => setShowCreate(true)}>
          <Plus className="h-4 w-4 me-1" /> {t("new")}
        </Button>
      </div>

      {showCreate && (
        <CreateHearingCard
          cases={cases}
          onCancel={() => setShowCreate(false)}
          onCreated={handleCreated}
        />
      )}

      {hearings.length === 0 && !showCreate && (
        <p className="text-sm text-muted-foreground">{t("empty")}</p>
      )}

      <Section title={t("today")} hearings={todayList} cases={cases} locale={locale} />
      <Section title={t("upcoming")} hearings={upcoming} cases={cases} locale={locale} />
      <Section title={t("past")} hearings={past.slice(0, 20)} cases={cases} locale={locale} />
    </>
  );
}


function Section({
  title,
  hearings,
  cases,
  locale,
}: {
  title: string;
  hearings: Hearing[];
  cases: CaseRef[];
  locale: string;
}) {
  if (hearings.length === 0) return null;
  return (
    <section className="space-y-2">
      <h2 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
        {title}
      </h2>
      <ul className="space-y-2">
        {hearings.map((h) => {
          const c = cases.find((x) => x.id === h.case_id);
          const dt = new Date(h.scheduled_at);
          return (
            <Card key={h.id} className="p-4">
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <Link
                    href={`/dashboard/cases/${h.case_id}`}
                    className="font-medium hover:underline truncate block"
                  >
                    {c ? `${c.reference} · ${c.title}` : h.case_id}
                  </Link>
                  <p className="text-sm text-muted-foreground mt-1">
                    <Badge variant="outline" className="me-2">
                      {kindLabel(h.kind, locale === "ar")}
                    </Badge>
                    <span className="font-mono text-xs">
                      {dt.toLocaleString(locale === "ar" ? "ar-SA" : "en-GB", {
                        day: "2-digit",
                        month: "short",
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </span>
                    {h.court_name && <span> · {h.court_name}</span>}
                    {h.court_room && <span> · {h.court_room}</span>}
                    {h.judge_name && <span> · 👨‍⚖️ {h.judge_name}</span>}
                  </p>
                  {h.outcome && (
                    <p className="text-sm mt-2 border-s-2 ps-3 border-primary/40 text-muted-foreground">
                      {h.outcome}
                    </p>
                  )}
                </div>
                <Badge variant="secondary">{statusLabel(h.status, locale === "ar")}</Badge>
              </div>
            </Card>
          );
        })}
      </ul>
    </section>
  );
}


function CreateHearingCard({
  cases,
  onCancel,
  onCreated,
}: {
  cases: CaseRef[];
  onCancel: () => void;
  onCreated: (h: Hearing) => void;
}) {
  const t = useTranslations("dashboard.crm.hearings");
  const tCommon = useTranslations("dashboard.crm.common");
  const isAr = useLocale() === "ar";
  const [caseId, setCaseId] = useState(cases[0]?.id || "");
  const [scheduledAt, setScheduledAt] = useState("");
  const [kind, setKind] = useState("hearing");
  const [courtName, setCourtName] = useState("");
  const [room, setRoom] = useState("");
  const [judge, setJudge] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!caseId || !scheduledAt) return;
    setPending(true);
    setError(null);
    try {
      const res = await fetch("/api/v1/hearings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          case_id: caseId,
          scheduled_at: new Date(scheduledAt).toISOString(),
          kind,
          court_name: courtName || null,
          court_room: room || null,
          judge_name: judge || null,
        }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        throw new Error(body?.detail || `HTTP ${res.status}`);
      }
      onCreated((await res.json()) as Hearing);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed");
    } finally {
      setPending(false);
    }
  }

  return (
    <Card className="p-5">
      <form onSubmit={submit} className="space-y-3">
        <h3 className="font-semibold">{t("new")}</h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <select
            value={caseId}
            onChange={(e) => setCaseId(e.target.value)}
            className="rounded-md border bg-background px-3 py-2 text-sm"
            aria-label={t("fieldCase")}
            required
          >
            <option value="">— {t("fieldCase")} —</option>
            {cases.map((c) => (
              <option key={c.id} value={c.id}>
                {c.reference} · {c.title.slice(0, 40)}
              </option>
            ))}
          </select>
          <Input
            type="datetime-local"
            value={scheduledAt}
            onChange={(e) => setScheduledAt(e.target.value)}
            required
            aria-label={t("fieldDate")}
          />
          <select
            value={kind}
            onChange={(e) => setKind(e.target.value)}
            className="rounded-md border bg-background px-3 py-2 text-sm"
            aria-label={t("fieldKind")}
          >
            {KINDS.map((k) => (
              <option key={k} value={k}>
                {kindLabel(k, isAr)}
              </option>
            ))}
          </select>
          <Input
            placeholder={t("fieldCourt")}
            value={courtName}
            onChange={(e) => setCourtName(e.target.value)}
          />
          <Input
            placeholder={t("fieldRoom")}
            value={room}
            onChange={(e) => setRoom(e.target.value)}
          />
          <Input
            placeholder={t("fieldJudge")}
            value={judge}
            onChange={(e) => setJudge(e.target.value)}
          />
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
