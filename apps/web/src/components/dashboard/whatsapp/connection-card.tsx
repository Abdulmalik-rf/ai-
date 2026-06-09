"use client";

import { CheckCircle2, Loader2, Plug, Power, RefreshCw, Smartphone, XCircle } from "lucide-react";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useRef, useState } from "react";
import { QRCodeSVG } from "qrcode.react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type Status =
  | "disconnected"
  | "pairing"
  | "connected"
  | "logged_out"
  | "error";

interface SessionStatusRead {
  status: Status;
  qr?: string | null;
  phone_number?: string | null;
  display_name?: string | null;
  last_disconnect_reason?: string | null;
  last_connected_at?: string | null;
}

const PILL: Record<Status, { tone: string; key: string }> = {
  disconnected: {
    tone: "bg-muted text-muted-foreground",
    key: "statusDisconnected",
  },
  pairing: {
    tone: "bg-amber-500/15 text-amber-700 dark:text-amber-300",
    key: "statusPairing",
  },
  connected: {
    tone: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300",
    key: "statusConnected",
  },
  logged_out: {
    tone: "bg-muted text-muted-foreground",
    key: "statusLoggedOut",
  },
  error: {
    tone: "bg-destructive/15 text-destructive",
    key: "statusError",
  },
};

export function WhatsAppConnectionCard({
  initial,
}: {
  initial: SessionStatusRead;
}) {
  const t = useTranslations("dashboard.whatsapp.connection");
  const [session, setSession] = useState<SessionStatusRead>(initial);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = () => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  };

  const refresh = useCallback(async () => {
    try {
      const res = await fetch("/api/v1/whatsapp/session");
      if (!res.ok) return;
      const data = (await res.json()) as SessionStatusRead;
      setSession(data);
      if (data.status !== "pairing") stopPolling();
    } catch {
      // transient — keep polling
    }
  }, []);

  // Poll while pairing.
  useEffect(() => {
    if (session.status === "pairing") {
      pollRef.current = setInterval(refresh, 3000);
    }
    return stopPolling;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session.status]);

  async function connect() {
    setError(null);
    setBusy(true);
    try {
      const res = await fetch("/api/v1/whatsapp/session/start", {
        method: "POST",
      });
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        throw new Error(body?.detail || `${res.status}`);
      }
      const data = (await res.json()) as SessionStatusRead;
      setSession(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function disconnect() {
    setError(null);
    setBusy(true);
    try {
      const res = await fetch("/api/v1/whatsapp/session", { method: "DELETE" });
      if (!res.ok && res.status !== 204) {
        const body = await res.json().catch(() => null);
        throw new Error(body?.detail || `${res.status}`);
      }
      setSession({ status: "disconnected" });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  const pill = PILL[session.status];
  const isPairing = session.status === "pairing";
  const isConnected = session.status === "connected";

  return (
    <section className="rounded-2xl border border-border/60 bg-card p-6 shadow-sm">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-lg font-semibold">{t("title")}</h2>
        <span
          className={cn(
            "inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium",
            pill.tone
          )}
        >
          {isConnected ? (
            <CheckCircle2 className="h-3.5 w-3.5" />
          ) : session.status === "error" ? (
            <XCircle className="h-3.5 w-3.5" />
          ) : (
            <Smartphone className="h-3.5 w-3.5" />
          )}
          {t(pill.key)}
        </span>
      </div>

      <div className="mt-4 space-y-3 text-sm">
        {isConnected && session.phone_number && (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            <div>
              <div className="text-xs text-muted-foreground">
                {t("phoneLabel")}
              </div>
              <div className="font-mono text-foreground">
                +{session.phone_number}
              </div>
            </div>
            {session.display_name && (
              <div>
                <div className="text-xs text-muted-foreground">
                  {t("displayLabel")}
                </div>
                <div>{session.display_name}</div>
              </div>
            )}
          </div>
        )}

        {isPairing && (
          <div className="flex flex-col items-center gap-3 py-2">
            {session.qr ? (
              <div className="rounded-lg border border-border/60 bg-white p-3">
                <QRCodeSVG
                  value={session.qr}
                  size={220}
                  level="M"
                  includeMargin={false}
                  aria-label={t("qrAlt")}
                />
              </div>
            ) : (
              <div className="grid h-[220px] w-[220px] place-items-center rounded-lg border border-dashed border-border/60 bg-muted/30 text-muted-foreground">
                <Loader2 className="h-6 w-6 animate-spin" />
              </div>
            )}
            <p className="text-center text-xs text-muted-foreground max-w-md">
              {t("pairingHint")}
            </p>
            <button
              type="button"
              onClick={refresh}
              className="inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
            >
              <RefreshCw className="h-3 w-3" />
              {t("refreshQr")}
            </button>
          </div>
        )}

        {session.status === "error" && session.last_disconnect_reason && (
          <p className="text-sm text-destructive">
            {session.last_disconnect_reason}
          </p>
        )}

        {error && (
          <p className="text-sm text-destructive">
            {t("errorPrefix")}: {error}
          </p>
        )}
      </div>

      <div className="mt-5 flex items-center gap-2">
        {!isConnected && !isPairing && (
          <Button onClick={connect} disabled={busy} className="gap-2">
            {busy ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Plug className="h-4 w-4" />
            )}
            {t("connectButton")}
          </Button>
        )}
        {(isConnected || isPairing) && (
          <Button
            onClick={disconnect}
            disabled={busy}
            variant="outline"
            className="gap-2"
          >
            {busy ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Power className="h-4 w-4" />
            )}
            {t("disconnectButton")}
          </Button>
        )}
      </div>
    </section>
  );
}
