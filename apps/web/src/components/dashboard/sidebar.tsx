"use client";

import {
  BookOpen,
  Briefcase,
  CalendarClock,
  CheckSquare,
  Contact as ContactIcon,
  FilePlus2,
  Layers,
  LogOut,
  MessageCircle,
  Scale,
  ScanSearch,
  UserCog,
  Users,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";

import { BrandLogo } from "@/components/brand-logo";
import { logout } from "@/lib/auth";
import { Link, usePathname } from "@/i18n/routing";
import { cn } from "@/lib/utils";

type NavItem = {
  href: string;
  icon: LucideIcon;
  key: string;
  exact?: boolean;
};

const PRIMARY: NavItem[] = [
  { href: "/dashboard", icon: BookOpen, key: "overview", exact: true },
  { href: "/dashboard/clients", icon: Users, key: "clients" },
  { href: "/dashboard/cases", icon: Briefcase, key: "cases" },
  { href: "/dashboard/tasks", icon: CheckSquare, key: "tasks" },
  { href: "/dashboard/hearings", icon: CalendarClock, key: "hearings" },
  { href: "/dashboard/staff", icon: UserCog, key: "staff" },
  { href: "/dashboard/contacts", icon: ContactIcon, key: "contactsCrm" },
  { href: "/dashboard/consultations", icon: Scale, key: "consultations" },
  { href: "/dashboard/drafting", icon: FilePlus2, key: "create" },
  { href: "/dashboard/contracts", icon: ScanSearch, key: "review" },
  // "اسأل المساعد" (/dashboard/chat) was removed — the conversation now
  // lives inline on the dashboard home, accessible via "Overview" above.
  { href: "/dashboard/documents", icon: Layers, key: "files" },
  { href: "/dashboard/whatsapp", icon: MessageCircle, key: "whatsapp" },
];

// Secondary nav group used to host "Support", "Suggestions", and "Guide" —
// but those pages don't exist yet, so the links pointed at /billing or
// /settings and confused users. Until the pages are built (or an external
// help URL is decided), the secondary group is empty and the sidebar
// renders only the sign-out button below it.
const SECONDARY: NavItem[] = [];

/**
 * Icon-rail sidebar that expands on hover. Fixed-positioned so the main
 * content keeps its 5rem inline margin and the rail overlays it during
 * expansion — no layout shift, no JS state.
 */
export function DashboardSidebar() {
  const t = useTranslations("dashboard");
  const pathname = usePathname();
  const locale = useLocale();

  const isActive = (href: string, exact?: boolean) => {
    const path = href.split("?")[0];
    if (exact) return pathname === path;
    return pathname === path || pathname.startsWith(path + "/");
  };

  return (
    <aside
      aria-label="Sidebar"
      className={cn(
        "group/sidebar fixed inset-y-0 start-0 z-30 hidden md:flex",
        "w-20 hover:w-72 focus-within:w-72",
        "transition-[width] duration-300 ease-out",
        "flex-col border-e border-border/60 bg-card/80 backdrop-blur-md shadow-sm hover:shadow-xl"
      )}
    >
      {/* Brand block — monogram always; wordmark fades in on expand */}
      <Link
        href="/dashboard"
        className="flex items-center justify-center gap-2 h-20 px-4 border-b border-border/60 overflow-hidden"
      >
        <span className="grid place-items-center h-10 w-10 rounded-xl bg-primary/10 shrink-0">
          <BrandLogo size={24} locale={locale} />
        </span>
        <span
          className={cn(
            "flex items-baseline gap-1.5 leading-none whitespace-nowrap",
            "opacity-0 -translate-x-2 rtl:translate-x-2",
            "group-hover/sidebar:opacity-100 group-hover/sidebar:translate-x-0",
            "transition-all duration-200"
          )}
        >
          <span className="font-bold text-base text-primary">
            {locale === "ar" ? "مستشاري" : "Mostashari"}
          </span>
          <span className="font-semibold text-xs text-accent tracking-wide">
            AI
          </span>
        </span>
      </Link>

      <div className="flex-1 overflow-y-auto overflow-x-hidden px-3 py-4 flex flex-col gap-4">
        <NavGroup>
          {PRIMARY.map(({ href, icon, key, exact }) => (
            <RailItem
              key={key}
              href={href}
              icon={icon}
              label={t(`nav.${key}`)}
              active={isActive(href, exact)}
            />
          ))}
        </NavGroup>

        <NavGroup>
          {SECONDARY.map(({ href, icon, key }) => (
            <RailItem
              key={key}
              href={href}
              icon={icon}
              label={t(`nav.${key}`)}
              muted
            />
          ))}

          <form action={logout}>
            <button
              type="submit"
              className={cn(
                "group/item w-full flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm",
                "text-destructive hover:bg-destructive/10 transition-colors"
              )}
            >
              <LogOut className="h-5 w-5 shrink-0" />
              <span
                className={cn(
                  "whitespace-nowrap",
                  "opacity-0 group-hover/sidebar:opacity-100 transition-opacity duration-200"
                )}
              >
                {t("nav.logout")}
              </span>
            </button>
          </form>
        </NavGroup>
      </div>
    </aside>
  );
}

function NavGroup({ children }: { children: React.ReactNode }) {
  return <nav className="space-y-1">{children}</nav>;
}

function RailItem({
  href,
  icon: Icon,
  label,
  active,
  muted,
}: {
  href: string;
  icon: typeof BookOpen;
  label: string;
  active?: boolean;
  muted?: boolean;
}) {
  return (
    <Link
      href={href}
      title={label}
      className={cn(
        "group/item relative flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition-colors",
        active
          ? "bg-primary/10 text-primary font-semibold"
          : muted
            ? "text-muted-foreground hover:bg-muted hover:text-foreground"
            : "text-foreground/80 hover:bg-muted"
      )}
    >
      {/* Active indicator: a small gold tick on the inline-start edge */}
      {active && (
        <span className="absolute start-0 inset-y-2 w-1 rounded-full bg-accent" />
      )}
      <Icon
        className={cn(
          "h-5 w-5 shrink-0",
          active ? "text-primary" : "text-muted-foreground"
        )}
      />
      <span
        className={cn(
          "whitespace-nowrap",
          "opacity-0 group-hover/sidebar:opacity-100 transition-opacity duration-200"
        )}
      >
        {label}
      </span>
    </Link>
  );
}
