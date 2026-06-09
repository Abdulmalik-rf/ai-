"use client";

/**
 * Delete-client action with inline two-step confirm. On success routes back
 * to the clients list. Deleting a client that still has cases attached will
 * return a 409 from the API — we surface the message verbatim so the user
 * knows what to do.
 */
import { Loader2, Trash2 } from "lucide-react";
import { useLocale } from "next-intl";
import * as React from "react";

import { useRouter } from "@/i18n/routing";

import { Button } from "@/components/ui/button";

export function DeleteClientButton({ clientId }: { clientId: string }) {
  const router = useRouter();
  const locale = useLocale();
  const isAr = locale === "ar";
  const [confirming, setConfirming] = React.useState(false);
  const [busy, setBusy] = React.useState(false);

  React.useEffect(() => {
    if (!confirming) return;
    const id = window.setTimeout(() => setConfirming(false), 4000);
    return () => window.clearTimeout(id);
  }, [confirming]);

  async function doDelete() {
    setBusy(true);
    try {
      const res = await fetch(`/api/v1/clients/${clientId}`, {
        method: "DELETE",
      });
      if (!res.ok && res.status !== 204) {
        const text = await res.text();
        let msg = text;
        try {
          const j = JSON.parse(text);
          if (j?.detail) {
            msg = Array.isArray(j.detail)
              ? j.detail.map((d: { msg?: string }) => d.msg ?? "").join("; ")
              : String(j.detail);
          }
        } catch {
          /* keep raw */
        }
        alert(msg || `HTTP ${res.status}`);
        setBusy(false);
        return;
      }
      router.push("/dashboard/clients");
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
