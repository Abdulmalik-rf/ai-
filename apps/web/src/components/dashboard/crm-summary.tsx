import {
  CalendarClock,
  CheckSquare,
  Activity as ActivityIcon,
} from "lucide-react";
import { getTranslations, getLocale } from "next-intl/server";

import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Link } from "@/i18n/routing";
import { api } from "@/lib/api";
import { getAccessToken } from "@/lib/session";
import { cn, formatDate } from "@/lib/utils";

interface DashboardSummary {
  total_clients: number;
  active_clients: number;
  leads: number;
  open_cases: number;
  cases_in_court: number;
  overdue_tasks: number;
  open_tasks: number;
  today_hearings: HearingSummary[];
  upcoming_hearings: HearingSummary[];
  my_tasks: TaskSummary[];
  recent_activities: ActivitySummary[];
  unbilled_minutes_30d: number;
  unpaid_invoices_count: number;
}

interface HearingSummary {
  id: string;
  case_id: string;
  case_title: string | null;
  scheduled_at: string;
  court_name: string | null;
  kind: string;
}

interface TaskSummary {
  id: string;
  title: string;
  priority: "low" | "medium" | "high" | "urgent";
  due_date: string | null;
  case_id: string | null;
}

interface ActivitySummary {
  id: string;
  kind: string;
  summary: string;
  occurred_at: string;
  case_id: string | null;
  client_id: string | null;
}


/** Skeleton placeholder rendered by Suspense while CrmSummary fetches. */
export function CrmSummarySkeleton() {
  return (
    <section className="space-y-4 animate-pulse">
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3">
        {Array.from({ length: 7 }).map((_, i) => (
          <div key={i} className="rounded-lg border bg-card p-4 h-24" />
        ))}
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="rounded-lg border bg-card h-48" />
        <div className="rounded-lg border bg-card h-48" />
      </div>
      <div className="rounded-lg border bg-card h-40" />
    </section>
  );
}


