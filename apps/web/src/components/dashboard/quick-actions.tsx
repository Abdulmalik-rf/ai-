"use client";

/**
 * Three quick-create tiles shown on the dashboard home. Each tile is a
 * single button that opens a tailored creation modal:
 *
 *   - "قضية جديدة" → existing NewCaseDialog (full form) controlled here
 *     so the trigger can wear the tile chrome.
 *   - "استشارة جديدة" → lightweight Consultation dialog. Creates a Case
 *     with `[استشارة]` tag in description so it's visually distinct in
 *     the cases list; on success the user lands on that case page.
 *   - "مذكرة جديدة" → Memo dialog. Creates a Case (memo container) and
 *     redirects to the Drafting Studio with the memo case_id attached.
 *
 * Cases is the only persistence shape the backend currently exposes — we
 * route by post-create navigation rather than introducing new entities,
 * so the wiring stays small and reversible.
 */
import {
  ArrowLeft,
  ArrowRight,
  BookText,
  Briefcase,
  MessageSquareQuote,
  Plus,
  ScanSearch,
} from "lucide-react";
import { useLocale } from "next-intl";
import * as React from "react";

import { Field, QuickCreateDialog } from "@/components/dashboard/quick-create-dialog";
import { Input } from "@/components/ui/input";
import { NewCaseDialog } from "@/components/dashboard/new-case-dialog";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import { useRouter } from "@/i18n/routing";

interface QuickActionsProps {
  /** Compact horizontal pills (used at the top of the chat surface when
   *  a conversation is active). Default renders the spacious tile grid. */
  compact?: boolean;
}

export function QuickActions({ compact = false }: QuickActionsProps = {}) {
  const locale = useLocale();
  const isAr = locale === "ar";
  const router = useRouter();

  const [caseOpen, setCaseOpen] = React.useState(false);
  const [memoOpen, setMemoOpen] = React.useState(false);

  const items = [
    {
      icon: Briefcase,
      title: isAr ? "قضية جديدة" : "New case",
      subtitle: isAr
        ? "افتح ملف قضية كامل مع العميل والمحكمة والأولوية."
        : "Open a full matter with client, court, and priority.",
      tone: "primary" as const,
      onClick: () => setCaseOpen(true),
    },
    {
      icon: MessageSquareQuote,
      title: isAr ? "استشارة جديدة" : "New consultation",
      subtitle: isAr
        ? "اطرح سؤالاً فتحلّله لجنة مستشارين وتُنتج رأياً قانونياً موثَّقاً."
        : "Pose a question — an advisor panel produces a grounded legal opinion.",
      tone: "accent" as const,
      onClick: () => router.push("/dashboard/consultations"),
    },
    {
      icon: BookText,
      title: isAr ? "مذكرة جديدة" : "New memo",
      subtitle: isAr
        ? "ابدأ مذكرة قانونية واصِغها بمساعدة الذكاء الاصطناعي."
        : "Start a legal memo and draft it with AI assistance.",
      tone: "muted" as const,
      onClick: () => setMemoOpen(true),
    },
    {
      icon: ScanSearch,
      title: isAr ? "مراجعة عقد" : "Review contract",
      subtitle: isAr
        ? "ارفع عقدًا فتراجعه لجنة مستشارين وتكشف المخاطر والبنود الناقصة."
        : "Upload a contract — an advisor panel flags risks & missing clauses.",
      tone: "primary" as const,
      onClick: () => router.push("/dashboard/contracts"),
    },
  ];

  return (
    <>
      {compact ? (
        <div className="flex flex-wrap items-center gap-2">
          {items.map((it) => (
            <CompactPill
              key={it.title}
              icon={it.icon}
              label={it.title}
              tone={it.tone}
              onClick={it.onClick}
            />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {items.map((it) => (
            <Tile
              key={it.title}
              icon={it.icon}
              title={it.title}
              subtitle={it.subtitle}
              tone={it.tone}
              isAr={isAr}
              onClick={it.onClick}
            />
          ))}
        </div>
      )}

      {/* Existing full case dialog, controlled so the tile drives it. */}
      <NewCaseDialog open={caseOpen} onOpenChange={setCaseOpen} />

      {/* New-consultation now routes to the real Consultations section
          (the Legal Opinion Engine) instead of a quick case-with-tag. */}
      <MemoDialog open={memoOpen} onClose={() => setMemoOpen(false)} />
    </>
  );
}

/** Horizontal-row variant for when the chat surface is active. Same
 *  actions, same dialogs, less visual weight. */
function CompactPill({
  icon: Icon,
  label,
  tone,
  onClick,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  tone: "primary" | "accent" | "muted";
  onClick: () => void;
}) {
  const colors =
    tone === "primary"
      ? "bg-primary/10 text-primary hover:bg-primary/15 ring-1 ring-primary/15"
      : tone === "accent"
        ? "bg-accent/15 text-accent hover:bg-accent/20 ring-1 ring-accent/20"
        : "bg-muted text-foreground/90 hover:bg-muted/70 ring-1 ring-border/60";

  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "inline-flex items-center gap-2 rounded-full px-3.5 py-2 text-sm font-medium",
        "transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40",
        colors
      )}
    >
      <Plus className="h-3.5 w-3.5 opacity-70" />
      <Icon className="h-4 w-4" />
      <span>{label}</span>
    </button>
  );
}

