"use client";

import { useTranslations } from "next-intl";
import { Plus, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";

import { FilterBar, type ChipGroup } from "@/components/dashboard/filter-bar";
import { useLocale } from "next-intl";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";

interface Contact {
  id: string;
  name: string;
  kind: string;
  organization: string | null;
  title: string | null;
  phone: string | null;
  email: string | null;
  notes: string | null;
}

const KINDS = [
  "judge",
  "opposing_counsel",
  "expert",
  "witness",
  "mediator",
  "translator",
  "notary",
  "government",
  "opposing_party",
  "referee",
  "other",
] as const;

const KIND_LABEL_AR: Record<(typeof KINDS)[number], string> = {
  judge: "قاضٍ",
  opposing_counsel: "محامي الخصم",
  expert: "خبير",
  witness: "شاهد",
  mediator: "وسيط",
  translator: "مترجم",
  notary: "كاتب عدل",
  government: "جهة حكومية",
  opposing_party: "الخصم",
  referee: "محكَّم",
  other: "أخرى",
};

function kindLabel(kind: string, isAr: boolean): string {
  if (isAr && kind in KIND_LABEL_AR) {
    return KIND_LABEL_AR[kind as (typeof KINDS)[number]];
  }
  return kind.replace("_", " ");
}

export function ContactsWorkspace({
  initialContacts,
}: {
  initialContacts: Contact[];
}) {
  const t = useTranslations("dashboard.crm.contacts");
  const tCommon = useTranslations("dashboard.crm.common");
  const [contacts, setContacts] = useState<Contact[]>(initialContacts);
  const [showCreate, setShowCreate] = useState(false);
  const [filter, setFilter] = useState("");
  const [kindFilter, setKindFilter] = useState("");

  const locale = useLocale();
  const isAr = locale === "ar";

  const filtered = useMemo(
    () =>
      contacts.filter((c) => {
        if (kindFilter && c.kind !== kindFilter) return false;
        if (!filter) return true;
        const q = filter.toLowerCase();
        return (
          c.name.toLowerCase().includes(q) ||
          (c.organization || "").toLowerCase().includes(q) ||
          (c.phone || "").includes(q) ||
          (c.email || "").toLowerCase().includes(q)
        );
      }),
    [contacts, filter, kindFilter],
  );

  async function deleteContact(id: string) {
    const res = await fetch(`/api/v1/contacts/${id}`, { method: "DELETE" });
    if (res.ok) {
      setContacts((prev) => prev.filter((c) => c.id !== id));
    }
  }

  const chipGroups: ChipGroup[] = [
    {
      value: kindFilter || "all",
      onChange: (v) => setKindFilter(v === "all" ? "" : v),
      options: [
        { value: "all", label: isAr ? "كل الأنواع" : "All kinds" },
        ...KINDS.map((k) => ({ value: k, label: kindLabel(k, isAr) })),
      ],
    },
  ];

  return (
    <>
      <div className="flex items-start gap-3 justify-between flex-wrap">
        <div className="flex-1 min-w-[260px]">
          <FilterBar
            query={filter}
            onQueryChange={setFilter}
            placeholder={isAr ? "ابحث بالاسم أو المنظمة أو الهاتف…" : "Search name, org, phone…"}
            chipGroups={chipGroups}
            totalCount={contacts.length}
            filteredCount={filtered.length}
            hasFilters={filter !== "" || kindFilter !== ""}
            onReset={() => {
              setFilter("");
              setKindFilter("");
            }}
            isAr={isAr}
            noun={{ singular: "contact", plural: isAr ? "جهة" : "contacts" }}
          />
        </div>
        <Button size="sm" onClick={() => setShowCreate(true)}>
          <Plus className="h-4 w-4 me-1" /> {t("new")}
        </Button>
      </div>

      {showCreate && (
        <CreateContactCard
          onCancel={() => setShowCreate(false)}
          onCreated={(c) => {
            setContacts((prev) => [c, ...prev]);
            setShowCreate(false);
          }}
        />
      )}

      {filtered.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          {contacts.length === 0 ? t("empty") : tCommon("noResults")}
        </p>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {filtered.map((c) => (
            <Card key={c.id} className="p-4 group">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0 flex-1">
                  <p className="font-medium truncate">{c.name}</p>
                  <Badge variant="outline" className="mt-1 text-[10px]">
                    {kindLabel(c.kind, isAr)}
                  </Badge>
                  {c.organization && (
                    <p className="text-xs text-muted-foreground mt-2 truncate">
                      {c.organization}
                    </p>
                  )}
                  {c.title && (
                    <p className="text-xs text-muted-foreground truncate">{c.title}</p>
                  )}
                  {c.phone && (
                    <p className="text-xs mt-2">
                      <a href={`tel:${c.phone}`} className="text-primary hover:underline">
                        {c.phone}
                      </a>
                    </p>
                  )}
                  {c.email && (
                    <p className="text-xs truncate">
                      <a href={`mailto:${c.email}`} className="text-primary hover:underline">
                        {c.email}
                      </a>
                    </p>
                  )}
                </div>
                <button
                  onClick={() => deleteContact(c.id)}
                  className="opacity-0 group-hover:opacity-100 text-destructive transition-opacity"
                  aria-label="delete"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            </Card>
          ))}
        </div>
      )}
    </>
  );
}


function CreateContactCard({
  onCancel,
  onCreated,
}: {
  onCancel: () => void;
  onCreated: (c: Contact) => void;
}) {
  const t = useTranslations("dashboard.crm.contacts");
  const tCommon = useTranslations("dashboard.crm.common");
  const locale = useLocale();
  const isAr = locale === "ar";
  const [name, setName] = useState("");
  const [kind, setKind] = useState("other");
  const [organization, setOrganization] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [notes, setNotes] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    setPending(true);
    setError(null);
    try {
      const res = await fetch("/api/v1/contacts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name,
          kind,
          organization: organization || null,
          phone: phone || null,
          email: email || null,
          notes: notes || null,
        }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        throw new Error(body?.detail || `HTTP ${res.status}`);
      }
      onCreated((await res.json()) as Contact);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed");
    } finally {
      setPending(false);
    }
  }

  return (
    <Card className="p-5">
      <form onSubmit={submit} className="space-y-3">
        <h3 className="font-semibold">{t("new")}</h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <Input
            placeholder={t("fieldName")}
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            autoFocus
          />
          <select
            value={kind}
            onChange={(e) => setKind(e.target.value)}
            className="rounded-md border bg-background px-3 py-2 text-sm"
            aria-label={t("fieldKind")}
          >
            {KINDS.map((k) => (
              <option key={k} value={k}>
                {kindLabel(k, isAr)}
              </option>
            ))}
          </select>
          <Input
            placeholder={t("fieldOrganization")}
            value={organization}
            onChange={(e) => setOrganization(e.target.value)}
          />
          <Input
            placeholder={t("fieldPhone")}
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
          />
          <Input
            placeholder={t("fieldEmail")}
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="sm:col-span-2"
          />
        </div>
        <Textarea
          placeholder="Notes…"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          rows={2}
        />
        {error && <p className="text-sm text-destructive">{error}</p>}
        <div className="flex gap-2 justify-end">
          <Button type="button" variant="outline" size="sm" onClick={onCancel}>
            {tCommon("cancel")}
          </Button>
          <Button type="submit" size="sm" disabled={pending}>
            {pending ? "…" : tCommon("create")}
          </Button>
        </div>
      </form>
    </Card>
  );
}
