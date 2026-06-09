"use client";

/**
 * Filterable cases list. Server hands every case down; this component
 * handles search + status/domain/priority chips + sort. The previous
 * inline JSON dump of `ai_analysis` is gone — it belongs on the case
 * detail page where it's properly rendered.
 */
import { useMemo, useState } from "react";
import { ArrowRight, Brain, Briefcase, Sparkles } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { FilterBar, type ChipGroup } from "@/components/dashboard/filter-bar";
import { Link } from "@/i18n/routing";
import { formatDate } from "@/lib/utils";

export interface CaseRow {
  id: string;
  reference: string;
  title: string;
  domain: string;
  status: string;
  priority?: string;
  created_at: string;
  ai_analysis?: Record<string, unknown> | null;
}

type StatusFilter = "all" | "intake" | "open" | "in_court" | "settled" | "closed" | "archived";
type DomainFilter = "all" | "commercial" | "labor" | "family" | "criminal" | "real_estate" | "administrative" | "ip" | "corporate" | "banking" | "other";
type PriorityFilter = "all" | "low" | "medium" | "high" | "urgent";
type SortMode = "recent" | "oldest" | "reference";

const STATUS_LABEL_AR: Record<string, string> = {
  intake: "استقبال",
  open: "مفتوحة",
  in_court: "أمام المحكمة",
  settled: "تسوية",
  closed: "مغلقة",
  archived: "مؤرشفة",
};
const DOMAIN_LABEL_AR: Record<string, string> = {
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
const PRIORITY_LABEL_AR: Record<string, string> = {
  low: "منخفضة",
  medium: "متوسطة",
  high: "عالية",
  urgent: "عاجلة",
};

export function CasesList({
  cases,
  locale,
  isAr,
}: {
  cases: CaseRow[];
  locale: string;
  isAr: boolean;
}) {
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<StatusFilter>("all");
  const [domain, setDomain] = useState<DomainFilter>("all");
  const [priority, setPriority] = useState<PriorityFilter>("all");
  const [sort, setSort] = useState<SortMode>("recent");

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    const rows = cases.filter((c) => {
      if (status !== "all" && c.status !== status) return false;
      if (domain !== "all" && c.domain !== domain) return false;
      if (priority !== "all" && (c.priority ?? "medium") !== priority) return false;
      if (q) {
        const hay = `${c.title} ${c.reference}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
    return [...rows].sort((a, b) => {
      if (sort === "reference") return a.reference.localeCompare(b.reference);
      if (sort === "oldest") return a.created_at.localeCompare(b.created_at);
      return b.created_at.localeCompare(a.created_at);
    });
  }, [cases, query, status, domain, priority, sort]);

  const chipGroups: ChipGroup[] = [
    {
      label: isAr ? "الحالة" : "Status",
      value: status,
      onChange: (v) => setStatus(v as StatusFilter),
      options: [
        { value: "all", label: isAr ? "الكل" : "All" },
        ...(["intake", "open", "in_court", "settled", "closed", "archived"] as const).map(
          (s) => ({
            value: s,
            label: isAr ? STATUS_LABEL_AR[s] : s.replace("_", " "),
            activeClassName: statusActive(s),
          })
        ),
      ],
    },
    {
      label: isAr ? "الأولوية" : "Priority",
      value: priority,
      onChange: (v) => setPriority(v as PriorityFilter),
      options: [
        { value: "all", label: isAr ? "الكل" : "All" },
        {
          value: "urgent",
          label: isAr ? PRIORITY_LABEL_AR.urgent : "Urgent",
          activeClassName: "bg-red-100 text-red-900 dark:bg-red-900/30 dark:text-red-200",
        },
        {
          value: "high",
          label: isAr ? PRIORITY_LABEL_AR.high : "High",
          activeClassName: "bg-orange-100 text-orange-900 dark:bg-orange-900/30 dark:text-orange-200",
        },
        {
          value: "medium",
          label: isAr ? PRIORITY_LABEL_AR.medium : "Medium",
        },
        {
          value: "low",
          label: isAr ? PRIORITY_LABEL_AR.low : "Low",
        },
      ],
    },
  ];

  return (
    <div className="space-y-4">
      <FilterBar
        query={query}
        onQueryChange={setQuery}
        placeholder={
          isAr ? "ابحث بالعنوان أو الرقم المرجعي…" : "Search by title or reference…"
        }
        chipGroups={chipGroups}
        sort={sort}
        onSortChange={setSort}
        sortOptions={[
          { value: "recent", label: isAr ? "الأحدث أولًا" : "Newest first" },
          { value: "oldest", label: isAr ? "الأقدم أولًا" : "Oldest first" },
          { value: "reference", label: isAr ? "حسب الرقم المرجعي" : "By reference" },
        ]}
        totalCount={cases.length}
        filteredCount={filtered.length}
        hasFilters={
          query.trim() !== "" ||
          status !== "all" ||
          domain !== "all" ||
          priority !== "all" ||
          sort !== "recent"
        }
        onReset={() => {
          setQuery("");
          setStatus("all");
          setDomain("all");
          setPriority("all");
          setSort("recent");
        }}
        isAr={isAr}
        noun={{
          singular: "case",
          plural: isAr ? "قضايا" : "cases",
        }}
      />

      {/* Secondary chip row for domain — kept separate because it has many
          values and we don't want to crush the main filter row. */}
      <DomainBar value={domain} onChange={setDomain} isAr={isAr} />

      {filtered.length === 0 ? (
        <Card className="border-dashed py-10 text-center text-sm text-muted-foreground">
          {isAr
            ? "لا توجد قضايا مطابقة للمرشحات الحالية."
            : "No cases match the current filters."}
        </Card>
      ) : (
        <Card className="overflow-hidden">
          <ul className="divide-y divide-border/60">
            {filtered.map((c) => {
              const hasAnalysis =
                c.ai_analysis && Object.keys(c.ai_analysis).length > 0;
              return (
                <li key={c.id}>
                  <Link
                    href={`/dashboard/cases/${c.id}`}
                    className="group flex items-start gap-4 px-4 py-3.5 hover:bg-muted/40 transition-colors"
                  >
                    <div className="grid h-10 w-10 place-items-center rounded-md bg-primary/10 text-primary shrink-0">
                      <Briefcase className="h-5 w-5" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="text-xs text-muted-foreground">
                        <span className="font-mono">{c.reference}</span>
                        {" · "}
                        {formatDate(c.created_at, locale)}
                      </div>
                      <div className="font-medium truncate group-hover:text-primary transition-colors mt-0.5">
                        {c.title}
                      </div>
                      <div className="flex flex-wrap items-center gap-1.5 mt-1.5">
                        <Badge variant="outline" className="text-[10px]">
                          {isAr ? DOMAIN_LABEL_AR[c.domain] ?? c.domain : c.domain}
                        </Badge>
                        <Badge
                          variant="secondary"
                          className={"text-[10px] " + statusActive(c.status)}
                        >
                          {isAr ? STATUS_LABEL_AR[c.status] ?? c.status : c.status}
                        </Badge>
                        {c.priority && c.priority !== "medium" && (
                          <Badge
                            variant={
                              c.priority === "urgent"
                                ? "destructive"
                                : c.priority === "high"
                                  ? "warning"
                                  : "secondary"
                            }
                            className="text-[10px]"
                          >
                            {isAr ? PRIORITY_LABEL_AR[c.priority] ?? c.priority : c.priority}
                          </Badge>
                        )}
                        {hasAnalysis && (
                          <span className="inline-flex items-center gap-1 text-[10px] text-primary">
                            <Sparkles className="h-3 w-3" />
                            {isAr ? "محلَّلة" : "Analyzed"}
                          </span>
                        )}
                      </div>
                    </div>
                    <ArrowRight
                      className={
                        "h-4 w-4 text-muted-foreground shrink-0 mt-1 group-hover:text-primary transition-colors " +
                        (isAr ? "rotate-180" : "")
                      }
                    />
                  </Link>
                </li>
              );
            })}
          </ul>
        </Card>
      )}
    </div>
  );
}

function DomainBar({
  value,
  onChange,
  isAr,
}: {
  value: DomainFilter;
  onChange: (v: DomainFilter) => void;
  isAr: boolean;
}) {
  const opts: { v: DomainFilter; label: string }[] = [
    { v: "all", label: isAr ? "كل المجالات" : "All domains" },
    ...(["commercial", "labor", "family", "criminal", "real_estate", "administrative", "ip", "corporate", "banking", "other"] as const).map(
      (d) => ({ v: d as DomainFilter, label: isAr ? DOMAIN_LABEL_AR[d] : d.replace("_", " ") })
    ),
  ];
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {opts.map((o) => {
        const active = o.v === value;
        return (
          <button
            key={o.v}
            type="button"
            onClick={() => onChange(o.v)}
            className={
              "h-7 px-2.5 text-xs font-medium rounded-full border transition-colors " +
              (active
                ? "bg-primary text-primary-foreground border-primary"
                : "border-border bg-background text-muted-foreground hover:text-foreground hover:border-foreground/40")
            }
          >
            {o.label}
          </button>
        );
      })}
    </div>
  );
}

function statusActive(status: string): string {
  switch (status) {
    case "intake":
      return "bg-amber-100 text-amber-900 dark:bg-amber-900/30 dark:text-amber-200";
    case "open":
      return "bg-sky-100 text-sky-900 dark:bg-sky-900/30 dark:text-sky-200";
    case "in_court":
      return "bg-primary/15 text-primary";
    case "settled":
      return "bg-emerald-100 text-emerald-900 dark:bg-emerald-900/30 dark:text-emerald-200";
    case "closed":
      return "bg-muted text-muted-foreground";
    case "archived":
      return "bg-muted text-muted-foreground";
    default:
      return "bg-muted text-foreground";
  }
}
