import { type LucideIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Link } from "@/i18n/routing";

/**
 * Dashed-border empty-state placeholder used across dashboard list pages
 * when the section has no data yet. Replaces the silent blank screen the
 * user previously saw when a fresh tenant clicked into Cases / Clients /
 * Tasks / Documents / etc.
 *
 * Props are plain strings — pass already-translated copy from the calling
 * page. The icon is the "hero" glyph for the section (Briefcase, Users…).
 */
export function EmptyState({
  icon: Icon,
  title,
  body,
  actionLabel,
  actionHref,
}: {
  icon: LucideIcon;
  title: string;
  body: string;
  actionLabel?: string;
  actionHref?: string;
}) {
  return (
    <div className="rounded-2xl border border-dashed border-border/70 bg-card/40 py-16 px-6 text-center">
      <div className="mx-auto grid h-14 w-14 place-items-center rounded-2xl bg-gradient-to-br from-primary/[0.10] to-accent/[0.10] ring-1 ring-inset ring-border/60 text-primary">
        <Icon className="h-6 w-6" />
      </div>
      <h2 className="mt-5 text-lg md:text-xl font-semibold tracking-tight">
        {title}
      </h2>
      <p className="mt-2 max-w-md mx-auto text-sm text-muted-foreground leading-relaxed">
        {body}
      </p>
      {actionLabel && actionHref && (
        <Button asChild className="mt-6">
          <Link href={actionHref}>{actionLabel}</Link>
        </Button>
      )}
    </div>
  );
}
