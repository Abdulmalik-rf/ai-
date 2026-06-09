"use client";

import { useMemo, useState } from "react";
import { FileText } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { FilterBar, type ChipGroup } from "@/components/dashboard/filter-bar";

export interface DocRow {
  id: string;
  title: string;
  status: "uploaded" | "processing" | "indexed" | "failed";
  mime_type: string;
  byte_size: number;
  page_count: number;
  language: string;
  created_at: string;
}

type StatusFilter = "all" | "indexed" | "processing" | "uploaded" | "failed";
type LangFilter = "all" | "ar" | "en";
type SortMode = "recent" | "name" | "size";

export function DocumentsList({
  docs,
  isAr,
  statusLabels,
}: {
  docs: DocRow[];
  isAr: boolean;
  statusLabels: Record<DocRow["status"], string>;
}) {
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<StatusFilter>("all");
  const [lang, setLang] = useState<LangFilter>("all");
  const [sort, setSort] = useState<SortMode>("recent");

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    const rows = docs.filter((d) => {
      if (status !== "all" && d.status !== status) return false;
      if (lang !== "all" && d.language !== lang) return false;
      if (q && !d.title.toLowerCase().includes(q)) return false;
      return true;
    });
    return [...rows].sort((a, b) => {
      if (sort === "name") return a.title.localeCompare(b.title, isAr ? "ar" : "en");
      if (sort === "size") return b.byte_size - a.byte_size;
      return b.created_at.localeCompare(a.created_at);
    });
  }, [docs, query, status, lang, sort, isAr]);

  const chipGroups: ChipGroup[] = [
    {
      value: status,
      onChange: (v) => setStatus(v as StatusFilter),
      options: [
        { value: "all", label: isAr ? "الكل" : "All" },
        {
          value: "indexed",
          label: statusLabels.indexed,
          activeClassName: "bg-emerald-100 text-emerald-900 dark:bg-emerald-900/30 dark:text-emerald-200",
        },
        {
          value: "processing",
          label: statusLabels.processing,
          activeClassName: "bg-amber-100 text-amber-900 dark:bg-amber-900/30 dark:text-amber-200",
        },
        {
          value: "uploaded",
          label: statusLabels.uploaded,
        },
        {
          value: "failed",
          label: statusLabels.failed,
          activeClassName: "bg-red-100 text-red-900 dark:bg-red-900/30 dark:text-red-200",
        },
      ],
    },
    {
      value: lang,
      onChange: (v) => setLang(v as LangFilter),
      options: [
        { value: "all", label: isAr ? "الكل" : "All" },
        { value: "ar", label: "AR" },
        { value: "en", label: "EN" },
      ],
    },
  ];

  return (
    <div className="space-y-4">
      <FilterBar
        query={query}
        onQueryChange={setQuery}
        placeholder={isAr ? "ابحث بالعنوان…" : "Search by title…"}
        chipGroups={chipGroups}
        sort={sort}
        onSortChange={setSort}
        sortOptions={[
          { value: "recent", label: isAr ? "الأحدث أولًا" : "Newest first" },
          { value: "name", label: isAr ? "الاسم (أ–ي)" : "Name (A–Z)" },
          { value: "size", label: isAr ? "الأكبر حجمًا" : "Largest first" },
        ]}
        totalCount={docs.length}
        filteredCount={filtered.length}
        hasFilters={
          query.trim() !== "" || status !== "all" || lang !== "all" || sort !== "recent"
        }
        onReset={() => {
          setQuery("");
          setStatus("all");
          setLang("all");
          setSort("recent");
        }}
        isAr={isAr}
        noun={{
          singular: "document",
          plural: isAr ? "مستند" : "documents",
        }}
      />

      {filtered.length === 0 ? (
        <Card className="border-dashed py-10 text-center text-sm text-muted-foreground">
          {isAr
            ? "لا توجد مستندات مطابقة للمرشحات الحالية."
            : "No documents match the current filters."}
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filtered.map((d) => (
            <Card key={d.id} className="p-5 space-y-3">
              <div className="flex items-start gap-3">
                <FileText className="h-5 w-5 text-primary mt-1" />
                <div className="flex-1 min-w-0">
                  <div className="font-medium truncate" title={d.title}>
                    {d.title}
                  </div>
                  <div className="text-xs text-muted-foreground mt-1">
                    {(d.byte_size / 1024).toFixed(0)} KB · {d.page_count}{" "}
                    {isAr ? "صفحة" : d.page_count === 1 ? "page" : "pages"} ·{" "}
                    {d.language.toUpperCase()}
                  </div>
                </div>
              </div>
              <Badge variant={statusVariant(d.status)}>
                {statusLabels[d.status]}
              </Badge>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

function statusVariant(s: DocRow["status"]) {
  return s === "indexed"
    ? ("success" as const)
    : s === "failed"
      ? ("destructive" as const)
      : s === "processing"
        ? ("warning" as const)
        : ("secondary" as const);
}