// ---------------------------------------------------------------------------
// Tile
// ---------------------------------------------------------------------------

function Tile({
  icon: Icon,
  title,
  subtitle,
  tone,
  onClick,
  isAr,
}: {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  subtitle: string;
  tone: "primary" | "accent" | "muted";
  onClick: () => void;
  isAr: boolean;
}) {
  const ring =
    tone === "primary"
      ? "bg-primary/10 text-primary"
      : tone === "accent"
        ? "bg-accent/15 text-accent"
        : "bg-muted text-foreground";

  // The chevron points in the direction of "forward" for the active script.
  const Chevron = isAr ? ArrowLeft : ArrowRight;

  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "group text-start rounded-2xl border border-border/60 bg-card p-5",
        "transition-all hover:border-primary/40 hover:shadow-md hover:-translate-y-0.5",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
      )}
    >
      <div className="flex items-start gap-3">
        <div className={cn("grid h-10 w-10 place-items-center rounded-xl shrink-0", ring)}>
          <Icon className="h-5 w-5" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5 font-semibold tracking-tight">
            <span>{title}</span>
            <Plus className="h-4 w-4 text-muted-foreground group-hover:text-primary transition-colors" />
          </div>
          <p className="text-xs text-muted-foreground mt-1 leading-relaxed">
            {subtitle}
          </p>
        </div>
        <Chevron className="h-4 w-4 text-muted-foreground shrink-0 mt-1 group-hover:text-primary group-hover:translate-x-0.5 rtl:group-hover:-translate-x-0.5 transition-all" />
      </div>
    </button>
  );
}

// ---------------------------------------------------------------------------
// Consultation dialog — creates a Case with a [استشارة] tag, then routes
// the user to the case page so they can continue the consultation.
// ---------------------------------------------------------------------------

