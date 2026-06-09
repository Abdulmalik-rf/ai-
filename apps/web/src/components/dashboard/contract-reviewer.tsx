"use client";

/**
 * Contract review workspace.
 *
 * The page passes EVERY document (any status) so we can distinguish three
 * cases for the user:
 *
 *   1. No documents at all → "upload your first contract" empty state.
 *   2. Documents exist, but none indexed yet → "indexing in progress"
 *      banner with a refresh button. (This is what trips most users —
 *      they upload, see the empty review state immediately, and assume
 *      the feature is broken.)
 *   3. At least one indexed document → the picker + review action.
 *
 * Errors from the review call are rendered inline (not via alert()) so
 * the user actually sees what went wrong. The common 502 case
 * (ChatGPT OAuth token expired) gets a friendlier "ask your admin" copy.
 */
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState, useTransition } from "react";
import { useLocale, useTranslations } from "next-intl";
import {
  AlertTriangle,
  ArrowDownAZ,
  Clock,
  Eye,
  FileScan,
  FileText,
  History,
  Languages,
  ListChecks,
  Loader2,
  RefreshCw,
  Search,
  Upload,
} from "lucide-react";

import { Input } from "@/components/ui/input";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Link } from "@/i18n/routing";

interface Finding {
  severity: "info" | "low" | "medium" | "high" | "critical";
  category: string;
  title: string;
  description: string;
  clause_excerpt?: string | null;
  page_number?: number | null;
}

interface Suggestion {
  title: string;
  rationale: string;
  suggested_clause: string;
}

interface AdvisorOpinion {
  advisor_id: string;
  name: string;
  assessment: string;
  favors: "client" | "counterparty" | "balanced" | "na";
  findings: Finding[];
}

interface JobAdvisor {
  advisor_id: string;
  name: string;
  status: "queued" | "running" | "done" | "failed";
  favors: "client" | "counterparty" | "balanced" | "na";
  findings_count: number;
}

interface JobPayload {
  job_id: string;
  status: "queued" | "running" | "done" | "failed";
  advisors: JobAdvisor[];
  result: ReviewResponse | null;
  error: string | null;
}

interface ReviewResponse {
  document_id: string;
  summary: string;
  findings: Finding[];
  suggestions: Suggestion[];
  missing_clauses: string[];
  risk_score: number;
  advisors?: AdvisorOpinion[];
  party_favorability?: string | null;
}

interface DocLite {
  id: string;
  title: string;
  status: string;
  mime_type?: string;
  byte_size?: number;
  page_count?: number;
  language?: string;
  created_at?: string | null;
  last_review?: ReviewResponse | null;
  last_review_at?: string | null;
}

type RiskFilter = "all" | "low" | "medium" | "high";
type SortMode = "recent" | "risk_desc" | "risk_asc";

const severityVariant = (s: Finding["severity"]) =>
  s === "critical" || s === "high"
    ? "destructive"
    : s === "medium"
      ? "warning"
      : "secondary";

