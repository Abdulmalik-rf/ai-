import { useLocale, useTranslations } from "next-intl";
import { Link } from "@/i18n/routing";

import { BrandLockup } from "@/components/brand-logo";

export function MarketingFooter() {
  const t = useTranslations("marketing.footer");
  const locale = useLocale();
  const year = new Date().getFullYear();
  return (
    <footer className="border-t border-border/60 mt-24 bg-background/50 backdrop-blur-sm">
      <div className="container py-10 flex flex-col md:flex-row items-center justify-between gap-4 text-sm text-muted-foreground">
        <BrandLockup locale={locale} size={24} />
        <div>{t("rights", { year })}</div>
        <div className="flex gap-6">
          <Link href="/terms" className="hover:text-foreground transition-colors">
            {t("terms")}
          </Link>
          <Link href="/privacy" className="hover:text-foreground transition-colors">
            {t("privacy")}
          </Link>
        </div>
      </div>
    </footer>
  );
}
