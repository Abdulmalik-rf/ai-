import { api } from "@/lib/api";
import { getAccessToken } from "@/lib/session";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { TenantActions } from "@/components/admin/tenant-actions";

interface Tenant {
  id: string;
  name: string;
  slug: string;
  is_active: boolean;
  default_locale: string;
  created_at: string;
}

export default async function TenantsPage() {
  const token = await getAccessToken();
  let tenants: Tenant[] = [];
  try {
    tenants = (await api<Tenant[]>("/v1/admin/tenants", { token })) ?? [];
  } catch {
    tenants = [];
  }

  return (
    <div className="container py-8 space-y-6">
      <h1 className="text-3xl font-bold tracking-tight">Tenants</h1>
      <Card>
        <CardContent className="p-0">
          <table className="w-full text-sm">
            <thead className="bg-muted/30 text-left">
              <tr>
                <th className="p-3">Firm</th>
                <th className="p-3">Slug</th>
                <th className="p-3">Locale</th>
                <th className="p-3">Status</th>
                <th className="p-3 text-end">Actions</th>
              </tr>
            </thead>
            <tbody>
              {tenants.map((t) => (
                <tr key={t.id} className="border-t">
                  <td className="p-3 font-medium">{t.name}</td>
                  <td className="p-3 text-muted-foreground">{t.slug}</td>
                  <td className="p-3">{t.default_locale}</td>
                  <td className="p-3">
                    <Badge variant={t.is_active ? "success" : "destructive"}>
                      {t.is_active ? "active" : "suspended"}
                    </Badge>
                  </td>
                  <td className="p-3 text-end">
                    <TenantActions
                      id={t.id}
                      isActive={t.is_active}
                      slug={t.slug}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </div>
  );
}
