import {
  Briefcase,
  Building2,
  CreditCard,
  FileText,
  IdCard,
  Mail,
  MapPin,
  Phone,
  Tag,
  User,
} from "lucide-react";
import { notFound } from "next/navigation";
import { getLocale } from "next-intl/server";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DeleteClientButton } from "@/components/dashboard/delete-client-button";
import { EditClientDialog } from "@/components/dashboard/edit-client-dialog";
import { Link } from "@/i18n/routing";
import { api } from "@/lib/api";
import { getAccessToken } from "@/lib/session";
import { formatDate } from "@/lib/utils";

interface Client {
  id: string;
  name: string;
  kind: "person" | "company";
  status: "lead" | "prospect" | "active" | "archived";
  national_id: string | null;
  cr_number: string | null;
  vat_number: string | null;
  email: string | null;
  phone: string | null;
  address: string | null;
  city: string | null;
  lead_source: string | null;
  referred_by: string | null;
  kyc_completed_at: string | null;
  kyc_notes: string | null;
  notes: string | null;
  tags: string[];
  created_at: string;
  updated_at: string;
}

interface CaseRow {
  id: string;
  reference: string;
  title: string;
  domain: string;
  status: string;
  priority: string;
  next_hearing_at: string | null;
  created_at: string;
}

interface Activity {
  id: string;
  kind: string;
  summary: string;
  body: string | null;
  occurred_at: string;
}

