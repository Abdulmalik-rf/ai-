"use client";

/**
 * Consultations workspace — the Legal Opinion Engine UI.
 *
 * list ↔ new-question ↔ opinion-detail (no route changes). Submitting a
 * question kicks off the advisory panel server-side; the component polls
 * GET /v1/consultations/{id} every 4s until status leaves "running", then
 * renders the synthesized opinion + the verification verdict + the panel.
 */
import {
  AlertTriangle,
  ChevronRight,
  Loader2,
  Plus,
  RefreshCcw,
  Scale,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

type Status = "queued" | "running" | "done" | "failed";

interface AdvisorOpinion {
  advisor_id: string;
  status: Status;
  position: string | null;
  confidence: "high" | "medium" | "low" | null;
  key_points: string[];
  citations: { statute?: string; article?: string; relevance?: string }[];
  caveats: string[];
  extra: Record<string, unknown> | null;
  error: string | null;
}

interface Opinion {
  executive_answer?: string;
  answer_disposition?: "yes" | "no" | "depends" | "conditional";
  legal_basis?: { statute?: string; article?: string; summary?: string }[];
  analysis?: string;
  options?: { option?: string; pros?: string[]; cons?: string[]; rank?: number }[];
  risks?: string[];
  recommended_action?: string;
  caveats?: string[];
  human_review_points?: string[];
}

interface Verification {
  verdict?: "safe" | "safe_with_caveats" | "needs_review";
  confidence_level?: "high" | "medium" | "low";
  unsupported_claims?: { claim: string; why: string }[];
  notes?: string;
}

interface Framing {
  refined_questions?: string[];
  material_facts?: string[];
  missing_info?: string[];
  domain?: string;
}

interface Consultation {
  id: string;
  client_id: string | null;
  title: string;
  question: string;
  situation: string | null;
  client_type: string | null;
  domain: string | null;
  mode: "standard" | "deep";
  status: Status;
  error: string | null;
  framing: Framing | null;
  grounding: { citations?: { label?: string }[] } | null;
  final_opinion: Opinion | null;
  verification: Verification | null;
  confidence_level: "high" | "medium" | "low" | null;
  needs_human_review: boolean;
  created_at: string;
  advisors: AdvisorOpinion[];
}

interface AdvisorMeta {
  id: string;
  name_en: string;
  name_ar: string;
}

interface Props {
  initialConsultations: Consultation[];
  advisorMeta: Record<string, AdvisorMeta>;
  isAr: boolean;
}

export function ConsultationsWorkspace({ initialConsultations, advisorMeta, isAr }: Props) {
  const [items, setItems] = useState<Consultation[]>(initialConsultations);
  const [active, setActive] = useState<Consultation | null>(null);
  const [view, setView] = useState<"list" | "new" | "detail">("list");
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const refresh = useCallback(async () => {
    const r = await fetch("/api/v1/consultations?limit=50");
    if (r.ok) setItems((await r.json()) as Consultation[]);
  }, []);

  const pollActive = useCallback(async (id: string) => {
    const r = await fetch(`/api/v1/consultations/${id}`);
    if (!r.ok) return;
    const data = (await r.json()) as Consultation;
    setActive(data);
    if (data.status === "done" || data.status === "failed") {
      if (pollRef.current) clearInterval(pollRef.current);
      pollRef.current = null;
      refresh();
    }
  }, [refresh]);

  useEffect(() => {
    if (active && (active.status === "queued" || active.status === "running")) {
      if (!pollRef.current) pollRef.current = setInterval(() => pollActive(active.id), 4000);
    }
    return () => {
      if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
    };
  }, [active?.id, active?.status, pollActive]);

  const open = async (id: string) => {
    const r = await fetch(`/api/v1/consultations/${id}`);
    if (r.ok) { setActive(await r.json()); setView("detail"); }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight flex items-center gap-2">
            <Scale className="h-7 w-7 text-primary" />
            {isAr ? "الاستشارات القانونية" : "Legal Consultations"}
          </h1>
          <p className="text-sm text-muted-foreground max-w-2xl mt-1">
            {isAr
              ? "اطرح سؤالاً قانونياً، فتُحلّله لجنة من المستشارين (نظامي، مخاطر، خيارات، إجراءات) وتُنتج رأياً قانونياً موثَّقاً مع التحقق من الاستناد قبل تسليمه للعميل."
              : "Pose a legal question — an advisory panel (statutory, risk, options, procedural) analyzes it and produces a grounded legal opinion, verified before it reaches the client."}
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={refresh}><RefreshCcw className="h-4 w-4" /></Button>
          <Button onClick={() => { setView("new"); setActive(null); }}>
            <Plus className="h-4 w-4 me-1" />{isAr ? "استشارة جديدة" : "New consultation"}
          </Button>
        </div>
      </div>

      {view === "new" && (
        <NewForm isAr={isAr} onCreated={async (id) => { await refresh(); await open(id); }} />
      )}
      {view === "detail" && active && (
        <Detail c={active} meta={advisorMeta} isAr={isAr} onBack={() => setView("list")} />
      )}
      {view === "list" && <List items={items} isAr={isAr} onOpen={open} />}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────

function List({ items, isAr, onOpen }: { items: Consultation[]; isAr: boolean; onOpen: (id: string) => void }) {
  if (items.length === 0) {
    return (
      <Card><CardContent className="py-16 text-center text-sm text-muted-foreground">
        {isAr ? "لا توجد استشارات بعد. ابدأ باستشارة جديدة." : "No consultations yet. Start a new one."}
      </CardContent></Card>
    );
  }
  return (
    <div className="grid gap-3">
      {items.map((c) => (
        <button key={c.id} onClick={() => onOpen(c.id)}
          className="w-full text-start rounded-xl border bg-card hover:bg-accent/40 transition-colors p-4 flex items-start gap-4">
          <StatusPill status={c.status} isAr={isAr} />
          <div className="flex-1">
            <div className="font-semibold text-sm">{c.title}</div>
            <div className="text-xs text-muted-foreground mt-0.5 line-clamp-1">{c.question}</div>
            <div className="text-xs text-muted-foreground mt-0.5">
              {new Date(c.created_at).toLocaleString(isAr ? "ar-SA" : "en-US")}
              {c.final_opinion?.answer_disposition && (
                <> · <DispositionLabel d={c.final_opinion.answer_disposition} isAr={isAr} /></>
              )}
            </div>
          </div>
          <ChevronRight className={cn("h-5 w-5 text-muted-foreground", isAr && "rotate-180")} />
        </button>
      ))}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────

function NewForm({ isAr, onCreated }: { isAr: boolean; onCreated: (id: string) => void }) {
  const [title, setTitle] = useState("");
  const [question, setQuestion] = useState("");
  const [situation, setSituation] = useState("");
  const [clientType, setClientType] = useState("");
  const [mode, setMode] = useState<"standard" | "deep">("standard");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    setSubmitting(true); setError(null);
    try {
      const res = await fetch("/api/v1/consultations", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: title.trim(),
          question: question.trim(),
          situation: situation.trim() || null,
          client_type: clientType || null,
          mode,
        }),
      });
      if (!res.ok) {
        const d = await res.json().catch(() => ({ detail: "Request failed" }));
        throw new Error((d as { detail?: string }).detail ?? `HTTP ${res.status}`);
      }
      onCreated(((await res.json()) as Consultation).id);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally { setSubmitting(false); }
  };

  return (
    <Card>
      <CardHeader><CardTitle>{isAr ? "استشارة قانونية جديدة" : "New legal consultation"}</CardTitle></CardHeader>
      <CardContent className="space-y-4">
        {error && <div className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</div>}
        <div className="space-y-1.5">
          <label className="text-sm font-medium">{isAr ? "عنوان الاستشارة" : "Title"} *</label>
          <Input value={title} onChange={(e) => setTitle(e.target.value)} />
        </div>
        <div className="space-y-1.5">
          <label className="text-sm font-medium">{isAr ? "السؤال القانوني" : "Legal question"} *</label>
          <Textarea value={question} onChange={(e) => setQuestion(e.target.value)} rows={3}
            placeholder={isAr ? "مثال: هل يجوز لصاحب العمل فصل الموظف خلال فترة التجربة بدون تعويض؟" : "e.g. Can an employer dismiss a worker during probation without compensation?"} />
        </div>
        <div className="space-y-1.5">
          <label className="text-sm font-medium">{isAr ? "تفاصيل الموقف (الوقائع)" : "Situation / facts"}</label>
          <Textarea value={situation} onChange={(e) => setSituation(e.target.value)} rows={5}
            placeholder={isAr ? "صف الوقائع ذات الصلة: التواريخ، الأطراف، المبالغ، تفاصيل العقد…" : "Describe the relevant facts: dates, parties, amounts, contract details…"} />
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div className="space-y-1.5">
            <label className="text-sm font-medium">{isAr ? "نوع العميل" : "Client type"}</label>
            <select value={clientType} onChange={(e) => setClientType(e.target.value)}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm">
              <option value="">{isAr ? "غير محدد" : "Unspecified"}</option>
              <option value="individual">{isAr ? "فرد" : "Individual"}</option>
              <option value="company">{isAr ? "شركة" : "Company"}</option>
              <option value="government">{isAr ? "جهة حكومية" : "Government"}</option>
            </select>
          </div>
          <div className="space-y-1.5">
            <label className="text-sm font-medium">{isAr ? "عمق التحليل" : "Depth"}</label>
            <div className="flex gap-2">
              {([["standard", isAr ? "قياسي (٤ مستشارين)" : "Standard (4)"], ["deep", isAr ? "عميق (٥ مستشارين)" : "Deep (5)"]] as const).map(([m, label]) => (
                <button key={m} type="button" onClick={() => setMode(m)}
                  className={cn("flex-1 px-3 py-2 rounded-md text-xs border", mode === m ? "border-primary bg-primary/10 text-primary" : "border-border hover:bg-accent/40")}>
                  {label}
                </button>
              ))}
            </div>
          </div>
        </div>
        <Button onClick={submit} disabled={submitting || title.trim().length < 1 || question.trim().length < 10}>
          {submitting ? <Loader2 className="h-4 w-4 me-1 animate-spin" /> : <Sparkles className="h-4 w-4 me-1" />}
          {isAr ? "اطلب الرأي القانوني" : "Get legal opinion"}
        </Button>
        <p className="text-xs text-muted-foreground">{isAr ? "تستغرق عادةً ٢-٤ دقائق." : "Typically takes 2-4 minutes."}</p>
      </CardContent>
    </Card>
  );
}

// ─────────────────────────────────────────────────────────────────────────

function Detail({ c, meta, isAr, onBack }: { c: Consultation; meta: Record<string, AdvisorMeta>; isAr: boolean; onBack: () => void }) {
  const op = c.final_opinion;
  const running = c.status === "queued" || c.status === "running";

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <Button variant="ghost" size="sm" onClick={onBack}>← {isAr ? "العودة" : "Back"}</Button>
        <StatusPill status={c.status} isAr={isAr} />
      </div>

      <Card>
        <CardContent className="pt-6 space-y-2">
          <h2 className="text-xl font-bold">{c.title}</h2>
          <p className="text-sm text-foreground/90 whitespace-pre-wrap">{c.question}</p>
          {c.situation && <p className="text-xs text-muted-foreground whitespace-pre-wrap border-s-2 border-border ps-3">{c.situation}</p>}
        </CardContent>
      </Card>

      {running && (
        <Card><CardContent className="py-12 text-center">
          <Loader2 className="h-8 w-8 mx-auto animate-spin text-primary" />
          <div className="mt-2 text-sm font-medium">{isAr ? "لجنة المستشارين تعمل…" : "The advisory panel is working…"}</div>
          <div className="mt-1 text-xs text-muted-foreground">
            {c.advisors.filter((a) => a.status === "done").length} / {c.advisors.length} {isAr ? "اكتمل" : "completed"}
          </div>
        </CardContent></Card>
      )}

      {c.status === "failed" && (
        <Card><CardContent className="py-6">
          <div className="text-sm font-semibold text-destructive">{isAr ? "فشلت الاستشارة" : "Consultation failed"}</div>
          <div className="text-xs text-muted-foreground mt-1 whitespace-pre-wrap">{c.error}</div>
        </CardContent></Card>
      )}

      {c.status === "done" && op && (
        <>
          {/* Hero answer */}
          <Card className="border-primary/30">
            <CardContent className="pt-6 space-y-3">
              <div className="flex items-center gap-2 flex-wrap">
                {op.answer_disposition && <DispositionBadge d={op.answer_disposition} isAr={isAr} />}
                {c.confidence_level && (
                  <Badge variant="secondary" className="text-[10px]">
                    {isAr ? "الثقة" : "Confidence"}: {c.confidence_level}
                  </Badge>
                )}
                <VerdictBadge v={c.verification?.verdict} isAr={isAr} />
              </div>
              <p className="text-sm leading-relaxed whitespace-pre-wrap">{op.executive_answer}</p>
            </CardContent>
          </Card>

          {/* Human review banner */}
          {c.needs_human_review && (
            <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 px-4 py-3 flex items-start gap-2 text-sm">
              <AlertTriangle className="h-4 w-4 mt-0.5 text-amber-600 dark:text-amber-400 shrink-0" />
              <div>
                <span className="font-semibold text-amber-700 dark:text-amber-400">
                  {isAr ? "يتطلب مراجعة محامٍ مرخّص قبل الاعتماد. " : "Requires review by a licensed lawyer before relying on it. "}
                </span>
                {c.verification?.notes && <span className="text-muted-foreground">{c.verification.notes}</span>}
              </div>
            </div>
          )}

          {op.recommended_action && (
            <Card><CardContent className="pt-5">
              <div className="text-xs uppercase tracking-wider text-muted-foreground mb-1">{isAr ? "الإجراء الموصى به" : "Recommended action"}</div>
              <p className="text-sm whitespace-pre-wrap">{op.recommended_action}</p>
            </CardContent></Card>
          )}

          {/* Options */}
          {op.options && op.options.length > 0 && (
            <div>
              <SectionLabel>{isAr ? "الخيارات المتاحة" : "Available options"}</SectionLabel>
              <div className="grid gap-3 md:grid-cols-2">
                {[...op.options].sort((a, b) => (a.rank ?? 9) - (b.rank ?? 9)).map((o, i) => (
                  <div key={i} className="rounded-lg border p-3 space-y-2">
                    <div className="text-sm font-semibold flex items-center gap-2">
                      <span className="grid place-items-center h-5 w-5 rounded-full bg-primary/10 text-primary text-[11px]">{o.rank ?? i + 1}</span>
                      {o.option}
                    </div>
                    {(o.pros?.length ?? 0) > 0 && (
                      <ul className="text-xs space-y-0.5 list-disc list-inside text-emerald-800 dark:text-emerald-300">{o.pros!.map((p, j) => <li key={j}>{p}</li>)}</ul>
                    )}
                    {(o.cons?.length ?? 0) > 0 && (
                      <ul className="text-xs space-y-0.5 list-disc list-inside text-amber-800 dark:text-amber-300">{o.cons!.map((p, j) => <li key={j}>{p}</li>)}</ul>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Legal basis */}
          {op.legal_basis && op.legal_basis.length > 0 && (
            <Card><CardContent className="pt-5">
              <div className="text-xs uppercase tracking-wider text-muted-foreground mb-2">{isAr ? "الأساس النظامي" : "Legal basis"}</div>
              <ul className="space-y-2 text-sm">
                {op.legal_basis.map((b, i) => (
                  <li key={i} className="border-s-2 border-primary/30 ps-3">
                    <span className="font-medium">{[b.article, b.statute].filter(Boolean).join(" — ")}</span>
                    {b.summary && <div className="text-xs text-muted-foreground mt-0.5">{b.summary}</div>}
                  </li>
                ))}
              </ul>
            </CardContent></Card>
          )}

          {op.analysis && (
            <details className="rounded-lg border bg-card/50">
              <summary className="cursor-pointer px-4 py-2.5 text-sm font-medium">{isAr ? "التحليل" : "Analysis"}</summary>
              <p className="px-4 pb-4 text-sm whitespace-pre-wrap leading-relaxed">{op.analysis}</p>
            </details>
          )}

          {/* Risks + caveats */}
          {(op.risks?.length ?? 0) > 0 && (
            <Card><CardContent className="pt-5">
              <div className="text-xs uppercase tracking-wider text-amber-700 dark:text-amber-400 mb-2">{isAr ? "المخاطر" : "Risks"}</div>
              <ul className="space-y-1 text-sm list-disc list-inside text-amber-900 dark:text-amber-200">{op.risks!.map((r, i) => <li key={i}>{r}</li>)}</ul>
            </CardContent></Card>
          )}

          {(op.human_review_points?.length ?? 0) > 0 && (
            <details className="rounded-lg border border-amber-500/30 bg-amber-500/5">
              <summary className="cursor-pointer px-4 py-2.5 text-sm font-medium text-amber-700 dark:text-amber-400">{isAr ? "نقاط تتطلب تأكيد المحامي" : "Points to confirm with a lawyer"}</summary>
              <ul className="px-4 pb-4 text-xs space-y-1 list-disc list-inside text-amber-900 dark:text-amber-200">{op.human_review_points!.map((p, i) => <li key={i}>{p}</li>)}</ul>
            </details>
          )}

          {/* Advisor panel */}
          <details className="rounded-lg border bg-card/50">
            <summary className="cursor-pointer px-4 py-2.5 text-sm font-medium">{isAr ? `آراء المستشارين (${c.advisors.length})` : `Advisor opinions (${c.advisors.length})`}</summary>
            <div className="grid gap-3 md:grid-cols-2 p-4 pt-2">
              {c.advisors.map((a) => (
                <div key={a.advisor_id} className="rounded-lg border p-3 space-y-2">
                  <div className="text-sm font-semibold">{meta[a.advisor_id] ? (isAr ? meta[a.advisor_id].name_ar : meta[a.advisor_id].name_en) : a.advisor_id}</div>
                  {a.confidence && <Badge variant="secondary" className="text-[10px]">{isAr ? "الثقة" : "Confidence"}: {a.confidence}</Badge>}
                  {a.position && <p className="text-xs text-muted-foreground">{a.position}</p>}
                  {a.key_points.length > 0 && <ul className="text-xs space-y-0.5 list-disc list-inside">{a.key_points.map((k, i) => <li key={i}>{k}</li>)}</ul>}
                  {a.status === "failed" && a.error && <div className="text-xs text-destructive">{a.error}</div>}
                </div>
              ))}
            </div>
          </details>

          {/* Framing (what the AI extracted) */}
          {c.framing && (
            <details className="rounded-lg border bg-card/50">
              <summary className="cursor-pointer px-4 py-2.5 text-sm font-medium">{isAr ? "كيف فهم النظام السؤال" : "How the system framed the question"}</summary>
              <div className="px-4 pb-4 text-xs space-y-2">
                {(c.framing.refined_questions?.length ?? 0) > 0 && (
                  <div><span className="font-medium">{isAr ? "الأسئلة:" : "Questions:"}</span>
                    <ul className="list-disc list-inside text-muted-foreground">{c.framing.refined_questions!.map((q, i) => <li key={i}>{q}</li>)}</ul></div>
                )}
                {(c.framing.missing_info?.length ?? 0) > 0 && (
                  <div><span className="font-medium text-amber-700 dark:text-amber-400">{isAr ? "معلومات ناقصة:" : "Missing info:"}</span>
                    <ul className="list-disc list-inside text-amber-800 dark:text-amber-300">{c.framing.missing_info!.map((m, i) => <li key={i}>{m}</li>)}</ul></div>
                )}
              </div>
            </details>
          )}
        </>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────

function SectionLabel({ children }: { children: React.ReactNode }) {
  return <div className="text-xs uppercase tracking-wider text-muted-foreground font-semibold mb-2">{children}</div>;
}

function StatusPill({ status, isAr }: { status: Status; isAr: boolean }) {
  const cls = status === "done" ? "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400 border-emerald-500/30"
    : status === "running" || status === "queued" ? "bg-blue-500/15 text-blue-700 dark:text-blue-400 border-blue-500/30"
    : "bg-destructive/15 text-destructive border-destructive/30";
  const label = status === "done" ? (isAr ? "جاهز" : "Done") : status === "failed" ? (isAr ? "فشل" : "Failed") : (isAr ? "قيد التشغيل" : "Running");
  return <span className={cn("inline-flex items-center gap-1 px-2 py-0.5 rounded-full border text-[11px] font-medium", cls)}>
    {(status === "running" || status === "queued") && <Loader2 className="h-3 w-3 animate-spin" />}{label}
  </span>;
}

function DispositionBadge({ d, isAr }: { d: "yes" | "no" | "depends" | "conditional"; isAr: boolean }) {
  const cls = d === "yes" ? "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400"
    : d === "no" ? "bg-destructive/15 text-destructive"
    : "bg-amber-500/15 text-amber-700 dark:text-amber-400";
  return <span className={cn("px-2.5 py-1 rounded-full text-xs font-bold", cls)}><DispositionLabel d={d} isAr={isAr} /></span>;
}

function DispositionLabel({ d, isAr }: { d: "yes" | "no" | "depends" | "conditional"; isAr: boolean }) {
  const map = {
    yes: isAr ? "نعم" : "Yes",
    no: isAr ? "لا" : "No",
    depends: isAr ? "يعتمد" : "It depends",
    conditional: isAr ? "مشروط" : "Conditional",
  } as const;
  return <>{map[d]}</>;
}

function VerdictBadge({ v, isAr }: { v?: "safe" | "safe_with_caveats" | "needs_review"; isAr: boolean }) {
  if (!v) return null;
  const cls = v === "safe" ? "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400"
    : v === "safe_with_caveats" ? "bg-amber-500/15 text-amber-700 dark:text-amber-400"
    : "bg-destructive/15 text-destructive";
  const label = v === "safe" ? (isAr ? "تحقّق: آمن" : "Verified: safe")
    : v === "safe_with_caveats" ? (isAr ? "تحقّق: مع تحفظات" : "Verified: caveats")
    : (isAr ? "يحتاج مراجعة" : "Needs review");
  return <span className={cn("inline-flex items-center gap-1 px-2 py-1 rounded-full text-[10px] font-medium", cls)}><ShieldCheck className="h-3 w-3" />{label}</span>;
}