function ConsultationDialog({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const locale = useLocale();
  const isAr = locale === "ar";
  const router = useRouter();
  const [submitting, setSubmitting] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    setSubmitting(true);
    setError(null);
    try {
      const subject = String(fd.get("subject") || "").trim();
      const notes = String(fd.get("notes") || "").trim();
      // Reference prefix marks the record so the cases list can group/style
      // consultations distinctly later without a backend migration.
      const reference = `CONS-${Date.now().toString().slice(-7)}`;
      const body = {
        reference,
        title: subject || (isAr ? "استشارة قانونية" : "Legal consultation"),
        description: `[${isAr ? "استشارة" : "Consultation"}]${
          notes ? `\n${notes}` : ""
        }`,
        domain: "other",
        priority: "medium",
      };
      const res = await fetch("/api/v1/cases", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(safeDetail(text));
      }
      const created = (await res.json()) as { id: string };
      onClose();
      router.push(`/dashboard/cases/${created.id}`);
      router.refresh();
    } catch (err) {
      setError((err as Error).message || "Failed to create consultation");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <QuickCreateDialog
      open={open}
      onClose={onClose}
      title={isAr ? "استشارة جديدة" : "New consultation"}
      submitLabel={isAr ? "إنشاء الاستشارة" : "Create consultation"}
      cancelLabel={isAr ? "إلغاء" : "Cancel"}
      submitting={submitting}
      error={error}
      onSubmit={onSubmit}
    >
      <Field label={isAr ? "موضوع الاستشارة" : "Subject"}>
        <Input
          name="subject"
          required
          maxLength={300}
          autoFocus
          placeholder={
            isAr
              ? "مثل: استشارة في عقد عمل"
              : "e.g. Employment-contract advice"
          }
        />
      </Field>

      <Field label={isAr ? "ملاحظات أولية (اختياري)" : "Initial notes (optional)"}>
        <Textarea
          name="notes"
          rows={4}
          placeholder={
            isAr
              ? "ما يحتاج العميل لمعرفته بسرعة، أو السؤال المطلوب الرد عليه…"
              : "Quick context, what the client wants to know…"
          }
        />
      </Field>
    </QuickCreateDialog>
  );
}

// ---------------------------------------------------------------------------
// Memo dialog — creates a Case as the container, then jumps to the Drafting
// Studio so the user starts the actual memo with AI assistance immediately.
// ---------------------------------------------------------------------------

function MemoDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const locale = useLocale();
  const isAr = locale === "ar";
  const router = useRouter();
  const [submitting, setSubmitting] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    setSubmitting(true);
    setError(null);
    try {
      const title = String(fd.get("title") || "").trim();
      const summary = String(fd.get("summary") || "").trim();
      const reference = `MEMO-${Date.now().toString().slice(-7)}`;
      const body = {
        reference,
        title: title || (isAr ? "مذكرة قانونية" : "Legal memo"),
        description: `[${isAr ? "مذكرة" : "Memo"}]${summary ? `\n${summary}` : ""}`,
        domain: "other",
        priority: "medium",
      };
      const res = await fetch("/api/v1/cases", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(safeDetail(text));
      }
      const created = (await res.json()) as { id: string };
      onClose();
      // Drafting Studio picks up `?case=<id>` so the produced memo can be
      // linked back to this container.
      router.push(`/dashboard/drafting?case=${created.id}`);
      router.refresh();
    } catch (err) {
      setError((err as Error).message || "Failed to create memo");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <QuickCreateDialog
      open={open}
      onClose={onClose}
      title={isAr ? "مذكرة جديدة" : "New memo"}
      submitLabel={isAr ? "ابدأ الصياغة" : "Start drafting"}
      cancelLabel={isAr ? "إلغاء" : "Cancel"}
      submitting={submitting}
      error={error}
      onSubmit={onSubmit}
    >
      <Field label={isAr ? "عنوان المذكرة" : "Memo title"}>
        <Input
          name="title"
          required
          maxLength={300}
          autoFocus
          placeholder={
            isAr
              ? "مثل: مذكرة دفاع في الدعوى رقم …"
              : "e.g. Defense memo for case no. …"
          }
        />
      </Field>

      <Field label={isAr ? "ملخص قصير (اختياري)" : "Brief summary (optional)"}>
        <Textarea
          name="summary"
          rows={4}
          placeholder={
            isAr
              ? "النقاط الأساسية التي يجب أن تتضمنها المذكرة…"
              : "Key points the memo should cover…"
          }
        />
      </Field>
    </QuickCreateDialog>
  );
}

function safeDetail(text: string): string {
  try {
    const j = JSON.parse(text);
    if (j?.detail) {
      return Array.isArray(j.detail)
        ? j.detail.map((d: { msg?: string }) => d.msg ?? "").join("; ")
        : String(j.detail);
    }
  } catch {
    /* keep raw */
  }
  return text || "Request failed";
}