export default async function ClientDetailPage(props: {
  params: Promise<{ clientId: string }>;
}) {
  const { clientId } = await props.params;
  const locale = await getLocale();
  const isAr = locale === "ar";
  const token = await getAccessToken();

  let client: Client;
  try {
    client = await api<Client>(`/v1/clients/${clientId}`, { token });
  } catch {
    notFound();
  }

  const [cases, activities] = await Promise.all([
    api<CaseRow[]>(`/v1/cases?client_id=${clientId}&limit=200`, {
      token,
    }).catch(() => []),
    api<Activity[]>(`/v1/activities?client_id=${clientId}&limit=50`, {
      token,
    }).catch(() => []),
  ]);

  const openCases = cases.filter(
    (c) => c.status !== "closed" && c.status !== "archived"
  );
  const closedCases = cases.filter(
    (c) => c.status === "closed" || c.status === "archived"
  );
  const KindIcon = client.kind === "company" ? Building2 : User;

  return (
    <div className="container py-8 space-y-6">
      <header className="space-y-4">
        <div className="flex items-start justify-between gap-3 flex-wrap">
          <div className="flex items-start gap-4 flex-1 min-w-0">
            <div className="grid h-14 w-14 place-items-center rounded-2xl bg-primary/10 text-primary shrink-0">
              <KindIcon className="h-7 w-7" />
            </div>
            <div className="min-w-0">
              <div className="text-xs text-muted-foreground">
                {isAr ? "أُضيف " : "Added "}
                {formatDate(client.created_at, locale)}
              </div>
              <h1 className="text-3xl font-bold tracking-tight truncate">
                {client.name}
              </h1>
              <div className="flex flex-wrap items-center gap-2 mt-2">
                <Badge variant="outline">
                  {client.kind === "company"
                    ? isAr
                      ? "شركة"
                      : "Company"
                    : isAr
                      ? "فرد"
                      : "Person"}
                </Badge>
                <Badge variant={statusVariant(client.status)}>
                  {statusLabel(client.status, isAr)}
                </Badge>
                {client.tags?.map((t) => (
                  <Badge key={t} variant="secondary">
                    <Tag className="h-3 w-3" />
                    {t}
                  </Badge>
                ))}
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <EditClientDialog
              clientId={clientId}
              initial={{
                name: client.name,
                kind: client.kind,
                status: client.status,
                national_id: client.national_id,
                cr_number: client.cr_number,
                vat_number: client.vat_number,
                email: client.email,
                phone: client.phone,
                address: client.address,
                city: client.city,
                lead_source: client.lead_source,
                referred_by: client.referred_by,
                notes: client.notes,
              }}
            />
            <DeleteClientButton clientId={clientId} />
          </div>
        </div>

        {/* KPI strip — open vs closed cases. Last activity / KYC tiles were
            removed because they weren't actionable from this view. */}
        <div className="grid grid-cols-2 gap-3 md:max-w-md">
          <Kpi
            icon={Briefcase}
            label={isAr ? "قضايا مفتوحة" : "Open cases"}
            value={String(openCases.length)}
          />
          <Kpi
            icon={FileText}
            label={isAr ? "قضايا مغلقة" : "Closed cases"}
            value={String(closedCases.length)}
          />
        </div>
      </header>

      {/* Two-column body: contact card + linked cases */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className="lg:col-span-1">
          <CardHeader>
            <CardTitle className="text-base">
              {isAr ? "التواصل والتعريف" : "Contact & identifiers"}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4 text-sm">
            <ContactRow
              icon={Mail}
              label={isAr ? "البريد الإلكتروني" : "Email"}
              value={client.email}
              href={client.email ? `mailto:${client.email}` : undefined}
            />
            <ContactRow
              icon={Phone}
              label={isAr ? "الهاتف" : "Phone"}
              value={client.phone}
              href={client.phone ? `tel:${client.phone}` : undefined}
            />
            <ContactRow
              icon={MapPin}
              label={isAr ? "العنوان" : "Address"}
              value={[client.address, client.city].filter(Boolean).join(", ") || null}
            />

            <hr className="border-border/60" />

            <ContactRow
              icon={IdCard}
              label={isAr ? "الهوية الوطنية" : "National ID"}
              value={client.national_id}
              mono
            />
            <ContactRow
              icon={CreditCard}
              label={isAr ? "السجل التجاري" : "CR number"}
              value={client.cr_number}
              mono
            />
            <ContactRow
              icon={CreditCard}
              label={isAr ? "الرقم الضريبي" : "VAT number"}
              value={client.vat_number}
              mono
            />

            {(client.lead_source || client.referred_by) && (
              <>
                <hr className="border-border/60" />
                <ContactRow
                  icon={Tag}
                  label={isAr ? "المصدر" : "Lead source"}
                  value={client.lead_source}
                />
                <ContactRow
                  icon={User}
                  label={isAr ? "أحاله" : "Referred by"}
                  value={client.referred_by}
                />
              </>
            )}

            {client.notes && (
              <>
                <hr className="border-border/60" />
                <div>
                  <div className="text-xs uppercase tracking-wider text-muted-foreground mb-1.5">
                    {isAr ? "ملاحظات داخلية" : "Internal notes"}
                  </div>
                  <p className="text-sm whitespace-pre-wrap leading-relaxed">
                    {client.notes}
                  </p>
                </div>
              </>
            )}
          </CardContent>
        </Card>

        <div className="lg:col-span-2 space-y-6">
          <Card>
            <CardHeader className="flex-row items-center justify-between">
              <CardTitle className="text-base">
                {isAr ? "القضايا" : "Cases"}
              </CardTitle>
              <span className="text-xs text-muted-foreground">
                {cases.length}
              </span>
            </CardHeader>
            <CardContent>
              {cases.length === 0 ? (
                <p className="text-sm text-muted-foreground py-6 text-center">
                  {isAr
                    ? "لا توجد قضايا لهذا العميل بعد. افتح قضية من صفحة القضايا واربطها به."
                    : "No cases linked to this client yet. Open a case from the Cases page and link this client to it."}
                </p>
              ) : (
                <ul className="divide-y divide-border/60">
                  {cases.map((c) => (
                    <li key={c.id}>
                      <Link
                        href={`/dashboard/cases/${c.id}`}
                        className="flex items-center gap-3 py-3 hover:bg-muted/30 -mx-2 px-2 rounded-md transition-colors"
                      >
                        <div className="grid h-9 w-9 place-items-center rounded-md bg-primary/10 text-primary shrink-0">
                          <Briefcase className="h-4 w-4" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="text-xs text-muted-foreground">
                            {c.reference} ·{" "}
                            {formatDate(c.created_at, locale)}
                          </div>
                          <div className="font-medium truncate">{c.title}</div>
                          <div className="flex flex-wrap gap-1.5 mt-1">
                            <Badge variant="outline" className="text-xs">
                              {c.domain}
                            </Badge>
                            <Badge className="text-xs">{c.status}</Badge>
                            {c.priority !== "medium" && (
                              <Badge variant="secondary" className="text-xs">
                                {c.priority}
                              </Badge>
                            )}
                          </div>
                        </div>
                        {c.next_hearing_at && (
                          <div className="text-xs text-muted-foreground shrink-0 text-end">
                            <div>
                              {isAr ? "الجلسة القادمة" : "Next hearing"}
                            </div>
                            <div className="font-medium text-foreground">
                              {formatDate(c.next_hearing_at, locale)}
                            </div>
                          </div>
                        )}
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">
                {isAr ? "النشاط الأخير" : "Recent activity"}
              </CardTitle>
            </CardHeader>
            <CardContent>
              {activities.length === 0 ? (
                <p className="text-sm text-muted-foreground py-6 text-center">
                  {isAr
                    ? "لا يوجد نشاط مسجَّل بعد. تظهر هنا كل تفاعلات هذا العميل."
                    : "No activity logged yet. Every interaction with this client will show up here."}
                </p>
              ) : (
                <ul className="space-y-3">
                  {activities.slice(0, 12).map((a) => (
                    <li key={a.id} className="flex gap-3">
                      <div className="mt-1 grid h-6 w-6 place-items-center rounded-full bg-muted text-muted-foreground shrink-0">
                        <span className="text-[10px]">•</span>
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium">{a.summary}</div>
                        {a.body && (
                          <p className="text-xs text-muted-foreground mt-0.5 line-clamp-2">
                            {a.body}
                          </p>
                        )}
                        <div className="text-xs text-muted-foreground mt-0.5">
                          {formatDate(a.occurred_at, locale)} · {a.kind}
                        </div>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

function Kpi({
  icon: Icon,
  label,
  value,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-xl border border-border/60 bg-card p-4">
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <Icon className="h-3.5 w-3.5" />
        {label}
      </div>
      <div className="text-xl font-semibold mt-1.5">{value}</div>
    </div>
  );
}

function ContactRow({
  icon: Icon,
  label,
  value,
  href,
  mono,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string | null;
  href?: string;
  mono?: boolean;
}) {
  if (!value) {
    return (
      <div className="flex items-start gap-3">
        <Icon className="h-4 w-4 mt-0.5 text-muted-foreground shrink-0" />
        <div className="min-w-0">
          <div className="text-xs uppercase tracking-wider text-muted-foreground">
            {label}
          </div>
          <div className="text-muted-foreground/60 text-sm">—</div>
        </div>
      </div>
    );
  }
  const Wrapped = href ? "a" : "div";
  const props = href
    ? { href, className: "hover:underline underline-offset-2" }
    : {};
  return (
    <div className="flex items-start gap-3">
      <Icon className="h-4 w-4 mt-0.5 text-muted-foreground shrink-0" />
      <div className="min-w-0">
        <div className="text-xs uppercase tracking-wider text-muted-foreground">
          {label}
        </div>
        <Wrapped
          {...props}
          className={`text-sm break-words ${mono ? "font-mono" : ""} ${
            href ? "hover:underline underline-offset-2" : ""
          }`}
        >
          {value}
        </Wrapped>
      </div>
    </div>
  );
}

function statusVariant(s: Client["status"]) {
  if (s === "active") return "success" as const;
  if (s === "archived") return "secondary" as const;
  if (s === "lead") return "warning" as const;
  return "outline" as const;
}

function statusLabel(s: Client["status"], isAr: boolean) {
  if (!isAr) return s;
  return s === "lead"
    ? "محتمل"
    : s === "prospect"
      ? "اهتمام"
      : s === "active"
        ? "نشط"
        : "مؤرشف";
}
