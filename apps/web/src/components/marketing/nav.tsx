import { Link } from "@/i18n/routing";
import { useLocale, useTranslations } from "next-intl";

import { BrandLockup } from "@/components/brand-logo";
import { LocaleToggle } from "@/components/locale-toggle";
import { ThemeToggle } from "@/components/theme-toggle";
import { Button } from "@/components/ui/button";

export function MarketingNav() {
  const t = useTranslations("common");
  const locale = useLocale();
  return (
    <header className="sticky top-0 z-40 w-full border-b border-border/60 bg-background/70 backdrop-blur-md supports-[backdrop-filter]:bg-background/55">
      <div className="container flex h-16 items-center justify-between gap-4">
        <Link href="/" aria-label={t("appName")}>
          <BrandLockup locale={locale} size={28} />
        </Link>
        <nav className="hidden md:flex items-center gap-6 text-sm text-muted-foreground">
          <Link href="/features" className="hover:text-foreground transition-colors">
            {locale === "ar" ? "المميزات" : "Features"}
          </Link>
          <Link href="/pricing" className="hover:text-foreground transition-colors">
            {locale === "ar" ? "الأسعار" : "Pricing"}
          </Link>
          <Link href="/about" className="hover:text-foreground transition-colors">
            {locale === "ar" ? "من نحن" : "About"}
          </Link>
        </nav>
        <div className="flex items-center gap-2">
          <LocaleToggle />
          <ThemeToggle />
          <Button asChild variant="ghost" size="sm">
            <Link href="/sign-in">{t("signIn")}</Link>
          </Button>
          <Button asChild size="sm">
            <Link href="/sign-up">{t("signUp")}</Link>
          </Button>
        </div>
      </div>
    </header>
  );
}
