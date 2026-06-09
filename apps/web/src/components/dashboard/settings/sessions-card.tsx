"use client";

/**
 * Active sessions list. Each row = one live refresh token (one device).
 * "Sign out of this session" → DELETE /api/v1/auth/sessions/{id}.
 * "Sign out everywhere" → POST /api/v1/auth/logout-all then redirect.
 */
import { Loader2, LogOut, Monitor, Smartphone } from "lucide-react";
import { useLocale } from "next-intl";
import * as React from "react";

import { useRouter } from "@/i18n/routing";

import { Button } from "@/components/ui/button";

interface SessionRow {
  id: string;
  user_agent: string | null;
  ip_address: string | null;
  created_at: string;
  expires_at: string;
  last_used_at?: string | null;
}

export function SessionsCard({ initial }: { initial: SessionRow[] }) {
  const router = useRouter();
  const locale = useLocale();
  const isAr = locale === "ar";
  const [rows, setRows] = React.useState(initial);
  const [revoking, setRevoking] = React.useState<string | null>(null);
  const [signingOutAll, setSigningOutAll] = React.useState(false);

  async function revokeOne(id: string) {
    setRevoking(id);
    try {
      const res = await fetch(`/api/v1/auth/sessions/${id}`, {
        method: "DELETE",
      });
      if (res.ok || res.status === 204) {
        setRows((prev) => prev.filter((r) => r.id !== id));
      }
    } finally {
      setRevoking(null);
    }
  }

  async function signOutAll() {
    setSigningOutAll(true);
    try {
      await fetch("/api/v1/auth/logout-all", { method: "POST" });
      router.push("/sign-in");
      router.refresh();
    } catch {
      setSigningOutAll(false);
    }
  }

  if (rows.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        {isAr
          ? "لا توجد جلسات نشطة أخرى."
          : "No other active sessions."}
      </p>
    );
  }

  return (
    <div className="space-y-4">
      <ul className="divide-y divide-border/60 rounded-md border border-border/60">
        {rows.map((s) => {
          const Icon = isMobile(s.user_agent) ? Smartphone : Monitor;
          return (
            <li
              key={s.id}
              className="flex items-center gap-3 px-4 py-3"
            >
              <div className="grid h-9 w-9 place-items-center rounded-md bg-muted text-muted-foreground">
                <Icon className="h-4 w-4" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium truncate">
                  {prettyAgent(s.user_agent) ||
                    (isAr ? "جلسة غير معروفة" : "Unknown device")}
                </div>
                <div className="text-xs text-muted-foreground">
                  {s.ip_address || (isAr ? "IP غير معروف" : "Unknown IP")} ·{" "}
                  {formatRelative(s.created_at, isAr)}
                </div>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => revokeOne(s.id)}
                disabled={revoking === s.id}
              >
                {revoking === s.id && (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                )}
                {isAr ? "إنهاء" : "Revoke"}
              </Button>
            </li>
          );
        })}
      </ul>

      <Button
        variant="outline"
        onClick={signOutAll}
        disabled={signingOutAll}
      >
        {signingOutAll ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : (
          <LogOut className="h-4 w-4" />
        )}
        {isAr ? "تسجيل الخروج من كل الأجهزة" : "Sign out everywhere"}
      </Button>
    </div>
  );
}

function isMobile(ua: string | null) {
  if (!ua) return false;
  return /Mobile|Android|iPhone|iPad/i.test(ua);
}

function prettyAgent(ua: string | null) {
  if (!ua) return "";
  const m = ua.match(/(Chrome|Safari|Firefox|Edge|Opera)\/\d+/);
  const browser = m?.[1] ?? "Browser";
  if (/Windows/i.test(ua)) return `${browser} on Windows`;
  if (/Macintosh|Mac OS X/i.test(ua)) return `${browser} on macOS`;
  if (/Android/i.test(ua)) return `${browser} on Android`;
  if (/iPhone|iPad|iPod/i.test(ua)) return `${browser} on iOS`;
  if (/Linux/i.test(ua)) return `${browser} on Linux`;
  return browser;
}

function formatRelative(iso: string, isAr: boolean) {
  const d = new Date(iso);
  const diffMs = Date.now() - d.getTime();
  const mins = Math.floor(diffMs / 60_000);
  if (mins < 1) return isAr ? "الآن" : "just now";
  if (mins < 60) return isAr ? `قبل ${mins} د` : `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return isAr ? `قبل ${hrs} س` : `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  if (days < 30) return isAr ? `قبل ${days} يوم` : `${days}d ago`;
  return d.toLocaleDateString(isAr ? "ar" : "en");
}
