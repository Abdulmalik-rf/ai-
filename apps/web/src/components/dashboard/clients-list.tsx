"use client";

/**
 * Filterable clients list. Server fetches every client (cheap — they're
 * tenant-scoped) and the client component handles the search + chips +
 * sort interaction so filters feel instant.
 *
 * Filters offered:
 *   - free-text search across name, email, phone and the KSA IDs
 *   - status chips (all / lead / prospect / active / archived) — matches
 *     the `clients.status` column the API exposes
 *   - kind chips (all / person / company)
 *   - sort: most recent first (default), name A→Z
 */
import { useMemo, useState } from "react";
import {
  Building2,
  ChevronLeft,
  ChevronRight,
  Mail,
  Phone,
  Search,
  User,
  X,
} from "lucide-react";

import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Link } from "@/i18n/routing";
import { cn } from "@/lib/utils";

export interface ClientRow {
  id: string;
  name: string;
  kind: string;
  status?: string;
  email: string | null;
  phone: string | null;
  national_id: string | null;
  cr_number: string | null;
  created_at?: string;
}

type StatusFilter = "all" | "lead" | "prospect" | "active" | "archived";
type KindFilter = "all" | "person" | "company";
type SortMode = "recent" | "name";

export function ClientsList({
  clients,
  isAr,
  kindCompany,
  kindPerson,
}: {
  clients: ClientRow[];
  isAr: boolean;
  kindCompany: string;
  kindPerson: string;
}) {
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<StatusFilter>("all");
  const [kind, setKind] = useState<KindFilter>("all");
  const [sort, setSort] = useState<SortMode>("recent");

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    const rows = clients.filter((c) => {
      if (status !== "all" && (c.status ?? "active") !== status) return false;
      if (kind !== "all" && c.kind !== kind) return false;
      if (q) {
        const hay = [
          c.name,
          c.email ?? "",
          c.phone ?? "",
          c.national_id ?? "",
          c.cr_number ?? "",
        ]
          .join(" ")
          .toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
    return [...rows].sort((a, b) => {
      if (sort === "name") return a.name.localeCompare(b.name, isAr ? "ar" : "en");
      // recent
      return (b.created_at ?? "").localeCompare(a.created_at ?? "");
    });
  }, [clients, query, status, kind, sort, isAr]);

  const filtersActive =
    query.trim() !== "" || status !== "all" || kind !== "all" || sort !== "recent";

  return (
    <div className="space-y-3">
      {/* Filter bar */}
      <div className="grid grid-cols-1 md:grid-cols-[1fr_auto_auto_auto] gap-2">
        <div className="relative">
          <Search className="absolute start-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={
              isAr
                ? "ابحث بالاسم أو البريد أو الهاتف أو الهوية…"
                : "Search by name, email, phone, or ID…"
            }
            className="ps-9 pe-9"
          />
          {query && (
            <button
              type="button"
              onClick={() => setQuery("")}
              aria-label={isAr ? "مسح البحث" : "Clear search"}
              className="absolute end-2 top-1/2 -translate-y-1/2 grid h-6 w-6 place-items-center rounded-full text-muted-foreground hover:bg-muted hover:text-foreground"
            >
              <X className="h-3 w-3" />
            </button>
          )}
        </div>

        <StatusChips value={status} onChange={setStatus} isAr={isAr} />
        <KindChips
          value={kind}
          onChange={setKind}
          isAr={isAr}
          kindCompany={kindCompany}
          kindPerson={kindPerson}
        />

        <select
          value={sort}
          onChange={(e) => setSort(e.target.value as SortMode)}
          className="h-10 px-3 rounded-md border border-input bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
        >
          <option value="recent">{isAr ? "الأحدث أولًا" : "Newest first"}</option>
          <option value="name">{isAr ? "الاسم (أ–ي)" : "Name (A–Z)"}</option>
        </select>
      </div>

      {/* Counter + reset */}
      <div className="flex items-center justify-between text-xs text-muted-foreground px-1">
        <span>
          {filtered.length === clients.length
            ? isAr
              ? `${clients.length} عميل`
              : `${clients.length} ${clients.length === 1 ? "client" : "clients"}`
            : isAr
              ? `${filtered.length} من ${clients.length}`
              : `${filtered.length} of ${clients.length}`}
        </span>
        {filtersActive && (
          <button
            type="button"
            onClick={() => {
              setQuery("");
              setStatus("all");
              setKind("all");
              setSort("recent");
            }}
            className="hover:text-foreground underline-offset-4 hover:underline"
          >
            {isAr ? "مسح المرشحات" : "Reset filters"}
          </button>
        )}
      </div>

      {/* List */}
      {filtered.length === 0 ? (
        <Card className="border-dashed py-10 text-center text-sm text-muted-foreground">
          {isAr
            ? "لا توجد نتائج مطابقة للمرشحات الحالية."
            : "No clients match the current filters."}
        </Card>
      ) : (
        <Card className="overflow-hidden">
          <ul className="divide-y divide-border/60">
            {filtered.map((c) => {
              const Icon = c.kind === "company" ? Building2 : User;
              const Chevron = isAr ? ChevronLeft : ChevronRight;
              return (
                <li key={c.id}>
                  <Link
                    href={`/dashboard/clients/${c.id}`}
                    className="group flex items-center gap-4 px-4 py-3 hover:bg-muted/40 transition-colors"
                  >
                    <div className="grid h-10 w-10 place-items-center rounded-md bg-primary/10 text-primary shrink-0">
                      <Icon className="h-5 w-5" />
                    </div>

                    <div className="min-w-0 w-56 sm:w-64 shrink-0">
                      <div className="font-medium truncate group-hover:text-primary transition-colors">
                        {c.name}
                      </div>
                      <div className="flex items-center gap-1.5 mt-0.5">
                        <Badge variant="outline" className="text-[10px]">
                          {c.kind === "company" ? kindCompany : kindPerson}
                        </Badge>
                        {c.status && c.status !== "active" && (
                          <Badge variant={statusVariant(c.status)} className="text-[10px]">
                            {statusLabel(c.status, isAr)}
                          </Badge>
                        )}
                      </div>
                    </div>

                    <div className="hidden md:flex flex-1 min-w-0 items-center gap-x-6 gap-y-1 text-sm text-muted-foreground flex-wrap">
                      {c.email && (
                        <span className="inline-flex items-center gap-1.5 min-w-0">
                          <Mail className="h-3.5 w-3.5 shrink-0" />
                          <span className="truncate" dir="ltr">{c.email}</span>
                        </span>
                      )}
                      {c.phone && (
                        <span className="inline-flex items-center gap-1.5" dir="ltr">
                          <Phone className="h-3.5 w-3.5" />
                          {c.phone}
                        </span>
                      )}
                      {c.national_id && (
                        <span className="font-mono text-xs" dir="ltr">
                          ID · {c.national_id}
                        </span>
                      )}
                      {c.cr_number && (
                        <span className="font-mono text-xs" dir="ltr">
                          CR · {c.cr_number}
                        </span>
                      )}
                    </div>

                    <Chevron className="h-4 w-4 text-muted-foreground shrink-0 group-hover:text-primary transition-colors" />
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

// --- Chip groups ------------------------------------------------------------

function StatusChips({
  value,
  onChange,
  isAr,
}: {
  value: StatusFilter;
  onChange: (v: StatusFilter) => void;
  isAr: boolean;
}) {
  const opts: { v: StatusFilter; label: string; tone: string }[] = [
    { v: "all", label: isAr ? "الكل" : "All", tone: "bg-muted text-foreground" },
    {
      v: "lead",
      label: isAr ? "محتمل" : "Lead",
      tone: "bg-amber-100 text-amber-900 dark:bg-amber-900/30 dark:text-amber-200",
    },
    {
      v: "prospect",
      label: isAr ? "اهتمام" : "Prospect",
      tone: "bg-sky-100 text-sky-900 dark:bg-sky-900/30 dark:text-sky-200",
    },
    {
      v: "active",
      label: isAr ? "نشط" : "Active",
      tone: "bg-emerald-100 text-emerald-900 dark:bg-emerald-900/30 dark:text-emerald-200",
    },
    {
      v: "archived",
      label: isAr ? "مؤرشف" : "Archived",
      tone: "bg-muted text-muted-foreground",
    },
  ];
  return (
    <div className="inline-flex h-10 items-center rounded-md border border-input bg-background p-0.5 overflow-x-auto">
      {opts.map((o) => {
        const active = o.v === value;
        return (
          <button
            key={o.v}
            type="button"
            onClick={() => onChange(o.v)}
            className={cn(
              "h-full px-2.5 text-xs font-medium rounded-sm transition-colors whitespace-nowrap",
              active
                ? `${o.tone} shadow-sm`
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            {o.label}
          </button>
        );
      })}
    </div>
  );
}

function KindChips({
  value,
  onChange,
  isAr,
  kindCompany,
  kindPerson,
}: {
  value: KindFilter;
  onChange: (v: KindFilter) => void;
  isAr: boolean;
  kindCompany: string;
  kindPerson: string;
}) {
  const opts: { v: KindFilter; label: string; icon?: typeof Building2 }[] = [
    { v: "all", label: isAr ? "الكل" : "All" },
    { v: "person", label: kindPerson, icon: User },
    { v: "company", label: kindCompany, icon: Building2 },
  ];
  return (
    <div className="inline-flex h-10 items-center rounded-md border border-input bg-background p-0.5">
      {opts.map((o) => {
        const active = o.v === value;
        const Icon = o.icon;
        return (
          <button
            key={o.v}
            type="button"
            onClick={() => onChange(o.v)}
            className={cn(
              "h-full px-2.5 text-xs font-medium rounded-sm transition-colors inline-flex items-center gap-1.5",
              active
                ? "bg-primary/10 text-primary shadow-sm"
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            {Icon && <Icon className="h-3.5 w-3.5" />}
            {o.label}
          </button>
        );
      })}
    </div>
  );
}

function statusVariant(status: string) {
  if (status === "lead") return "warning" as const;
  if (status === "prospect") return "info" as const;
  if (status === "active") return "success" as const;
  return "secondary" as const;
}

function statusLabel(status: string, isAr: boolean) {
  if (!isAr) return status;
  return status === "lead"
    ? "محتمل"
    : status === "prospect"
      ? "اهتمام"
      : status === "active"
        ? "نشط"
        : "مؤرشف";
}
