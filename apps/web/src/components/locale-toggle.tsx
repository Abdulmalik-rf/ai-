"use client";

import { useLocale, useTranslations } from "next-intl";
import { usePathname, useRouter } from "@/i18n/routing";
import { Button } from "@/components/ui/button";
import { Languages } from "lucide-react";

export function LocaleToggle() {
  const t = useTranslations("common");
  const router = useRouter();
  const pathname = usePathname();
  const locale = useLocale();
  const next = locale === "ar" ? "en" : "ar";
  return (
    <Button
      variant="ghost"
      size="sm"
      className="gap-2"
      onClick={() => router.replace(pathname, { locale: next })}
    >
      <Languages className="h-4 w-4" />
      {t("languageToggle")}
    </Button>
  );
}
