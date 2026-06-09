import { getTranslations } from "next-intl/server";
import { Suspense } from "react";

import { AgentProfileForm } from "@/components/dashboard/whatsapp/agent-profile-form";
import type { AgentProfile } from "@/components/dashboard/whatsapp/agent-profile-form";
import { WhatsAppConnectionCard } from "@/components/dashboard/whatsapp/connection-card";
import { PromptPreview } from "@/components/dashboard/whatsapp/prompt-preview";
import { api } from "@/lib/api";
import { getAccessToken } from "@/lib/session";

interface SessionStatusRead {
  status: "disconnected" | "pairing" | "connected" | "logged_out" | "error";
  qr?: string | null;
  phone_number?: string | null;
  display_name?: string | null;
  last_disconnect_reason?: string | null;
  last_connected_at?: string | null;
}

export default async function WhatsAppPage() {
  const t = await getTranslations("dashboard.whatsapp");
  return (
    <div className="container max-w-4xl py-8 space-y-6">
      <header className="space-y-2">
        <h1 className="text-2xl font-bold tracking-tight">{t("title")}</h1>
        <p className="text-muted-foreground">{t("subtitle")}</p>
      </header>

      <Suspense fallback={<WhatsAppSkeleton />}>
        <WhatsAppPanels />
      </Suspense>
    </div>
  );
}

async function WhatsAppPanels() {
  const token = await getAccessToken();
  const [session, profile] = await Promise.all([
    safe<SessionStatusRead>("/v1/whatsapp/session", token, {
      status: "disconnected",
    }),
    safe<AgentProfile>("/v1/whatsapp/agent-profile", token, {
      enabled_domains: [],
      timezone: "Asia/Riyadh",
      is_enabled: true,
    }),
  ]);

  return (
    <>
      <WhatsAppConnectionCard initial={session} />
      <AgentProfileForm initial={profile} />
      <PromptPreview />
    </>
  );
}

function WhatsAppSkeleton() {
  return (
    <div className="space-y-4 animate-pulse">
      <div className="rounded-lg border bg-card h-48" />
      <div className="rounded-lg border bg-card h-64" />
      <div className="rounded-lg border bg-card h-32" />
    </div>
  );
}

async function safe<T>(
  path: string,
  token: string | null,
  fallback: T
): Promise<T> {
  if (!token) return fallback;
  try {
    return (await api<T>(path, { token })) ?? fallback;
  } catch {
    return fallback;
  }
}
