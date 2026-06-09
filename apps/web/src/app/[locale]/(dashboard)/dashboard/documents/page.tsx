import { FileText } from "lucide-react";
import { getTranslations, getLocale } from "next-intl/server";
import { Suspense } from "react";

import { api } from "@/lib/api";
import { getAccessToken } from "@/lib/session";
import { Card } from "@/components/ui/card";
import { DocumentsList, type DocRow } from "@/components/dashboard/documents-list";
import { DocumentUploader } from "@/components/dashboard/document-uploader";
import { EmptyState } from "@/components/dashboard/empty-state";

export default async function DocumentsPage() {
  const t = await getTranslations("dashboard.documents");

  return (
    <div className="container py-8 space-y-6">
      <header className="flex items-center justify-between">
        <h1 className="text-3xl font-bold tracking-tight">{t("title")}</h1>
        <DocumentUploader />
      </header>

      <Suspense fallback={<DocumentsSkeleton />}>
        <DocumentsView />
      </Suspense>
    </div>
  );
}

async function DocumentsView() {
  const [token, t, locale] = await Promise.all([
    getAccessToken(),
    getTranslations("dashboard.documents"),
    getLocale(),
  ]);

  let docs: DocRow[] = [];
  try {
    docs = (await api<DocRow[]>("/v1/documents?limit=500", { token })) ?? [];
  } catch {
    docs = [];
  }

  if (docs.length === 0) {
    return (
      <EmptyState
        icon={FileText}
        title={locale === "ar" ? "لا توجد مستندات بعد" : "No documents yet"}
        body={
          locale === "ar"
            ? "ارفع عقدًا أو مذكرة أو ملف قضية — سنفهرسه ويصبح قابلًا للبحث والاستشهاد به."
            : "Upload a contract, memo, or case file — we'll index it and make it searchable and citable."
        }
      />
    );
  }

  return (
    <DocumentsList
      docs={docs}
      isAr={locale === "ar"}
      statusLabels={{
        uploaded: t("status.uploaded"),
        processing: t("status.processing"),
        indexed: t("status.indexed"),
        failed: t("status.failed"),
      }}
    />
  );
}

function DocumentsSkeleton() {
  return (
    <div className="space-y-4 animate-pulse">
      <div className="h-10 bg-muted/40 rounded-md" />
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {Array.from({ length: 6 }).map((_, i) => (
          <Card key={i} className="h-32 bg-muted/30" />
        ))}
      </div>
    </div>
  );
}
