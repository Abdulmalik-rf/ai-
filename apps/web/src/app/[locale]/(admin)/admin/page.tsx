import {
  Building2,
  FileText,
  Gauge,
  MessagesSquare,
  Receipt,
  Users,
} from "lucide-react";

import { api } from "@/lib/api";
import { getAccessToken } from "@/lib/session";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Link } from "@/i18n/routing";

interface Metrics {
  tenants: number;
  users: number;
  active_subscriptions: number;
  documents: number;
  messages_30d: number;
  contract_reviews_30d: number;
}

export default async function AdminOverviewPage() {
  const token = await getAccessToken();
  let m: Metrics | null = null;
  try {
    m = await api<Metrics>("/v1/admin/metrics", { token });
  } catch {
    m = null;
  }

  const cards = [
    { icon: Building2, label: "Tenants", value: m?.tenants ?? 0 },
    { icon: Users, label: "Users", value: m?.users ?? 0 },
    { icon: Receipt, label: "Active subs", value: m?.active_subscriptions ?? 0 },
    { icon: FileText, label: "Documents", value: m?.documents ?? 0 },
    { icon: MessagesSquare, label: "Messages (30d)", value: m?.messages_30d ?? 0 },
    {
      icon: Gauge,
      label: "Contract reviews (30d)",
      value: m?.contract_reviews_30d ?? 0,
    },
  ];

  return (
    <div className="container py-8 space-y-6">
      <header>
        <h1 className="text-3xl font-bold tracking-tight">Platform metrics</h1>
        <p className="text-muted-foreground">Cross-tenant rollups for super admins.</p>
      </header>

      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        {cards.map(({ icon: Icon, label, value }) => (
          <Card key={label}>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
                <Icon className="h-4 w-4" />
                {label}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold">{value}</div>
            </CardContent>
          </Card>
        ))}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Quick links</CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
          <Link href="/admin/tenants" className="text-primary hover:underline">
            → Manage tenants
          </Link>
          <Link href="/admin/datasets" className="text-primary hover:underline">
            → Upload Saudi-law datasets
          </Link>
        </CardContent>
      </Card>
    </div>
  );
}
