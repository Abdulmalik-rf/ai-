import { Suspense } from "react";

import { api } from "@/lib/api";
import { getAccessToken } from "@/lib/session";
import { ContractReviewer } from "@/components/dashboard/contract-reviewer";

// Always fetch fresh — without this, the empty-state render from the
// user's first visit gets cached and they never see newly-indexed docs.
export const dynamic = "force-dynamic";
export const revalidate = 0;

interface ContractReview {
  document_id: string;
  summary: string;
  findings: {
    severity: "info" | "low" | "medium" | "high" | "critical";
    category: string;
    title: string;
    description: string;
    clause_excerpt?: string | null;
    page_number?: number | null;
  }[];
  suggestions: { title: string; rationale: string; suggested_clause: string }[];
  missing_clauses: string[];
  risk_score: number;
}

interface Doc {
  id: string;
  title: string;
  status: string;
  mime_type?: string;
  byte_size?: number;
  page_count?: number;
  language?: string;
  created_at?: string;
  last_contract_review?: ContractReview | null;
  last_contract_review_at?: string | null;
}

export default function ContractsPage() {
  return (
    <Suspense fallback={<ContractsSkeleton />}>
      <ContractsView />
    </Suspense>
  );
}

async function ContractsView() {
  const token = await getAccessToken();
  let docs: Doc[] = [];
  let fetchFailed = false;
  try {
    docs = (await api<Doc[]>("/v1/documents", { token })) ?? [];
  } catch {
    fetchFailed = true;
  }
  return (
    <ContractReviewer
      documents={docs.map((d) => ({
        id: d.id,
        title: d.title,
        status: d.status,
        mime_type: d.mime_type ?? "",
        byte_size: d.byte_size ?? 0,
        page_count: d.page_count ?? 0,
        language: d.language ?? "",
        created_at: d.created_at ?? null,
        last_review: d.last_contract_review ?? null,
        last_review_at: d.last_contract_review_at ?? null,
      }))}
      fetchFailed={fetchFailed}
    />
  );
}

function ContractsSkeleton() {
  return (
    <div className="container py-8 space-y-6 animate-pulse">
      <div className="rounded-lg border bg-card h-12 w-1/3" />
      <div className="rounded-lg border bg-card h-64" />
    </div>
  );
}