export function ContractReviewer({
  documents,
  fetchFailed,
}: {
  documents: DocLite[];
  fetchFailed?: boolean;
}) {
  const t = useTranslations("dashboard.contracts");
  const locale = useLocale();
  const router = useRouter();
  const isAr = locale === "ar";

  const indexed = useMemo(
    () => documents.filter((d) => d.status === "indexed"),
    [documents],
  );
  const processing = documents.filter(
    (d) => d.status === "uploaded" || d.status === "processing"
  );
  const failed = documents.filter((d) => d.status === "failed");

  // On first render, auto-select the most recently reviewed doc (if any),
  // otherwise the first indexed doc — so when the user comes back from
  // another section they see their last analysis instead of a blank picker.
  const initialSelected = useMemo(() => {
    const reviewed = indexed
      .filter((d) => d.last_review)
      .sort((a, b) =>
        (b.last_review_at ?? "").localeCompare(a.last_review_at ?? "")
      );
    return reviewed[0]?.id ?? indexed[0]?.id ?? "";
  }, [indexed]);

  const [selected, setSelected] = useState<string>(initialSelected);
  const [loading, setLoading] = useState(false);
  // Seed the result from the selected doc's persisted review so we render
  // the saved analysis on mount.
  const [result, setResult] = useState<ReviewResponse | null>(() => {
    const d = indexed.find((x) => x.id === initialSelected);
    return d?.last_review ?? null;
  });
  const [resultAt, setResultAt] = useState<string | null>(() => {
    const d = indexed.find((x) => x.id === initialSelected);
    return d?.last_review_at ?? null;
  });
  const [error, setError] = useState<{ kind: "ai" | "other"; msg: string } | null>(null);
  const [refreshing, startRefreshTransition] = useTransition();
  // Live advisor-panel progress while a review job runs.
  const [progress, setProgress] = useState<JobAdvisor[] | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  useEffect(() => () => { if (pollRef.current) clearInterval(pollRef.current); }, []);

  const selectedDoc = indexed.find((d) => d.id === selected);
  const hasSavedResult = !!selectedDoc?.last_review;

  // History list — every indexed doc that has a persisted analysis, sorted
  // newest-first. Clicking one loads its analysis below.
  const reviewed = useMemo(
    () =>
      indexed
        .filter((d) => d.last_review)
        .sort((a, b) =>
          (b.last_review_at ?? "").localeCompare(a.last_review_at ?? "")
        ),
    [indexed],
  );

  const resultRef = useRef<HTMLDivElement | null>(null);

  function openSavedAnalysis(doc: DocLite) {
    if (!doc.last_review) return;
    setSelected(doc.id);
    setResult(doc.last_review);
    setResultAt(doc.last_review_at ?? null);
    setError(null);
    // Defer until the new result renders, then scroll it into view.
    requestAnimationFrame(() => {
      resultRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }

  // Open the file itself (the original PDF) in a new tab via a presigned
  // MinIO URL — handy when the user wants to cross-reference findings
  // with the actual document text without leaving the analysis.
  const [pdfBusyId, setPdfBusyId] = useState<string | null>(null);
  async function viewPdf(docId: string) {
    setPdfBusyId(docId);
    try {
      const res = await fetch(`/api/v1/documents/${docId}/download-url`);
      if (!res.ok) {
        setError({
          kind: "other",
          msg: isAr ? "تعذّر فتح الملف" : "Couldn't open the file",
        });
        return;
      }
      const { url } = (await res.json()) as { url: string };
      window.open(url, "_blank", "noopener,noreferrer");
    } catch (err) {
      setError({ kind: "other", msg: (err as Error).message });
    } finally {
      setPdfBusyId(null);
    }
  }

  // Filter + sort state for the past-analyses list.
  const [query, setQuery] = useState("");
  const [risk, setRisk] = useState<RiskFilter>("all");
  const [sort, setSort] = useState<SortMode>("recent");

  const filteredReviewed = useMemo(() => {
    const q = query.trim().toLowerCase();
    const filtered = reviewed.filter((d) => {
      if (q && !d.title.toLowerCase().includes(q)) return false;
      const score = d.last_review?.risk_score ?? 0;
      if (risk === "low" && score > 40) return false;
      if (risk === "medium" && (score <= 40 || score > 70)) return false;
      if (risk === "high" && score <= 70) return false;
      return true;
    });
    return [...filtered].sort((a, b) => {
      if (sort === "recent") {
        return (b.last_review_at ?? "").localeCompare(a.last_review_at ?? "");
      }
      const ra = a.last_review?.risk_score ?? 0;
      const rb = b.last_review?.risk_score ?? 0;
      return sort === "risk_desc" ? rb - ra : ra - rb;
    });
  }, [reviewed, query, risk, sort]);

  async function run() {
    if (!selected) return;
    setLoading(true);
    setError(null);
    setProgress(null);
    if (pollRef.current) clearInterval(pollRef.current);
    try {
      // Kick off the async multi-advisor job — it returns immediately with
      // the queued advisor list, then we poll and watch them finish.
      const res = await fetch("/api/v1/contracts/review-jobs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ document_id: selected, locale }),
      });
      if (!res.ok) {
        const text = await res.text();
        let msg = text;
        try { msg = JSON.parse(text)?.detail || text; } catch { /* keep raw */ }
        const isAi = res.status === 502 || String(msg).includes("AI provider") || String(msg).includes("ChatGPT");
        setError({ kind: isAi ? "ai" : "other", msg: msg || `HTTP ${res.status}` });
        setLoading(false);
        return;
      }
      const job = (await res.json()) as JobPayload;
      setProgress(job.advisors ?? []);

      const poll = async () => {
        try {
          const r = await fetch(`/api/v1/contracts/review-jobs/${job.job_id}`);
          if (!r.ok) return;
          const data = (await r.json()) as JobPayload;
          setProgress(data.advisors ?? []);
          if (data.status === "done" || data.status === "failed") {
            if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
            setLoading(false);
            setProgress(null);
            if (data.status === "failed") {
              setError({ kind: "other", msg: data.error || "Review failed" });
            } else if (data.result) {
              setResult(data.result);
              setResultAt(new Date().toISOString());
              router.refresh();
            }
          }
        } catch { /* transient — keep polling */ }
      };
      pollRef.current = setInterval(poll, 3000);
      poll();
    } catch (err) {
      setError({ kind: "other", msg: (err as Error).message || "Request failed" });
      setLoading(false);
    }
  }

  function refresh() {
    startRefreshTransition(() => {
      router.refresh();
    });
  }

  // --- Inline upload --------------------------------------------------------
  // Lets the user add a new contract without leaving the page. We accept the
  // same file types the documents page does (.pdf .docx .txt), POST to
  // /api/v1/documents (multipart), then router.refresh() so the new doc
  // shows up in the picker once indexing finishes.
  const uploadInputRef = useRef<HTMLInputElement | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadedJustNow, setUploadedJustNow] = useState<string | null>(null);

  async function onUploadChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("language", isAr ? "ar" : "en");
      const res = await fetch("/api/v1/documents", { method: "POST", body: fd });
      if (!res.ok) {
        const text = await res.text();
        let msg = text;
        try {
          const j = JSON.parse(text);
          msg = j?.detail || text;
        } catch {
          /* keep raw */
        }
        throw new Error(msg || `HTTP ${res.status}`);
      }
      setUploadedJustNow(file.name);
      router.refresh();
    } catch (err) {
      setError({
        kind: "other",
        msg: (err as Error).message || "Upload failed",
      });
    } finally {
      setUploading(false);
      if (uploadInputRef.current) uploadInputRef.current.value = "";
    }
  }

  return (
    <div className="container py-8 space-y-6">
      <header className="flex items-start justify-between gap-3 flex-wrap">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">{t("title")}</h1>
          <p className="text-muted-foreground mt-1 max-w-2xl">
            {isAr
              ? "ارفع عقدًا ثم اختره هنا لمراجعة مفصلة: مخاطر، ملاحظات، وبنود مقترحة."
              : "Upload a contract, then pick it here for a detailed review: risks, findings, and suggested clauses."}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {/* Hidden file input — clicked programmatically by the Upload button */}
          <input
            ref={uploadInputRef}
            type="file"
            accept=".pdf,.docx,.txt"
            className="hidden"
            onChange={onUploadChange}
          />
          <Button
            size="sm"
            onClick={() => uploadInputRef.current?.click()}
            disabled={uploading}
          >
            {uploading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Upload className="h-4 w-4" />
            )}
            {isAr ? "ارفع عقدًا" : "Upload contract"}
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={refresh}
            disabled={refreshing}
          >
            {refreshing ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4" />
            )}
            {isAr ? "تحديث" : "Refresh"}
          </Button>
        </div>
      </header>

      {uploadedJustNow && (
        <InlineError
          tone="info"
          icon={<Loader2 className="h-4 w-4 animate-spin" />}
          title={
            isAr
              ? `جارٍ فهرسة "${uploadedJustNow}"…`
              : `Indexing "${uploadedJustNow}"…`
          }
          body={
            isAr
              ? "سيظهر في القائمة بعد ثوانٍ. اضغط تحديث لاحقًا إذا لم يظهر."
              : "It'll show up in the picker in a few seconds. Hit Refresh if it doesn't appear."
          }
        />
      )}

      {fetchFailed && (
        <InlineError
          tone="warning"
          title={isAr ? "تعذّر تحميل المستندات" : "Couldn't load documents"}
          body={
            isAr
              ? "تحقق من اتصالك ثم اضغط تحديث."
              : "Check your connection and click Refresh."
          }
        />
      )}

      {/* CASE 1: no docs at all */}
      {documents.length === 0 && !fetchFailed && (
        <div className="rounded-2xl border border-dashed border-border/70 bg-card/40 py-14 px-6 text-center">
          <div className="mx-auto grid h-14 w-14 place-items-center rounded-2xl bg-gradient-to-br from-primary/[0.10] to-accent/[0.10] ring-1 ring-inset ring-border/60 text-primary">
            <FileScan className="h-6 w-6" />
          </div>
          <h2 className="mt-5 text-lg md:text-xl font-semibold tracking-tight">
            {isAr ? "لا توجد عقود جاهزة للمراجعة" : "No contracts ready to review"}
          </h2>
          <p className="mt-2 max-w-md mx-auto text-sm text-muted-foreground leading-relaxed">
            {isAr
              ? "ارفع عقدًا من قسم المستندات وسنفهرسه لمراجعته هنا."
              : "Upload a contract from the Documents section and we'll index it so you can review it here."}
          </p>
          <Button asChild className="mt-6">
            <Link href="/dashboard/documents">
              <Upload className="h-4 w-4" />
              {isAr ? "ارفع عقدًا" : "Upload a contract"}
            </Link>
          </Button>
        </div>
      )}

      {/* CASE 2: docs exist but still indexing — the case the user hit */}
      {documents.length > 0 && indexed.length === 0 && processing.length > 0 && (
        <InlineError
          tone="info"
          icon={<Loader2 className="h-4 w-4 animate-spin" />}
          title={
            isAr
              ? `${processing.length} مستند قيد الفهرسة…`
              : `${processing.length} document${processing.length === 1 ? "" : "s"} indexing…`
          }
          body={
            isAr
              ? "ستظهر فور انتهاء الفهرسة (عادةً دقيقة أو دقيقتان). اضغط تحديث لاحقًا."
              : "They'll appear here as soon as indexing finishes (usually a minute or two). Hit Refresh in a bit."
          }
        />
      )}

      {/* CASE 3: at least one indexed doc — picker */}
      {indexed.length > 0 && (
        <Card>
          <CardContent className="p-6 flex flex-col md:flex-row gap-3 items-end">
            <div className="flex-1 w-full">
              <label className="text-sm font-medium block mb-1.5">
                {t("selectDocument")}
              </label>
              <select
                value={selected}
                onChange={(e) => {
                  const next = e.target.value;
                  setSelected(next);
                  setError(null);
                  const d = indexed.find((x) => x.id === next);
                  // Restore the persisted result for the newly-picked doc
                  // (or clear it when the user picks the placeholder).
                  setResult(d?.last_review ?? null);
                  setResultAt(d?.last_review_at ?? null);
                }}
                className="w-full rounded-md border border-input bg-background h-10 px-3 text-sm"
              >
                <option value="">
                  {isAr ? "اختر عقدًا..." : "Choose a contract…"}
                </option>
                {indexed.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.last_review ? "✓ " : ""}
                    {d.title}
                  </option>
                ))}
              </select>
              {processing.length > 0 && (
                <p className="mt-2 text-xs text-muted-foreground">
                  {isAr
                    ? `${processing.length} مستند آخر لا يزال قيد الفهرسة…`
                    : `${processing.length} other document${processing.length === 1 ? " is" : "s are"} still indexing…`}
                </p>
              )}
            </div>
            <Button onClick={run} disabled={!selected || loading}>
              {loading && <Loader2 className="h-4 w-4 animate-spin" />}
              {hasSavedResult
                ? isAr
                  ? "إعادة التحليل"
                  : "Re-analyze"
                : t("review")}
            </Button>

            {/* Live advisor-panel progress (watch advisors finish one by one). */}
            {loading && progress && (
              <ContractReviewProgress advisors={progress} isAr={isAr} />
            )}
          </CardContent>
        </Card>
      )}

      {/* Past analyses — every reviewed contract, filterable, with per-row
          actions to view the PDF or load its saved analysis. */}
      {reviewed.length > 0 && (
        <Card>
          <CardHeader className="space-y-4">
            <div className="flex items-center justify-between">
              <CardTitle className="text-base flex items-center gap-2">
                <History className="h-4 w-4 text-primary" />
                {isAr ? "تحليلات سابقة" : "Past analyses"}
              </CardTitle>
              <span className="text-xs text-muted-foreground">
                {filteredReviewed.length === reviewed.length
                  ? reviewed.length
                  : `${filteredReviewed.length} / ${reviewed.length}`}
              </span>
            </div>

            {/* Filter bar */}
            <div className="grid grid-cols-1 md:grid-cols-[1fr_auto_auto] gap-2">
              <div className="relative">
                <Search className="absolute start-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder={isAr ? "بحث بالعنوان…" : "Search by title…"}
                  className="ps-9"
                />
              </div>

              <RiskFilterChips value={risk} onChange={setRisk} isAr={isAr} />

              <div className="relative">
                <ArrowDownAZ className="absolute start-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none" />
                <select
                  value={sort}
                  onChange={(e) => setSort(e.target.value as SortMode)}
                  className="h-10 ps-9 pe-3 rounded-md border border-input bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                >
                  <option value="recent">
                    {isAr ? "الأحدث أولًا" : "Newest first"}
                  </option>
                  <option value="risk_desc">
                    {isAr ? "الأعلى مخاطر" : "Highest risk"}
                  </option>
                  <option value="risk_asc">
                    {isAr ? "الأقل مخاطر" : "Lowest risk"}
                  </option>
                </select>
              </div>
            </div>

            {(query || risk !== "all" || sort !== "recent") && (
              <button
                type="button"
                onClick={() => {
                  setQuery("");
                  setRisk("all");
                  setSort("recent");
                }}
                className="text-xs text-muted-foreground hover:text-foreground underline-offset-4 hover:underline w-fit"
              >
                {isAr ? "مسح المرشحات" : "Reset filters"}
              </button>
            )}
          </CardHeader>
          <CardContent className="p-0">
            {filteredReviewed.length === 0 ? (
              <div className="px-6 py-10 text-center text-sm text-muted-foreground">
                {isAr
                  ? "لا توجد نتائج مطابقة لهذه المرشحات."
                  : "No analyses match the current filters."}
              </div>
            ) : (
              <ul className="divide-y divide-border/60">
                {filteredReviewed.map((d) => {
                  const isOpen = d.id === selected && !!result;
                  const riskScore = d.last_review?.risk_score ?? 0;
                  const riskTone =
                    riskScore > 70
                      ? "destructive"
                      : riskScore > 40
                        ? "warning"
                        : "success";
                  const findings = d.last_review?.findings ?? [];
                  const critical = findings.filter(
                    (f) => f.severity === "critical" || f.severity === "high"
                  ).length;
                  const missing = d.last_review?.missing_clauses?.length ?? 0;
                  return (
                    <li
                      key={d.id}
                      className={
                        "px-4 py-3 transition-colors " +
                        (isOpen ? "bg-primary/[0.06]" : "hover:bg-muted/30")
                      }
                    >
                      <div className="flex items-start gap-3">
                        <div className="grid h-10 w-10 place-items-center rounded-md bg-primary/10 text-primary shrink-0">
                          <FileScan className="h-4 w-4" />
                        </div>

                        <div className="flex-1 min-w-0 space-y-1">
                          <div className="font-medium truncate">{d.title}</div>

                          {/* Meta row: analyzed timestamp + file details */}
                          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
                            {d.last_review_at && (
                              <span className="inline-flex items-center gap-1">
                                <Clock className="h-3 w-3" />
                                {isAr ? "تم التحليل " : "Analyzed "}
                                {formatRelative(d.last_review_at, isAr)}
                              </span>
                            )}
                            {d.page_count ? (
                              <span className="inline-flex items-center gap-1">
                                <FileText className="h-3 w-3" />
                                {d.page_count}{" "}
                                {isAr
                                  ? "صفحة"
                                  : d.page_count === 1
                                    ? "page"
                                    : "pages"}
                              </span>
                            ) : null}
                            {d.byte_size ? (
                              <span>{formatBytes(d.byte_size, isAr)}</span>
                            ) : null}
                            {d.language ? (
                              <span className="inline-flex items-center gap-1 uppercase">
                                <Languages className="h-3 w-3" />
                                {d.language}
                              </span>
                            ) : null}
                          </div>

                          {/* Findings summary */}
                          <div className="flex flex-wrap gap-1.5 pt-1">
                            <Badge variant={riskTone}>
                              {isAr ? "مخاطر " : "risk "}
                              {riskScore}/100
                            </Badge>
                            {critical > 0 && (
                              <Badge variant="destructive">
                                <AlertTriangle className="h-3 w-3" />
                                {critical}{" "}
                                {isAr
                                  ? "حرجة/عالية"
                                  : critical === 1
                                    ? "critical"
                                    : "critical"}
                              </Badge>
                            )}
                            <Badge variant="secondary">
                              <ListChecks className="h-3 w-3" />
                              {findings.length}{" "}
                              {isAr
                                ? "ملاحظة"
                                : findings.length === 1
                                  ? "finding"
                                  : "findings"}
                            </Badge>
                            {missing > 0 && (
                              <Badge variant="warning">
                                {missing}{" "}
                                {isAr ? "بنود ناقصة" : "missing"}
                              </Badge>
                            )}
                          </div>
                        </div>

                        {/* Per-row actions */}
                        <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-1.5 shrink-0">
                          <Button
                            type="button"
                            variant="outline"
                            size="sm"
                            onClick={() => viewPdf(d.id)}
                            disabled={pdfBusyId === d.id}
                          >
                            {pdfBusyId === d.id ? (
                              <Loader2 className="h-3.5 w-3.5 animate-spin" />
                            ) : (
                              <Eye className="h-3.5 w-3.5" />
                            )}
                            {isAr ? "عرض الملف" : "View file"}
                          </Button>
                          <Button
                            type="button"
                            size="sm"
                            variant={isOpen ? "secondary" : "default"}
                            onClick={() => openSavedAnalysis(d)}
                            disabled={isOpen}
                          >
                            {isOpen
                              ? isAr
                                ? "معروض"
                                : "Open"
                              : isAr
                                ? "افتح التحليل"
                                : "Open analysis"}
                          </Button>
                        </div>
                      </div>
                    </li>
                  );
                })}
              </ul>
            )}
          </CardContent>
        </Card>
      )}

      {failed.length > 0 && (
        <InlineError
          tone="warning"
          title={
            isAr
              ? `فشلت فهرسة ${failed.length} مستند`
              : `${failed.length} document${failed.length === 1 ? "" : "s"} failed to index`
          }
          body={
            isAr
              ? "افتح صفحة المستندات لإعادة رفعها أو حذفها."
              : "Open the Documents page to re-upload or remove them."
          }
        />
      )}

      {error && (
        <InlineError
          tone="error"
          title={
            error.kind === "ai"
              ? isAr
                ? "خدمة المراجعة بالذكاء الاصطناعي معطّلة مؤقتًا"
                : "AI review is temporarily unavailable"
              : isAr
                ? "تعذّرت المراجعة"
                : "Review failed"
          }
          body={
            error.kind === "ai"
              ? isAr
                ? "انتهت صلاحية بيانات اعتماد مزود الذكاء الاصطناعي. تواصل مع مسؤول النظام لتحديثها."
                : "The AI provider's credentials have expired. Ask your admin to refresh them."
              : error.msg
          }
        />
      )}

      {result && (
        <div ref={resultRef} className="space-y-4 scroll-mt-6">
          <Card>
            <CardHeader className="flex-row justify-between items-center">
              <div className="space-y-1">
                <CardTitle>{t("summary")}</CardTitle>
                {resultAt && (
                  <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                    <Clock className="h-3 w-3" />
                    {isAr ? "تم التحليل: " : "Analyzed "}
                    {formatRelative(resultAt, isAr)}
                  </div>
                )}
              </div>
              <div className="flex items-center gap-2">
                <span className="text-sm text-muted-foreground">
                  {t("riskScore")}:
                </span>
                <Badge
                  variant={
                    result.risk_score > 70
                      ? "destructive"
                      : result.risk_score > 40
                        ? "warning"
                        : "success"
                  }
                >
                  {result.risk_score}/100
                </Badge>
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              <p className="text-sm whitespace-pre-wrap">{result.summary}</p>
              {result.party_favorability && (
                <div className="rounded-md bg-muted/40 px-3 py-2 text-sm">
                  <span className="text-xs font-semibold text-muted-foreground">
                    {isAr ? "ميل العقد: " : "Contract favors: "}
                  </span>
                  {result.party_favorability}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Multi-advisor panel — each advisor's independent read. */}
          {result.advisors && result.advisors.length > 0 && (
            <details className="rounded-xl border border-border bg-card/50">
              <summary className="cursor-pointer px-5 py-3 font-semibold text-sm">
                {isAr
                  ? `آراء لجنة المستشارين (${result.advisors.length})`
                  : `Advisor panel (${result.advisors.length})`}
              </summary>
              <div className="grid gap-3 md:grid-cols-2 p-4 pt-2">
                {result.advisors.map((a) => (
                  <div key={a.advisor_id} className="rounded-lg border p-3 space-y-2">
                    <div className="flex items-center justify-between gap-2">
                      <div className="text-sm font-semibold">{a.name}</div>
                      <FavorsBadge favors={a.favors} isAr={isAr} />
                    </div>
                    {a.assessment && (
                      <p className="text-xs text-muted-foreground">{a.assessment}</p>
                    )}
                    {a.findings.length > 0 && (
                      <ul className="text-xs space-y-1">
                        {a.findings.map((f, i) => (
                          <li key={i} className="flex items-start gap-1.5">
                            <Badge variant={severityVariant(f.severity)} className="text-[9px] shrink-0 mt-0.5">
                              {f.severity}
                            </Badge>
                            <span>{f.title}</span>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                ))}
              </div>
            </details>
          )}

          <Card>
            <CardHeader>
              <CardTitle>{t("findings")}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {result.findings.map((f, i) => (
                <div key={i} className="border-s-4 border-primary/40 ps-4 py-2">
                  <div className="flex items-center gap-2 mb-1">
                    <Badge variant={severityVariant(f.severity)}>
                      {f.severity}
                    </Badge>
                    <span className="text-xs text-muted-foreground">
                      {f.category}
                    </span>
                    {f.page_number && (
                      <span className="text-xs text-muted-foreground">
                        · p.{f.page_number}
                      </span>
                    )}
                  </div>
                  <div className="font-medium">{f.title}</div>
                  <p className="text-sm text-muted-foreground mt-1">
                    {f.description}
                  </p>
                  {f.clause_excerpt && (
                    <pre className="mt-2 text-xs bg-muted p-2 rounded whitespace-pre-wrap">
                      {f.clause_excerpt}
                    </pre>
                  )}
                </div>
              ))}
            </CardContent>
          </Card>

          {result.suggestions.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>{t("suggestions")}</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {result.suggestions.map((s, i) => (
                  <div key={i} className="border rounded-md p-4">
                    <div className="font-medium">{s.title}</div>
                    <p className="text-sm text-muted-foreground mt-1">
                      {s.rationale}
                    </p>
                    <pre className="mt-2 text-xs bg-muted p-3 rounded whitespace-pre-wrap">
                      {s.suggested_clause}
                    </pre>
                  </div>
                ))}
              </CardContent>
            </Card>
          )}

          {result.missing_clauses.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <AlertTriangle className="h-5 w-5 text-amber-500" />
                  {t("missing")}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="list-disc list-inside space-y-1 text-sm">
                  {result.missing_clauses.map((c, i) => (
                    <li key={i}>{c}</li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}

function RiskFilterChips({
  value,
  onChange,
  isAr,
}: {
  value: RiskFilter;
  onChange: (v: RiskFilter) => void;
  isAr: boolean;
}) {
  const opts: { v: RiskFilter; label: string; cls: string }[] = [
    {
      v: "all",
      label: isAr ? "الكل" : "All",
      cls: "bg-muted text-foreground",
    },
    {
      v: "low",
      label: isAr ? "منخفض" : "Low",
      cls: "bg-emerald-100 text-emerald-900 dark:bg-emerald-900/30 dark:text-emerald-200",
    },
    {
      v: "medium",
      label: isAr ? "متوسط" : "Medium",
      cls: "bg-amber-100 text-amber-900 dark:bg-amber-900/30 dark:text-amber-200",
    },
    {
      v: "high",
      label: isAr ? "عالٍ" : "High",
      cls: "bg-red-100 text-red-900 dark:bg-red-900/30 dark:text-red-200",
    },
  ];
  return (
    <div className="inline-flex h-10 items-center rounded-md border border-input bg-background p-0.5">
      {opts.map((o) => {
        const active = o.v === value;
        return (
          <button
            key={o.v}
            type="button"
            onClick={() => onChange(o.v)}
            className={
              "h-full px-3 text-xs font-medium rounded-sm transition-colors " +
              (active
                ? o.cls + " shadow-sm"
                : "text-muted-foreground hover:text-foreground")
            }
          >
            {o.label}
          </button>
        );
      })}
    </div>
  );
}

function formatBytes(bytes: number, isAr: boolean): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} ${isAr ? "ك.ب" : "KB"}`;
  return `${(bytes / 1024 / 1024).toFixed(1)} ${isAr ? "م.ب" : "MB"}`;
}

function ContractReviewProgress({
  advisors,
  isAr,
}: {
  advisors: JobAdvisor[];
  isAr: boolean;
}) {
  const done = advisors.filter((a) => a.status === "done").length;
  const total = advisors.filter((a) => a.advisor_id !== "_synthesis").length;
  const pct = total > 0 ? Math.round((Math.min(done, total) / total) * 100) : 0;
  return (
    <div className="w-full mt-3 rounded-lg border border-border/60 bg-muted/30 p-3 space-y-2">
      <div className="flex items-center justify-between text-xs">
        <span className="font-medium">
          {isAr ? "لجنة المستشارين تعمل…" : "Advisor panel working…"}
        </span>
        <span className="text-muted-foreground">
          {Math.min(done, total)} / {total}
        </span>
      </div>
      <div className="h-1.5 w-full rounded-full bg-border/60 overflow-hidden">
        <div className="h-full bg-primary transition-all duration-500" style={{ width: `${pct}%` }} />
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5">
        {advisors.map((a) => (
          <div key={a.advisor_id} className="flex items-center gap-2 text-xs">
            {a.status === "done" ? (
              <span className="h-3.5 w-3.5 rounded-full bg-emerald-500/20 grid place-items-center shrink-0">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
              </span>
            ) : a.status === "running" ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin text-primary shrink-0" />
            ) : (
              <span className="h-3.5 w-3.5 rounded-full border border-border shrink-0" />
            )}
            <span className={a.status === "done" ? "text-foreground" : "text-muted-foreground"}>
              {a.advisor_id === "_synthesis" ? (isAr ? "الدمج النهائي" : "Synthesizing") : a.name}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function FavorsBadge({
  favors,
  isAr,
}: {
  favors: "client" | "counterparty" | "balanced" | "na";
  isAr: boolean;
}) {
  if (favors === "na") return null;
  const map = {
    client: { ar: "لصالح موكلنا", en: "Favors client", v: "success" as const },
    counterparty: { ar: "لصالح الطرف الآخر", en: "Favors counterparty", v: "destructive" as const },
    balanced: { ar: "متوازن", en: "Balanced", v: "secondary" as const },
  };
  const m = map[favors];
  return (
    <Badge variant={m.v} className="text-[9px] shrink-0">
      {isAr ? m.ar : m.en}
    </Badge>
  );
}

function formatRelative(iso: string, isAr: boolean): string {
  const d = new Date(iso);
  const diff = Date.now() - d.getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 1) return isAr ? "الآن" : "just now";
  if (mins < 60) return isAr ? `قبل ${mins} د` : `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return isAr ? `قبل ${hrs} س` : `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  if (days < 7) return isAr ? `قبل ${days} يوم` : `${days}d ago`;
  return d.toLocaleDateString(isAr ? "ar" : "en");
}

function InlineError({
  tone,
  title,
  body,
  icon,
}: {
  tone: "info" | "warning" | "error";
  title: string;
  body: string;
  icon?: React.ReactNode;
}) {
  const palette: Record<typeof tone, string> = {
    info: "border-primary/30 bg-primary/5 text-foreground",
    warning: "border-amber-500/30 bg-amber-500/5 text-foreground",
    error: "border-destructive/30 bg-destructive/5 text-foreground",
  };
  const iconColor: Record<typeof tone, string> = {
    info: "text-primary",
    warning: "text-amber-600 dark:text-amber-400",
    error: "text-destructive",
  };
  return (
    <div
      className={`rounded-xl border px-4 py-3 flex items-start gap-3 ${palette[tone]}`}
    >
      <div className={`mt-0.5 shrink-0 ${iconColor[tone]}`}>
        {icon ?? <AlertTriangle className="h-4 w-4" />}
      </div>
      <div className="min-w-0 text-sm">
        <div className="font-semibold">{title}</div>
        <p className="mt-0.5 text-muted-foreground">{body}</p>
      </div>
    </div>
  );
}
