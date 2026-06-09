"use client";

import { Bell, Crown, HelpCircle, PanelRight, User } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";

import { Link } from "@/i18n/routing";
import { ThemeToggle } from "@/components/theme-toggle";
import { LocaleToggle } from "@/components/locale-toggle";
import { cn } from "@/lib/utils";

export function DashboardTopbar({ userName }: { userName: string }) {
  const t = useTranslations("dashboard.topbar");
  const locale = useLocale();
  const comma = locale === "ar" ? "،" : ",";

  return (
    <header className="h-16 border-b border-border/60 bg-background flex items-center justify-between px-6">
      {/* Leading (right in RTL): greeting + sidebar toggle */}
      <div className="flex items-center gap-3">
        <div className="text-sm">
          <span className="text-muted-foreground">
            {t("welcome")}
            {comma}
          </span>{" "}
          <span className="font-semibold">{userName}</span>
        </div>
        <button
          type="button"
          aria-label={t("toggleSidebar")}
          className="grid place-items-center h-9 w-9 rounded-lg text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
        >
          <PanelRight className="h-4 w-4" />
        </button>
      </div>

      {/* Trailing (left in RTL): action cluster */}
      <div className="flex items-center gap-1.5">
        <button
          type="button"
          aria-label={t("help")}
          className="grid place-items-center h-9 w-9 rounded-full border border-border/60 text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
        >
          <HelpCircle className="h-4 w-4" />
        </button>

        <Link
          href="/dashboard/billing"
          className={cn(
            "inline-flex items-center gap-1.5 h-9 px-4 rounded-full text-sm font-semibold",
            "bg-primary text-primary-foreground hover:bg-primary/90 shadow-sm transition-colors"
          )}
        >
          <Crown className="h-4 w-4" />
          <span>{t("subscribe")}</span>
        </Link>

        <ThemeToggle />

        <button
          type="button"
          aria-label={t("notifications")}
          className="relative grid place-items-center h-9 w-9 rounded-full border border-border/60 text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
        >
          <Bell className="h-4 w-4" />
          <span className="absolute top-1.5 end-1.5 h-2 w-2 rounded-full bg-destructive" />
        </button>

        <Link
          href="/dashboard/settings"
          aria-label={t("profile")}
          className="grid place-items-center h-9 w-9 rounded-full border border-border/60 text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
        >
          <User className="h-4 w-4" />
        </Link>

        <div className="ms-1">
          <LocaleToggle />
        </div>
      </div>
    </header>
  );
}
