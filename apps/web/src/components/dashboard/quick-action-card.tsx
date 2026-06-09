import type { LucideIcon } from "lucide-react";
import { ArrowUpRight } from "lucide-react";

import { Link } from "@/i18n/routing";
import { cn } from "@/lib/utils";

export type QuickActionTone =
  | "purple"
  | "blue"
  | "emerald"
  | "indigo"
  | "pink"
  | "amber"
  | "feature";

const TONES: Record<QuickActionTone, string> = {
  purple:
    "bg-purple-100 text-purple-600 dark:bg-purple-500/15 dark:text-purple-300",
  blue: "bg-sky-100 text-sky-600 dark:bg-sky-500/15 dark:text-sky-300",
  emerald:
    "bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300",
  indigo:
    "bg-indigo-100 text-indigo-600 dark:bg-indigo-500/15 dark:text-indigo-300",
  pink: "bg-pink-100 text-pink-600 dark:bg-pink-500/15 dark:text-pink-300",
  amber:
    "bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300",
  feature: "bg-primary-foreground/15 text-primary-foreground",
};

interface QuickActionCardProps {
  href: string;
  icon: LucideIcon;
  title: string;
  subtitle: string;
  tone: QuickActionTone;
  /** Tall feature variant — used for the WhatsApp hero tile in the bento. */
  feature?: boolean;
  /** Optional CTA label rendered as a chip on feature cards. */
  cta?: string;
  className?: string;
}

export function QuickActionCard({
  href,
  icon: Icon,
  title,
  subtitle,
  tone,
  feature = false,
  cta,
  className,
}: QuickActionCardProps) {
  if (feature) {
    return (
      <Link
        href={href}
        className={cn(
          "group relative flex flex-col justify-between overflow-hidden rounded-3xl p-7",
          "bg-primary text-primary-foreground shadow-sm transition-all hover:shadow-lg hover:-translate-y-0.5",
          className
        )}
      >
        {/* Decorative gold orb in the trailing-top corner */}
        <span className="pointer-events-none absolute -top-16 -end-12 h-44 w-44 rounded-full bg-accent/30 blur-2xl" />
        <span className="pointer-events-none absolute bottom-0 start-0 h-32 w-32 rounded-full bg-primary-foreground/10 blur-2xl" />

        <div className="relative space-y-4">
          <div
            className={cn(
              "grid h-14 w-14 place-items-center rounded-2xl",
              TONES.feature
            )}
          >
            <Icon className="h-7 w-7" />
          </div>
          <div>
            <h3 className="text-xl font-bold leading-tight">{title}</h3>
            <p className="mt-2 text-sm/6 text-primary-foreground/80">
              {subtitle}
            </p>
          </div>
        </div>

        <div className="relative mt-6 inline-flex items-center gap-1.5 self-start rounded-full bg-primary-foreground/10 px-4 py-1.5 text-sm font-medium">
          {cta ?? title}
          <ArrowUpRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5 rtl:group-hover:-translate-x-0.5" />
        </div>
      </Link>
    );
  }

  return (
    <Link
      href={href}
      className={cn(
        "group flex items-start gap-4 rounded-2xl border border-border/60 bg-card p-5 shadow-sm transition-all hover:-translate-y-0.5 hover:shadow-md hover:border-primary/30",
        className
      )}
    >
      <div
        className={cn(
          "grid h-12 w-12 shrink-0 place-items-center rounded-2xl",
          TONES[tone]
        )}
      >
        <Icon className="h-5 w-5" />
      </div>
      <div className="min-w-0 flex-1 text-start">
        <div className="font-semibold text-foreground">{title}</div>
        <div className="mt-0.5 text-xs text-muted-foreground line-clamp-2">
          {subtitle}
        </div>
      </div>
      <ArrowUpRight className="h-4 w-4 text-muted-foreground/60 shrink-0 transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5 rtl:group-hover:-translate-x-0.5" />
    </Link>
  );
}
