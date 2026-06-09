"use client";

/**
 * Delete-case action with inline confirmation. Sends DELETE /api/v1/cases/{id}
 * and, on success, routes back to the cases list. We deliberately gate this
 * behind a two-step confirm in the same button — cheaper than a full
 * AlertDialog component and harder to misclick than a single press.
 */
import { Loader2, Trash2 } from "lucide-react";
import { useLocale } from "next-intl";
import * as React from "react";

import { useRouter } from "@/i18n/routing";

import { Button } from "@/components/ui/button";

export function DeleteCaseButton({ caseId }: { caseId: string }) {
  const router = useRouter();
  const locale = useLocale();
  const isAr = locale === "ar";
  const [confirming, setConfirming] = React.useState(false);
  const [busy, setBusy] = React.useState(false);

  // Auto-collapse the confirm state after 4s if the user walks away.
  React.useEffect(() => {
    if (!confirming) return;
    const id = window.setTimeout(() => setConfirming(false), 4000);
    return () => window.clearTimeout(id);
  }, [confirming]);

  async function doDelete() {
    setBusy(true);
    try {
      const res = await fetch(`/api/v1/cases/${caseId}`, { method: "DELETE" });
      if (!res.ok && res.status !== 204) {
        const text = await res.text();
        alert(text || `HTTP ${res.status}`);
        setBusy(false);
        return;
      }
      router.push("/dashboard/cases");
      router.refresh();
    } catch (err) {
      alert((err as Error).message);
      setBusy(false);
    }
  }

  if (confirming) {
    return (
      <div className="inline-flex items-center gap-2">
        <Button
          variant="destructive"
          size="sm"
          onClick={doDelete}
          disabled={busy}
        >
          {busy && <Loader2 className="h-4 w-4 animate-spin" />}
          {isAr ? "تأكيد الحذف" : "Confirm delete"}
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={() => setConfirming(false)}
          disabled={busy}
        >
          {isAr ? "إلغاء" : "Cancel"}
        </Button>
      </div>
    );
  }

  return (
    <Button
      variant="outline"
      size="sm"
      onClick={() => setConfirming(true)}
      className="text-destructive hover:bg-destructive/10 hover:text-destructive"
    >
      <Trash2 className="h-4 w-4" />
      {isAr ? "حذف" : "Delete"}
    </Button>
  );
}
