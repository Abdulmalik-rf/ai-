import { User } from "lucide-react";
import { notFound } from "next/navigation";
import { getTranslations, getLocale } from "next-intl/server";

import { Card } from "@/components/ui/card";
import { CaseAnalysisPanel } from "@/components/dashboard/case-analysis-panel";
import { CaseMemoReviewPanel } from "@/components/dashboard/case-memo-review-panel";
import { CaseDetailWorkspace } from "@/components/dashboard/case-detail-workspace";
import { DeleteCaseButton } from "@/components/dashboard/delete-case-button";
import { EditCaseDialog } from "@/components/dashboard/edit-case-dialog";
import { Link } from "@/i18n/routing";
import { api } from "@/lib/api";
import { getAccessToken } from "@/lib/session";
import { formatDate } from "@/lib/utils";

interface Case {
  id: string;
  reference: string;
  title: string;
  description: string | null;
  domain: string;
  status: string;
  priority: string;
  client_id: string | null;
  opposing_party_name: string | null;
  opposing_counsel: string | null;
  court_name: string | null;
  court_circuit: string | null;
  court_case_number: string | null;
  judge_name: string | null;
  opened_at: string | null;
  closed_at: string | null;
  next_hearing_at: string | null;
  ai_analysis: Record<string, unknown>;
  created_at: string;
}

interface ClientLite {
  id: string;
  name: string;
  kind: string;
}

interface Hearing {
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
}

export default async function CaseDetailPage(props: {
  params: Promise<{ caseId: string }>;
}) {
  const { caseId } = await props.params;
  const t = await getTranslations("dashboard.crm.case");
  const locale = await getLocale();
  const isAr = locale === "ar";
  const token = await getAccessToken();

  let theCase: Case;
  try {
    theCase = await api<Case>(`/v1/cases/${caseId}`, { token });
  } catch {
    notFound();
  }

  // Hearings + the firm's client list are the only related data the page
  // still consumes (tasks/time/notes/activity tabs were removed in favor of
  // a focused hearings feed).
  const [hearings, clientsList] = await Promise.all([
    api<Hearing[]>(`/v1/hearings?case_id=${caseId}&limit=200`, {
      token,
    }).catch(() => []),
    api<ClientLite[]>(`/v1/clients?limit=200`, { token }).catch(() => []),
  ]);

  const linkedClient = theCase.client_id
    ? clientsList.find((c) => c.id === theCase.client_id) ?? null
    : null;

  return (
    <div className="container py-8 space-y-6">
      <header className="space-y-3">
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <div className="text-xs text-muted-foreground">
            {theCase.reference} · {formatDate(theCase.created_at, locale)}
          </div>
          <div className="flex items-center gap-2">
            <EditCaseDialog
              caseId={caseId}
              initial={{
                title: theCase.title,
                description: theCase.description,
                domain: theCase.domain,
                status: theCase.status,
                priority: theCase.priority,
                client_id: theCase.client_id,
                opposing_party_name: theCase.opposing_party_name,
                opposing_counsel: theCase.opposing_counsel,
                court_name: theCase.court_name,
                court_circuit: theCase.court_circuit,
                court_case_number: theCase.court_case_number,
                judge_name: theCase.judge_name,
                opened_at: theCase.opened_at,
                closed_at: theCase.closed_at,
              }}
              clients={clientsList.map((c) => ({ id: c.id, name: c.name }))}
            />
            <DeleteCaseButton caseId={caseId} />
          </div>
        </div>

        <h1 className="text-3xl font-bold tracking-tight">{theCase.title}</h1>

        {linkedClient && (
          <Link
            href="/dashboard/clients"
            className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
          >
            <User className="h-4 w-4" />
            <span>{isAr ? "العميل: " : "Client: "}</span>
            <span className="font-medium text-foreground underline-offset-4 hover:underline">
              {linkedClient.name}
            </span>
          </Link>
        )}

        {theCase.description && (
          <p className="text-sm text-muted-foreground max-w-3xl whitespace-pre-wrap">
            {theCase.description}
          </p>
        )}
      </header>

      {/* Court / matter card */}
      <Card className="p-5">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
          <FactRow label={t("court")} value={theCase.court_name} />
          <FactRow
            label={t("courtCaseNo")}
            value={theCase.court_case_number}
          />
          <FactRow label={t("judge")} value={theCase.judge_name} />
          <FactRow
            label={t("nextHearing")}
            value={
              theCase.next_hearing_at
                ? formatDate(theCase.next_hearing_at, locale)
                : t("noNextHearing")
            }
          />
          <FactRow
            label={t("opposingParty")}
            value={theCase.opposing_party_name}
          />
          <FactRow
            label={t("opposingCounsel")}
            value={theCase.opposing_counsel}
          />
          <FactRow
            label={isAr ? "الدائرة" : "Circuit"}
            value={theCase.court_circuit}
          />
          <FactRow
            label={isAr ? "تاريخ الفتح" : "Opened on"}
            value={theCase.opened_at ? formatDate(theCase.opened_at, locale) : null}
          />
        </div>
      </Card>

      <CaseAnalysisPanel
        caseId={caseId}
        initialAnalysis={
          theCase.ai_analysis && Object.keys(theCase.ai_analysis).length > 0
            ? (theCase.ai_analysis as Parameters<typeof CaseAnalysisPanel>[0]["initialAnalysis"])
            : null
        }
      />

      {/* Multi-advisor memo review → Najiz final review (chained workflow). */}
      <CaseMemoReviewPanel
        caseId={caseId}
        caseTitle={theCase.title}
        caseType={theCase.domain}
        caseFacts={theCase.description}
      />

      <CaseDetailWorkspace caseId={caseId} hearings={hearings} />
    </div>
  );
}

function FactRow({
  label,
  value,
}: {
  label: string;
  value: string | null | undefined;
}) {
  return (
    <div>
      <div className="text-xs uppercase tracking-wider text-muted-foreground">
        {label}
      </div>
      <div className="font-medium mt-1 truncate">{value || "—"}</div>
    </div>
  );
}
