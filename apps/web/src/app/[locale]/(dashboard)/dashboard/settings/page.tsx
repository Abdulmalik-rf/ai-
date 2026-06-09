import { getLocale } from "next-intl/server";
import { Suspense } from "react";

import { api } from "@/lib/api";
import { getAccessToken, requireUser } from "@/lib/session";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { FirmForm } from "@/components/dashboard/settings/firm-form";
import { ProfileForm } from "@/components/dashboard/settings/profile-form";
import { SessionsCard } from "@/components/dashboard/settings/sessions-card";

interface TenantSelf {
  id: string;
  name: string;
  slug: string;
  subdomain: string;
  country: string;
  default_locale: string;
  is_active: boolean;
  vat_number: string | null;
  billing_email: string | null;
  billing_address: string | null;
  dashboard_url: string | null;
}

interface SessionRead {
  id: string;
  user_agent: string | null;
  ip_address: string | null;
  created_at: string;
  expires_at: string;
}

export default async function SettingsPage() {
  const locale = await getLocale();
  const isAr = locale === "ar";

  return (
    <div className="container max-w-3xl py-8 space-y-6">
      <header className="space-y-1">
        <h1 className="text-3xl font-bold tracking-tight">
          {isAr ? "الإعدادات" : "Settings"}
        </h1>
        <p className="text-muted-foreground">
          {isAr
            ? "ملفك الشخصي، الشركة، وأمن الحساب."
            : "Your profile, firm, and account security."}
        </p>
      </header>

      <Suspense fallback={<SettingsSkeleton />}>
        <SettingsPanels isAr={isAr} />
      </Suspense>
    </div>
  );
}

async function SettingsPanels({ isAr }: { isAr: boolean }) {
  // requireUser() is memoized at the request level — the layout already
  // resolved it, so this is effectively a free lookup.
  const [user, token] = await Promise.all([requireUser(), getAccessToken()]);

  const [tenant, sessions] = await Promise.all([
    safe<TenantSelf | null>("/v1/tenants/me", token, null),
    safe<SessionRead[]>("/v1/auth/sessions", token, []),
  ]);

  const isAdmin = user.role === "admin" || user.role === "super_admin";

  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle>{isAr ? "ملفك الشخصي" : "Your profile"}</CardTitle>
          <CardDescription>
            {isAr
              ? "اسمك ولغتك المفضلة. تطبّق على لوحة التحكم والإشعارات."
              : "Your name and preferred language. Applied to the dashboard and notifications."}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <ProfileForm
            initial={{
              full_name: user.full_name,
              email: user.email,
              locale: user.locale,
              role: user.role,
              phone_number: user.phone_number,
            }}
          />
        </CardContent>
      </Card>

      {isAdmin && tenant && (
        <Card>
          <CardHeader>
            <CardTitle>{isAr ? "بيانات الشركة" : "Firm details"}</CardTitle>
            <CardDescription>
              {isAr
                ? "اسم المكتب، الفوترة، والرقم الضريبي — يظهر على الفواتير والإيصالات."
                : "Office name, billing, and tax information — appears on invoices and receipts."}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <FirmForm
              initial={{
                name: tenant.name,
                subdomain: tenant.subdomain,
                default_locale: tenant.default_locale,
                vat_number: tenant.vat_number,
                billing_email: tenant.billing_email,
                billing_address: tenant.billing_address,
                dashboard_url: tenant.dashboard_url,
              }}
            />
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>
            {isAr ? "الجلسات النشطة" : "Active sessions"}
          </CardTitle>
          <CardDescription>
            {isAr
              ? "الأجهزة التي سجّلت الدخول منها مؤخرًا. أنه أي جلسة لا تعرفها."
              : "Devices you've recently signed in from. Revoke any session you don't recognise."}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <SessionsCard initial={sessions} />
        </CardContent>
      </Card>
    </>
  );
}

function SettingsSkeleton() {
  return (
    <div className="space-y-6 animate-pulse">
      <div className="rounded-lg border bg-card h-56" />
      <div className="rounded-lg border bg-card h-56" />
      <div className="rounded-lg border bg-card h-40" />
    </div>
  );
}

async function safe<T>(path: string, token: string | null, fallback: T): Promise<T> {
  if (!token) return fallback;
  try {
    return (await api<T>(path, { token })) ?? fallback;
  } catch {
    return fallback;
  }
}
