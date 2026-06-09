import { getTranslations } from "next-intl/server";
import { Suspense } from "react";

import { ContactsWorkspace } from "@/components/dashboard/contacts-workspace";
import { api } from "@/lib/api";
import { getAccessToken } from "@/lib/session";

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

export default async function ContactsPage() {
  const t = await getTranslations("dashboard.crm.contacts");

  return (
    <div className="container py-8 space-y-6">
      <header>
        <h1 className="text-3xl font-bold tracking-tight">{t("title")}</h1>
      </header>
      <Suspense fallback={<ContactsSkeleton />}>
        <ContactsList />
      </Suspense>
    </div>
  );
}

async function ContactsList() {
  const token = await getAccessToken();

  let contacts: Contact[] = [];
  try {
    contacts = await api<Contact[]>("/v1/contacts?limit=200", { token });
  } catch {
    // empty
  }

  return <ContactsWorkspace initialContacts={contacts} />;
}

function ContactsSkeleton() {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 animate-pulse">
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} className="rounded-lg border bg-card h-32" />
      ))}
    </div>
  );
}