export async function CrmSummary() {
  const token = await getAccessToken();
  const t = await getTranslations("dashboard.crm.summary");
  const locale = await getLocale();

  let summary: DashboardSummary | null = null;
  try {
    summary = await api<DashboardSummary>("/v1/dashboard/summary", { token });
  } catch {
    return null;
  }
  if (!summary) return null;

  return (
    <section className="space-y-4">
      {/* Today + My tasks */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card className="p-5">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-semibold flex items-center gap-2">
              <CalendarClock className="h-4 w-4 text-primary" />
              {t("todayHearings")}
            </h3>
            <Link href="/dashboard/hearings" className="text-xs text-muted-foreground hover:underline">→</Link>
          </div>
          {summary.today_hearings.length === 0 ? (
            <p className="text-sm text-muted-foreground">{t("noHearingsToday")}</p>
          ) : (
            <ul className="space-y-2">
              {summary.today_hearings.map((h) => (
                <HearingRow key={h.id} h={h} locale={locale} />
              ))}
            </ul>
          )}
          {summary.upcoming_hearings.length > 0 && (
            <>
              <div className="mt-4 text-xs uppercase tracking-wider text-muted-foreground mb-2">{t("upcomingHearings")}</div>
              <ul className="space-y-2">
                {summary.upcoming_hearings.slice(0, 4).map((h) => (
                  <HearingRow key={h.id} h={h} locale={locale} />
                ))}
              </ul>
            </>
          )}
        </Card>

        <Card className="p-5">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-semibold flex items-center gap-2">
              <CheckSquare className="h-4 w-4 text-primary" />
              {t("myTasks")}
            </h3>
            <Link href="/dashboard/tasks" className="text-xs text-muted-foreground hover:underline">→</Link>
          </div>
          {summary.my_tasks.length === 0 ? (
            <p className="text-sm text-muted-foreground">{t("noTasks")}</p>
          ) : (
            <ul className="space-y-2">
              {summary.my_tasks.map((task) => (
                <li key={task.id} className="flex items-start justify-between gap-3 text-sm">
                  <Link
                    href={task.case_id ? `/dashboard/cases/${task.case_id}` : "/dashboard/tasks"}
                    className="flex-1 hover:underline truncate"
                  >
                    {task.title}
                  </Link>
                  <div className="flex items-center gap-2 shrink-0">
                    <PriorityBadge priority={task.priority} />
                    {task.due_date && (
                      <span className="text-xs text-muted-foreground">
                        {formatDate(task.due_date, locale)}
                      </span>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      {/* Recent activity */}
      <Card className="p-5">
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-semibold flex items-center gap-2">
            <ActivityIcon className="h-4 w-4 text-primary" />
            {t("recentActivity")}
          </h3>
        </div>
        {summary.recent_activities.length === 0 ? (
          <p className="text-sm text-muted-foreground">{t("noActivity")}</p>
        ) : (
          <ul className="space-y-2 text-sm">
            {summary.recent_activities.slice(0, 8).map((a) => (
              <li key={a.id} className="flex items-start gap-3">
                <span className="mt-1.5 h-1.5 w-1.5 rounded-full bg-primary/60 shrink-0" />
                <div className="flex-1 min-w-0">
                  <Link
                    href={a.case_id ? `/dashboard/cases/${a.case_id}` : a.client_id ? `/dashboard/clients` : "#"}
                    className="hover:underline truncate block"
                  >
                    {localizeActivity(a, locale)}
                  </Link>
                </div>
                <time className="text-xs text-muted-foreground shrink-0">
                  {formatDate(a.occurred_at, locale)}
                </time>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </section>
  );
}


function HearingRow({ h, locale }: { h: HearingSummary; locale: string }) {
  const dt = new Date(h.scheduled_at);
  const timeStr = dt.toLocaleTimeString(locale === "ar" ? "ar-SA" : "en-GB", {
    hour: "2-digit",
    minute: "2-digit",
  });
  return (
    <li className="flex items-start gap-3 text-sm">
      <span className="font-mono text-xs px-2 py-0.5 rounded bg-muted shrink-0">
        {timeStr}
      </span>
      <div className="flex-1 min-w-0">
        <Link href={`/dashboard/cases/${h.case_id}`} className="hover:underline truncate block">
          {h.case_title || "—"}
        </Link>
        <div className="text-xs text-muted-foreground truncate">
          {h.court_name || "—"} · {h.kind}
        </div>
      </div>
      <time className="text-xs text-muted-foreground shrink-0">
        {formatDate(h.scheduled_at, locale)}
      </time>
    </li>
  );
}


/**
 * Render an activity feed entry in the user's language.
 *
 * Server-side summaries are baked in English ("Hearing scheduled for {iso}…")
 * — translating them here keeps the activity log readable for Arabic firms
 * without forcing a backend schema change. For known `kind` values we emit
 * a localized template; otherwise we fall back to whatever the server gave.
 * Any ISO datetime embedded in the summary is reformatted using the user's
 * locale.
 */
function localizeActivity(
  a: { kind: string; summary: string },
  locale: string,
): string {
  const isAr = locale === "ar";

  // Pull an ISO timestamp out of the legacy English summary, if present,
  // and render it via the same date formatter we use everywhere else.
  const isoMatch = a.summary.match(/\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[^\s)]*/);
  const isoDate = isoMatch ? formatDate(isoMatch[0], locale) : null;

  switch (a.kind) {
    case "hearing_scheduled":
      return isoDate
        ? isAr
          ? `جدولة جلسة في ${isoDate}`
          : `Hearing scheduled for ${isoDate}`
        : isAr
          ? "تمت جدولة جلسة"
          : "Hearing scheduled";
    case "hearing_outcome":
      return isAr ? "تم تسجيل نتيجة الجلسة" : "Hearing outcome recorded";
    case "task_completed":
      return isAr ? "اكتملت مهمة" : "Task completed";
    case "case_opened":
      return isAr ? "تم فتح قضية" : "Case opened";
    case "case_closed":
      return isAr ? "تم إغلاق قضية" : "Case closed";
    case "note_added":
      return isAr ? "تمت إضافة ملاحظة" : "Note added";
    case "document_uploaded":
      return isAr ? "تم رفع مستند" : "Document uploaded";
    case "document_shared":
      return isAr ? "تمت مشاركة مستند" : "Document shared";
    case "client_intake":
      return isAr ? "استقبال عميل جديد" : "New client intake";
    case "status_change":
      return isAr ? "تغيّر الحالة" : "Status changed";
    case "payment_received":
      return isAr ? "استلام دفعة" : "Payment received";
    case "invoice_sent":
      return isAr ? "إرسال فاتورة" : "Invoice sent";
    case "phone_call":
      return isAr ? "مكالمة هاتفية" : "Phone call";
    case "meeting":
      return isAr ? "اجتماع" : "Meeting";
    case "email":
      return isAr ? "بريد إلكتروني" : "Email";
    case "whatsapp":
      return isAr ? "رسالة واتساب" : "WhatsApp message";
    case "sms":
      return isAr ? "رسالة نصية" : "SMS";
    default:
      // Unknown kind — surface the server's summary verbatim so we never
      // silently drop information.
      return a.summary;
  }
}

function PriorityBadge({ priority }: { priority: TaskSummary["priority"] }) {
  const color =
    priority === "urgent"
      ? "bg-destructive/15 text-destructive"
      : priority === "high"
        ? "bg-orange-500/15 text-orange-600 dark:text-orange-400"
        : priority === "low"
          ? "bg-muted text-muted-foreground"
          : "bg-primary/15 text-primary";
  return (
    <span className={cn("text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-full", color)}>
      {priority}
    </span>
  );
}
