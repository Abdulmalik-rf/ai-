import { Shield } from "lucide-react";
import { getLocale } from "next-intl/server";
import { redirect } from "next/navigation";

import { BrandLogo } from "@/components/brand-logo";
import { LocaleToggle } from "@/components/locale-toggle";
import { ThemeToggle } from "@/components/theme-toggle";
import { Link } from "@/i18n/routing";
import { requireUser } from "@/lib/session";

export default async function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const user = await requireUser();
  if (user.role !== "super_admin") {
    redirect("/dashboard");
  }
  const locale = await getLocale();
  return (
    <div className="min-h-screen flex flex-col">
      <header className="h-16 border-b border-border/60 flex items-center px-6 bg-muted/30 justify-between">
        <Link href="/admin" className="flex items-center gap-3 font-semibold">
          <BrandLogo size={28} locale={locale} />
          <span className="flex items-center gap-2">
            <Shield className="h-4 w-4 text-accent" />
            <span className="text-foreground">
              {locale === "ar" ? "لوحة مدير المنصة" : "Platform Admin"}
            </span>
          </span>
        </Link>
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground">{user.email}</span>
          <LocaleToggle />
          <ThemeToggle />
        </div>
      </header>
      <main className="flex-1">{children}</main>
    </div>
  );
}
